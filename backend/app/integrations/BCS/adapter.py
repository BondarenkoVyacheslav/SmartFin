from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

import httpx


@dataclass(frozen=True)
class BcsBalance:
    asset: str
    free: Optional[float]
    locked: Optional[float]
    total: Optional[float]
    raw: Dict[str, Any]


@dataclass(frozen=True)
class BcsPosition:
    symbol: str  # ticker/isin/figi — что есть
    qty: Optional[float]
    avg_price: Optional[float]
    current_price: Optional[float]
    unrealized_pnl: Optional[float]
    currency: Optional[str]
    raw: Dict[str, Any]


@dataclass(frozen=True)
class ActivityLine:
    activity_type: str
    symbol: Optional[str]
    base_asset: Optional[str]
    quote_asset: Optional[str]
    side: Optional[str]
    amount: Optional[float]
    price: Optional[float]
    fee: Optional[float]
    fee_currency: Optional[str]
    timestamp: Optional[datetime]
    raw: Dict[str, Any]


@dataclass(frozen=True)
class BcsSnapshot:
    balances: List[BcsBalance]
    positions: List[BcsPosition]
    activities: List[ActivityLine]


class BcsAdapter:
    """
    BCS Trade API adapter (unofficial), focused on:
    - portfolio/limits (assets/balances/positions)
    - orders as "activities" fallback

    Auth: Authorization: Bearer <access_token>
    """

    DEFAULT_BASE_URL = "https://be.broker.ru"
    TOKEN_PATH = "/trade-api-keycloak/realms/tradeapi/protocol/openid-connect/token"

    # Publicly documented endpoints (minimum)
    LIMITS_PATH = "/trade-api-bff-limit/api/v1/limits"
    PORTFOLIO_PATH = "/trade-api-bff-portfolio/api/v1/portfolio"
    ORDERS_PATH = "/trade-api-bff-operations/api/v1/orders"  # POST create; list may or may not exist for your access
    LIMITS_RPS = 10
    PORTFOLIO_RPS = 10

    def __init__(
        self,
        *,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        client_id: str = "trade-api-read",
        access_expires_at: Optional[datetime] = None,
        refresh_expires_at: Optional[datetime] = None,
        token_margin_s: int = 300,
        token_updater: Optional[
            Callable[[str, Optional[str], Optional[datetime], Optional[datetime]], None]
        ] = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout_s: float = 20.0,
        extra_headers: Optional[Dict[str, str]] = None,
        verify_tls: bool = True,
    ) -> None:
        self._access_token = access_token.strip() if access_token else None
        self._refresh_token = refresh_token.strip() if refresh_token else None
        self._client_id = client_id
        self._access_expires_at = _ensure_aware(access_expires_at)
        self._refresh_expires_at = _ensure_aware(refresh_expires_at)
        self._token_margin = max(int(token_margin_s), 0)
        self._token_updater = token_updater
        self._token_lock = asyncio.Lock()
        self._base_url = base_url.rstrip("/")
        self._timeout = httpx.Timeout(timeout_s)
        self._headers = {"Accept": "application/json", **(extra_headers or {})}
        if self._access_token:
            self._headers["Authorization"] = f"Bearer {self._access_token}"
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers=self._headers,
            timeout=self._timeout,
            verify=verify_tls,
        )
        self._rate_limits = {
            self.LIMITS_PATH: _RateLimiter(self.LIMITS_RPS, 1.0),
            self.PORTFOLIO_PATH: _RateLimiter(self.PORTFOLIO_RPS, 1.0),
        }
        self._auth_client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={"Accept": "application/json"},
            timeout=self._timeout,
            verify=verify_tls,
        )

    async def aclose(self) -> None:
        await self._client.aclose()
        await self._auth_client.aclose()

    async def fetch_limits_raw(self) -> Dict[str, Any]:
        """
        Fetch full limits payload (portfolio snapshot) from BCS.
        Ensures access_token is valid before the request.
        """
        return await self._request_json("GET", self.LIMITS_PATH)

    async def fetch_balances(self) -> List[BcsBalance]:
        raw = await self.fetch_limits_raw()
        return _parse_balances_from_limits(raw)

    async def fetch_positions(self) -> List[BcsPosition]:
        raw = await self.fetch_limits_raw()
        return _parse_positions_from_limits(raw)

    async def fetch_portfolio_raw(self) -> List[Dict[str, Any]]:
        """
        Fetch full portfolio payload from BCS (list of portfolio items).
        Ensures access_token is valid before the request.
        """
        data = await self._request_json("GET", self.PORTFOLIO_PATH)
        items = _coerce_list(data.get("data") or data.get("items") or data)
        return [item for item in items if isinstance(item, dict)]

    async def fetch_portfolio_balances(self) -> List[BcsBalance]:
        items = await self.fetch_portfolio_raw()
        return _parse_balances_from_portfolio(items)

    async def fetch_portfolio_positions(self) -> List[BcsPosition]:
        items = await self.fetch_portfolio_raw()
        return _parse_positions_from_portfolio(items)

    async def fetch_activities(
        self,
        *,
        since: Optional[datetime] = None,
        limit: int = 200,
    ) -> List[ActivityLine]:
        """
        WARNING:
        BCS docs publicly show order create/status endpoints.
        A "list orders" endpoint may exist for your token/scopes, but not always exposed in docs.
        This method is implemented as:
        - try GET /orders with pagination params (best effort)
        - otherwise returns empty list
        """
        params: Dict[str, Any] = {"limit": int(limit)}
        if since is not None:
            params["since"] = _to_iso_utc(since)

        try:
            raw = await self._request_json("GET", self.ORDERS_PATH, params=params)
        except httpx.HTTPStatusError:
            return []

        items = _coerce_list(raw.get("items") or raw.get("orders") or raw.get("list") or raw)
        activities: List[ActivityLine] = []
        for o in items:
            if not isinstance(o, dict):
                continue
            activities.append(
                ActivityLine(
                    activity_type="order",
                    symbol=_to_str(o.get("ticker") or o.get("symbol") or o.get("isin")),
                    base_asset=None,
                    quote_asset=_to_str(o.get("currency") or o.get("currencyCode")),
                    side=_to_str(o.get("side") or o.get("operation")),
                    amount=_to_float(o.get("qty") or o.get("quantity") or o.get("lots")),
                    price=_to_float(o.get("price")),
                    fee=_to_float(o.get("fee")),
                    fee_currency=_to_str(o.get("feeCurrency")),
                    timestamp=_to_dt(o.get("time") or o.get("createdAt") or o.get("timestamp")),
                    raw=o,
                )
            )

        activities.sort(key=lambda a: a.timestamp or datetime.min.replace(tzinfo=timezone.utc))
        return activities

    async def fetch_snapshot(
        self,
        *,
        since: Optional[datetime] = None,
        limit: int = 200,
    ) -> BcsSnapshot:
        balances, positions, activities = await asyncio.gather(
            self.fetch_balances(),
            self.fetch_positions(),
            self.fetch_activities(since=since, limit=limit),
        )
        return BcsSnapshot(balances=balances, positions=positions, activities=activities)

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        await self._ensure_access_token()
        limiter = self._rate_limits.get(path)
        if limiter is not None:
            await limiter.acquire()
        resp = await self._client.request(method, path, params=params, json=json)
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, dict) else {"data": data}

    async def _ensure_access_token(self) -> None:
        if not self._token_needs_refresh():
            return

        if not self._refresh_token:
            raise RuntimeError("BCS refresh_token is required to obtain access_token")

        async with self._token_lock:
            if not self._token_needs_refresh():
                return
            await self._refresh_access_token()

    def _token_needs_refresh(self) -> bool:
        if not self._access_token:
            return True
        if not self._refresh_token:
            return False
        if self._access_expires_at is None:
            return True
        return _utcnow() + timedelta(seconds=self._token_margin) >= self._access_expires_at

    async def _refresh_access_token(self) -> None:
        payload = {
            "client_id": self._client_id,
            "refresh_token": self._refresh_token,
            "grant_type": "refresh_token",
        }
        resp = await self._auth_client.post(
            self.TOKEN_PATH,
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, dict):
            raise RuntimeError("BCS token response is not a JSON object")

        access_token = _to_str(data.get("access_token"))
        if not access_token:
            raise RuntimeError("BCS token response missing access_token")

        refresh_token = _to_str(data.get("refresh_token")) or self._refresh_token
        access_expires_at = _add_seconds(_utcnow(), data.get("expires_in"))
        refresh_expires_at = _add_seconds(_utcnow(), data.get("refresh_expires_in"))

        self._access_token = access_token
        self._refresh_token = refresh_token
        self._access_expires_at = access_expires_at
        self._refresh_expires_at = refresh_expires_at
        self._client.headers["Authorization"] = f"Bearer {access_token}"

        if self._token_updater:
            self._token_updater(
                access_token,
                refresh_token,
                access_expires_at,
                refresh_expires_at,
            )


