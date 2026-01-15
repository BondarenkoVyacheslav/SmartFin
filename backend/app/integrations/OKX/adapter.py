from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import inspect
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class OKXBalance:
    asset: str
    free: Optional[float]
    locked: Optional[float]
    total: Optional[float]


@dataclass(frozen=True)
class OKXPosition:
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
class OKXSnapshot:
    balances: List[OKXBalance]
    positions: List[OKXPosition]
    activities: List[ActivityLine]


class OKXAdapter:
    """
    OKX adapter powered by the official okx-python SDK.

    Required dependency: okx
    """

    DEFAULT_QUOTE_ASSETS = ("USDT", "USDC", "USD", "BTC", "ETH", "EUR", "RUB")
    DEFAULT_INSTRUMENT_TYPES = ("SPOT", "SWAP", "FUTURES")

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        passphrase: str,
        *,
        testnet: bool = False,
        flag: Optional[str] = None,
        use_server_time: bool = False,
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> None:
        params = extra_params or {}
        resolved_flag = flag if flag is not None else ("1" if testnet else "0")
        self._account = self._make_account_client(
            api_key=api_key,
            api_secret=api_secret,
            passphrase=passphrase,
            flag=resolved_flag,
            use_server_time=use_server_time,
            extra_params=_pick_client_params(params, "account"),
        )
        self._trade = self._make_trade_client(
            api_key=api_key,
            api_secret=api_secret,
            passphrase=passphrase,
            flag=resolved_flag,
            use_server_time=use_server_time,
            extra_params=_pick_client_params(params, "trade"),
        )
        self._funding = self._make_funding_client(
            api_key=api_key,
            api_secret=api_secret,
            passphrase=passphrase,
            flag=resolved_flag,
            use_server_time=use_server_time,
            extra_params=_pick_client_params(params, "funding"),
        )

    @staticmethod
    def _make_account_client(
        *,
        api_key: str,
        api_secret: str,
        passphrase: str,
        flag: str,
        use_server_time: bool,
        extra_params: Dict[str, Any],
    ):
        try:
            from okx.api.account import Account  # type: ignore
        except Exception:
            Account = None
        if Account is not None:
            params = _filter_client_params(
                extra_params,
                allowed_keys={"flag", "proxies", "proxy_host", "retry_num", "retry_delay"},
            )
            params.setdefault("flag", flag)
            return Account(api_key, api_secret, passphrase, **params)

        try:
            from okx.Account import AccountAPI  # type: ignore
        except Exception as exc:
            raise RuntimeError("okx SDK не установлен. Установи: uv add okx") from exc

        params = _filter_client_params(
            extra_params,
            allowed_keys={"flag", "use_server_time", "proxies", "proxy_host"},
        )
        params.setdefault("flag", flag)
        params.setdefault("use_server_time", use_server_time)
        return AccountAPI(api_key, api_secret, passphrase, **params)

    @staticmethod
    def _make_trade_client(
        *,
        api_key: str,
        api_secret: str,
        passphrase: str,
        flag: str,
        use_server_time: bool,
        extra_params: Dict[str, Any],
    ):
        try:
            from okx.api.trade import Trade  # type: ignore
        except Exception:
            Trade = None
        if Trade is not None:
            params = _filter_client_params(
                extra_params,
                allowed_keys={"flag", "proxies", "proxy_host", "retry_num", "retry_delay"},
            )
            params.setdefault("flag", flag)
            return Trade(api_key, api_secret, passphrase, **params)

        try:
            from okx.Trade import TradeAPI  # type: ignore
        except Exception as exc:
            raise RuntimeError("okx SDK не установлен. Установи: uv add okx") from exc

        params = _filter_client_params(
            extra_params,
            allowed_keys={"flag", "use_server_time", "proxies", "proxy_host"},
        )
        params.setdefault("flag", flag)
        params.setdefault("use_server_time", use_server_time)
        return TradeAPI(api_key, api_secret, passphrase, **params)

    @staticmethod
    def _make_funding_client(
        *,
        api_key: str,
        api_secret: str,
        passphrase: str,
        flag: str,
        use_server_time: bool,
        extra_params: Dict[str, Any],
    ):
        try:
            from okx.api.fundingaccount import FundingAccount  # type: ignore
        except Exception:
            FundingAccount = None
        if FundingAccount is not None:
            params = _filter_client_params(
                extra_params,
                allowed_keys={"flag", "proxies", "proxy_host", "retry_num", "retry_delay"},
            )
            params.setdefault("flag", flag)
            return FundingAccount(api_key, api_secret, passphrase, **params)

        try:
            from okx.Funding import FundingAPI  # type: ignore
        except Exception as exc:
            raise RuntimeError("okx SDK не установлен. Установи: uv add okx") from exc

        params = _filter_client_params(
            extra_params,
            allowed_keys={"flag", "use_server_time", "proxies", "proxy_host"},
        )
        params.setdefault("flag", flag)
        params.setdefault("use_server_time", use_server_time)
        return FundingAPI(api_key, api_secret, passphrase, **params)

    async def fetch_balances(self, *, ccy: Optional[str] = None) -> List[OKXBalance]:
        resp = await self._call(_resolve_method(self._account, "get_balance", "get_account_balance"), ccy=ccy)
        balances: List[OKXBalance] = []

        for item in _extract_list(resp, "data"):
            details = item.get("details")
            if isinstance(details, list):
                items = details
            else:
                items = [item]
            for detail in items:
                if not isinstance(detail, dict):
                    continue
                asset = str(detail.get("ccy") or "").upper()
                free = _to_float(detail.get("availBal") or detail.get("availEq"))
                locked = _to_float(detail.get("frozenBal"))
                total = _to_float(detail.get("eq") or detail.get("bal"))
                if total is None:
                    total = _sum_optional(free, locked)
                if asset:
                    balances.append(
                        OKXBalance(
                            asset=asset,
                            free=free,
                            locked=locked,
                            total=total,
                        )
                    )

        return balances

    async def fetch_positions(
        self,
        *,
        inst_types: Sequence[str] = ("SWAP", "FUTURES"),
        inst_id: Optional[str] = None,
    ) -> List[OKXPosition]:
        positions: List[OKXPosition] = []
        for inst_type in inst_types:
            resp = await self._call(
                self._account.get_positions,
                instType=str(inst_type),
                instId=inst_id,
            )
            for p in _extract_list(resp, "data"):
                if not isinstance(p, dict):
                    continue
                size = _to_float(p.get("pos"))
                positions.append(
                    OKXPosition(
                        symbol=str(p.get("instId") or ""),
                        side=_derive_position_side(p.get("posSide"), size),
                        size=abs(size) if size is not None else None,
                        entry_price=_to_float(p.get("avgPx")),
                        mark_price=_to_float(p.get("markPx")),
                        unrealized_pnl=_to_float(p.get("upl")),
                        leverage=_to_float(p.get("lever")),
                    )
                )

        return positions

    async def fetch_activities(
        self,
        *,
        since: Optional[datetime] = None,
        limit: int = 200,
        quote_assets: Optional[Sequence[str]] = None,
        inst_types: Optional[Sequence[str]] = None,
        inst_ids: Optional[Sequence[str]] = None,
    ) -> List[ActivityLine]:
        quote_assets = _normalize_quote_assets(quote_assets, self.DEFAULT_QUOTE_ASSETS)
        inst_types = tuple(inst_types) if inst_types is not None else self.DEFAULT_INSTRUMENT_TYPES
        since_ms = _to_timestamp_ms(since)

        activities: List[ActivityLine] = []
        activities.extend(
            await self._fetch_trades(
                inst_types=inst_types,
                limit=limit,
                since_ms=since_ms,
                quote_assets=quote_assets,
                inst_ids=inst_ids,
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
        ccy: Optional[str] = None,
        inst_types: Sequence[str] = ("SWAP", "FUTURES"),
        since: Optional[datetime] = None,
        limit: int = 200,
        quote_assets: Optional[Sequence[str]] = None,
        inst_ids: Optional[Sequence[str]] = None,
    ) -> OKXSnapshot:
        balances = await self.fetch_balances(ccy=ccy)
        positions = await self.fetch_positions(inst_types=inst_types)
        activities = await self.fetch_activities(
            since=since,
            limit=limit,
            quote_assets=quote_assets,
            inst_types=inst_types,
            inst_ids=inst_ids,
        )
        return OKXSnapshot(balances=balances, positions=positions, activities=activities)

    async def _fetch_trades(
        self,
        *,
        inst_types: Sequence[str],
        limit: int,
        since_ms: Optional[int],
        quote_assets: Sequence[str],
        inst_ids: Optional[Sequence[str]],
    ) -> List[ActivityLine]:
        activities: List[ActivityLine] = []
        for inst_type in inst_types:
            resp = await self._call(
                self._trade.get_fills,
                instType=str(inst_type),
                limit=limit,
            )
            activity_type = "spot_trade" if str(inst_type).upper() == "SPOT" else "futures_trade"
            activities.extend(
                _parse_fills(
                    resp,
                    activity_type=activity_type,
                    quote_assets=quote_assets,
                    since_ms=since_ms,
                    inst_ids=inst_ids,
                )
            )
        return activities

    async def _fetch_deposits(
        self,
        *,
        limit: int,
        since_ms: Optional[int],
    ) -> List[ActivityLine]:
        if not hasattr(self._funding, "get_deposit_history"):
            return []
        resp = await self._call(
            self._funding.get_deposit_history,
            limit=limit,
        )
        return _parse_transfers(resp, "deposit", since_ms=since_ms)

    async def _fetch_withdrawals(
        self,
        *,
        limit: int,
        since_ms: Optional[int],
    ) -> List[ActivityLine]:
        if not hasattr(self._funding, "get_withdrawal_history"):
            return []
        resp = await self._call(
            self._funding.get_withdrawal_history,
            limit=limit,
        )
        return _parse_transfers(resp, "withdrawal", since_ms=since_ms)

    async def _fetch_conversions(
        self,
        *,
        limit: int,
        since_ms: Optional[int],
    ) -> List[ActivityLine]:
        fetchers = []
        if hasattr(self._trade, "get_easy_convert_history"):
            fetchers.append(self._trade.get_easy_convert_history)
        if hasattr(self._trade, "get_convert_history"):
            fetchers.append(self._trade.get_convert_history)
        if hasattr(self._trade, "get_convert_trade_history"):
            fetchers.append(self._trade.get_convert_trade_history)
        if not fetchers:
            return []

        activities: List[ActivityLine] = []
        for fetcher in fetchers:
            resp = await self._call(fetcher, limit=limit)
            activities.extend(_parse_conversions(resp, since_ms=since_ms))
        return activities

    @staticmethod
    async def _call(func, /, **kwargs):
        filtered = _filter_kwargs(func, kwargs)
        return await asyncio.to_thread(func, **filtered)


def _pick_client_params(extra_params: Dict[str, Any], name: str) -> Dict[str, Any]:
    scoped = extra_params.get(name)
    if isinstance(scoped, dict):
        return dict(scoped)
    return dict(extra_params)


def _filter_client_params(extra_params: Dict[str, Any], *, allowed_keys: set[str]) -> Dict[str, Any]:
    return {k: v for k, v in extra_params.items() if k in allowed_keys}


def _resolve_method(obj: Any, *names: str):
    for name in names:
        if hasattr(obj, name):
            return getattr(obj, name)
    raise AttributeError(f"None of methods found on {obj}: {', '.join(names)}")


def _filter_kwargs(func, kwargs: Dict[str, Any]) -> Dict[str, Any]:
    try:
        sig = inspect.signature(func)
    except (TypeError, ValueError):
        return kwargs
    if any(p.kind == p.VAR_KEYWORD for p in sig.parameters.values()):
        return kwargs
    return {k: v for k, v in kwargs.items() if k in sig.parameters}


def _normalize_quote_assets(
    custom: Optional[Sequence[str]],
    defaults: Sequence[str],
) -> Tuple[str, ...]:
    items = custom if custom is not None else defaults
    return tuple(str(a).upper() for a in items if a)


def _extract_list(resp: Any, *keys: str) -> List[Any]:
    if isinstance(resp, list):
        return resp
    if isinstance(resp, dict):
        for key in keys:
            value = resp.get(key)
            if isinstance(value, list):
                return value
    return []


def _parse_fills(
    resp: Any,
    *,
    activity_type: str,
    quote_assets: Sequence[str],
    since_ms: Optional[int],
    inst_ids: Optional[Sequence[str]],
) -> List[ActivityLine]:
    activities: List[ActivityLine] = []
    inst_id_set = {str(i).upper() for i in inst_ids or [] if i}
    for t in _extract_list(resp, "data"):
        if not isinstance(t, dict):
            continue
        symbol = str(t.get("instId") or "")
        if inst_id_set and symbol.upper() not in inst_id_set:
            continue
        ts_value = t.get("ts")
        if since_ms is not None:
            ts_num = _to_float(ts_value)
            if ts_num is not None and ts_num < since_ms:
                continue
        base_asset, quote_asset = _split_symbol(symbol, quote_assets)
        activities.append(
            ActivityLine(
                activity_type=activity_type,
                symbol=symbol or None,
                base_asset=base_asset,
                quote_asset=quote_asset,
                side=_to_str(t.get("side")),
                amount=_to_float(t.get("fillSz") or t.get("sz")),
                price=_to_float(t.get("fillPx") or t.get("px")),
                fee=_to_float(t.get("fee")),
                fee_currency=_to_str(t.get("feeCcy")),
                timestamp=_to_dt_from_ms(ts_value),
                raw=t,
            )
        )
    return activities


def _parse_transfers(
    resp: Any,
    activity_type: str,
    *,
    since_ms: Optional[int],
) -> List[ActivityLine]:
    activities: List[ActivityLine] = []
    for t in _extract_list(resp, "data"):
        if not isinstance(t, dict):
            continue
        ts_value = t.get("ts")
        if since_ms is not None:
            ts_num = _to_float(ts_value)
            if ts_num is not None and ts_num < since_ms:
                continue
        coin = _to_str(t.get("ccy"))
        amount = _to_float(t.get("amt"))
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
                timestamp=_to_dt_from_ms(ts_value),
                raw=t,
            )
        )
    return activities


