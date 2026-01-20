from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional


@dataclass(frozen=True)
class TBalance:
    asset: str
    free: Optional[float]
    locked: Optional[float]
    total: Optional[float]


@dataclass(frozen=True)
class TPosition:
    symbol: str
    qty: Optional[float]
    avg_price: Optional[float]
    current_price: Optional[float]
    unrealized_pnl: Optional[float]
    currency: Optional[str]


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
class TSnapshot:
    balances: List[TBalance]
    positions: List[TPosition]
    activities: List[ActivityLine]


@dataclass(frozen=True)
class TPingResult:
    """Result of a credentials/token check."""

    ok: bool
    account_ids: List[str]
    message: Optional[str] = None
    error_type: Optional[str] = None
    error_code: Optional[str] = None
    raw_error: Optional[str] = None


class TAdapter:
    """
    T-Bank Invest API adapter powered by the official tinkoff-investments client.

    Required dependency: tinkoff-investments
    """

    DEFAULT_ACTIVITY_DAYS = 30

    def __init__(
        self,
        token: str,
        *,
        account_id: Optional[str] = None,
        app_name: Optional[str] = None,
        extra_params: Optional[Dict[str, Any]] = None,
        token_provider: Optional[Callable[[], str]] = None,
        rate_limits: Optional[Dict[str, int]] = None,
    ) -> None:
        self._token = token.strip()
        self._token_provider = token_provider
        self._account_id = account_id.strip() if account_id else None
        self._client_params = dict(extra_params or {})
        if app_name:
            self._client_params.setdefault("app_name", app_name)
        self._client_cls = _load_client_class()
        self._last_cursor: Optional[str] = None
        self._rate_limiters = _build_rate_limiters(rate_limits)

    async def ping(self) -> TPingResult:
        """Validate that the provided token works.

        Implementation strategy: try to authorize and read the user's accounts.
        If the token is invalid / revoked / has insufficient scope, the SDK will raise.
        """

        if not (self._token_provider or self._token):
            return TPingResult(
                ok=False,
                account_ids=[],
                message="Empty token",
                error_type="ValueError",
                error_code="EMPTY_TOKEN",
                raw_error=None,
            )

        try:
            resp = await self._call(lambda client: _get_accounts(client), rate_key="users")
            accounts = getattr(resp, "accounts", None) or []
            ids: List[str] = []
            for acc in accounts:
                acc_id = _to_str(getattr(acc, "id", None) or getattr(acc, "account_id", None))
                if acc_id:
                    ids.append(acc_id)
            # Even if the user has zero accounts, a successful response means the token is valid.
            return TPingResult(ok=True, account_ids=ids, message="OK")
        except Exception as exc:
            msg, etype, ecode = _classify_ping_error(exc)
            return TPingResult(
                ok=False,
                account_ids=[],
                message=msg,
                error_type=etype,
                error_code=ecode,
                raw_error=_safe_repr(exc),
            )

    async def validate_token(self) -> bool:
        """Boolean-only shortcut for ping()."""

        return (await self.ping()).ok

    async def fetch_accounts(self) -> List[str]:
        resp = await self._call(lambda client: _get_accounts(client), rate_key="users")
        accounts = getattr(resp, "accounts", None) or []
        ids: List[str] = []
        for acc in accounts:
            acc_id = _to_str(getattr(acc, "id", None) or getattr(acc, "account_id", None))
            if acc_id:
                ids.append(acc_id)
        return ids

    async def fetch_balances(self, *, account_id: Optional[str] = None) -> List[TBalance]:
        account_id = await self._resolve_account_id(account_id)
        positions_resp, withdraw_resp = await asyncio.gather(
            self._call(lambda client: _get_positions(client, account_id), rate_key="operations"),
            self._call(
                lambda client: _get_withdraw_limits(client, account_id),
                rate_key="operations",
            ),
        )
        return _parse_balances(positions_resp, withdraw_resp)

    async def fetch_positions(self, *, account_id: Optional[str] = None) -> List[TPosition]:
        account_id = await self._resolve_account_id(account_id)
        positions_resp, portfolio_resp = await asyncio.gather(
            self._call(lambda client: _get_positions(client, account_id), rate_key="operations"),
            self._call(lambda client: _get_portfolio(client, account_id), rate_key="operations"),
        )
        positions = _parse_positions_from_positions(positions_resp)
        portfolio_positions = _parse_positions_from_portfolio(portfolio_resp)
        if not positions:
            return portfolio_positions
        return _merge_positions(positions, portfolio_positions)

    async def fetch_activities(
        self,
        *,
        account_id: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 200,
        state: Optional[Any] = None,
        cursor: Optional[str] = None,
    ) -> List[ActivityLine]:
        account_id = await self._resolve_account_id(account_id)
        now = _utcnow()
        if since is None:
            since = now - timedelta(days=self.DEFAULT_ACTIVITY_DAYS)
        if until is None:
            until = now
        since = _ensure_aware(since)
        until = _ensure_aware(until)

        if state is None:
            state = _default_operation_state()

        resp = await self._call(
            lambda client: _get_operations_by_cursor(
                client,
                account_id=account_id,
                since=since,
                until=until,
                state=state,
                limit=limit,
                cursor=cursor,
            ),
            rate_key="operations",
        )
        operations = _extract_operations(resp)
        self._last_cursor = _extract_next_cursor(resp)
        activities = [_parse_operation(op) for op in operations]
        activities = [item for item in activities if item is not None]
        activities.sort(key=lambda a: a.timestamp or datetime.min.replace(tzinfo=timezone.utc))
        if limit and limit > 0:
            return activities[: int(limit)]
        return activities

    async def fetch_snapshot(
        self,
        *,
        account_id: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 200,
        state: Optional[Any] = None,
    ) -> TSnapshot:
        account_id = await self._resolve_account_id(account_id)
        balances, positions, activities = await asyncio.gather(
            self.fetch_balances(account_id=account_id),
            self.fetch_positions(account_id=account_id),
            self.fetch_activities(
                account_id=account_id,
                since=since,
                until=until,
                limit=limit,
                state=state,
            ),
        )
        return TSnapshot(balances=balances, positions=positions, activities=activities)

    async def _resolve_account_id(self, account_id: Optional[str]) -> str:
        if account_id:
            return account_id
        if self._account_id:
            return self._account_id
        accounts = await self.fetch_accounts()
        if not accounts:
            raise RuntimeError("T-Bank account_id is required but no accounts were found")
        self._account_id = accounts[0]
        return self._account_id

    async def _call(self, handler: Callable[[Any], Any], *, rate_key: Optional[str] = None) -> Any:
        if rate_key:
            limiter = self._rate_limiters.get(rate_key)
            if limiter:
                await limiter.acquire()
        return await asyncio.to_thread(self._call_sync, handler)

    def _call_sync(self, handler: Callable[[Any], Any]) -> Any:
        token = self._token_provider() if self._token_provider else self._token
        token = token.strip()
        with self._client_cls(token, **self._client_params) as client:
            return handler(client)

    @property
    def last_cursor(self) -> Optional[str]:
        return self._last_cursor


