from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class BinanceBalance:
    asset: str
    free: Optional[float]
    locked: Optional[float]
    total: Optional[float]


@dataclass(frozen=True)
class BinancePosition:
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
class BinanceSnapshot:
    balances: List[BinanceBalance]
    positions: List[BinancePosition]
    activities: List[ActivityLine]


class BinanceAdapter:
    """
    Binance adapter powered by the official binance-connector client.

    Required dependency: binance-connector
    """

    DEFAULT_QUOTE_ASSETS = ("USDT", "USDC", "USD", "BTC", "ETH", "EUR", "RUB")
    DEFAULT_CONCURRENCY = 5

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        *,
        testnet: bool = False,
        recv_window: int = 5000,
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> None:
        params = extra_params or {}
        self._spot = self._make_spot_client(
            api_key=api_key,
            api_secret=api_secret,
            testnet=testnet,
            extra_params=_pick_client_params(params, "spot"),
        )
        self._um_futures = self._make_um_futures_client(
            api_key=api_key,
            api_secret=api_secret,
            testnet=testnet,
            extra_params=_pick_client_params(params, "um_futures"),
        )
        self._cm_futures = self._make_cm_futures_client(
            api_key=api_key,
            api_secret=api_secret,
            testnet=testnet,
            extra_params=_pick_client_params(params, "cm_futures"),
        )
        self._recv_window = recv_window

    @staticmethod
    def _make_spot_client(
        *,
        api_key: str,
        api_secret: str,
        testnet: bool,
        extra_params: Dict[str, Any],
    ):
        try:
            from binance.spot import Spot  # type: ignore
        except Exception as exc:
            raise RuntimeError(
                "binance-connector not installed. Install: uv add binance-connector"
            ) from exc

        params = dict(extra_params)
        if testnet:
            params.setdefault("base_url", "https://testnet.binance.vision")
        return Spot(api_key=api_key, api_secret=api_secret, **params)

    @staticmethod
    def _make_um_futures_client(
        *,
        api_key: str,
        api_secret: str,
        testnet: bool,
        extra_params: Dict[str, Any],
    ):
        try:
            from binance.um_futures import UMFutures  # type: ignore
        except Exception as exc:
            raise RuntimeError(
                "binance-connector not installed. Install: uv add binance-connector"
            ) from exc

        params = dict(extra_params)
        if testnet:
            params.setdefault("base_url", "https://testnet.binancefuture.com")
        return UMFutures(api_key=api_key, api_secret=api_secret, **params)

    @staticmethod
    def _make_cm_futures_client(
        *,
        api_key: str,
        api_secret: str,
        testnet: bool,
        extra_params: Dict[str, Any],
    ):
        try:
            from binance.cm_futures import CMFutures  # type: ignore
        except Exception as exc:
            raise RuntimeError(
                "binance-connector not installed. Install: uv add binance-connector"
            ) from exc

        params = dict(extra_params)
        if testnet:
            params.setdefault("base_url", "https://testnet.binancefuture.com")
        return CMFutures(api_key=api_key, api_secret=api_secret, **params)

    async def fetch_balances(self) -> List[BinanceBalance]:
        resp = await self._call(self._spot.account, signed=True)
        balances = []
        for item in _extract_list(resp, "balances"):
            if not isinstance(item, dict):
                continue
            asset = str(item.get("asset") or "").upper()
            free = _to_float(item.get("free"))
            locked = _to_float(item.get("locked"))
            total = _sum_optional(free, locked)
            balances.append(
                BinanceBalance(
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
        categories: Sequence[str] = ("um", "cm"),
    ) -> List[BinancePosition]:
        positions: List[BinancePosition] = []
        for category in categories:
            cat = str(category).lower()
            if cat == "um" and self._um_futures is not None:
                resp = await self._call(self._um_futures.account, signed=True)
                positions.extend(_parse_positions(resp))
            elif cat == "cm" and self._cm_futures is not None:
                resp = await self._call(self._cm_futures.account, signed=True)
                positions.extend(_parse_positions(resp))
        return positions

    async def fetch_activities(
        self,
        *,
        since: Optional[datetime] = None,
        limit: int = 200,
        quote_assets: Optional[Sequence[str]] = None,
        spot_symbols: Optional[Sequence[str]] = None,
        um_symbols: Optional[Sequence[str]] = None,
        cm_symbols: Optional[Sequence[str]] = None,
    ) -> List[ActivityLine]:
        quote_assets = _normalize_quote_assets(quote_assets, self.DEFAULT_QUOTE_ASSETS)
        since_ms = _to_timestamp_ms(since)

        spot_symbols = await self._resolve_spot_symbols(
            symbols=spot_symbols,
            quote_assets=quote_assets,
        )
        um_symbols = await self._resolve_futures_symbols(
            client=self._um_futures,
            symbols=um_symbols,
            quote_assets=quote_assets,
        )
        cm_symbols = await self._resolve_futures_symbols(
            client=self._cm_futures,
            symbols=cm_symbols,
            quote_assets=quote_assets,
        )

        activities: List[ActivityLine] = []
        activities.extend(
            await self._fetch_spot_trades(
                symbols=spot_symbols,
                limit=limit,
                since_ms=since_ms,
                quote_assets=quote_assets,
            )
        )
        activities.extend(
            await self._fetch_um_trades(
                symbols=um_symbols,
                limit=limit,
                since_ms=since_ms,
                quote_assets=quote_assets,
            )
        )
        activities.extend(
            await self._fetch_cm_trades(
                symbols=cm_symbols,
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
        categories: Sequence[str] = ("um", "cm"),
        since: Optional[datetime] = None,
        limit: int = 200,
        quote_assets: Optional[Sequence[str]] = None,
        spot_symbols: Optional[Sequence[str]] = None,
        um_symbols: Optional[Sequence[str]] = None,
        cm_symbols: Optional[Sequence[str]] = None,
    ) -> BinanceSnapshot:
        balances = await self.fetch_balances()
        positions = await self.fetch_positions(categories=categories)
        activities = await self.fetch_activities(
            since=since,
            limit=limit,
            quote_assets=quote_assets,
            spot_symbols=spot_symbols,
            um_symbols=um_symbols,
            cm_symbols=cm_symbols,
        )
        return BinanceSnapshot(balances=balances, positions=positions, activities=activities)

    async def _fetch_spot_trades(
        self,
        *,
        symbols: Sequence[str],
        limit: int,
        since_ms: Optional[int],
        quote_assets: Sequence[str],
    ) -> List[ActivityLine]:
        if not symbols or not hasattr(self._spot, "my_trades"):
            return []
        return await self._fetch_trades_for_symbols(
            symbols=symbols,
            fetcher=lambda symbol: self._call(
                self._spot.my_trades,
                signed=True,
                symbol=symbol,
                limit=limit,
                startTime=since_ms,
            ),
            activity_type="spot_trade",
            quote_assets=quote_assets,
            parser=_parse_spot_trades,
        )

    async def _fetch_um_trades(
        self,
        *,
        symbols: Sequence[str],
        limit: int,
        since_ms: Optional[int],
        quote_assets: Sequence[str],
    ) -> List[ActivityLine]:
        if not symbols or not self._um_futures or not hasattr(self._um_futures, "user_trades"):
            return []
        return await self._fetch_trades_for_symbols(
            symbols=symbols,
            fetcher=lambda symbol: self._call(
                self._um_futures.user_trades,
                signed=True,
                symbol=symbol,
                limit=limit,
                startTime=since_ms,
            ),
            activity_type="futures_trade",
            quote_assets=quote_assets,
            parser=_parse_futures_trades,
        )

    async def _fetch_cm_trades(
        self,
        *,
        symbols: Sequence[str],
        limit: int,
        since_ms: Optional[int],
        quote_assets: Sequence[str],
    ) -> List[ActivityLine]:
        if not symbols or not self._cm_futures or not hasattr(self._cm_futures, "user_trades"):
            return []
        return await self._fetch_trades_for_symbols(
            symbols=symbols,
            fetcher=lambda symbol: self._call(
                self._cm_futures.user_trades,
                signed=True,
                symbol=symbol,
                limit=limit,
                startTime=since_ms,
            ),
            activity_type="futures_trade",
            quote_assets=quote_assets,
            parser=_parse_futures_trades,
        )

    async def _fetch_deposits(
        self,
        *,
        limit: int,
        since_ms: Optional[int],
    ) -> List[ActivityLine]:
        if not hasattr(self._spot, "deposit_history"):
            return []
        resp = await self._call(
            self._spot.deposit_history,
            signed=True,
            startTime=since_ms,
            limit=limit,
        )
        return _parse_transfers(resp, "deposit", keys=("depositList",))

    async def _fetch_withdrawals(
        self,
        *,
        limit: int,
        since_ms: Optional[int],
    ) -> List[ActivityLine]:
        if not hasattr(self._spot, "withdraw_history"):
            return []
        resp = await self._call(
            self._spot.withdraw_history,
            signed=True,
            startTime=since_ms,
            limit=limit,
        )
        return _parse_transfers(resp, "withdrawal", keys=("withdrawList",))

    async def _fetch_conversions(
        self,
        *,
        limit: int,
        since_ms: Optional[int],
    ) -> List[ActivityLine]:
        if not hasattr(self._spot, "convert_trade_history"):
            return []
        resp = await self._call(
            self._spot.convert_trade_history,
            signed=True,
            startTime=since_ms,
            limit=limit,
        )
        return _parse_conversions(resp)

    async def _fetch_trades_for_symbols(
        self,
        *,
        symbols: Sequence[str],
        fetcher,
        activity_type: str,
        quote_assets: Sequence[str],
        parser,
    ) -> List[ActivityLine]:
        if not symbols:
            return []

        semaphore = asyncio.Semaphore(self.DEFAULT_CONCURRENCY)

        async def _task(symbol: str) -> List[ActivityLine]:
            async with semaphore:
                resp = await fetcher(symbol)
                return parser(resp, activity_type, quote_assets)

        results = await asyncio.gather(*[_task(symbol) for symbol in symbols])
        activities: List[ActivityLine] = []
        for chunk in results:
            activities.extend(chunk)
        return activities

    async def _resolve_spot_symbols(
        self,
        *,
        symbols: Optional[Sequence[str]],
        quote_assets: Sequence[str],
    ) -> List[str]:
        if symbols:
            return [str(s).upper() for s in symbols if s]
        resp = await self._call(self._spot.exchange_info)
        items = _extract_list(resp, "symbols")
        return _filter_symbols(items, quote_assets)

    async def _resolve_futures_symbols(
        self,
        *,
        client,
        symbols: Optional[Sequence[str]],
        quote_assets: Sequence[str],
    ) -> List[str]:
        if not client:
            return []
        if symbols:
            return [str(s).upper() for s in symbols if s]
        if not hasattr(client, "exchange_info"):
            return []
        resp = await self._call(client.exchange_info)
        items = _extract_list(resp, "symbols")
        return _filter_symbols(items, quote_assets)

    async def _call(self, func, /, *, signed: bool = False, **kwargs):
        if signed:
            kwargs.setdefault("recvWindow", self._recv_window)
        return await asyncio.to_thread(func, **kwargs)


def _pick_client_params(extra_params: Dict[str, Any], name: str) -> Dict[str, Any]:
    scoped = extra_params.get(name)
    if isinstance(scoped, dict):
        return dict(scoped)
    return dict(extra_params)


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


def _filter_symbols(items: Iterable[Any], quote_assets: Sequence[str]) -> List[str]:
    results = []
    quote_set = {q.upper() for q in quote_assets}
    for item in items:
        if not isinstance(item, dict):
            continue
        if item.get("status") not in (None, "TRADING"):
            continue
        quote = (item.get("quoteAsset") or "").upper()
        symbol = (item.get("symbol") or "").upper()
        if symbol and (not quote_set or quote in quote_set):
            results.append(symbol)
    return results


def _parse_positions(resp: Any) -> List[BinancePosition]:
    items = _extract_list(resp, "positions")
    positions: List[BinancePosition] = []
    for p in items:
        if not isinstance(p, dict):
            continue
        position_amt = _to_float(p.get("positionAmt"))
        size = abs(position_amt) if position_amt is not None else None
        side = _derive_position_side(p.get("positionSide"), position_amt)
        positions.append(
            BinancePosition(
                symbol=str(p.get("symbol") or ""),
                side=side,
                size=size,
                entry_price=_to_float(p.get("entryPrice")),
                mark_price=_to_float(p.get("markPrice")),
                unrealized_pnl=_to_float(p.get("unRealizedProfit") or p.get("unrealizedProfit")),
                leverage=_to_float(p.get("leverage")),
            )
        )
    return positions


def _parse_spot_trades(
    resp: Any,
    activity_type: str,
    quote_assets: Sequence[str],
) -> List[ActivityLine]:
    activities: List[ActivityLine] = []
    for t in _extract_list(resp):
        if not isinstance(t, dict):
            continue
        symbol = str(t.get("symbol") or "")
        base_asset, quote_asset = _split_symbol(symbol, quote_assets)
        ts = _to_dt_from_ms(t.get("time"))
        side = "buy" if t.get("isBuyer") else "sell"
        activities.append(
            ActivityLine(
                activity_type=activity_type,
                symbol=symbol or None,
                base_asset=base_asset,
                quote_asset=quote_asset,
                side=side,
                amount=_to_float(t.get("qty")),
                price=_to_float(t.get("price")),
                fee=_to_float(t.get("commission")),
                fee_currency=_to_str(t.get("commissionAsset")),
                timestamp=ts,
                raw=t,
            )
        )
    return activities


def _parse_futures_trades(
    resp: Any,
    activity_type: str,
    quote_assets: Sequence[str],
) -> List[ActivityLine]:
    activities: List[ActivityLine] = []
    for t in _extract_list(resp):
        if not isinstance(t, dict):
            continue
        symbol = str(t.get("symbol") or "")
        base_asset, quote_asset = _split_symbol(symbol, quote_assets)
        ts = _to_dt_from_ms(t.get("time"))
        side = _to_str(t.get("side")) or _to_str(t.get("positionSide"))
        activities.append(
            ActivityLine(
                activity_type=activity_type,
                symbol=symbol or None,
                base_asset=base_asset,
                quote_asset=quote_asset,
                side=side.lower() if side else None,
                amount=_to_float(t.get("qty")),
                price=_to_float(t.get("price")),
                fee=_to_float(t.get("commission")),
                fee_currency=_to_str(t.get("commissionAsset")),
                timestamp=ts,
                raw=t,
            )
        )
    return activities


def _parse_transfers(
    resp: Any,
    activity_type: str,
    *,
    keys: Tuple[str, ...],
) -> List[ActivityLine]:
    activities: List[ActivityLine] = []
    for t in _extract_list(resp, *keys):
        if not isinstance(t, dict):
            continue
        coin = _to_str(t.get("coin") or t.get("asset"))
        amount = _to_float(t.get("amount"))
        ts = _to_dt_from_ms(t.get("insertTime") or t.get("applyTime") or t.get("successTime"))
        fee = _to_float(t.get("transactionFee") or t.get("fee"))
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


def _parse_conversions(resp: Any) -> List[ActivityLine]:
    activities: List[ActivityLine] = []
    for t in _extract_list(resp, "list"):
        if not isinstance(t, dict):
            continue
        from_coin = _to_str(t.get("fromAsset"))
        to_coin = _to_str(t.get("toAsset"))
        from_amount = _to_float(t.get("fromAmount"))
        to_amount = _to_float(t.get("toAmount"))
        ts = _to_dt_from_ms(t.get("createTime") or t.get("timestamp"))
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


def _derive_position_side(position_side: Any, position_amt: Optional[float]) -> Optional[str]:
    side = _to_str(position_side)
    if side:
        side_upper = side.upper()
        if side_upper in {"LONG", "SHORT"}:
            return side_upper.lower()
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
