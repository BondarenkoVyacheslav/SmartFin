from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class BybitBalance:
    asset: str
    free: Optional[float]
    locked: Optional[float]
    total: Optional[float]


@dataclass(frozen=True)
class BybitPosition:
    symbol: str
    side: Optional[str]
    size: Optional[float]
    entry_price: Optional[float]
    mark_price: Optional[float]
    unrealized_pnl: Optional[float]
    leverage: Optional[float]


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
class BybitSnapshot:
    balances: List[BybitBalance]
    positions: List[BybitPosition]
    activities: List[ActivityLine]


class BybitAdapter:
    """
    Bybit adapter powered by the official pybit client.

    Required dependency: pybit
    """

    DEFAULT_QUOTE_ASSETS = ("USDT", "USDC", "USD", "BTC", "ETH", "EUR", "RUB")

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        *,
        testnet: bool = False,
        recv_window: int = 5000,
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._client = self._make_client(
            api_key=api_key,
            api_secret=api_secret,
            testnet=testnet,
            recv_window=recv_window,
            extra_params=extra_params or {},
        )

    @staticmethod
    def _make_client(
        *,
        api_key: str,
        api_secret: str,
        testnet: bool,
        recv_window: int,
        extra_params: Dict[str, Any],
    ):
        try:
            from pybit.unified_trading import HTTP  # type: ignore
        except Exception as exc:
            raise RuntimeError("pybit не установлен. Установи: uv add pybit") from exc

        return HTTP(
            api_key=api_key,
            api_secret=api_secret,
            testnet=testnet,
            recv_window=recv_window,
            **extra_params,
        )

    async def fetch_balances(self, *, account_type: str = "UNIFIED") -> List[BybitBalance]:
        resp = await self._call(self._client.get_wallet_balance, accountType=account_type)
        result = (resp or {}).get("result") or {}
        items = result.get("list") or []
        balances: List[BybitBalance] = []

        if isinstance(items, list) and items:
            coins = items[0].get("coin") or []
            for c in coins:
                if not isinstance(c, dict):
                    continue
                balances.append(
                    BybitBalance(
                        asset=str(c.get("coin") or "").upper(),
                        free=_to_float(c.get("availableToWithdraw")),
                        locked=_to_float(c.get("locked")),
                        total=_to_float(c.get("walletBalance")),
                    )
                )

        return balances

    async def fetch_positions(
        self,
        *,
        categories: Sequence[str] = ("linear", "inverse"),
    ) -> List[BybitPosition]:
        positions: List[BybitPosition] = []
        for category in categories:
            resp = await self._call(self._client.get_positions, category=category)
            for p in _result_list(resp):
                if not isinstance(p, dict):
                    continue
                positions.append(
                    BybitPosition(
                        symbol=str(p.get("symbol") or ""),
                        side=_to_str(p.get("side")),
                        size=_to_float(p.get("size")),
                        entry_price=_to_float(p.get("entryPrice")),
                        mark_price=_to_float(p.get("markPrice")),
                        unrealized_pnl=_to_float(p.get("unrealisedPnl")),
                        leverage=_to_float(p.get("leverage")),
                    )
                )

        return positions

    async def fetch_activities(
        self,
        *,
        since: Optional[datetime] = None,
        limit: int = 200,
        quote_assets: Optional[Sequence[str]] = None,
    ) -> List[ActivityLine]:
        quote_assets = _normalize_quote_assets(quote_assets, self.DEFAULT_QUOTE_ASSETS)
        since_ms = _to_timestamp_ms(since)

        activities: List[ActivityLine] = []
        activities.extend(
            await self._fetch_spot_trades(limit=limit, since_ms=since_ms, quote_assets=quote_assets)
        )
        activities.extend(
            await self._fetch_derivatives_trades(
                limit=limit,
                since_ms=since_ms,
                quote_assets=quote_assets,
            )
        )
        activities.extend(await self._fetch_deposits(limit=limit, since_ms=since_ms))
        activities.extend(await self._fetch_withdrawals(limit=limit, since_ms=since_ms))
        activities.extend(await self._fetch_conversions(limit=limit, since_ms=since_ms))

        activities.sort(key=lambda a: a.timestamp or datetime.min.replace(tzinfo=timezone.utc))
        return activities

    async def fetch_snapshot(
        self,
        *,
        account_type: str = "UNIFIED",
        categories: Sequence[str] = ("linear", "inverse"),
        since: Optional[datetime] = None,
        limit: int = 200,
        quote_assets: Optional[Sequence[str]] = None,
    ) -> BybitSnapshot:
        balances = await self.fetch_balances(account_type=account_type)
        positions = await self.fetch_positions(categories=categories)
        activities = await self.fetch_activities(
            since=since,
            limit=limit,
            quote_assets=quote_assets,
        )
        return BybitSnapshot(balances=balances, positions=positions, activities=activities)

    async def _fetch_spot_trades(
        self,
        *,
        limit: int,
        since_ms: Optional[int],
        quote_assets: Sequence[str],
    ) -> List[ActivityLine]:
        resp = await self._call(
            self._client.get_executions,
            category="spot",
            limit=limit,
            startTime=since_ms,
        )
        return _parse_trades(resp, "spot_trade", quote_assets)

    async def _fetch_derivatives_trades(
        self,
        *,
        limit: int,
        since_ms: Optional[int],
        quote_assets: Sequence[str],
    ) -> List[ActivityLine]:
        activities: List[ActivityLine] = []
        for category in ("linear", "inverse"):
            resp = await self._call(
                self._client.get_executions,
                category=category,
                limit=limit,
                startTime=since_ms,
            )
            activities.extend(_parse_trades(resp, "futures_trade", quote_assets))
        return activities

    async def _fetch_deposits(
        self,
        *,
        limit: int,
        since_ms: Optional[int],
    ) -> List[ActivityLine]:
        if not hasattr(self._client, "get_deposit_records"):
            return []
        resp = await self._call(
            self._client.get_deposit_records,
            limit=limit,
            startTime=since_ms,
        )
        return _parse_transfers(resp, "deposit")

    async def _fetch_withdrawals(
        self,
        *,
        limit: int,
        since_ms: Optional[int],
    ) -> List[ActivityLine]:
        if not hasattr(self._client, "get_withdrawal_records"):
            return []
        resp = await self._call(
            self._client.get_withdrawal_records,
            limit=limit,
            startTime=since_ms,
        )
        return _parse_transfers(resp, "withdrawal")

    async def _fetch_conversions(
        self,
        *,
        limit: int,
        since_ms: Optional[int],
    ) -> List[ActivityLine]:
        if not hasattr(self._client, "get_convert_trade_history"):
            return []
        resp = await self._call(
            self._client.get_convert_trade_history,
            limit=limit,
            startTime=since_ms,
        )
        return _parse_conversions(resp)

    @staticmethod
    async def _call(func, /, **kwargs):
        return await asyncio.to_thread(func, **kwargs)


