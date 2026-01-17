import asyncio
import dataclasses
import json
import os
import sys
import unittest
from datetime import datetime
from pathlib import Path
from typing import Optional

ROOT_DIR = Path(__file__).resolve().parents[4]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.app.integrations.T.adapter import TAdapter


def _env(name: str) -> Optional[str]:
    value = os.getenv(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _debug_enabled() -> bool:
    return (_env("T_DEBUG") or "").lower() in {"1", "true", "yes"}


def _dump_enabled() -> bool:
    return (_env("T_DUMP") or "").lower() in {"1", "true", "yes"}


def _use_token_provider() -> bool:
    value = _env("T_USE_TOKEN_PROVIDER")
    if value is None:
        return True
    return value.lower() in {"1", "true", "yes"}


def _load_env_from_dotenv() -> None:
    if _env("T_TOKEN"):
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


def _serialize_payload(value: object) -> object:
    if dataclasses.is_dataclass(value):
        return _serialize_payload(dataclasses.asdict(value))
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _serialize_payload(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize_payload(v) for v in value]
    return value


def _dump_payload(label: str, payload: object) -> None:
    if not _dump_enabled():
        return
    print(f"{label}:")
    print(json.dumps(_serialize_payload(payload), ensure_ascii=True, indent=2, sort_keys=True))


class TAdapterLiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _load_env_from_dotenv()
        cls.token = _env("T_TOKEN")
        if not cls.token:
            raise unittest.SkipTest("T_TOKEN not set")

        cls.account_id = _env("T_ACCOUNT_ID")
        cls.app_name = _env("T_APP_NAME")
        cls.token_calls = 0
        token_provider = None

        if _use_token_provider():
            def _provider() -> str:
                cls.token_calls += 1
                return cls.token or ""

            token_provider = _provider

        cls.adapter = TAdapter(
            token=cls.token,
            account_id=cls.account_id,
            app_name=cls.app_name,
            token_provider=token_provider,
        )

    def test_fetch_accounts(self):
        accounts = asyncio.run(self.adapter.fetch_accounts())
        self.assertIsInstance(accounts, list)
        _dump_payload("accounts", accounts)
        if _use_token_provider():
            self.assertGreater(self.__class__.token_calls, 0)
        if _debug_enabled():
            print(f"accounts: {len(accounts)}")
            for item in accounts[:3]:
                print(f"  {item}")

    def test_fetch_balances(self):
        balances = asyncio.run(self.adapter.fetch_balances(account_id=self.__class__.account_id))
        self.assertIsInstance(balances, list)
        _dump_payload("balances", balances)
        if _debug_enabled():
            print(f"balances: {len(balances)}")
            for item in balances[:5]:
                print(f"  {item.asset}: free={item.free} locked={item.locked} total={item.total}")

    def test_fetch_positions(self):
        positions = asyncio.run(self.adapter.fetch_positions(account_id=self.__class__.account_id))
        self.assertIsInstance(positions, list)
        _dump_payload("positions", positions)
        if _debug_enabled():
            print(f"positions: {len(positions)}")
            for item in positions[:5]:
                print(
                    f"  {item.symbol} qty={item.qty} avg={item.avg_price} "
                    f"last={item.current_price} pnl={item.unrealized_pnl} {item.currency}"
                )

    def test_fetch_activities(self):
        activities = asyncio.run(
            self.adapter.fetch_activities(account_id=self.__class__.account_id, limit=50)
        )
        self.assertIsInstance(activities, list)
        _dump_payload("activities", activities)
        if _debug_enabled():
            print(f"activities: {len(activities)}")
            for item in activities[:5]:
                print(
                    f"  {item.activity_type} {item.symbol} side={item.side} "
                    f"amount={item.amount} price={item.price} ts={item.timestamp}"
                )

    def test_fetch_snapshot(self):
        snapshot = asyncio.run(self.adapter.fetch_snapshot(account_id=self.__class__.account_id))
        self.assertIsInstance(snapshot.balances, list)
        self.assertIsInstance(snapshot.positions, list)
        self.assertIsInstance(snapshot.activities, list)
        _dump_payload("snapshot", snapshot)
        if _debug_enabled():
            print(
                f"snapshot: balances={len(snapshot.balances)} "
                f"positions={len(snapshot.positions)} activities={len(snapshot.activities)}"
            )


if __name__ == "__main__":
    unittest.main()
