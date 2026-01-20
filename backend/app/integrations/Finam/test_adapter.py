import asyncio
import dataclasses
import json
import os
import unittest
from datetime import datetime
from pathlib import Path
from typing import Optional

# ✅ ВАЖНО: файл рядом с тестом.
# Если твой файл называется иначе — поменяй "finam_adapter" на реальное имя.
from .adapter import FinamAdapter  # type: ignore


def _env(name: str) -> Optional[str]:
    v = os.getenv(name)
    if v is None:
        return None
    v = v.strip()
    return v or None


def _verbose_enabled() -> bool:
    v = _env("FINAM_VERBOSE")
    if v is None:
        return True
    return v.lower() in {"1", "true", "yes"}


def _dump_enabled() -> bool:
    return (_env("FINAM_DUMP") or "").lower() in {"1", "true", "yes"}


def _load_env_from_dotenv() -> None:
    """
    Loads .env from current directory upward until found.
    """
    if _env("FINAM_TOKEN"):
        return

    for parent in [Path.cwd(), *Path.cwd().parents]:
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
    print(f"\n--- {label} (dump) ---")
    print(json.dumps(_serialize_payload(payload), ensure_ascii=True, indent=2, sort_keys=True))


class FinamAdapterLiveTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        _load_env_from_dotenv()
        cls.token = _env("FINAM_TOKEN")
        if not cls.token:
            raise unittest.SkipTest("FINAM_TOKEN not set (put it into .env as FINAM_TOKEN=...)")

        cls.account_id = _env("FINAM_ACCOUNT_ID")
        cls.token_calls = 0

        def _provider() -> str:
            cls.token_calls += 1
            return cls.token or ""

        cls.adapter = FinamAdapter(
            secret=cls.token,
            account_id=cls.account_id,
            secret_provider=_provider,
        )

    @classmethod
    def tearDownClass(cls):
        try:
            asyncio.run(cls.adapter.aclose())
        except Exception:
            pass

    async def test_ping(self):
        res = await self.__class__.adapter.ping()
        _dump_payload("ping", res)

        if _verbose_enabled():
            print(f"\nping: ok={res.ok} accounts={getattr(res, 'account_ids', [])}")
            if not res.ok:
                print("ping error:",
                      getattr(res, "error_code", None),
                      getattr(res, "error_type", None),
                      getattr(res, "message", None))

        self.assertTrue(res.ok, msg=f"FINAM_TOKEN invalid? {getattr(res, 'message', None)}")
        self.assertGreater(self.__class__.token_calls, 0)

        if not self.__class__.account_id:
            ids = getattr(res, "account_ids", []) or []
            if ids:
                self.__class__.account_id = ids[0]
                if _verbose_enabled():
                    print("using account_id from token:", self.__class__.account_id)

    async def test_fetch_balances_positions(self):
        account_id = self.__class__.account_id

        balances = await self.__class__.adapter.fetch_balances(account_id=account_id)
        positions = await self.__class__.adapter.fetch_positions(account_id=account_id)

        _dump_payload("balances", balances)
        _dump_payload("positions", positions)

        self.assertIsInstance(balances, list)
        self.assertIsInstance(positions, list)
        self.assertGreaterEqual(len(balances), 1)

        if _verbose_enabled():
            print("\n=== BALANCES ===")
            for b in balances[:30]:
                print(f"  {b.asset}: free={b.free} locked={b.locked} total={b.total}")

            print("\n=== POSITIONS ===")
            if not positions:
                print("  (no positions)")
            for p in positions[:80]:
                print(
                    f"  {p.symbol} qty={p.qty} avg={p.avg_price} "
                    f"last={p.current_price} pnl={p.unrealized_pnl} {p.currency}"
                )

    async def test_fetch_trades_transactions(self):
        account_id = self.__class__.account_id

        trades = await self.__class__.adapter.fetch_trades(account_id=account_id, limit=50)
        txs = await self.__class__.adapter.fetch_transactions(account_id=account_id, limit=50)

        _dump_payload("trades", trades)
        _dump_payload("transactions", txs)

        self.assertIsInstance(trades, list)
        self.assertIsInstance(txs, list)

        if _verbose_enabled():
            print("\n=== TRADES (first 15) ===")
            for t in trades[:15]:
                print(
                    f"  {t.timestamp} {t.symbol} side={t.side} amount={t.amount} "
                    f"price={t.price} fee={t.fee} {t.fee_currency}"
                )

            print("\n=== TRANSACTIONS (first 20) ===")
            for x in txs[:20]:
                name = (x.raw or {}).get("transaction_name") or (x.raw or {}).get("transactionName") or ""
                print(
                    f"  {x.timestamp} {x.activity_type} {name} "
                    f"symbol={x.symbol} ccy={x.quote_asset} amount={x.amount} price={x.price}"
                )

    async def test_snapshot_quick_check(self):
        snap = await self.__class__.adapter.fetch_snapshot(account_id=self.__class__.account_id, limit=50)
        _dump_payload("snapshot", snap)

        self.assertIsInstance(snap.balances, list)
        self.assertIsInstance(snap.positions, list)
        self.assertIsInstance(snap.activities, list)

        if _verbose_enabled():
            print("\n=== SNAPSHOT QUICK CHECK ===")
            print(f"balances={len(snap.balances)} positions={len(snap.positions)} activities={len(snap.activities)}")

            print("\nBalances:")
            for b in snap.balances[:30]:
                print(f"  {b.asset}: total={b.total}")

            print("\nPositions:")
            if not snap.positions:
                print("  (no positions)")
            for p in snap.positions[:80]:
                print(f"  {p.symbol}: qty={p.qty} avg={p.avg_price} last={p.current_price} pnl={p.unrealized_pnl}")

            print("\nActivities (first 20):")
            for a in snap.activities[:20]:
                print(f"  {a.timestamp} {a.activity_type} {a.symbol} side={a.side} amount={a.amount} price={a.price}")

            print("===========================\n")