def _load_client_class():
    try:
        from tinkoff.invest import Client  # type: ignore
    except Exception as exc:
        try:
            from t_tech.invest import Client  # type: ignore
        except Exception:
            raise RuntimeError(
                "Python SDK для T-Invest не установлен. Установи: uv add tinkoff-investments "
                "или uv pip install t-tech-investments"
            ) from exc
    return Client


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
    defaults = {
        "instruments": 200,
        "users": 100,
        "operations": 200,
        "marketdata": 600,
        "stop_orders": 50,
        "orders": 100,
        "signals": 100,
        "copy_trading": 100,
        "sandbox": 200,
        "reports": 5,
    }
    limits = dict(defaults)
    if rate_limits:
        limits.update({k: v for k, v in rate_limits.items() if v})
    return {key: _RateLimiter(limit) for key, limit in limits.items()}


def _get_accounts(client: Any) -> Any:
    users = getattr(client, "users", None)
    if users and hasattr(users, "get_accounts"):
        return users.get_accounts()
    if hasattr(client, "get_accounts"):
        return client.get_accounts()
    raise RuntimeError("tinkoff-investments client does not expose users.get_accounts")


def _get_portfolio(client: Any, account_id: str) -> Any:
    operations = getattr(client, "operations", None)
    portfolio = getattr(client, "portfolio", None)
    if operations and hasattr(operations, "get_portfolio"):
        return operations.get_portfolio(account_id=account_id)
    if portfolio and hasattr(portfolio, "get_portfolio"):
        return portfolio.get_portfolio(account_id=account_id)
    raise RuntimeError("tinkoff-investments client does not expose get_portfolio")


