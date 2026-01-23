import os
import sys
import unittest
from pathlib import Path
from time import perf_counter
from typing import Any, Dict, List, Sequence
import asyncio

import httpx


BACKEND_ROOT = Path(__file__).resolve().parents[3]
PROJECT_ROOT = BACKEND_ROOT.parents[1]
DOTENV_PATH = PROJECT_ROOT / ".env"
DOTENV_FALLBACK = Path.cwd() / ".env"
sys.path.insert(0, str(BACKEND_ROOT))

from .alpaca import AlpacaProvider


DEFAULT_STOCK_SYMBOLS = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL"]
DEFAULT_INDEX_SYMBOLS = ["SPY", "QQQ", "DIA", "IWM", "ONEQ"]


class NullCache:
    async def get(self, _key: str, default: Any = None) -> Any:
        return default

    async def get_many(self, keys: List[str]) -> Dict[str, Any]:
        return {key: None for key in keys}

    async def set(self, _key: str, _value: Any, ttl: int | None = None) -> bool:
        return True

    async def set_many(self, _data: Dict[str, Any], ttl: int | None = None) -> bool:
        return True


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


def _mask_secret(value: str | None) -> str:
    if not value:
        return "missing"
    if len(value) <= 6:
        return "***"
    return f"{value[:4]}...{value[-2:]}"


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


def _print_quotes(title: str, quotes) -> None:
    print(f"{title}: {len(quotes)} quotes")
    for quote in quotes:
        ts = quote.ts.isoformat() if quote.ts else "n/a"
        print(
            f"  {quote.symbol} last={quote.last} bid={quote.bid} ask={quote.ask} ts={ts}"
        )


class AlpacaProviderLiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _load_dotenv(DOTENV_PATH)
        if DOTENV_FALLBACK != DOTENV_PATH:
            _load_dotenv(DOTENV_FALLBACK)
        cls.loop = asyncio.new_event_loop()
        cls.provider = AlpacaProvider()
        cls.provider._cache_service = NullCache()

        cls.skip_alpaca = (os.getenv("MARKETDATA_SKIP_ALPACA") or "").lower() in {
            "1",
            "true",
            "yes",
        }
        cls.api_key = os.getenv("ALPACA_API_KEY")
        cls.api_secret = os.getenv("ALPACA_API_SECRET")
        print(
            "Alpaca env loaded: "
            f"ALPACA_API_KEY={_mask_secret(cls.api_key)} "
            f"ALPACA_API_SECRET={_mask_secret(cls.api_secret)}"
        )

        cls.stock_symbols = [] if cls.skip_alpaca else _env_list(
            "ALPACA_STOCK_SYMBOLS",
            DEFAULT_STOCK_SYMBOLS,
        )
        cls.index_symbols = [] if cls.skip_alpaca else _env_list(
            "ALPACA_INDEX_SYMBOLS",
            DEFAULT_INDEX_SYMBOLS,
        )
        cls.latency_limit = _maybe_latency_limit()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.loop.run_until_complete(cls.provider.aclose())
        cls.loop.close()

    def _require_credentials(self) -> None:
        if self.skip_alpaca:
            print("Skipping Alpaca tests: MARKETDATA_SKIP_ALPACA is set")
            self.skipTest("MARKETDATA_SKIP_ALPACA is set")
        if not self.api_key or not self.api_secret:
            print("Skipping Alpaca tests: missing ALPACA_API_KEY or ALPACA_API_SECRET")
            self.skipTest("ALPACA_API_KEY/ALPACA_API_SECRET are not set")

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

    def test_provider_quotes_stocks(self) -> None:
        self._require_credentials()
        if not self.stock_symbols:
            self.skipTest("ALPACA_STOCK_SYMBOLS not configured")

        try:
            quotes = self._timed(
                "Alpaca provider stock quotes",
                lambda: self.loop.run_until_complete(
                    self.provider.quotes(self.stock_symbols)
                ),
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in {401, 403}:
                self.skipTest("Alpaca returned unauthorized/forbidden")
            raise

        _print_quotes("Alpaca stocks", quotes)
        self.assertTrue(quotes, "No Alpaca stock quotes returned")

        wanted = {s.upper() for s in self.stock_symbols}
        for quote in quotes:
            self.assertIn(quote.symbol, wanted)
            self.assertIsNotNone(quote.last)
            if quote.last is not None:
                self.assertGreater(quote.last, 0)

        summary = ", ".join(f"{q.symbol}={q.last}" for q in quotes)
        print(f"Alpaca stock latest prices: {summary}")

    def test_provider_quotes_indices(self) -> None:
        self._require_credentials()
        if not self.index_symbols:
            self.skipTest("ALPACA_INDEX_SYMBOLS not configured")

        try:
            quotes = self._timed(
                "Alpaca provider index quotes",
                lambda: self.loop.run_until_complete(
                    self.provider.index_quotes(self.index_symbols)
                ),
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in {401, 403}:
                self.skipTest("Alpaca returned unauthorized/forbidden")
            raise

        _print_quotes("Alpaca indices (ETF proxies)", quotes)
        self.assertTrue(quotes, "No Alpaca index quotes returned")

        wanted = {s.upper() for s in self.index_symbols}
        for quote in quotes:
            self.assertIn(quote.symbol, wanted)
            self.assertIsNotNone(quote.last)
            if quote.last is not None:
                self.assertGreater(quote.last, 0)

        summary = ", ".join(f"{q.symbol}={q.last}" for q in quotes)
        print(f"Alpaca index latest prices: {summary}")

    def test_provider_latest_price(self) -> None:
        self._require_credentials()
        if not self.stock_symbols:
            self.skipTest("ALPACA_STOCK_SYMBOLS not configured")

        symbol = self.stock_symbols[0]
        try:
            price = self._timed(
                f"Alpaca provider latest_price {symbol}",
                lambda: self.loop.run_until_complete(
                    self.provider.latest_price(symbol)
                ),
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in {401, 403}:
                self.skipTest("Alpaca returned unauthorized/forbidden")
            raise

        print(f"Alpaca latest price {symbol}={price}")
        self.assertIsNotNone(price)
        if price is not None:
            self.assertGreater(price, 0)


if __name__ == "__main__":
    unittest.main()