def _parse_conversions(resp: Any, *, since_ms: Optional[int]) -> List[ActivityLine]:
    activities: List[ActivityLine] = []
    for t in _extract_list(resp, "data"):
        if not isinstance(t, dict):
            continue
        ts_value = t.get("ts") or t.get("cTime")
        if since_ms is not None:
            ts_num = _to_float(ts_value)
            if ts_num is not None and ts_num < since_ms:
                continue
        from_coin = _to_str(t.get("fromCcy"))
        to_coin = _to_str(t.get("toCcy"))
        from_amount = _to_float(t.get("fromSz"))
        to_amount = _to_float(t.get("toSz"))
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
                timestamp=_to_dt_from_ms(ts_value),
                raw=t,
            )
        )
    return activities


def _split_symbol(symbol: str, quote_assets: Sequence[str]) -> Tuple[Optional[str], Optional[str]]:
    if not symbol:
        return None, None
    if "-" in symbol:
        parts = symbol.split("-")
        if len(parts) >= 2:
            return parts[0].upper(), parts[1].upper()
    if "/" in symbol:
        base, quote = symbol.split("/", 1)
        return base.upper(), quote.upper()

    upper = symbol.upper()
    for quote in quote_assets:
        if upper.endswith(quote):
            base = upper[: -len(quote)]
            return (base or None), quote

    return upper, None


def _derive_position_side(position_side: Any, position_amt: Optional[float]) -> Optional[str]:
    side = _to_str(position_side)
    if side:
        side_upper = side.upper()
        if side_upper in {"LONG", "SHORT"}:
            return side_upper.lower()
        if side_upper == "NET" and position_amt is not None:
            if position_amt > 0:
                return "long"
            if position_amt < 0:
                return "short"
    if position_amt is None:
        return None
    if position_amt > 0:
        return "long"
    if position_amt < 0:
        return "short"
    return None


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
    text = str(value).strip()
    return text or None


def _sum_optional(first: Optional[float], second: Optional[float]) -> Optional[float]:
    if first is None and second is None:
        return None
    return (first or 0.0) + (second or 0.0)
