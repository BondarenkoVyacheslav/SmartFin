import os
import sys
import types
import unittest
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Sequence
from time import perf_counter
import json

import httpx
import asyncio


def _install_fake_assets_models() -> None:
    module = types.ModuleType("app.assets.models")

    class FakeQuerySet(list):
        def values_list(self, *fields):
            if len(fields) != 2:
                raise ValueError("values_list only supports 2 fields in tests")
            return [(getattr(item, fields[0]), getattr(item, fields[1])) for item in self]

    class FakeManager:
        def __init__(self) -> None:
            self._data: List[Any] = []

        def set(self, items: List[Any]) -> None:
            self._data = list(items)

        def select_related(self, *_args, **_kwargs):
            return self

        def filter(self, **kwargs):
            if "name__in" in kwargs:
                names = set(kwargs["name__in"])
                return FakeQuerySet([item for item in self._data if item.name in names])
            if "symbol__in" in kwargs:
                symbols = {str(s).upper() for s in kwargs["symbol__in"]}
                return FakeQuerySet(
                    [item for item in self._data if str(item.symbol).upper() in symbols]
                )
            return FakeQuerySet([])

    class AssetType:
        objects = FakeManager()

        def __init__(self, id: int, name: str, code: str = "") -> None:
            self.id = id
            self.name = name
            self.code = code

    class Asset:
        objects = FakeManager()

        def __init__(self, symbol: str, asset_type: AssetType) -> None:
            self.symbol = symbol
            self.asset_type = asset_type
            self.asset_type_id = asset_type.id

    module.AssetType = AssetType
    module.Asset = Asset
    sys.modules["app.assets.models"] = module


BACKEND_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_ROOT))
_install_fake_assets_models()

from app.assets.models import Asset, AssetType
from app.marketdata.api import MarketDataAPI
from app.marketdata.USA.usa import USAStockProvider


DEFAULT_US_SYMBOLS = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL"]


def _print_quotes(title: str, quotes) -> None:
    print(f"{title}: {len(quotes)} quotes")
    for quote in quotes:
        ts = quote.ts.isoformat() if quote.ts else "n/a"
        print(
            f"  {quote.symbol} last={quote.last} bid={quote.bid} ask={quote.ask} ts={ts}"
        )


class NullCache:
    async def get(self, _key: str, default: Any = None) -> Any:
        return default

    async def get_many(self, keys: List[str]) -> Dict[str, Any]:
        return {key: None for key in keys}

    async def set(self, _key: str, _value: Any, ttl: int | None = None) -> bool:
        return True

    async def set_many(self, _data: Dict[str, Any], ttl: int | None = None) -> bool:
        return True


def _env_list(name: str, default: Sequence[str]) -> List[str]:
    raw = os.getenv(name)
    if not raw:
        return list(default)
    return [item.strip() for item in raw.split(",") if item.strip()]


def _maybe_latency_limit() -> float | None:
    raw = os.getenv("MARKETDATA_MAX_LATENCY_S")
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


class MarketDataAPILiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.loop = asyncio.new_event_loop()
        cls.api = MarketDataAPI()
        cls.api._run_async = lambda coro: cls.loop.run_until_complete(coro)
        null_cache = NullCache()
        cls.api.usa_provider._cache_service = null_cache
        cls.api.moex_provider._cache_service = null_cache
        cls.api.coin_gecko_provider._cache_service = null_cache

        cls.us_type = AssetType(id=1, name="Акции США", code="stock-us")
        cls.ru_type = AssetType(id=2, name="Акции РФ", code="stock-ru")
        cls.crypto_type = AssetType(id=3, name="Криптовалюты", code="crypto")
        AssetType.objects.set([cls.us_type, cls.ru_type, cls.crypto_type])

        skip_us = (os.getenv("MARKETDATA_SKIP_US") or "").lower() in {"1", "true", "yes"}
        cls.us_symbols = [] if skip_us else _env_list("MARKETDATA_US_SYMBOLS", DEFAULT_US_SYMBOLS)
        cls.ru_symbols = _env_list("MARKETDATA_RU_SYMBOLS", ["SBER"])
        cls.crypto_symbols = _env_list("MARKETDATA_CRYPTO_SYMBOLS", ["BTC"])

        Asset.objects.set(
            [
                Asset(symbol=sym, asset_type=cls.us_type) for sym in cls.us_symbols
            ]
            + [
                Asset(symbol=sym, asset_type=cls.ru_type) for sym in cls.ru_symbols
            ]
            + [
                Asset(symbol=sym, asset_type=cls.crypto_type) for sym in cls.crypto_symbols
            ]
        )

        cls.latency_limit = _maybe_latency_limit()

    @classmethod
    def tearDownClass(cls) -> None:
        async def _close():
            await cls.api.usa_provider.aclose()
            await cls.api.coin_gecko_provider.aclose()

        cls.loop.run_until_complete(_close())
        cls.loop.close()

    def _timed(self, label: str, func, *args, **kwargs):
        start = perf_counter()
        result = func(*args, **kwargs)
        elapsed = perf_counter() - start
        print(f"{label} took {elapsed:.3f}s")
        if self.latency_limit is not None:
            self.assertLessEqual(
                elapsed,
                self.latency_limit,
                msg=f"{label} exceeded {self.latency_limit:.2f}s",
            )
        return result

    def test_health_ok(self) -> None:
        self.assertEqual(self.api.health(), {"status": "ok"})

    def test_get_quotes_stock_us(self) -> None:
        if not self.us_symbols:
            self.skipTest("USA symbols not configured")
        try:
            quotes = self._timed(
                "USA quotes",
                self.api.get_quotes,
                self.us_symbols,
                "stock-us",
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 401:
                self.skipTest("Yahoo Finance returned 401 Unauthorized")
            raise
        _print_quotes("USA", quotes)
        self.assertTrue(quotes, "No USA quotes returned")
        for quote in quotes:
            self.assertIsNotNone(quote.last)

    def test_get_quotes_stock_ru(self) -> None:
        quotes = self._timed(
            "MOEX quotes",
            self.api.get_quotes,
            self.ru_symbols,
            "stock-ru",
        )
        _print_quotes("MOEX", quotes)
        self.assertTrue(quotes, "No MOEX quotes returned")
        for quote in quotes:
            self.assertIsNotNone(quote.last)

    def test_get_quotes_crypto(self) -> None:
        quotes = self._timed(
            "Crypto quotes",
            self.api.get_quotes,
            self.crypto_symbols,
            "crypto",
        )
        _print_quotes("Crypto", quotes)
        self.assertTrue(quotes, "No crypto quotes returned")
        for quote in quotes:
            self.assertIsNotNone(quote.last)

    def test_get_quotes_by_symbols(self) -> None:
        combined = self.us_symbols + self.ru_symbols + self.crypto_symbols
        if not combined:
            self.skipTest("No symbols configured")
        try:
            quotes = self._timed(
                "All quotes by symbols",
                self.api.get_quotes_by_symbols,
                combined,
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 401:
                self.skipTest("Yahoo Finance returned 401 Unauthorized")
            raise
        _print_quotes("All", quotes)
        self.assertEqual([q.symbol for q in quotes], [s.upper() for s in combined])

    def test_get_quote_by_symbol(self) -> None:
        if not self.us_symbols:
            self.skipTest("USA symbols not configured")
        symbol = self.us_symbols[0]
        try:
            quote = self._timed(
                f"Single quote {symbol}",
                self.api.get_quote_by_symbol,
                symbol,
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 401:
                self.skipTest("Yahoo Finance returned 401 Unauthorized")
            raise
        self.assertIsNotNone(quote)
        if quote is not None:
            print(
                f"Single {quote.symbol} last={quote.last} bid={quote.bid} ask={quote.ask}"
            )
            self.assertIsNotNone(quote.last)

    def test_get_candles_returns_empty(self) -> None:
        candles = self.api.get_candles("AAPL", "1d", "stock-us")
        self.assertEqual(candles, [])

    def test_get_fx_rates_returns_empty(self) -> None:
        self.assertEqual(self.api.get_fx_rates(["USD/RUB"]), {})


class USAStockProviderLiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.loop = asyncio.new_event_loop()
        cls.provider = USAStockProvider()
        cls.provider._cache_service = NullCache()
        skip_us = (os.getenv("MARKETDATA_SKIP_US") or "").lower() in {"1", "true", "yes"}
        cls.us_symbols = [] if skip_us else _env_list("MARKETDATA_US_SYMBOLS", DEFAULT_US_SYMBOLS)
        cls.latency_limit = _maybe_latency_limit()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.loop.run_until_complete(cls.provider.aclose())
        cls.loop.close()

    def _timed(self, label: str, func, *args, **kwargs):
        start = perf_counter()
        result = func(*args, **kwargs)
        elapsed = perf_counter() - start
        print(f"{label} took {elapsed:.3f}s")
        if self.latency_limit is not None:
            self.assertLessEqual(
                elapsed,
                self.latency_limit,
                msg=f"{label} exceeded {self.latency_limit:.2f}s",
            )
        return result

    def test_provider_quotes_multiple(self) -> None:
        if not self.us_symbols:
            self.skipTest("USA symbols not configured")
        try:
            quotes = self._timed(
                "USA provider quotes",
                lambda: self.loop.run_until_complete(self.provider.quotes(self.us_symbols)),
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 401:
                self.skipTest("Yahoo Finance returned 401 Unauthorized")
            raise
        _print_quotes("USA provider", quotes)
        self.assertTrue(quotes, "No USA provider quotes returned")
        for quote in quotes:
            self.assertIn(quote.symbol, [s.upper() for s in self.us_symbols])
            self.assertIsNotNone(quote.last)
            self.assertGreater(quote.last, 0)

        summary = ", ".join(f"{q.symbol}={q.last}" for q in quotes)
        print(f"USA latest prices: {summary}")

    def test_provider_latest_price(self) -> None:
        if not self.us_symbols:
            self.skipTest("USA symbols not configured")
        symbol = self.us_symbols[0]
        try:
            price = self._timed(
                f"USA provider latest_price {symbol}",
                lambda: self.loop.run_until_complete(self.provider.latest_price(symbol)),
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 401:
                self.skipTest("Yahoo Finance returned 401 Unauthorized")
            raise
        self.assertIsNotNone(price)
        if price is not None:
            print(f"USA latest price {symbol}={price}")
            self.assertGreater(price, 0)

    def test_provider_raw_response(self) -> None:
        if not self.us_symbols:
            self.skipTest("USA symbols not configured")
        try:
            data = self._timed(
                "USA provider raw response",
                lambda: self.loop.run_until_complete(
                    self.provider._get(
                        "/v7/finance/quote",
                        params={"symbols": ",".join(self.us_symbols)},
                    )
                ),
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 401:
                self.skipTest("Yahoo Finance returned 401 Unauthorized")
            raise
        print("USA raw response:")
        print(json.dumps(data, ensure_ascii=True, indent=2, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
