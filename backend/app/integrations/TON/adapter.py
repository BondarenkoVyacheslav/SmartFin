from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import httpx


@dataclass(frozen=True)
class TONBalance:
    asset: str
    free: Optional[float]
    locked: Optional[float]
    total: Optional[float]


@dataclass(frozen=True)
class TONPosition:
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
class TONSnapshot:
    balances: List[TONBalance]
    positions: List[TONPosition]
    activities: List[ActivityLine]


class TONAdapter:
    """
    TON adapter using Toncenter/TonAPI for read-only portfolio and history access.

    Baseline security:
    - address comes from TON Connect
    - only HTTPS read APIs are used
    - no seed/private keys stored server-side
    """

    DEFAULT_TONCENTER_URL = "https://toncenter.com/api/v2"
    DEFAULT_TONAPI_URL = "https://tonapi.io"
    DEFAULT_TIMEOUT_S = 20.0
    DEFAULT_LIMIT = 200
    DEFAULT_RPS = 5
    TON_DECIMALS = 9

    def __init__(
        self,
        *,
        address: Optional[str] = None,
        toncenter_api_key: Optional[str] = None,
        tonapi_api_key: Optional[str] = None,
        toncenter_base_url: str = DEFAULT_TONCENTER_URL,
        tonapi_base_url: Optional[str] = DEFAULT_TONAPI_URL,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        verify_tls: bool = True,
        extra_headers: Optional[Dict[str, str]] = None,
        rate_limits: Optional[Dict[str, int]] = None,
    ) -> None:
        self._address = address.strip() if address else None
        self._toncenter_api_key = toncenter_api_key.strip() if toncenter_api_key else None
        self._tonapi_api_key = tonapi_api_key.strip() if tonapi_api_key else None
        self._address_cache: Dict[str, Sequence[str]] = {}

        headers = {"Accept": "application/json", **(extra_headers or {})}
        toncenter_headers = dict(headers)
        if self._toncenter_api_key:
            toncenter_headers.setdefault("X-API-Key", self._toncenter_api_key)
        self._toncenter_client = httpx.AsyncClient(
            base_url=toncenter_base_url.rstrip("/"),
            headers=toncenter_headers,
            timeout=httpx.Timeout(timeout_s),
            verify=verify_tls,
        )

        self._tonapi_client: Optional[httpx.AsyncClient] = None
        if tonapi_base_url:
            tonapi_headers = dict(headers)
            if self._tonapi_api_key:
                tonapi_headers.setdefault("X-API-Key", self._tonapi_api_key)
            self._tonapi_client = httpx.AsyncClient(
                base_url=tonapi_base_url.rstrip("/"),
                headers=tonapi_headers,
                timeout=httpx.Timeout(timeout_s),
                verify=verify_tls,
            )

        limits = dict(rate_limits or {})
        self._rate_limits = {
            "toncenter": _RateLimiter(limits.get("toncenter", self.DEFAULT_RPS)),
            "tonapi": _RateLimiter(limits.get("tonapi", self.DEFAULT_RPS)),
        }

    async def aclose(self) -> None:
        await self._toncenter_client.aclose()
        if self._tonapi_client is not None:
            await self._tonapi_client.aclose()

    async def fetch_balances(
        self,
        *,
        address: Optional[str] = None,
        include_jettons: bool = True,
        jetton_limit: int = DEFAULT_LIMIT,
    ) -> List[TONBalance]:
        address = await self._resolve_address(address)
        balances: List[TONBalance] = []

        ton_balance = await self._fetch_ton_balance(address)
        if ton_balance is not None:
            balances.append(
                TONBalance(asset="TON", free=ton_balance, locked=None, total=ton_balance)
            )

        if include_jettons:
            try:
                balances.extend(await self._fetch_jetton_balances(address, limit=jetton_limit))
            except httpx.HTTPStatusError as exc:
                if not _is_rate_limit_error(exc):
                    raise

        return balances

    async def fetch_positions(
        self,
        *,
        address: Optional[str] = None,
        include_staking: bool = True,
    ) -> List[TONPosition]:
        address = await self._resolve_address(address)
        if not include_staking or self._tonapi_client is None:
            return []

        try:
            data = await self._tonapi_request("GET", f"/v2/accounts/{address}/staking")
        except httpx.HTTPStatusError:
            return []

        items = _coerce_list(data.get("items") or data.get("positions") or data)
        positions: List[TONPosition] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            pool = _to_str(item.get("pool") or item.get("name") or item.get("pool_name"))
            symbol = pool or "TON Staking"
            amount = _apply_decimals(item.get("amount") or item.get("balance") or item.get("staked"), 9)
            positions.append(
                TONPosition(
                    symbol=symbol,
                    qty=amount,
                    avg_price=None,
                    current_price=None,
                    unrealized_pnl=None,
                    currency=_to_str(item.get("currency") or "TON"),
                )
            )
        return positions

    async def fetch_activities(
        self,
        *,
        address: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = DEFAULT_LIMIT,
    ) -> List[ActivityLine]:
        address = await self._resolve_address(address)
        activities: List[ActivityLine] = []
        if self._tonapi_client is not None:
            try:
                activities = await self._fetch_events_tonapi(address, since=since, limit=limit)
            except httpx.HTTPStatusError as exc:
                if not _is_rate_limit_error(exc):
                    raise
        if not activities:
            activities = await self._fetch_transactions_toncenter(
                address, since=since, limit=limit
            )
        activities.sort(key=lambda a: a.timestamp or datetime.min.replace(tzinfo=timezone.utc))
        if limit and limit > 0:
            return activities[: int(limit)]
        return activities

    async def fetch_snapshot(
        self,
        *,
        address: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = DEFAULT_LIMIT,
        include_jettons: bool = True,
        include_staking: bool = True,
    ) -> TONSnapshot:
        address = await self._resolve_address(address)
        balances, positions, activities = await asyncio.gather(
            self.fetch_balances(
                address=address,
                include_jettons=include_jettons,
                jetton_limit=limit,
            ),
            self.fetch_positions(address=address, include_staking=include_staking),
            self.fetch_activities(address=address, since=since, limit=limit),
        )
        return TONSnapshot(balances=balances, positions=positions, activities=activities)

    async def _fetch_ton_balance(self, address: str) -> Optional[float]:
        params = {"address": address}
        data = await self._toncenter_request("GET", "/getAddressBalance", params=params)
        result = data.get("result") if isinstance(data, dict) else None
        return _apply_decimals(result, self.TON_DECIMALS)

    async def _fetch_jetton_balances(self, address: str, *, limit: int) -> List[TONBalance]:
        if self._tonapi_client is None:
            return []
        params = {"limit": int(limit)} if limit else None
        data = await self._tonapi_request("GET", f"/v2/accounts/{address}/jettons", params=params)
        items = _coerce_list(data.get("balances") or data.get("items") or data.get("jettons"))
        balances: List[TONBalance] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            jetton = item.get("jetton") or {}
            symbol = _to_str(jetton.get("symbol") or jetton.get("name") or jetton.get("address"))
            decimals = _to_int(jetton.get("decimals"))
            amount = _apply_decimals(item.get("balance") or item.get("amount"), decimals)
            if not symbol or amount is None:
                continue
            balances.append(TONBalance(asset=symbol, free=amount, locked=None, total=amount))
        return balances

    async def _fetch_events_tonapi(
        self,
        address: str,
        *,
        since: Optional[datetime],
        limit: int,
    ) -> List[ActivityLine]:
        params = {"limit": int(limit)} if limit else None
        data = await self._tonapi_request("GET", f"/v2/accounts/{address}/events", params=params)
        items = _coerce_list(data.get("events") or data.get("items") or data.get("list") or data)
        address_variants = await self._resolve_address_variants(address)
        activities: List[ActivityLine] = []
        for event in items:
            if not isinstance(event, dict):
                continue
            timestamp = _to_dt(event.get("timestamp") or event.get("utime") or event.get("time"))
            if since and timestamp and timestamp < _ensure_aware(since):
                continue
            fee = _apply_decimals(
                event.get("fee") or event.get("event_fee") or event.get("total_fee"),
                self.TON_DECIMALS,
            )
            actions = _coerce_list(event.get("actions") or event.get("action") or [])
            for action in actions:
                if not isinstance(action, dict):
                    continue
                parsed = _parse_event_action(
                    action,
                    address_variants=address_variants,
                    default_timestamp=timestamp,
                    default_fee=fee,
                )
                if parsed is None:
                    continue
                activities.append(parsed)
        return activities

    async def _fetch_transactions_toncenter(
        self,
        address: str,
        *,
        since: Optional[datetime],
        limit: int,
    ) -> List[ActivityLine]:
        params: Dict[str, Any] = {"address": address, "limit": int(limit)}
        data = await self._toncenter_request("GET", "/getTransactions", params=params)
        items = data.get("result") if isinstance(data, dict) else None
        items = _coerce_list(items)
        address_variants = await self._resolve_address_variants(address)
        activities: List[ActivityLine] = []
        for tx in items:
            if not isinstance(tx, dict):
                continue
            timestamp = _to_dt(tx.get("utime") or tx.get("timestamp"))
            if since and timestamp and timestamp < _ensure_aware(since):
                continue
            in_msg = tx.get("in_msg")
            if isinstance(in_msg, dict):
                act = _parse_ton_message(
                    in_msg,
                    address_variants=address_variants,
                    timestamp=timestamp,
                )
                if act is not None:
                    activities.append(act)
            out_msgs = _coerce_list(tx.get("out_msgs"))
            for msg in out_msgs:
                if not isinstance(msg, dict):
                    continue
                act = _parse_ton_message(
                    msg,
                    address_variants=address_variants,
                    timestamp=timestamp,
                )
                if act is not None:
                    activities.append(act)
        return activities

    async def _resolve_address(self, address: Optional[str]) -> str:
        resolved = (address or self._address or "").strip()
        if not resolved:
            raise RuntimeError("TON address is required")
        return resolved

    async def _resolve_address_variants(self, address: str) -> Sequence[str]:
        if address in self._address_cache:
            return self._address_cache[address]
        variants = {address}
        if self._tonapi_client is not None:
            try:
                data = await self._tonapi_request("GET", f"/v2/address/{address}")
            except httpx.HTTPStatusError:
                data = {}
            if isinstance(data, dict):
                for key in ("raw_address", "bounceable", "non_bounceable", "address"):
                    value = _to_str(data.get(key))
                    if value:
                        variants.add(value)
        self._address_cache[address] = tuple(variants)
        return self._address_cache[address]

    async def _toncenter_request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        await self._rate_limits["toncenter"].acquire()
        params = dict(params or {})
        if self._toncenter_api_key:
            params.setdefault("api_key", self._toncenter_api_key)
        resp = await self._toncenter_client.request(method, path, params=params)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict) and data.get("ok") is False:
            raise httpx.HTTPStatusError("Toncenter error", request=resp.request, response=resp)
        if not isinstance(data, dict):
            return {}
        return data

    async def _tonapi_request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if self._tonapi_client is None:
            raise RuntimeError("TonAPI client not configured")
        await self._rate_limits["tonapi"].acquire()
        resp = await self._tonapi_client.request(method, path, params=params)
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, dict):
            return {}
        return data


