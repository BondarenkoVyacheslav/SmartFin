from __future__ import annotations

import base64
import json
import re
import asyncio
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple
from urllib.parse import quote

import httpx


# =========
#   DTOs
# =========

@dataclass(frozen=True)
class FinamBalance:
    asset: str
    free: Optional[float]
    locked: Optional[float]
    total: Optional[float]
    raw: Dict[str, Any]


@dataclass(frozen=True)
class FinamPosition:
    symbol: str  # e.g. YDEX@MISX
    qty: Optional[float]
    avg_price: Optional[float]
    current_price: Optional[float]
    unrealized_pnl: Optional[float]
    currency: Optional[str]
    raw: Dict[str, Any]


@dataclass(frozen=True)
class ActivityLine:
    activity_type: str  # "trade" | "transaction" | "commission" | ...
    symbol: Optional[str]
    base_asset: Optional[str]
    quote_asset: Optional[str]
    side: Optional[str]          # BUY/SELL
    amount: Optional[float]      # qty/size
    price: Optional[float]
    fee: Optional[float]
    fee_currency: Optional[str]
    timestamp: Optional[datetime]
    raw: Dict[str, Any]


@dataclass(frozen=True)
class FinamSnapshot:
    balances: List[FinamBalance]
    positions: List[FinamPosition]
    activities: List[ActivityLine]


@dataclass(frozen=True)
class FinamPingResult:
    ok: bool
    account_ids: List[str]
    message: Optional[str] = None
    error_type: Optional[str] = None
    error_code: Optional[str] = None
    raw_error: Optional[str] = None


# ==========================
#   Adapter implementation
# ==========================

