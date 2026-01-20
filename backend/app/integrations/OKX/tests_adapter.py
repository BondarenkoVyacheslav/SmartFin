import asyncio
import os
import unittest
from pathlib import Path
from typing import List, Optional

from backend.app.integrations.OKX.adapter import OKXAdapter


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
    return (_env("OKX_DEBUG") or "").lower() in {"1", "true", "yes"}


def _print_lines(lines: List[str]) -> None:
    for line in lines:
        print(line)


def _load_env_from_dotenv() -> None:
    if _env("OKX_API_KEY") and _env("OKX_API_SECRET") and _env("OKX_PASSPHRASE"):
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


class OKXAdapterLiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _load_env_from_dotenv()
        cls.api_key = _env("OKX_API_KEY")
        cls.api_secret = _env("OKX_API_SECRET")
        cls.passphrase = _env("OKX_PASSPHRASE")
        if not cls.api_key or not cls.api_secret or not cls.passphrase:
            raise unittest.SkipTest("OKX_API_KEY/OKX_API_SECRET/OKX_PASSPHRASE not set")

        testnet = _env("OKX_TESTNET")
        flag = _env("OKX_FLAG")

        cls.adapter = OKXAdapter(
            api_key=cls.api_key,
            api_secret=cls.api_secret,
            passphrase=cls.passphrase,
            testnet=(testnet or "").lower() in {"1", "true", "yes"},
            flag=flag,
        )
        cls.inst_types = _env_list("OKX_INST_TYPES") or ["SPOT", "SWAP", "FUTURES"]
        cls.quote_assets = _env_list("OKX_QUOTE_ASSETS")
        cls.inst_ids = _env_list("OKX_INST_IDS")
        cls.ccy = _env("OKX_CCY")

    def test_ping(self):
        res = asyncio.run(self.adapter.ping())
        self.assertIsInstance(res.ok, bool)
        if _debug_enabled():
            _print_lines(
                [
                    "ping:",
                    f"  ok={res.ok}",
                    f"  message={res.message}",
                    f"  error_code={res.error_code}",
                ]
            )

    def test_fetch_balances(self):
        balances = asyncio.run(self.adapter.fetch_balances(ccy=self.ccy))
        self.assertIsInstance(balances, list)
        lines = [f"balances: {len(balances)}"]
        if _debug_enabled():
            lines.extend(
                [
                    f"  {item.asset}: free={item.free} locked={item.locked} total={item.total}"
                    for item in balances[:5]
                ]
            )
        _print_lines(lines)

    def test_fetch_positions(self):
        positions = asyncio.run(self.adapter.fetch_positions(inst_types=self.inst_types))
        self.assertIsInstance(positions, list)
        lines = [f"positions: {len(positions)}"]
        if _debug_enabled():
            lines.extend(
                [
                    (
                        f"  {item.symbol} side={item.side} size={item.size} "
                        f"entry={item.entry_price} mark={item.mark_price} pnl={item.unrealized_pnl}"
                    )
                    for item in positions[:5]
                ]
            )
        _print_lines(lines)

    def test_fetch_activities(self):
        activities = asyncio.run(
            self.adapter.fetch_activities(
                limit=50,
                quote_assets=self.quote_assets,
                inst_types=self.inst_types,
                inst_ids=self.inst_ids,
            )
        )
        self.assertIsInstance(activities, list)
        lines = [f"activities: {len(activities)}"]
        if _debug_enabled():
            lines.extend(
                [
                    (
                        f"  {item.activity_type} {item.symbol} side={item.side} "
                        f"amount={item.amount} price={item.price} ts={item.timestamp}"
                    )
                    for item in activities[:5]
                ]
            )
        _print_lines(lines)

    def test_fetch_snapshot(self):
        snapshot = asyncio.run(
            self.adapter.fetch_snapshot(
                ccy=self.ccy,
                inst_types=self.inst_types,
                limit=50,
                quote_assets=self.quote_assets,
                inst_ids=self.inst_ids,
            )
        )
        self.assertIsInstance(snapshot.balances, list)
        self.assertIsInstance(snapshot.positions, list)
        self.assertIsInstance(snapshot.activities, list)
        lines = [
            (
                f"snapshot: balances={len(snapshot.balances)} "
                f"positions={len(snapshot.positions)} activities={len(snapshot.activities)}"
            )
        ]
        _print_lines(lines)


if __name__ == "__main__":
    unittest.main()