def _parse_balances_from_limits(payload: Dict[str, Any]) -> List[BcsBalance]:
    root = payload.get("data") if isinstance(payload.get("data"), dict) else payload

    candidates = []
    for key in (
        "moneyLimits",
        "currencies",
        "currencyLimits",
        "money",
        "cash",
        "limitsByCurrency",
        "items",
        "list",
    ):
        val = root.get(key)
        if isinstance(val, list):
            candidates = val
            break

    balances: List[BcsBalance] = []
    for row in candidates:
        if not isinstance(row, dict):
            continue
        asset = _to_str(row.get("currencyCode") or row.get("currency") or row.get("asset"))
        if not asset:
            continue
        qty = row.get("quantity")
        qty_value = _to_float(qty.get("value")) if isinstance(qty, dict) else None
        free = _to_float(
            row.get("free") or row.get("available") or row.get("availableAmount") or qty_value
        )
        locked = _to_float(row.get("locked") or row.get("blocked") or row.get("reserved"))
        total = _to_float(row.get("total") or row.get("balance") or row.get("amount") or qty_value)
        if total is None and free is not None and locked is not None:
            total = free + locked
        balances.append(BcsBalance(asset=asset.upper(), free=free, locked=locked, total=total, raw=row))

    return balances


def _parse_positions_from_limits(payload: Dict[str, Any]) -> List[BcsPosition]:
    root = payload.get("data") if isinstance(payload.get("data"), dict) else payload

    positions: List[BcsPosition] = []
    depo_limits = root.get("depoLimit")
    future_limits = root.get("futureHolding")

    if isinstance(depo_limits, list):
        for row in depo_limits:
            if not isinstance(row, dict):
                continue
            symbol = _to_str(
                row.get("ticker") or row.get("symbol") or row.get("isin") or row.get("figi")
            )
            qty = None
            quantity = row.get("quantity")
            if isinstance(quantity, dict):
                qty = _to_float(quantity.get("value"))
            qty = qty if qty is not None else _to_float(row.get("quantity") or row.get("lots"))
            if not symbol and qty is None:
                continue

            positions.append(
                BcsPosition(
                    symbol=symbol or "",
                    qty=qty,
                    avg_price=_to_float(row.get("averagePrice") or row.get("avgPrice")),
                    current_price=_to_float(row.get("price") or row.get("currentPrice")),
                    unrealized_pnl=_to_float(row.get("pnl") or row.get("unrealizedPnl")),
                    currency=_to_str(row.get("currency") or row.get("currencyCode")),
                    raw=row,
                )
            )

    if isinstance(future_limits, list):
        for row in future_limits:
            if not isinstance(row, dict):
                continue
            symbol = _to_str(
                row.get("ticker") or row.get("symbol") or row.get("isin") or row.get("figi")
            )
            qty = _to_float(row.get("totalNet") or row.get("positionValue"))
            if not symbol and qty is None:
                continue

            positions.append(
                BcsPosition(
                    symbol=symbol or "",
                    qty=qty,
                    avg_price=_to_float(row.get("averagePrice") or row.get("avgPrice")),
                    current_price=_to_float(row.get("price") or row.get("currentPrice")),
                    unrealized_pnl=_to_float(row.get("varMargin") or row.get("realVarMargin")),
                    currency=_to_str(row.get("currency") or row.get("currencyCode")),
                    raw=row,
                )
            )

    if positions:
        return positions

    candidates = []
    for key in ("positions", "securities", "instruments", "instrumentLimits", "items", "list"):
        val = root.get(key)
        if isinstance(val, list):
            candidates = val
            break

    for row in candidates:
        if not isinstance(row, dict):
            continue
        symbol = _to_str(row.get("ticker") or row.get("symbol") or row.get("isin") or row.get("figi"))
        qty = _to_float(row.get("qty") or row.get("quantity") or row.get("balance") or row.get("lots"))
        if not symbol and qty is None:
            continue

        positions.append(
            BcsPosition(
                symbol=symbol or "",
                qty=qty,
                avg_price=_to_float(row.get("avgPrice") or row.get("averagePrice") or row.get("entryPrice")),
                current_price=_to_float(row.get("price") or row.get("currentPrice") or row.get("marketPrice")),
                unrealized_pnl=_to_float(row.get("pnl") or row.get("unrealizedPnl")),
                currency=_to_str(row.get("currency") or row.get("currencyCode")),
                raw=row,
            )
        )

    return positions