class FinamAdapter:
    """
    Finam Trade API adapter.

    SDK (finam-trade-api) используется для:
      - trades
      - transactions
      - token details (account_ids, expires_at)

    REST fallback используется для:
      - GetAccount (balances/positions), потому что SDK иногда падает на pydantic-модели,
        когда API не возвращает некоторые поля.
    """

    DEFAULT_ACTIVITY_DAYS = 30
    DEFAULT_REFRESH_SAFETY_WINDOW = timedelta(seconds=60)

    def __init__(
        self,
        secret: str,
        *,
        account_id: Optional[str] = None,
        extra_params: Optional[Dict[str, Any]] = None,
        secret_provider: Optional[Callable[[], str]] = None,
        rate_limits: Optional[Dict[str, int]] = None,
    ) -> None:
        self._secret = (secret or "").strip()
        self._secret_provider = secret_provider
        self._account_id = account_id.strip() if account_id else None

        self._client_params = dict(extra_params or {})
        self._client: Optional[Any] = None
        self._client_lock = asyncio.Lock()

        # SDK jwt lifecycle
        self._sdk_jwt_expires_at: Optional[datetime] = None
        self._current_secret: Optional[str] = None

        self._rate_limiters = _build_rate_limiters(rate_limits)

        # SDK imports
        (
            self._Client,
            self._TokenManager,
            self._GetTransactionsRequest,
            self._GetTradesRequest,
        ) = _load_finam_sdk()

        # REST client (fallback) — важно: НЕ создаём сразу, потому что в IsolatedAsyncioTestCase новый loop на каждый тест
        self._rest: Optional[httpx.AsyncClient] = None
        self._rest_loop_id: Optional[int] = None

        self._rest_jwt_token: Optional[str] = None
        self._rest_jwt_expire_at: float = 0.0
        self._rest_auth_lock = asyncio.Lock()

    # -----------------------
    # Public API
    # -----------------------

    async def ping(self) -> FinamPingResult:
        """
        Проверка ключа: пытаемся получить TokenDetails через SDK.
        """
        if not (self._secret_provider or self._secret):
            return FinamPingResult(
                ok=False,
                account_ids=[],
                message="Empty secret",
                error_type="ValueError",
                error_code="EMPTY_SECRET",
            )

        try:
            client = await self._get_client()
            await self._ensure_sdk_jwt(client)
            details = await self._rl_call("auth", client.access_tokens.get_jwt_token_details)
            ids = _extract_account_ids(details)
            return FinamPingResult(ok=True, account_ids=ids, message="OK")
        except Exception as exc:
            msg, etype, ecode = _classify_ping_error(exc)
            return FinamPingResult(
                ok=False,
                account_ids=[],
                message=msg,
                error_type=etype,
                error_code=ecode,
                raw_error=_safe_repr(exc),
            )

    async def validate_secret(self) -> bool:
        return (await self.ping()).ok

    async def fetch_accounts(self) -> List[str]:
        client = await self._get_client()
        await self._ensure_sdk_jwt(client)
        details = await self._rl_call("auth", client.access_tokens.get_jwt_token_details)
        return _extract_account_ids(details)

    async def fetch_balances(self, *, account_id: Optional[str] = None) -> List[FinamBalance]:
        account_id = await self._resolve_account_id(account_id)
        info = await self._get_account_info(account_id)

        # SDK object
        if not isinstance(info, dict):
            return _parse_balances_from_account_info(info)

        # REST dict fallback
        return _parse_balances_from_rest_account(info)

    async def fetch_positions(self, *, account_id: Optional[str] = None) -> List[FinamPosition]:
        account_id = await self._resolve_account_id(account_id)
        info = await self._get_account_info(account_id)

        # SDK object
        if not isinstance(info, dict):
            return _parse_positions_from_account_info(info)

        # REST dict fallback
        return _parse_positions_from_rest_account(info)

    async def fetch_trades(
        self,
        *,
        account_id: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 200,
    ) -> List[ActivityLine]:
        account_id = await self._resolve_account_id(account_id)
        since, until = _normalize_period(since, until, self.DEFAULT_ACTIVITY_DAYS)

        client = await self._get_client()
        await self._ensure_sdk_jwt(client)

        req = self._GetTradesRequest(
            account_id=account_id,
            start_time=_to_iso_utc(since),
            end_time=_to_iso_utc(until),
            limit=int(limit) if limit and limit > 0 else None,
        )
        resp = await self._rl_call("accounts", client.account.get_trades, req)

        items = _parse_trades(resp)
        items.sort(key=lambda a: a.timestamp or datetime.min.replace(tzinfo=timezone.utc))
        return items[: int(limit)] if (limit and limit > 0) else items

    async def fetch_transactions(
        self,
        *,
        account_id: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 200,
    ) -> List[ActivityLine]:
        account_id = await self._resolve_account_id(account_id)
        since, until = _normalize_period(since, until, self.DEFAULT_ACTIVITY_DAYS)

        client = await self._get_client()
        await self._ensure_sdk_jwt(client)

        req = self._GetTransactionsRequest(
            account_id=account_id,
            start_time=_to_iso_utc(since),
            end_time=_to_iso_utc(until),
            limit=int(limit) if limit and limit > 0 else None,
        )
        resp = await self._rl_call("accounts", client.account.get_transactions, req)

        items = _parse_transactions(resp)
        items.sort(key=lambda a: a.timestamp or datetime.min.replace(tzinfo=timezone.utc))
        return items[: int(limit)] if (limit and limit > 0) else items

    async def fetch_activities(
        self,
        *,
        account_id: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 200,
    ) -> List[ActivityLine]:
        account_id = await self._resolve_account_id(account_id)
        since, until = _normalize_period(since, until, self.DEFAULT_ACTIVITY_DAYS)

        trades, txs = await asyncio.gather(
            self.fetch_trades(account_id=account_id, since=since, until=until, limit=limit),
            self.fetch_transactions(account_id=account_id, since=since, until=until, limit=limit),
        )
        activities = [*trades, *txs]
        activities.sort(key=lambda a: a.timestamp or datetime.min.replace(tzinfo=timezone.utc))
        return activities[: int(limit)] if (limit and limit > 0) else activities

    async def fetch_snapshot(
        self,
        *,
        account_id: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 200,
    ) -> FinamSnapshot:
        account_id = await self._resolve_account_id(account_id)
        balances, positions, activities = await asyncio.gather(
            self.fetch_balances(account_id=account_id),
            self.fetch_positions(account_id=account_id),
            self.fetch_activities(account_id=account_id, since=since, until=until, limit=limit),
        )
        return FinamSnapshot(balances=balances, positions=positions, activities=activities)

    async def aclose(self) -> None:
        async with self._client_lock:
            if self._client is not None:
                await _client_close(self._client)
                self._client = None

        # REST close
        if self._rest is not None:
            try:
                await self._rest.aclose()
            except Exception:
                pass
            self._rest = None
            self._rest_loop_id = None

        self._sdk_jwt_expires_at = None
        self._current_secret = None
        self._rest_jwt_token = None
        self._rest_jwt_expire_at = 0.0

    async def __aenter__(self) -> "FinamAdapter":
        await self._get_client()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.aclose()

    # -----------------------
    # Internals
    # -----------------------

    async def _resolve_account_id(self, account_id: Optional[str]) -> str:
        if account_id:
            return account_id
        if self._account_id:
            return self._account_id
        accounts = await self.fetch_accounts()
        if not accounts:
            raise RuntimeError("Finam account_id is required but no accounts were found in token details")
        self._account_id = accounts[0]
        return self._account_id

    def _get_secret(self) -> str:
        secret = self._secret_provider() if self._secret_provider else self._secret
        secret = (secret or "").strip()
        if not secret:
            raise RuntimeError("Finam secret (API token) is empty")
        return secret

    async def _get_client(self) -> Any:
        async with self._client_lock:
            secret = self._get_secret()
            if self._client is not None and self._current_secret == secret:
                return self._client

            # recreate if secret changed
            if self._client is not None:
                await _client_close(self._client)

            token_manager = self._TokenManager(secret)
            self._client = self._Client(token_manager, **self._client_params)
            self._current_secret = secret
            self._sdk_jwt_expires_at = None
            return self._client

    async def _ensure_sdk_jwt(self, client: Any) -> None:
        """
        SDK refresh JWT (POST /v1/sessions under the hood).
        """
        if self._sdk_jwt_expires_at is not None:
            if _utcnow() + self.DEFAULT_REFRESH_SAFETY_WINDOW < self._sdk_jwt_expires_at:
                return

        await self._rl_call("auth", client.access_tokens.set_jwt_token)
        details = await self._rl_call("auth", client.access_tokens.get_jwt_token_details)
        self._sdk_jwt_expires_at = _parse_expires_at(details)

    async def _get_rest_client(self) -> httpx.AsyncClient:
        """
        Важно для тестов на IsolatedAsyncioTestCase:
        новый event loop на каждый тест => AsyncClient должен жить внутри актуального loop.
        """
        loop_id = id(asyncio.get_running_loop())

        if self._rest is not None and self._rest_loop_id == loop_id:
            return self._rest

        # loop сменился — закрываем старый клиент
        if self._rest is not None:
            try:
                await self._rest.aclose()
            except Exception:
                pass
            self._rest = None
            self._rest_loop_id = None

        self._rest = httpx.AsyncClient(
            base_url="https://api.finam.ru",
            timeout=httpx.Timeout(15.0),
            http2=True,
            headers={"User-Agent": "SmartFin/1.0"},
        )
        self._rest_loop_id = loop_id
        return self._rest

    async def _ensure_rest_jwt(self) -> str:
        """
        REST JWT for fallback requests (POST /v1/sessions).

        Делаем совместимость по форматам запроса:
          - json {"secret": "..."}
          - form secret=...
          - query ?secret=...
        + проверка, что token похож на JWT (a.b.c).
        """
        now = time.time()
        if self._rest_jwt_token and now < (self._rest_jwt_expire_at - 20):
            return self._rest_jwt_token

        async with self._rest_auth_lock:
            now = time.time()
            if self._rest_jwt_token and now < (self._rest_jwt_expire_at - 20):
                return self._rest_jwt_token

            secret = self._get_secret()
            rest = await self._get_rest_client()

            attempts = [
                ("json", dict(json={"secret": secret})),
                ("form", dict(data={"secret": secret})),
                ("query", dict(params={"secret": secret})),
            ]

            last_err: Optional[BaseException] = None

            for mode, kwargs in attempts:
                resp = await rest.post("/v1/sessions", **kwargs)
                try:
                    if resp.status_code >= 400:
                        body = await resp.aread()
                        snippet = body[:500].decode("utf-8", errors="replace")
                        last_err = RuntimeError(f"Finam Auth {resp.status_code} ({mode}) /v1/sessions: {snippet}")
                        continue

                    data = resp.json()
                    if not isinstance(data, dict):
                        last_err = RuntimeError(f"Finam Auth ({mode}) returned non-object JSON: {data!r}")
                        continue

                    token = (data.get("token") or "").strip()
                    if not token:
                        last_err = RuntimeError(f"Finam Auth ({mode}) returned no token: {data!r}")
                        continue

                    if not _looks_like_jwt(token):
                        last_err = RuntimeError(f"Finam Auth ({mode}) returned non-JWT token: {token!r}")
                        continue

                    # ставим TTL 14 минут (консервативно)
                    self._rest_jwt_token = token
                    self._rest_jwt_expire_at = time.time() + 14 * 60
                    return token
                finally:
                    await resp.aclose()

            raise last_err or RuntimeError("Finam Auth failed: no successful attempts")

    async def _rest_get(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        *,
        jwt_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        rest = await self._get_rest_client()
        jwt = jwt_override or await self._ensure_rest_jwt()
        jwt = _normalize_bearer_token(jwt)

        last_exc: Optional[BaseException] = None

        auth_mode = "raw"  # сначала пробуем без Bearer

        for attempt in range(3):
            headers = {"Authorization": jwt} if auth_mode == "raw" else {"Authorization": f"Bearer {jwt}"}
            resp = await rest.get(path, params=params, headers=headers)

            try:
                if resp.status_code >= 400:
                    body = await resp.aread()
                    snippet = body[:500].decode("utf-8", errors="replace")

                    # Finam иногда возвращает 500 на проблемы JWT — делаем refresh и пробуем снова
                    if ("Jwt token check failed" in snippet) and attempt == 0:
                        # если raw не прокатил — попробуем Bearer на следующей попытке
                        if auth_mode == "raw":
                            auth_mode = "bearer"
                        self._rest_jwt_token = None
                        self._rest_jwt_expire_at = 0.0
                        jwt = _normalize_bearer_token(await self._ensure_rest_jwt())
                        continue

                    # 401/403 — возможно протух jwt или неверный формат auth header
                    if resp.status_code in (401, 403) and attempt == 0:
                        if auth_mode == "raw":
                            auth_mode = "bearer"  # переключимся и попробуем ещё раз
                        self._rest_jwt_token = None
                        self._rest_jwt_expire_at = 0.0
                        jwt = _normalize_bearer_token(await self._ensure_rest_jwt())
                        continue

                    # retry на 5xx (транзиенты)
                    if 500 <= resp.status_code <= 599 and attempt < 2:
                        await asyncio.sleep(0.3 * (attempt + 1))
                        continue

                    raise RuntimeError(f"Finam REST {resp.status_code} for {path}: {snippet}")

                data = resp.json()
                if not isinstance(data, dict):
                    raise RuntimeError(f"Unexpected Finam REST response for {path}: {data!r}")
                return data

            except BaseException as exc:
                last_exc = exc
                raise
            finally:
                await resp.aclose()

        raise RuntimeError(f"Finam REST failed for {path}") from last_exc


    async def _get_account_info(self, account_id: str) -> Any:
        """
        Try SDK first; if SDK model validation fails => REST fallback.
        """
        client = await self._get_client()
        await self._ensure_sdk_jwt(client)

        try:
            return await self._rl_call("accounts", client.account.get_account_info, account_id)
        except Exception as exc:
            # SDK иногда падает на pydantic-моделях (missing fields).
            # Finam REST может ожидать как полный id (например TRQD05:413249),
            # так и числовой суффикс (413249) — попробуем оба.
            candidates: List[str] = []
            original = (account_id or "").strip()
            if original:
                candidates.append(original)

            rest_suffix = _rest_account_id(original)
            if rest_suffix and rest_suffix != original:
                candidates.append(rest_suffix)

            jwt_sdk = self._extract_sdk_jwt(client)
            # На всякий случай: не используем override, если вдруг это не JWT
            if jwt_sdk and not _looks_like_jwt(jwt_sdk):
                jwt_sdk = None

            last_rest_exc: Optional[BaseException] = None
            raw: Optional[Dict[str, Any]] = None
            for cid in candidates:
                safe_account_id = quote(cid, safe="")
                try:
                    raw = await self._rest_get(
                        f"/v1/accounts/{safe_account_id}",
                        jwt_override=jwt_sdk,
                    )
                    break
                except RuntimeError as rest_exc:
                    last_rest_exc = rest_exc
                    # Если аккаунт не найден — пробуем следующий формат id.
                    if "Finam REST 404" in str(rest_exc):
                        continue
                    raise

            if raw is None:
                raise RuntimeError("Finam REST fallback failed for account info") from (last_rest_exc or exc)

            raw["_source"] = "rest_fallback"
            raw["_sdk_error"] = repr(exc)
            raw["_jwt_source"] = "sdk" if jwt_sdk else "rest_sessions"
            return raw


    async def _rl_call(self, key: str, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        limiter = self._rate_limiters.get(key)
        if limiter:
            await limiter.acquire()
        return await fn(*args, **kwargs)
    
    def _extract_sdk_jwt(self, client: Any) -> Optional[str]:
        # Пытаемся найти jwt по типичным атрибутам разных реализаций SDK
        candidates = []

        access_tokens = getattr(client, "access_tokens", None)
        if access_tokens is not None:
            for name in ("jwt_token", "token", "_jwt_token", "_token"):
                candidates.append(getattr(access_tokens, name, None))

        token_manager = getattr(client, "token_manager", None) or getattr(client, "_token_manager", None)
        if token_manager is not None:
            for name in ("jwt_token", "token", "_jwt_token", "_token"):
                candidates.append(getattr(token_manager, name, None))

        # Иногда токен лежит прямо на клиенте
        for name in ("jwt_token", "_jwt_token", "token"):
            candidates.append(getattr(client, name, None))

        for c in candidates:
            if isinstance(c, str) and c.strip():
                t = _normalize_bearer_token(c)
                if _looks_like_jwt(t):
                    return t

        return None



# ======================
#   Rate limiting
# ======================

class _RateLimiter:
    def __init__(self, limit_per_minute: int) -> None:
        self._interval = 60.0 / max(1, int(limit_per_minute))
        self._lock = asyncio.Lock()
        self._last_call: Optional[float] = None

    async def acquire(self) -> None:
        async with self._lock:
            now = asyncio.get_running_loop().time()
            if self._last_call is None:
                self._last_call = now
                return
            wait_for = self._interval - (now - self._last_call)
            if wait_for > 0:
                await asyncio.sleep(wait_for)
                now = asyncio.get_running_loop().time()
            self._last_call = now


def _build_rate_limiters(rate_limits: Optional[Dict[str, int]]) -> Dict[str, _RateLimiter]:
    defaults = {"auth": 60, "accounts": 180, "market": 300}
    limits = dict(defaults)
    if rate_limits:
        limits.update({k: v for k, v in rate_limits.items() if v})
    return {k: _RateLimiter(v) for k, v in limits.items()}


# ======================
#   SDK loading / close
# ======================

def _load_finam_sdk() -> Tuple[Any, Any, Any, Any]:
    try:
        from finam_trade_api import Client, TokenManager  # type: ignore
        from finam_trade_api.account import GetTransactionsRequest, GetTradesRequest  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "Finam Python SDK wrapper not installed. Install:\n"
            "  uv add finam-trade-api\n"
            "or\n"
            "  pip install finam-trade-api"
        ) from exc
    return Client, TokenManager, GetTransactionsRequest, GetTradesRequest


async def _client_close(client: Any) -> None:
    aexit = getattr(client, "__aexit__", None)
    if callable(aexit):
        try:
            await client.__aexit__(None, None, None)
            return
        except Exception:
            pass

    close = getattr(client, "close", None)
    if callable(close):
        res = close()
        if asyncio.iscoroutine(res):
            await res
        return

    session = getattr(client, "session", None)
    if session is not None:
        sclose = getattr(session, "close", None)
        if callable(sclose):
            res = sclose()
            if asyncio.iscoroutine(res):
                await res


# ======================
#   Parsing layer
# ======================

def _extract_account_ids(details: Any) -> List[str]:
    account_ids = getattr(details, "account_ids", None) or getattr(details, "accountIds", None) or []
    out: List[str] = []
    for x in account_ids:
        s = _to_str(x)
        if s:
            out.append(s)
    return out


def _parse_balances_from_account_info(info: Any) -> List[FinamBalance]:
    cash_items = _coerce_list(getattr(info, "cash", None))
    balances: List[FinamBalance] = []
    for item in cash_items:
        currency = _first_str(
            getattr(item, "currency_code", None),
            getattr(item, "currencyCode", None),
            getattr(item, "currency", None),
        )
        amount = _moneylike_to_float(item)
        if not currency and amount is None:
            continue
        balances.append(
            FinamBalance(
                asset=(currency or "").upper() or "UNKNOWN",
                free=amount,
                locked=None,
                total=amount,
                raw=_obj_to_dict(item),
            )
        )
    return balances


def _parse_positions_from_account_info(info: Any) -> List[FinamPosition]:
    items = _coerce_list(getattr(info, "positions", None))
    out: List[FinamPosition] = []
    for p in items:
        symbol = _to_str(getattr(p, "symbol", None)) or ""
        qty = _decimal_like_to_float(getattr(p, "quantity", None))
        avg = _decimal_like_to_float(getattr(p, "average_price", None))
        cur = _decimal_like_to_float(getattr(p, "current_price", None))
        pnl = _decimal_like_to_float(getattr(p, "unrealized_pnl", None))
        currency = _to_str(getattr(p, "currency", None))
        if not symbol and qty is None:
            continue
        out.append(
            FinamPosition(
                symbol=symbol,
                qty=qty,
                avg_price=avg,
                current_price=cur,
                unrealized_pnl=pnl,
                currency=currency,
                raw=_obj_to_dict(p),
            )
        )
    return out


def _parse_balances_from_rest_account(info: Dict[str, Any]) -> List[FinamBalance]:
    cash_items = info.get("cash") or []
    balances: List[FinamBalance] = []
    for m in cash_items:
        if not isinstance(m, dict):
            continue
        ccy = _first_str(m.get("currency_code"), m.get("currencyCode"), m.get("currency"))
        amount = _money_to_float(m)
        if not ccy:
            continue
        balances.append(
            FinamBalance(
                asset=ccy.upper(),
                free=amount,
                locked=None,
                total=amount,
                raw=m,
            )
        )
    return balances


def _parse_positions_from_rest_account(info: Dict[str, Any]) -> List[FinamPosition]:
    items = info.get("positions") or []
    out: List[FinamPosition] = []
    for p in items:
        if not isinstance(p, dict):
            continue
        symbol = _to_str(p.get("symbol")) or ""
        qty = _decimal_like_to_float(p.get("quantity"))
        avg = _decimal_like_to_float(p.get("average_price"))
        cur = _decimal_like_to_float(p.get("current_price"))
        pnl = _decimal_like_to_float(p.get("unrealized_pnl"))
        currency = _to_str(p.get("currency"))
        if not symbol and qty is None:
            continue
        out.append(
            FinamPosition(
                symbol=symbol,
                qty=qty,
                avg_price=avg,
                current_price=cur,
                unrealized_pnl=pnl,
                currency=currency,
                raw=p,
            )
        )
    return out


def _parse_transactions(resp: Any) -> List[ActivityLine]:
    txs = _coerce_list(getattr(resp, "transactions", None)) or _coerce_list(getattr(resp, "items", None))
    out: List[ActivityLine] = []
    for tx in txs:
        category = _to_str(getattr(tx, "category", None)) or _to_str(getattr(tx, "transaction_category", None))
        tx_name = _to_str(getattr(tx, "transaction_name", None))
        activity_type = (category or "transaction").lower()

        symbol = _to_str(getattr(tx, "symbol", None))
        ts = _parse_dt(getattr(tx, "timestamp", None))

        change_money = getattr(tx, "change", None)
        quote_ccy = _first_str(
            getattr(change_money, "currency_code", None),
            getattr(change_money, "currencyCode", None),
            getattr(change_money, "currency", None),
        )

        trade = getattr(tx, "trade", None)
        size = _decimal_like_to_float(getattr(trade, "size", None)) if trade else None
        price = _decimal_like_to_float(getattr(trade, "price", None)) if trade else None

        side = None
        if trade is not None:
            side = _to_str(getattr(trade, "side", None))
        if side:
            side = _normalize_side(side)

        raw = _obj_to_dict(tx)
        if tx_name:
            raw.setdefault("transaction_name", tx_name)

        out.append(
            ActivityLine(
                activity_type=activity_type,
                symbol=symbol,
                base_asset=None,
                quote_asset=quote_ccy,
                side=side,
                amount=size,
                price=price,
                fee=None,
                fee_currency=None,
                timestamp=ts,
                raw=raw,
            )
        )
    return out


def _parse_trades(resp: Any) -> List[ActivityLine]:
    trades = _coerce_list(getattr(resp, "trades", None)) or _coerce_list(getattr(resp, "items", None))
    out: List[ActivityLine] = []
    for tr in trades:
        symbol = _to_str(getattr(tr, "symbol", None))
        price = _decimal_like_to_float(getattr(tr, "price", None))
        size = _decimal_like_to_float(getattr(tr, "size", None))
        side = _normalize_side(_to_str(getattr(tr, "side", None)) or "")
        ts = _parse_dt(getattr(tr, "timestamp", None))

        fee = _moneylike_to_float(getattr(tr, "fee", None))
        fee_ccy = _first_str(
            getattr(getattr(tr, "fee", None), "currency_code", None),
            getattr(getattr(tr, "fee", None), "currency", None),
        )

        out.append(
            ActivityLine(
                activity_type="trade",
                symbol=symbol,
                base_asset=None,
                quote_asset=None,
                side=side,
                amount=size,
                price=price,
                fee=fee,
                fee_currency=fee_ccy,
                timestamp=ts,
                raw=_obj_to_dict(tr),
            )
        )
    return out


def _parse_expires_at(details: Any) -> Optional[datetime]:
    exp = getattr(details, "expires_at", None) or getattr(details, "expiresAt", None)
    return _parse_dt(exp)


# ======================
#   Period helpers
# ======================

def _normalize_period(
    since: Optional[datetime],
    until: Optional[datetime],
    default_days: int,
) -> Tuple[datetime, datetime]:
    now = _utcnow()
    if until is None:
        until = now
    if since is None:
        since = until - timedelta(days=int(default_days))
    since = _ensure_aware(since)
    until = _ensure_aware(until)
    if since > until:
        since, until = until, since
    return since, until


# ======================
#   Low-level coercions
# ======================

def _coerce_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    if isinstance(value, (str, bytes, dict)):
        return []
    return list(value) if isinstance(value, Iterable) else []


def _decimal_like_to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    v = getattr(value, "value", None)
    if v is not None:
        return _to_float(v)
    if isinstance(value, dict) and "value" in value:
        return _to_float(value.get("value"))
    return _to_float(value)


def _moneylike_to_float(value: Any) -> Optional[float]:
    if value is None:
        return None

    # Decimal-like
    dec = _decimal_like_to_float(value)
    if dec is not None and not hasattr(value, "units"):
        return dec

    units = getattr(value, "units", None)
    nanos = getattr(value, "nanos", None)
    nano = getattr(value, "nano", None)
    if units is not None:
        return float(units) + float(nanos or nano or 0) / 1e9

    if isinstance(value, dict):
        if "units" in value:
            return float(value.get("units") or 0) + float(value.get("nanos") or value.get("nano") or 0) / 1e9
        if "value" in value:
            return _to_float(value.get("value"))

    return _to_float(value)


def _obj_to_dict(obj: Any) -> Dict[str, Any]:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return dict(obj)
    dump = getattr(obj, "model_dump", None)  # pydantic v2
    if callable(dump):
        try:
            return dump()
        except Exception:
            pass
    dump = getattr(obj, "dict", None)  # pydantic v1
    if callable(dump):
        try:
            return dump()
        except Exception:
            pass
    out: Dict[str, Any] = {}
    for k in dir(obj):
        if k.startswith("_"):
            continue
        try:
            v = getattr(obj, k)
        except Exception:
            continue
        if callable(v):
            continue
        if isinstance(v, (str, int, float, bool, type(None))):
            out[k] = v
    return out


def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return _ensure_aware(value)
    s = _to_str(value)
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        return _ensure_aware(dt)
    except Exception:
        return None


def _normalize_side(side: str) -> Optional[str]:
    s = (side or "").strip().upper()
    if not s:
        return None
    if "BUY" in s:
        return "BUY"
    if "SELL" in s:
        return "SELL"
    return None


def _to_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _to_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def _first_str(*values: Any) -> Optional[str]:
    for v in values:
        s = _to_str(v)
        if s:
            return s
    return None


def _ensure_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def _to_iso_utc(dt: datetime) -> str:
    dt = _ensure_aware(dt)
    return dt.isoformat().replace("+00:00", "Z")


# ======================
#   ping() error classify
# ======================

def _safe_repr(exc: BaseException) -> str:
    try:
        return repr(exc)
    except Exception:
        try:
            return str(exc)
        except Exception:
            return "<unreprable error>"


def _classify_ping_error(exc: BaseException) -> Tuple[str, str, str]:
    etype = type(exc).__name__
    msg = str(exc) or "Secret validation failed"
    ecode = "UNKNOWN"

    status = getattr(exc, "status", None)
    if status is None:
        status = getattr(getattr(exc, "response", None), "status", None)
    if isinstance(status, int):
        if status == 401:
            return "Unauthenticated (invalid/expired secret)", etype, "UNAUTHENTICATED"
        if status == 403:
            return "Permission denied (insufficient scope)", etype, "PERMISSION_DENIED"
        if status == 429:
            return "Rate limit exceeded", etype, "RATE_LIMIT"
        if 500 <= status <= 599:
            return "Service error", etype, "UPSTREAM_5XX"
        return msg, etype, f"HTTP_{status}"

    low = (msg or "").lower()
    if "unauthor" in low or "invalid" in low or "token" in low or "secret" in low:
        ecode = "AUTH_FAILED"
    if "timeout" in low or "timed out" in low:
        ecode = "TIMEOUT"
    if "rate" in low and "limit" in low:
        ecode = "RATE_LIMIT"
    if "connect" in low or "dns" in low or "name resolution" in low:
        ecode = "NETWORK"

    return msg, etype, ecode


def _rest_account_id(account_id: str) -> str:
    """
    Finam REST /v1/accounts/{account_id} часто ожидает только числовой id
    (без префикса КЛФ, например из TRQD05:413249 -> 413249).
    """
    s = (account_id or "").strip()
    m = re.search(r"(\d+)$", s)
    return m.group(1) if m else s


def _looks_like_jwt(token: str) -> bool:
    """
    Строгая проверка JWT: token должен иметь 3 части и
    header/payload должны быть валидным base64url JSON.
    """
    t = (token or "").strip()
    parts = t.split(".")
    if len(parts) != 3:
        return False

    for part in parts[:2]:
        pad = "=" * ((4 - (len(part) % 4)) % 4)
        try:
            raw = base64.urlsafe_b64decode((part + pad).encode("utf-8"))
            json.loads(raw.decode("utf-8"))
        except Exception:
            return False

    return True


# ✅ Лучше как утилита на уровне модуля (чистая функция)
def _money_to_float(m: Dict[str, Any]) -> float:
    units = float(m.get("units", 0) or 0)
    nanos = float(m.get("nanos", 0) or 0)
    return units + nanos / 1_000_000_000


def _normalize_bearer_token(token: str) -> str:
    t = (token or "").strip().strip('"').strip("'")
    # если сервер вернул "Bearer <jwt>" — вытащим только jwt
    if " " in t:
        parts = [p for p in t.split() if p]
        if parts and _looks_like_jwt(parts[-1]):
            t = parts[-1]
    if t.lower().startswith("bearer "):
        t = t[7:].strip()
    return t
