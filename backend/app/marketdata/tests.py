import os
import sys
import types
import unittest
from pathlib import Path
from typing import Any, Dict, List, Sequence
from time import perf_counter

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
PROJECT_ROOT = BACKEND_ROOT.parents[1]
DOTENV_PATH = PROJECT_ROOT / ".env"
DOTENV_FALLBACK = Path.cwd() / ".env"
sys.path.insert(0, str(BACKEND_ROOT))
_install_fake_assets_models()

from app.assets.models import Asset, AssetType
from app.marketdata.api import MarketDataAPI


DEFAULT_US_SYMBOLS = ["AAPL", "GOOGL", "NVDA", "SPY", "QQQ"]
US_WATCHLIST = ["AAPL", "GOOGL", "NVDA", "SPY", "QQQ"]


def _print_quotes(title: str, quotes) -> None:
    print(f"{title}: {len(quotes)} quotes")
    for quote in quotes:
        ts = quote.ts.isoformat() if quote.ts else "n/a"
        print(
            f"  {quote.symbol} last={quote.last} bid={quote.bid} ask={quote.ask} ts={ts}"
        )


def _print_us_watchlist(quotes) -> None:
    mapping = {
        "AAPL": "Apple",
        "GOOGL": "Alphabet",
        "NVDA": "Nvidia",
        "SPY": "S&P 500 (SPY)",
        "QQQ": "Nasdaq (QQQ)",
    }
    by_symbol = {q.symbol.upper(): q for q in quotes}
    print("US watchlist:")
    for symbol, label in mapping.items():
        quote = by_symbol.get(symbol)
        price = quote.last if quote is not None else None
        print(f"  {label}: {price}")


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


def _normalize_symbols(symbols: Sequence[str]) -> List[str]:
    seen = set()
    ordered: List[str] = []
    for symbol in symbols:
        if not symbol:
            continue
        normalized = symbol.strip().upper()
        if normalized and normalized not in seen:
            seen.add(normalized)
            ordered.append(normalized)
    return ordered


def _maybe_latency_limit() -> float | None:
    raw = os.getenv("MARKETDATA_MAX_LATENCY_S")
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or key in os.environ:
            continue
        if (value.startswith("\"") and value.endswith("\"")) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        os.environ[key] = value


def _alpaca_enabled() -> bool:
    return bool(os.getenv("ALPACA_API_KEY") and os.getenv("ALPACA_API_SECRET"))


def _alpaca_skipped() -> bool:
    return (os.getenv("MARKETDATA_SKIP_ALPACA") or "").lower() in {"1", "true", "yes"}


class MarketDataAPILiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _load_dotenv(DOTENV_PATH)
        if DOTENV_FALLBACK != DOTENV_PATH:
            _load_dotenv(DOTENV_FALLBACK)
        cls.loop = asyncio.new_event_loop()
        cls.api = MarketDataAPI()
        cls.api._run_async = lambda coro: cls.loop.run_until_complete(coro)
        null_cache = NullCache()
        cls.api.alpaca_provider._cache_service = null_cache
        cls.api.moex_provider._cache_service = null_cache
        cls.api.coin_gecko_provider._cache_service = null_cache

        cls.us_type = AssetType(id=1, name="Акции США", code="stock-us")
        cls.ru_type = AssetType(id=2, name="Акции РФ", code="stock-ru")
        cls.crypto_type = AssetType(id=3, name="Криптовалюты", code="crypto")
        AssetType.objects.set([cls.us_type, cls.ru_type, cls.crypto_type])

        skip_us = (os.getenv("MARKETDATA_SKIP_US") or "").lower() in {"1", "true", "yes"}
        if skip_us or _alpaca_skipped() or not _alpaca_enabled():
            cls.us_symbols = []
        else:
            cls.us_symbols = _env_list("MARKETDATA_US_SYMBOLS", DEFAULT_US_SYMBOLS)
        cls.us_watchlist = list(US_WATCHLIST)
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
            await cls.api.alpaca_provider.aclose()
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
            self.skipTest("US symbols not configured or Alpaca disabled")
        try:
            symbols = _normalize_symbols(self.us_symbols + self.us_watchlist)
            quotes = self._timed(
                "USA quotes",
                self.api.get_quotes,
                symbols,
                "stock-us",
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in {401, 403}:
                self.skipTest("Alpaca returned unauthorized/forbidden")
            raise
        _print_quotes("USA", quotes)
        _print_us_watchlist(quotes)
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
            if exc.response.status_code in {401, 403}:
                self.skipTest("Alpaca returned unauthorized/forbidden")
            raise
        _print_quotes("All", quotes)
        self.assertEqual([q.symbol for q in quotes], [s.upper() for s in combined])

    def test_get_quote_by_symbol(self) -> None:
        if not self.us_symbols:
            self.skipTest("US symbols not configured or Alpaca disabled")
        symbol = self.us_symbols[0]
        try:
            quote = self._timed(
                f"Single quote {symbol}",
                self.api.get_quote_by_symbol,
                symbol,
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in {401, 403}:
                self.skipTest("Alpaca returned unauthorized/forbidden")
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


if __name__ == "__main__":
    unittest.main()