def _get_positions(client: Any, account_id: str) -> Any:
    operations = getattr(client, "operations", None)
    if operations and hasattr(operations, "get_positions"):
        return operations.get_positions(account_id=account_id)
    if hasattr(client, "get_positions"):
        return client.get_positions(account_id=account_id)
    raise RuntimeError("tinkoff-investments client does not expose get_positions")


def _get_withdraw_limits(client: Any, account_id: str) -> Any:
    operations = getattr(client, "operations", None)
    if operations and hasattr(operations, "get_withdraw_limits"):
        return operations.get_withdraw_limits(account_id=account_id)
    if hasattr(client, "get_withdraw_limits"):
        return client.get_withdraw_limits(account_id=account_id)
    raise RuntimeError("tinkoff-investments client does not expose get_withdraw_limits")


def _get_operations(
    client: Any,
    *,
    account_id: str,
    since: datetime,
    until: datetime,
    state: Optional[Any],
) -> Any:
    operations = getattr(client, "operations", None)
    if operations and hasattr(operations, "get_operations"):
        if state is None:
            return operations.get_operations(account_id=account_id, from_=since, to=until)
        return operations.get_operations(account_id=account_id, from_=since, to=until, state=state)
    if hasattr(client, "get_operations"):
        if state is None:
            return client.get_operations(account_id=account_id, from_=since, to=until)
        return client.get_operations(account_id=account_id, from_=since, to=until, state=state)
    raise RuntimeError("tinkoff-investments client does not expose get_operations")


def _get_operations_by_cursor(
    client: Any,
    *,
    account_id: str,
    since: Optional[datetime],
    until: Optional[datetime],
    state: Optional[Any],
    limit: Optional[int],
    cursor: Optional[str],
) -> Any:
    import inspect

    operations = getattr(client, "operations", None)
    handler = None
    if operations and hasattr(operations, "get_operations_by_cursor"):
        handler = operations.get_operations_by_cursor
    elif hasattr(client, "get_operations_by_cursor"):
        handler = client.get_operations_by_cursor
    if handler is None:
        return _get_operations(
            client,
            account_id=account_id,
            since=since or _utcnow() - timedelta(days=TAdapter.DEFAULT_ACTIVITY_DAYS),
            until=until or _utcnow(),
            state=state,
        )
    kwargs: Dict[str, Any] = {"account_id": account_id}
    if since is not None:
        kwargs["from_"] = since
    if until is not None:
        kwargs["to"] = until
    if state is not None:
        kwargs["state"] = state
    if limit is not None and limit > 0:
        kwargs["limit"] = int(limit)
    if cursor:
        kwargs["cursor"] = cursor
    if _supports_request_param(handler):
        request = _build_operations_by_cursor_request(**kwargs)
        if request is None:
            return handler(**kwargs)
        return handler(request)
    try:
        return handler(**kwargs)
    except TypeError:
        request = _build_operations_by_cursor_request(**kwargs)
        if request is None:
            raise
        return handler(request)


def _extract_operations(resp: Any) -> List[Any]:
    items = getattr(resp, "operations", None)
    if isinstance(items, list):
        return items
    items = getattr(resp, "items", None)
    if isinstance(items, list):
        return items
    if isinstance(resp, dict):
        val = resp.get("operations") or resp.get("items") or resp.get("list")
        if isinstance(val, list):
            return val
    return []


def _extract_next_cursor(resp: Any) -> Optional[str]:
    for key in ("next_cursor", "cursor", "next"):
        value = _to_str(getattr(resp, key, None))
        if value:
            return value
        if isinstance(resp, dict):
            value = _to_str(resp.get(key))
            if value:
                return value
    return None


def _supports_request_param(handler: Callable[..., Any]) -> bool:
    import inspect

    try:
        sig = inspect.signature(handler)
    except (TypeError, ValueError):
        return False
    params = list(sig.parameters.values())
    if not params:
        return False
    if params[0].name == "request":
        return True
    return "request" in sig.parameters and len(params) == 1


