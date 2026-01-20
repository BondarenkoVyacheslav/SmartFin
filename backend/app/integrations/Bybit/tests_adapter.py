import asyncio
import os
import unittest
from pathlib import Path
from typing import List, Optional

from backend.app.integrations.Bybit.adapter import BybitAdapter


def _env(name: str) -> Optional[str]:
    value = os.getenv(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _env_list(name: str) -> Optional[List[str]]:
    value = _env(name)
    if not value:
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


def _debug_enabled() -> bool:
    return (_env("BYBIT_DEBUG") or "").lower() in {"1", "true", "yes"}


def _load_env_from_dotenv() -> None:
    if _env("BYBIT_API_KEY") and _env("BYBIT_API_SECRET"):
        return

    for parent in Path(__file__).resolve().parents:
        candidate = parent / ".env"
        if candidate.is_file():
            for line in candidate.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key:
                    os.environ.setdefault(key, value)
            return


class BybitAdapterLiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _load_env_from_dotenv()
        cls.api_key = _env("BYBIT_API_KEY")
        cls.api_secret = _env("BYBIT_API_SECRET")
        if not cls.api_key or not cls.api_secret:
            raise unittest.SkipTest("BYBIT_API_KEY/BYBIT_API_SECRET not set")

        testnet = _env("BYBIT_TESTNET")
        recv_window = _env("BYBIT_RECV_WINDOW")

        cls.adapter = BybitAdapter(
            api_key=cls.api_key,
            api_secret=cls.api_secret,
            testnet=(testnet or "").lower() in {"1", "true", "yes"},
            recv_window=int(recv_window) if recv_window and recv_window.isdigit() else 5000,
        )
        cls.account_type = _env("BYBIT_ACCOUNT_TYPE") or "UNIFIED"
        cls.categories = _env_list("BYBIT_CATEGORIES") or ["linear", "inverse"]
        cls.quote_assets = _env_list("BYBIT_QUOTE_ASSETS")
        cls.settle_coins = _env_list("BYBIT_SETTLE_COINS")

    def test_fetch_balances(self):
        balances = asyncio.run(self.adapter.fetch_balances(account_type=self.account_type))
        self.assertIsInstance(balances, list)
        if _debug_enabled():
            print(f"balances: {len(balances)}")
            for item in balances[:5]:
                print(f"  {item.asset}: free={item.free} locked={item.locked} total={item.total}")

    def test_ping(self):
        res = asyncio.run(self.adapter.ping(account_type=self.account_type))
        self.assertIsInstance(res.ok, bool)
        if _debug_enabled():
            print(
                "ping:",
                "ok=",
                res.ok,
                "message=",
                res.message,
                "error_code=",
                res.error_code,
            )

    def test_fetch_positions(self):
        positions = asyncio.run(
            self.adapter.fetch_positions(
                categories=self.categories,
                settle_coins=self.settle_coins,
            )
        )
        self.assertIsInstance(positions, list)
        if _debug_enabled():
            print(f"positions: {len(positions)}")
            for item in positions[:5]:
                print(
                    f"  {item.symbol} side={item.side} size={item.size} "
                    f"entry={item.entry_price} mark={item.mark_price} pnl={item.unrealized_pnl}"
                )

    def test_fetch_activities(self):
        activities = asyncio.run(
            self.adapter.fetch_activities(
                limit=50,
                quote_assets=self.quote_assets,
            )
        )
        self.assertIsInstance(activities, list)
        if _debug_enabled():
            print(f"activities: {len(activities)}")
            for item in activities[:5]:
                print(
                    f"  {item.activity_type} {item.symbol} side={item.side} "
                    f"amount={item.amount} price={item.price} ts={item.timestamp}"
                )

    def test_fetch_snapshot(self):
        snapshot = asyncio.run(
            self.adapter.fetch_snapshot(
                account_type=self.account_type,
                categories=self.categories,
                limit=50,
                quote_assets=self.quote_assets,
                settle_coins=self.settle_coins,
            )
        )
        self.assertIsInstance(snapshot.balances, list)
        self.assertIsInstance(snapshot.positions, list)
        self.assertIsInstance(snapshot.activities, list)
        if _debug_enabled():
            print(
                f"snapshot: balances={len(snapshot.balances)} "
                f"positions={len(snapshot.positions)} activities={len(snapshot.activities)}"
            )


if __name__ == "__main__":
    unittest.main()