class _RateLimiter:
    def __init__(self, rps: int) -> None:
        self._interval = 1.0 / max(1, int(rps))
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


def _parse_event_action(
    action: Dict[str, Any],
    *,
    address_variants: Sequence[str],
    default_timestamp: Optional[datetime],
    default_fee: Optional[float],
) -> Optional[ActivityLine]:
    action_type = _to_str(action.get("type") or action.get("action_type") or action.get("actionType"))
    action_key = action_type.lower() if action_type else ""
    payload = _extract_action_payload(action, action_type)

    if "ton" in action_key and "transfer" in action_key:
        return _parse_transfer_action(
            payload,
            asset="TON",
            decimals=TONAdapter.TON_DECIMALS,
            address_variants=address_variants,
            timestamp=default_timestamp,
            fee=default_fee,
            raw=action,
        )
    if "jetton" in action_key and "transfer" in action_key:
        jetton = payload.get("jetton") or {}
        symbol = _to_str(jetton.get("symbol") or jetton.get("name") or jetton.get("address"))
        decimals = _to_int(jetton.get("decimals"))
        return _parse_transfer_action(
            payload,
            asset=symbol or "JETTON",
            decimals=decimals,
            address_variants=address_variants,
            timestamp=default_timestamp,
            fee=default_fee,
            raw=action,
        )
    if "nft" in action_key and "transfer" in action_key:
        nft = payload.get("nft") or payload.get("item") or {}
        symbol = _to_str(nft.get("name") or nft.get("address"))
        return _parse_transfer_action(
            payload,
            asset=symbol or "NFT",
            decimals=None,
            address_variants=address_variants,
            timestamp=default_timestamp,
            fee=default_fee,
            raw=action,
            activity_type_prefix="nft_transfer",
        )

    if action_key:
        return ActivityLine(
            activity_type=action_key,
            symbol=None,
            base_asset=None,
            quote_asset=None,
            side=None,
            amount=None,
            price=None,
            fee=default_fee,
            fee_currency="TON" if default_fee is not None else None,
            timestamp=default_timestamp,
            raw=action,
        )
    return None