def _build_operations_by_cursor_request(**kwargs: Any) -> Optional[Any]:
    request_cls = _load_operations_by_cursor_request_class()
    if request_cls is None:
        return None
    request = request_cls()
    request.account_id = kwargs.get("account_id") or ""
    if kwargs.get("from_") is not None:
        request.from_ = kwargs["from_"]
    if kwargs.get("to") is not None:
        request.to = kwargs["to"]
    if kwargs.get("cursor"):
        request.cursor = kwargs["cursor"]
    if kwargs.get("limit") is not None:
        request.limit = int(kwargs["limit"])
    if kwargs.get("state") is not None:
        request.state = kwargs["state"]
    return request


def _load_operations_by_cursor_request_class() -> Optional[Any]:
    try:
        from tinkoff.invest.schemas import GetOperationsByCursorRequest  # type: ignore
    except Exception:
        try:
            from t_tech.invest.schemas import GetOperationsByCursorRequest  # type: ignore
        except Exception:
            return None
    return GetOperationsByCursorRequest


def _parse_balances(positions_resp: Any, withdraw_resp: Any) -> List[TBalance]:
    positions = _balances_from_positions(positions_resp)
    withdraw = _balances_from_withdraw_limits(withdraw_resp)
    merged: Dict[str, Dict[str, Optional[float]]] = {}

    for currency, values in positions.items():
        merged[currency] = dict(values)

    for currency, values in withdraw.items():
        entry = merged.setdefault(currency, {"free": None, "locked": None, "total": None})
        if values.get("free") is not None:
            entry["free"] = values.get("free")
        if values.get("locked") is not None:
            entry["locked"] = values.get("locked")
        if entry.get("total") is None:
            entry["total"] = values.get("total")

    out: List[TBalance] = []
    for currency, values in merged.items():
        free = values.get("free")
        locked = values.get("locked")
        total = values.get("total")
        if total is None:
            total = _sum_optional(free, locked)
        if free is None and locked is None and total is None:
            continue
        out.append(TBalance(asset=currency.upper(), free=free, locked=locked, total=total))
    return out


def _balances_from_positions(resp: Any) -> Dict[str, Dict[str, Optional[float]]]:
    money = _coerce_list(getattr(resp, "money", None))
    blocked = _coerce_list(getattr(resp, "blocked", None))
    balances: Dict[str, Dict[str, Optional[float]]] = {}

    for item in money:
        currency = _to_str(getattr(item, "currency", None))
        amount = _money_to_float(item)
        if not currency:
            continue
        entry = balances.setdefault(currency, {"free": None, "locked": None, "total": None})
        entry["free"] = _sum_optional(entry.get("free"), amount)

    for item in blocked:
        currency = _to_str(getattr(item, "currency", None))
        amount = _money_to_float(item)
        if not currency:
            continue
        entry = balances.setdefault(currency, {"free": None, "locked": None, "total": None})
        entry["locked"] = _sum_optional(entry.get("locked"), amount)

    for currency, values in balances.items():
        values["total"] = _sum_optional(values.get("free"), values.get("locked"))

    return balances


def _balances_from_withdraw_limits(resp: Any) -> Dict[str, Dict[str, Optional[float]]]:
    money = _coerce_list(getattr(resp, "money", None))
    blocked = _coerce_list(getattr(resp, "blocked", None))
    balances: Dict[str, Dict[str, Optional[float]]] = {}

    for item in money:
        currency = _to_str(getattr(item, "currency", None))
        amount = _money_to_float(item)
        if not currency:
            continue
        entry = balances.setdefault(currency, {"free": None, "locked": None, "total": None})
        entry["free"] = _sum_optional(entry.get("free"), amount)

    for item in blocked:
        currency = _to_str(getattr(item, "currency", None))
        amount = _money_to_float(item)
        if not currency:
            continue
        entry = balances.setdefault(currency, {"free": None, "locked": None, "total": None})
        entry["locked"] = _sum_optional(entry.get("locked"), amount)

    for currency, values in balances.items():
        values["total"] = _sum_optional(values.get("free"), values.get("locked"))

    return balances


def _parse_positions_from_portfolio(resp: Any) -> List[TPosition]:
    positions = _coerce_list(getattr(resp, "positions", None))
    out: List[TPosition] = []
    for p in positions:
        symbol = _first_str(
            getattr(p, "ticker", None),
            getattr(p, "figi", None),
            getattr(p, "instrument_uid", None),
            getattr(p, "uid", None),
        )
        qty = _quotation_to_float(getattr(p, "quantity", None))
        avg_price = _money_to_float(getattr(p, "average_position_price", None))
        current_price = _money_to_float(getattr(p, "current_price", None))
        pnl = _money_to_float(getattr(p, "expected_yield", None))
        currency = _to_str(getattr(p, "currency", None))
        if not symbol and qty is None:
            continue
        out.append(
            TPosition(
                symbol=symbol or "",
                qty=qty,
                avg_price=avg_price,
                current_price=current_price,
                unrealized_pnl=pnl,
                currency=currency,
            )
        )
    return out


