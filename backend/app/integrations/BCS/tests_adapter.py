import base64
import json
import os
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from backend.app.integrations.BCS.adapter import BcsAdapter


def _env(name: str) -> Optional[str]:
    value = os.getenv(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _debug_enabled() -> bool:
    return (_env("BCS_DEBUG") or "").lower() in {"1", "true", "yes"}


def _verbose_enabled() -> bool:
    value = _env("BCS_VERBOSE")
    if value is None:
        return True
    return value.lower() in {"1", "true", "yes"}


def _dump_enabled() -> bool:
    return (_env("BCS_DUMP") or "").lower() in {"1", "true", "yes"}


def _dump_json(label: str, payload: object) -> None:
    if not _dump_enabled():
        return
    print(f"{label}:")
    print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))


def _load_env_from_dotenv() -> None:
    if _env("BCS_REFRESH_TOKEN") or _env("BCS_TOKEN") or _env("BCS_ACCESS_TOKEN"):
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


def _jwt_claim(token: str, claim: str) -> Optional[str]:
    parts = token.split(".")
    if len(parts) < 2:
        return None
    payload = parts[1]
    padding = "=" * (-len(payload) % 4)
    try:
        raw = base64.urlsafe_b64decode(payload + padding)
        data = json.loads(raw.decode("utf-8"))
        value = data.get(claim)
    except Exception:
        return None
    if value is None:
        return None
    return str(value).strip() or None


class BcsAdapterLiveTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        _load_env_from_dotenv()
        raw_token = _env("BCS_TOKEN")
        cls.refresh_token = _env("BCS_REFRESH_TOKEN")
        cls.access_token = _env("BCS_ACCESS_TOKEN")
        if not cls.refresh_token and raw_token and _jwt_claim(raw_token, "typ") == "Refresh":
            cls.refresh_token = raw_token
        elif not cls.access_token and raw_token:
            cls.access_token = raw_token

        if not cls.refresh_token and not cls.access_token:
            raise unittest.SkipTest("BCS_REFRESH_TOKEN/BCS_TOKEN or BCS_ACCESS_TOKEN not set")

        inferred_client_id = _jwt_claim(cls.refresh_token or "", "azp") if cls.refresh_token else None
        cls.client_id = _env("BCS_CLIENT_ID") or inferred_client_id or "trade-api-read"
        cls.base_url = _env("BCS_BASE_URL") or "https://be.broker.ru"

        cls.last_access_token = None
        cls.last_refresh_token = None
        cls.last_access_exp = None
        cls.last_refresh_exp = None

    async def asyncSetUp(self):
        def _on_tokens(access_token, refresh_token, access_exp, refresh_exp):
            self.__class__.last_access_token = access_token
            self.__class__.last_refresh_token = refresh_token
            self.__class__.last_access_exp = access_exp
            self.__class__.last_refresh_exp = refresh_exp
            if _debug_enabled():
                print(
                    "token_update:",
                    f"access_exp={access_exp}",
                    f"refresh_exp={refresh_exp}",
                )

        self.adapter = BcsAdapter(
            access_token=self.__class__.access_token,
            refresh_token=self.__class__.refresh_token,
            client_id=self.__class__.client_id,
            token_updater=_on_tokens,
            base_url=self.__class__.base_url,
        )

    async def asyncTearDown(self):
        await self.adapter.aclose()

    async def test_fetch_limits_raw(self):
        data = await self.adapter.fetch_limits_raw()
        self.assertIsInstance(data, dict)
        if _verbose_enabled():
            print("limits: ok")
        if _debug_enabled():
            print("  limits keys:", list(data.keys())[:10])
        _dump_json("limits_raw", data)

    async def test_fetch_balances(self):
        balances = await self.adapter.fetch_balances()
        self.assertIsInstance(balances, list)
        if _verbose_enabled():
            print(f"balances: {len(balances)}")
        if _debug_enabled():
            for item in balances[:5]:
                print(f"  {item.asset}: free={item.free} locked={item.locked} total={item.total}")

    async def test_fetch_positions(self):
        positions = await self.adapter.fetch_positions()
        self.assertIsInstance(positions, list)
        if _verbose_enabled():
            print(f"positions: {len(positions)}")
        if _debug_enabled():
            for item in positions[:5]:
                print(
                    f"  {item.symbol} qty={item.qty} avg={item.avg_price} "
                    f"price={item.current_price} pnl={item.unrealized_pnl}"
                )

    async def test_fetch_portfolio_raw(self):
        items = await self.adapter.fetch_portfolio_raw()
        self.assertIsInstance(items, list)
        if _verbose_enabled():
            print(f"portfolio items: {len(items)}")
        if _debug_enabled() and items:
            print("  first type:", items[0].get("type"))
        _dump_json("portfolio_raw", items)

    async def test_fetch_portfolio_balances(self):
        balances = await self.adapter.fetch_portfolio_balances()
        self.assertIsInstance(balances, list)
        if _verbose_enabled():
            print(f"portfolio balances: {len(balances)}")
        if _debug_enabled():
            for item in balances[:5]:
                print(f"  {item.asset}: free={item.free} locked={item.locked} total={item.total}")

    async def test_fetch_portfolio_positions(self):
        positions = await self.adapter.fetch_portfolio_positions()
        self.assertIsInstance(positions, list)
        if _verbose_enabled():
            print(f"portfolio positions: {len(positions)}")
        if _debug_enabled():
            for item in positions[:5]:
                print(
                    f"  {item.symbol} qty={item.qty} avg={item.avg_price} "
                    f"price={item.current_price} pnl={item.unrealized_pnl}"
                )

    async def test_fetch_snapshot(self):
        snapshot = await self.adapter.fetch_snapshot(limit=50)
        self.assertIsInstance(snapshot.balances, list)
        self.assertIsInstance(snapshot.positions, list)
        self.assertIsInstance(snapshot.activities, list)
        if _verbose_enabled():
            print(
                f"snapshot: balances={len(snapshot.balances)} "
                f"positions={len(snapshot.positions)} activities={len(snapshot.activities)}"
            )
        if _dump_enabled():
            _dump_json("snapshot_balances", [b.raw for b in snapshot.balances])
            _dump_json("snapshot_positions", [p.raw for p in snapshot.positions])
            _dump_json("snapshot_activities", [a.raw for a in snapshot.activities])

    def test_token_refresh_info(self):
        if self.__class__.last_access_exp and _verbose_enabled():
            now = datetime.now(tz=timezone.utc)
            print("access_token expires in:", self.__class__.last_access_exp - now)


if __name__ == "__main__":
    unittest.main()