def _parse_transfer_action(
    payload: Dict[str, Any],
    *,
    asset: str,
    decimals: Optional[int],
    address_variants: Sequence[str],
    timestamp: Optional[datetime],
    fee: Optional[float],
    raw: Dict[str, Any],
    activity_type_prefix: str = "transfer",
) -> Optional[ActivityLine]:
    sender = _extract_address(payload.get("sender") or payload.get("from") or payload.get("source"))
    recipient = _extract_address(
        payload.get("recipient") or payload.get("to") or payload.get("destination")
    )
    side = None
    activity_type = activity_type_prefix
    if _address_matches(recipient, address_variants):
        side = "in"
        activity_type = f"{activity_type_prefix}_in"
    elif _address_matches(sender, address_variants):
        side = "out"
        activity_type = f"{activity_type_prefix}_out"

    amount = _apply_decimals(payload.get("amount") or payload.get("value"), decimals)
    if amount is None and activity_type_prefix == "nft_transfer":
        amount = 1.0

    return ActivityLine(
        activity_type=activity_type,
        symbol=None,
        base_asset=asset,
        quote_asset=None,
        side=side,
        amount=amount,
        price=None,
        fee=fee,
        fee_currency="TON" if fee is not None else None,
        timestamp=timestamp,
        raw=raw,
    )