def _parse_positions_from_positions(resp: Any) -> List[TPosition]:
    positions: List[TPosition] = []
    for field_name in ("securities", "futures", "options"):
        items = _coerce_list(getattr(resp, field_name, None))
        for row in items:
            symbol = _first_str(
                getattr(row, "ticker", None),
                getattr(row, "figi", None),
                getattr(row, "instrument_uid", None),
                getattr(row, "uid", None),
            )
            qty = _quotation_to_float(getattr(row, "balance", None))
            currency = _to_str(getattr(row, "currency", None))
            if not symbol and qty is None:
                continue
            positions.append(
                TPosition(
                    symbol=symbol or "",
                    qty=qty,
                    avg_price=_money_to_float(getattr(row, "average_position_price", None)),
                    current_price=_money_to_float(getattr(row, "current_price", None)),
                    unrealized_pnl=_money_to_float(getattr(row, "expected_yield", None)),
                    currency=currency,
                )
            )
    return positions


def _merge_positions(base: List[TPosition], overlay: List[TPosition]) -> List[TPosition]:
    overlay_map: Dict[str, TPosition] = {}
    for item in overlay:
        if item.symbol:
            overlay_map[item.symbol] = item

    merged: List[TPosition] = []
    for item in base:
        extra = overlay_map.get(item.symbol)
        if extra is None:
            merged.append(item)
            continue
        merged.append(
            TPosition(
                symbol=item.symbol,
                qty=item.qty if item.qty is not None else extra.qty,
                avg_price=extra.avg_price if extra.avg_price is not None else item.avg_price,
                current_price=(
                    extra.current_price if extra.current_price is not None else item.current_price
                ),
                unrealized_pnl=(
                    extra.unrealized_pnl if extra.unrealized_pnl is not None else item.unrealized_pnl
                ),
                currency=extra.currency or item.currency,
            )
        )
    return merged


def _parse_operation(op: Any) -> Optional[ActivityLine]:
    if op is None:
        return None
    operation_type = _operation_type_name(
        getattr(op, "operation_type", None) or getattr(op, "type", None)
    )
    symbol = _first_str(
        getattr(op, "ticker", None),
        getattr(op, "figi", None),
        getattr(op, "instrument_uid", None),
        getattr(op, "uid", None),
    )
    quantity = _quotation_to_float(getattr(op, "quantity", None))
    price = _money_to_float(getattr(op, "price", None))
    payment = _money_to_float(getattr(op, "payment", None))
    if price is None and quantity:
        price = _safe_div(abs(payment) if payment is not None else None, quantity)
    commission = _money_to_float(getattr(op, "commission", None))
    commission_currency = _to_str(getattr(getattr(op, "commission", None), "currency", None))
    timestamp = _ensure_aware(getattr(op, "date", None))
    side = _infer_side(operation_type)
    quote_asset = _to_str(getattr(getattr(op, "price", None), "currency", None))
    if quote_asset is None:
        quote_asset = _to_str(getattr(getattr(op, "payment", None), "currency", None))

    if not operation_type:
        operation_type = "operation"

    return ActivityLine(
        activity_type=operation_type,
        symbol=symbol,
        base_asset=None,
        quote_asset=quote_asset,
        side=side,
        amount=quantity,
        price=price,
        fee=commission,
        fee_currency=commission_currency,
        timestamp=timestamp,
        raw=_operation_raw(op),
    )


def _operation_raw(op: Any) -> Dict[str, Any]:
    return {
        "id": _to_str(getattr(op, "id", None)),
        "operation_type": _operation_type_name(
            getattr(op, "operation_type", None) or getattr(op, "type", None)
        ),
        "figi": _to_str(getattr(op, "figi", None)),
        "ticker": _to_str(getattr(op, "ticker", None)),
        "instrument_uid": _to_str(getattr(op, "instrument_uid", None)),
        "instrument_type": _to_str(getattr(op, "instrument_type", None)),
        "quantity": _quotation_to_float(getattr(op, "quantity", None)),
        "price": _money_to_float(getattr(op, "price", None)),
        "payment": _money_to_float(getattr(op, "payment", None)),
        "commission": _money_to_float(getattr(op, "commission", None)),
        "date": _to_iso_utc(getattr(op, "date", None)),
    }