class FinamAdapterFallbackTests(unittest.IsolatedAsyncioTestCase):
    class _Adapter(FinamAdapter):
        def __init__(self) -> None:
            super().__init__(secret="dummy", account_id=None)
            self.rest_paths = []
            self.rest_responses = {}

        async def _get_client(self):
            return object()

        async def _ensure_sdk_jwt(self, client):  # type: ignore[override]
            return None

        async def _rl_call(self, key, fn, *args, **kwargs):  # type: ignore[override]
            raise Exception("pydantic validation error")

        def _extract_sdk_jwt(self, client):  # type: ignore[override]
            return None

        async def _rest_get(self, path, params=None, *, jwt_override=None):  # type: ignore[override]
            self.rest_paths.append(path)
            resp = self.rest_responses.get(path)
            if isinstance(resp, BaseException):
                raise resp
            if resp is None:
                raise RuntimeError(f"unexpected path: {path}")
            return resp

    async def test_rest_fallback_tries_full_account_id_first(self):
        adapter = self._Adapter()
        try:
            full_path = "/v1/accounts/TRQD05%3A413249"
            adapter.rest_responses[full_path] = {"cash": [], "positions": []}

            info = await adapter._get_account_info("TRQD05:413249")
            self.assertEqual(adapter.rest_paths, [full_path])
            self.assertIsInstance(info, dict)
            self.assertEqual(info.get("_source"), "rest_fallback")
        finally:
            await adapter.aclose()

    async def test_rest_fallback_tries_numeric_suffix_after_404(self):
        adapter = self._Adapter()
        try:
            full_path = "/v1/accounts/TRQD05%3A413249"
            numeric_path = "/v1/accounts/413249"
            adapter.rest_responses[full_path] = RuntimeError("Finam REST 404 for /v1/accounts/TRQD05%3A413249: not found")
            adapter.rest_responses[numeric_path] = {"cash": [], "positions": []}

            info = await adapter._get_account_info("TRQD05:413249")
            self.assertEqual(adapter.rest_paths, [full_path, numeric_path])
            self.assertIsInstance(info, dict)
            self.assertEqual(info.get("_source"), "rest_fallback")
        finally:
            await adapter.aclose()


if __name__ == "__main__":
    unittest.main(verbosity=2)