def _parse_ton_message(
    msg: Dict[str, Any],
    *,
    address_variants: Sequence[str],
    timestamp: Optional[datetime],
) -> Optional[ActivityLine]:
    sender = _extract_address(msg.get("source") or msg.get("from"))
    recipient = _extract_address(msg.get("destination") or msg.get("to"))
    side = None
    activity_type = "transfer"
    if _address_matches(recipient, address_variants):
        side = "in"
        activity_type = "transfer_in"
    elif _address_matches(sender, address_variants):
        side = "out"
        activity_type = "transfer_out"

    amount = _apply_decimals(msg.get("value") or msg.get("amount"), TONAdapter.TON_DECIMALS)
    if amount is None or amount == 0:
        return None
    return ActivityLine(
        activity_type=activity_type,
        symbol=None,
        base_asset="TON",
        quote_asset=None,
        side=side,
        amount=amount,
        price=None,
        fee=None,
        fee_currency=None,
        timestamp=timestamp,
        raw=msg,
    )


def _extract_action_payload(action: Dict[str, Any], action_type: Optional[str]) -> Dict[str, Any]:
    if action_type and action_type in action and isinstance(action.get(action_type), dict):
        return action[action_type]
    lower_type = action_type.lower() if action_type else ""
    for key in (action_type, lower_type, "payload", "data"):
        if key and isinstance(action.get(key), dict):
            return action[key]
    return action


def _extract_address(value: Any) -> Optional[str]:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("address", "raw", "raw_address", "account", "account_address"):
            addr = _to_str(value.get(key))
            if addr:
                return addr
    return None


def _address_matches(candidate: Optional[str], variants: Sequence[str]) -> bool:
    if not candidate:
        return False
    if candidate in variants:
        return True
    candidate_lower = candidate.lower()
    return any(candidate_lower == v.lower() for v in variants)


def _coerce_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _apply_decimals(value: Any, decimals: Optional[int]) -> Optional[float]:
    if value is None:
        return None
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return None
    if decimals is None:
        return amount
    try:
        scale = 10 ** int(decimals)
    except (TypeError, ValueError):
        return amount
    if scale == 0:
        return amount
    return amount / scale


def _to_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _to_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return _ensure_aware(value)
    try:
        ts = float(value)
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc)


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _is_rate_limit_error(exc: httpx.HTTPStatusError) -> bool:
    response = exc.response
    if response is None:
        return False
    return response.status_code in {401, 403, 429}