def _parse_balances_from_portfolio(items: List[Dict[str, Any]]) -> List[BcsBalance]:
    balances: List[BcsBalance] = []
    for row in items:
        if not isinstance(row, dict):
            continue
        upper_type = _to_str(row.get("upperType"))
        item_type = _to_str(row.get("type"))
        if upper_type != "CURRENCY" and item_type != "moneyLimit":
            continue
        asset = _to_str(row.get("currency") or row.get("ticker") or row.get("baseAssetTicker"))
        if not asset:
            continue
        free = _to_float(row.get("quantity"))
        locked = _to_float(row.get("locked") or row.get("lockedForFutures"))
        total = _to_float(row.get("balanceValue") or row.get("quantity"))
        if total is None and free is not None and locked is not None:
            total = free + locked
        balances.append(
            BcsBalance(
                asset=asset.upper(),
                free=free,
                locked=locked,
                total=total,
                raw=row,
            )
        )
    return balances


def _parse_positions_from_portfolio(items: List[Dict[str, Any]]) -> List[BcsPosition]:
    positions: List[BcsPosition] = []
    for row in items:
        if not isinstance(row, dict):
            continue
        upper_type = _to_str(row.get("upperType"))
        item_type = _to_str(row.get("type"))
        if upper_type == "CURRENCY" or item_type == "moneyLimit":
            continue
        symbol = _to_str(row.get("ticker") or row.get("baseAssetTicker") or row.get("displayName"))
        qty = _to_float(row.get("quantity"))
        if not symbol and qty is None:
            continue
        positions.append(
            BcsPosition(
                symbol=symbol or "",
                qty=qty,
                avg_price=_to_float(row.get("balancePrice")),
                current_price=_to_float(row.get("currentPrice")),
                unrealized_pnl=_to_float(row.get("unrealizedPL")),
                currency=_to_str(row.get("currency")),
                raw=row,
            )
        )
    return positions