def _default_operation_state() -> Optional[Any]:
    for module in (
        "tinkoff.invest.schemas",
        "tinkoff.invest",
        "t_tech.invest.schemas",
        "t_tech.invest",
    ):
        try:
            OperationState = __import__(module, fromlist=["OperationState"]).OperationState
            return OperationState.OPERATION_STATE_EXECUTED
        except Exception:
            continue
    return None


def _operation_type_name(value: Any) -> Optional[str]:
    if value is None:
        return None
    name = getattr(value, "name", None)
    if not name:
        name = str(value)
    name = name.replace("OPERATION_TYPE_", "").strip().lower()
    return name or None


def _infer_side(activity_type: Optional[str]) -> Optional[str]:
    if not activity_type:
        return None
    upper = activity_type.upper()
    if "BUY" in upper:
        return "BUY"
    if "SELL" in upper:
        return "SELL"
    return None


def _coerce_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    if isinstance(value, (str, bytes, dict)):
        return []
    return list(value) if isinstance(value, Iterable) else []


def _money_to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    units = getattr(value, "units", None)
    nano = getattr(value, "nano", None)
    if units is None:
        return _to_float(value)
    return float(units) + float(nano or 0) / 1e9


def _quotation_to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    units = getattr(value, "units", None)
    nano = getattr(value, "nano", None)
    if units is None:
        return _to_float(value)
    return float(units) + float(nano or 0) / 1e9


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
    for value in values:
        s = _to_str(value)
        if s:
            return s
    return None


def _sum_optional(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None and b is None:
        return None
    return (a or 0.0) + (b or 0.0)


def _safe_div(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b in (None, 0):
        return None
    return a / b


def _ensure_aware(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def _to_iso_utc(dt: Optional[datetime]) -> Optional[str]:
    dt = _ensure_aware(dt)
    if dt is None:
        return None
    return dt.isoformat().replace("+00:00", "Z")


def _safe_repr(exc: BaseException) -> str:
    try:
        return repr(exc)
    except Exception:
        try:
            return str(exc)
        except Exception:
            return "<unreprable error>"


def _classify_ping_error(exc: BaseException) -> tuple[str, str, str]:
    """Normalize SDK/network errors into stable codes for the frontend."""

    etype = type(exc).__name__
    # Defaults
    msg = str(exc) or "Token validation failed"
    ecode = "UNKNOWN"

    # gRPC errors (tinkoff-investments uses gRPC under the hood)
    try:
        import grpc  # type: ignore

        if isinstance(exc, grpc.RpcError):
            try:
                status = exc.code()
                if status is not None:
                    ecode = getattr(status, "name", None) or str(status)
            except Exception:
                pass
            try:
                details = exc.details()
                if details:
                    msg = details
            except Exception:
                pass
            # Friendly mapping for the most common auth failures
            upper = (ecode or "").upper()
            if "UNAUTHENTICATED" in upper:
                return "Unauthenticated (invalid/expired token)", etype, "UNAUTHENTICATED"
            if "PERMISSION_DENIED" in upper:
                return "Permission denied (insufficient token scope)", etype, "PERMISSION_DENIED"
            if "RESOURCE_EXHAUSTED" in upper:
                return "Rate limit exceeded", etype, "RATE_LIMIT"
            if "DEADLINE_EXCEEDED" in upper:
                return "Request timeout", etype, "TIMEOUT"
            if "UNAVAILABLE" in upper:
                return "Service unavailable", etype, "UNAVAILABLE"
            return msg, etype, ecode or "GRPC_ERROR"
    except Exception:
        pass

    # Some SDK variants wrap errors into RequestError (best-effort introspection)
    for attr in ("code", "status", "status_code"):
        val = getattr(exc, attr, None)
        if val is not None:
            try:
                sval = str(getattr(val, "name", None) or val)
                if sval:
                    ecode = sval
            except Exception:
                pass
            break

    # Heuristics
    low = (msg or "").lower()
    if "unauth" in low or "invalid token" in low or "permission" in low or "denied" in low:
        ecode = "AUTH_FAILED"

    return msg, etype, ecode
