import asyncio
import os
import unittest
from pathlib import Path
from typing import Optional

from backend.app.integrations.TON.adapter import TONAdapter


def _env(name: str) -> Optional[str]:
    value = os.getenv(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _env_int(name: str) -> Optional[int]:
    value = _env(name)
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _env_bool(name: str, default: bool) -> bool:
    value = _env(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes"}


def _debug_enabled() -> bool:
    value = _env("TON_DEBUG")
    if value is None:
        return True
    return value.lower() in {"1", "true", "yes"}


def _load_env_from_dotenv() -> None:
    if _env("TON_ADDRESS"):
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


class TONAdapterLiveTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        _load_env_from_dotenv()
        cls.address = _env("TON_ADDRESS")
        if not cls.address:
            raise unittest.SkipTest("TON_ADDRESS not set")

        cls.toncenter_api_key = _env("TONCENTER_API_KEY")
        cls.tonapi_api_key = _env("TONAPI_API_KEY")
        cls.toncenter_url = _env("TONCENTER_URL")
        cls.tonapi_url = _env("TONAPI_URL")

        cls.limit = _env_int("TON_LIMIT") or 50
        cls.include_jettons = _env_bool("TON_INCLUDE_JETTONS", True)
        cls.include_staking = _env_bool("TON_INCLUDE_STAKING", True)

    async def asyncSetUp(self):
        self.adapter = TONAdapter(
            address=self.__class__.address,
            toncenter_api_key=self.__class__.toncenter_api_key,
            tonapi_api_key=self.__class__.tonapi_api_key,
            toncenter_base_url=self.__class__.toncenter_url or TONAdapter.DEFAULT_TONCENTER_URL,
            tonapi_base_url=self.__class__.tonapi_url or TONAdapter.DEFAULT_TONAPI_URL,
        )

    async def asyncTearDown(self):
        await self.adapter.aclose()

    async def test_ping(self):
        res = await self.adapter.ping()
        self.assertIsInstance(res.ok, bool)
        self.assertGreaterEqual(len(res.ok_addresses) + len(res.failed_addresses), 1)
        if _debug_enabled():
            print(
                "ping:",
                "ok=",
                res.ok,
                "ok_addresses=",
                res.ok_addresses,
                "failed_addresses=",
                res.failed_addresses,
                "message=",
                res.message,
                "error_code=",
                res.error_code,
                "status_code=",
                res.status_code,
            )

    async def test_fetch_balances(self):
        balances = await self.adapter.fetch_balances(
            include_jettons=self.__class__.include_jettons,
            jetton_limit=self.__class__.limit,
        )
        self.assertIsInstance(balances, list)
        if _debug_enabled():
            print(f"balances: {len(balances)}")
            for item in balances:
                print(f"  {item.asset}: free={item.free} locked={item.locked} total={item.total}")

    async def test_fetch_positions(self):
        positions = await self.adapter.fetch_positions(
            include_staking=self.__class__.include_staking
        )
        self.assertIsInstance(positions, list)
        if _debug_enabled():
            print(f"positions: {len(positions)}")
            for item in positions:
                print(f"  {item.symbol}: qty={item.qty} currency={item.currency}")

    async def test_fetch_activities(self):
        activities = await self.adapter.fetch_activities(limit=self.__class__.limit)
        self.assertIsInstance(activities, list)
        if _debug_enabled():
            print(f"activities: {len(activities)}")
            for item in activities:
                print(
                    f"  {item.activity_type} {item.base_asset} side={item.side} "
                    f"amount={item.amount} ts={item.timestamp}"
                )

    async def test_fetch_snapshot(self):
        snapshot = await self.adapter.fetch_snapshot(
            limit=self.__class__.limit,
            include_jettons=self.__class__.include_jettons,
            include_staking=self.__class__.include_staking,
        )
        self.assertIsInstance(snapshot.balances, list)
        self.assertIsInstance(snapshot.positions, list)
        self.assertIsInstance(snapshot.activities, list)
        if _debug_enabled():
            print(
                f"snapshot: balances={len(snapshot.balances)} "
                f"positions={len(snapshot.positions)} activities={len(snapshot.activities)}"
            )
            for item in snapshot.balances:
                print(f"  balance {item.asset}: free={item.free} locked={item.locked} total={item.total}")
            for item in snapshot.positions:
                print(f"  position {item.symbol}: qty={item.qty} currency={item.currency}")
            for item in snapshot.activities:
                print(
                    f"  activity {item.activity_type} {item.base_asset} side={item.side} "
                    f"amount={item.amount} ts={item.timestamp}"
                )


if __name__ == "__main__":
    unittest.main()