def _coerce_list(x: Any) -> List[Any]:
    if isinstance(x, list):
        return x
    if isinstance(x, dict):
        # sometimes payload is {"items":[...]}
        for key in ("items", "list", "rows", "data"):
            if isinstance(x.get(key), list):
                return x[key]
    return []


class _RateLimiter:
    def __init__(self, max_requests: int, interval_s: float) -> None:
        self._max_requests = max(1, int(max_requests))
        self._interval_s = max(0.001, float(interval_s))
        self._timestamps: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        while True:
            sleep_for = None
            async with self._lock:
                now = time.monotonic()
                cutoff = now - self._interval_s
                while self._timestamps and self._timestamps[0] <= cutoff:
                    self._timestamps.popleft()
                if len(self._timestamps) < self._max_requests:
                    self._timestamps.append(now)
                    return
                sleep_for = (self._timestamps[0] + self._interval_s) - now
            if sleep_for and sleep_for > 0:
                await asyncio.sleep(sleep_for)


def _to_iso_utc(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def _to_dt(v: Any) -> Optional[datetime]:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.astimezone(timezone.utc) if v.tzinfo else v.replace(tzinfo=timezone.utc)
    # try unix seconds/ms
    num = _to_float(v)
    if num is not None:
        # heuristic: ms if too large
        if num > 10_000_000_000:
            num /= 1000.0
        return datetime.fromtimestamp(num, tz=timezone.utc)
    # try ISO string
    try:
        s = str(v).strip()
        if not s:
            return None
        # minimal ISO parsing
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s).astimezone(timezone.utc)
    except Exception:
        return None


def _to_float(v: Any) -> Optional[float]:
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        return None


def _to_str(v: Any) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _ensure_aware(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def _add_seconds(now: datetime, value: Any) -> Optional[datetime]:
    seconds = _to_float(value)
    if seconds is None:
        return None
    return now + timedelta(seconds=seconds)