def _normalize_quote_assets(
    custom: Optional[Sequence[str]],
    defaults: Sequence[str],
) -> Tuple[str, ...]:
    items = custom if custom is not None else defaults
    return tuple(str(a).upper() for a in items if a)


def _result_list(resp: Dict[str, Any]) -> List[Dict[str, Any]]:
    result = (resp or {}).get("result") or {}
    for key in ("list", "rows"):
        items = result.get(key)
        if isinstance(items, list):
            return items
    return []


def _parse_trades(
    resp: Dict[str, Any],
    activity_type: str,
    quote_assets: Sequence[str],
) -> List[ActivityLine]:
    activities: List[ActivityLine] = []
    for t in _result_list(resp):
        if not isinstance(t, dict):
            continue
        symbol = str(t.get("symbol") or "")
        base_asset, quote_asset = _split_symbol(symbol, quote_assets)
        ts = _to_dt_from_ms(t.get("execTime") or t.get("execTimeMs") or t.get("timestamp"))
        fee = t.get("execFee") or t.get("fee")
        fee_currency = t.get("feeToken") or t.get("feeCurrency")
        activities.append(
            ActivityLine(
                activity_type=activity_type,
                symbol=symbol or None,
                base_asset=base_asset,
                quote_asset=quote_asset,
                side=_to_str(t.get("side")),
                amount=_to_float(t.get("execQty") or t.get("qty") or t.get("size")),
                price=_to_float(t.get("execPrice") or t.get("price")),
                fee=_to_float(fee),
                fee_currency=_to_str(fee_currency),
                timestamp=ts,
                raw=t,
            )
        )

    return activities


def _parse_transfers(resp: Dict[str, Any], activity_type: str) -> List[ActivityLine]:
    activities: List[ActivityLine] = []
    for t in _result_list(resp):
        if not isinstance(t, dict):
            continue
        coin = _to_str(t.get("coin"))
        amount = _to_float(t.get("amount") or t.get("qty"))
        ts = _to_dt_from_ms(t.get("successAt") or t.get("createdTime"))
        fee = _to_float(t.get("fee"))
        activities.append(
            ActivityLine(
                activity_type=activity_type,
                symbol=None,
                base_asset=coin,
                quote_asset=None,
                side=None,
                amount=amount,
                price=None,
                fee=fee,
                fee_currency=coin,
                timestamp=ts,
                raw=t,
            )
        )

    return activities


def _parse_conversions(resp: Dict[str, Any]) -> List[ActivityLine]:
    activities: List[ActivityLine] = []
    for t in _result_list(resp):
        if not isinstance(t, dict):
            continue
        from_coin = _to_str(t.get("fromCoin"))
        to_coin = _to_str(t.get("toCoin"))
        from_amount = _to_float(t.get("fromAmount"))
        to_amount = _to_float(t.get("toAmount"))
        ts = _to_dt_from_ms(t.get("exchangeTime") or t.get("createdTime"))
        activities.append(
            ActivityLine(
                activity_type="conversion",
                symbol=None,
                base_asset=from_coin,
                quote_asset=to_coin,
                side=None,
                amount=from_amount,
                price=to_amount,
                fee=None,
                fee_currency=None,
                timestamp=ts,
                raw=t,
            )
        )

    return activities


def _split_symbol(symbol: str, quote_assets: Sequence[str]) -> Tuple[Optional[str], Optional[str]]:
    if not symbol:
        return None, None
    if "/" in symbol:
        base, quote = symbol.split("/", 1)
        return base.upper(), quote.upper()

    upper = symbol.upper()
    for quote in quote_assets:
        if upper.endswith(quote):
            base = upper[: -len(quote)]
            return (base or None), quote

    return upper, None


def _to_timestamp_ms(ts: Optional[datetime]) -> Optional[int]:
    if ts is None:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    else:
        ts = ts.astimezone(timezone.utc)
    return int(ts.timestamp() * 1000)


def _to_dt_from_ms(value: Any) -> Optional[datetime]:
    num = _to_float(value)
    if num is None:
        return None
    return datetime.fromtimestamp(num / 1000, tz=timezone.utc)


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
