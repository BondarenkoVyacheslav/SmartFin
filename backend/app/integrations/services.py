from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from asgiref.sync import async_to_sync, sync_to_async
from django.utils import timezone

from app.assets.models import Asset, AssetType
from app.integrations.models import Integration, WalletAddress
from app.transaction.models import Transaction


@dataclass(frozen=True)
class CashflowSyncResult:
    portfolio_id: int
    date: date
    integrations_checked: int
    activities_found: int
    transactions_created: int
    skipped_missing_asset: int
    skipped_missing_amount: int
    errors: List[str]


def sync_portfolio_cashflow(
    portfolio_id: int,
    *,
    target_date: Optional[date] = None,
    limit: int = 200,
    max_concurrency: int = 5,
) -> CashflowSyncResult:
    return async_to_sync(async_sync_portfolio_cashflow)(
        portfolio_id,
        target_date=target_date,
        limit=limit,
        max_concurrency=max_concurrency,
    )


async def async_sync_portfolio_cashflow(
    portfolio_id: int,
    *,
    target_date: Optional[date] = None,
    limit: int = 200,
    max_concurrency: int = 5,
) -> CashflowSyncResult:
    target_date = target_date or timezone.localdate()
    since = _start_of_day(target_date)

    integrations = await sync_to_async(list)(
        Integration.objects.select_related("exchange_id").filter(portfolio_id=portfolio_id)
    )

    limiter = asyncio.Semaphore(max(1, int(max_concurrency)))

    async def _runner(integration: Integration) -> Tuple[Integration, List[Any], Optional[str]]:
        async with limiter:
            try:
                activities = await _fetch_integration_activities(
                    integration,
                    since=since,
                    limit=limit,
                )
                return integration, activities, None
            except Exception as exc:  # noqa: BLE001
                return integration, [], f"{integration.id}:{exc!r}"

    tasks = [_runner(integration) for integration in integrations]
    results = await asyncio.gather(*tasks)

    return await sync_to_async(_persist_cashflow_results)(
        portfolio_id,
        target_date,
        results,
    )


# ----------------------
# Persistence (sync DB)
# ----------------------

def _persist_cashflow_results(
    portfolio_id: int,
    target_date: date,
    results: Sequence[Tuple[Integration, List[Any], Optional[str]]],
) -> CashflowSyncResult:
    created: List[Transaction] = []
    skipped_missing_asset = 0
    skipped_missing_amount = 0
    activities_found = 0
    errors: List[str] = []

    for integration, activities, error in results:
        if error:
            errors.append(error)
            continue
        if not activities:
            continue
        activities_found += len(activities)
        exchange_name = _normalize_exchange_name(integration.exchange_id.name)
        exchange_kind = (integration.exchange_id.kind or "").lower()

        for activity in activities:
            txs, skipped_amount, skipped_asset = _build_transactions_for_activity(
                integration,
                activity,
                exchange_name=exchange_name,
                exchange_kind=exchange_kind,
                target_date=target_date,
            )
            created.extend(txs)
            skipped_missing_amount += skipped_amount
            skipped_missing_asset += skipped_asset

    if created:
        unique: Dict[Tuple[Optional[int], Optional[str]], Transaction] = {}
        for tx in created:
            key = (tx.integration_id, tx.dedupe_key)
            if key in unique:
                continue
            unique[key] = tx
        created = list(unique.values())
        Transaction.objects.bulk_create(created, ignore_conflicts=True)

    return CashflowSyncResult(
        portfolio_id=portfolio_id,
        date=target_date,
        integrations_checked=len(results),
        activities_found=activities_found,
        transactions_created=len(created),
        skipped_missing_asset=skipped_missing_asset,
        skipped_missing_amount=skipped_missing_amount,
        errors=errors,
    )


# ----------------------
# Activity normalization
# ----------------------


def _build_transactions_for_activity(
    integration: Integration,
    activity: Any,
    *,
    exchange_name: str,
    exchange_kind: str,
    target_date: date,
) -> Tuple[List[Transaction], int, int]:
    if not _is_activity_in_date(activity, target_date):
        return [], 0, 0

    tx_type = _map_activity_to_transaction_type(activity)
    if tx_type is None:
        return [], 0, 0

    if tx_type == "conversion":
        return _build_conversion_transactions(
            integration=integration,
            activity=activity,
            exchange_kind=exchange_kind,
        )

    amount = _to_decimal(getattr(activity, "amount", None))
    if amount is None:
        return [], 1, 0

    asset_symbol = _asset_symbol_for_activity(activity, tx_type=tx_type)
    asset = _resolve_asset(
        asset_symbol,
        exchange_kind=exchange_kind,
    )
    if asset is None:
        return [], 0, 1

    price = _to_decimal(getattr(activity, "price", None))
    price_currency = _normalize_upper(getattr(activity, "quote_asset", None))
    executed_at = _ensure_aware(getattr(activity, "timestamp", None))

    dedupe_key = _build_dedupe_key(
        integration_id=integration.id,
        activity=activity,
        tx_type=tx_type,
        asset_symbol=asset_symbol,
        amount=amount,
        price=price,
        price_currency=price_currency,
        executed_at=executed_at,
    )

    tx = Transaction(
        portfolio=integration.portfolio_id,
        asset=asset,
        transaction_type=tx_type,
        amount=amount,
        price=price,
        price_currency=price_currency,
        executed_at=executed_at,
        source="INTEGRATION",
        integration=integration,
        dedupe_key=dedupe_key,
    )

    return [tx], 0, 0


def _build_conversion_transactions(
    *,
    integration: Integration,
    activity: Any,
    exchange_kind: str,
) -> Tuple[List[Transaction], int, int]:
    from_symbol = _normalize_upper(getattr(activity, "base_asset", None))
    to_symbol = _normalize_upper(getattr(activity, "quote_asset", None))
    from_amount = _to_decimal(getattr(activity, "amount", None))
    to_amount = _to_decimal(getattr(activity, "price", None))

    results: List[Transaction] = []
    skipped_amount = 0
    skipped_asset = 0

    executed_at = _ensure_aware(getattr(activity, "timestamp", None))

    if from_symbol and from_amount is not None:
        from_asset = _resolve_asset(from_symbol, exchange_kind=exchange_kind)
        if from_asset is not None:
            dedupe_key = _build_dedupe_key(
                integration_id=integration.id,
                activity=activity,
                tx_type="conversion",
                asset_symbol=from_symbol,
                amount=from_amount,
                price=to_amount,
                price_currency=to_symbol or None,
                executed_at=executed_at,
            )
            results.append(
                Transaction(
                    portfolio=integration.portfolio_id,
                    asset=from_asset,
                    transaction_type="conversion",
                    amount=from_amount,
                    price=to_amount,
                    price_currency=to_symbol or None,
                    executed_at=executed_at,
                    source="INTEGRATION",
                    integration=integration,
                    dedupe_key=dedupe_key,
                )
            )
        else:
            skipped_asset += 1
    else:
        if not from_symbol:
            skipped_asset += 1
        if from_amount is None:
            skipped_amount += 1

    if to_symbol and to_amount is not None:
        to_asset = _resolve_asset(to_symbol, exchange_kind=exchange_kind)
        if to_asset is not None:
            dedupe_key = _build_dedupe_key(
                integration_id=integration.id,
                activity=activity,
                tx_type="conversion",
                asset_symbol=to_symbol,
                amount=to_amount,
                price=from_amount,
                price_currency=from_symbol or None,
                executed_at=executed_at,
            )
            results.append(
                Transaction(
                    portfolio=integration.portfolio_id,
                    asset=to_asset,
                    transaction_type="conversion",
                    amount=to_amount,
                    price=from_amount,
                    price_currency=from_symbol or None,
                    executed_at=executed_at,
                    source="INTEGRATION",
                    integration=integration,
                    dedupe_key=dedupe_key,
                )
            )
        else:
            skipped_asset += 1
    else:
        if not to_symbol:
            skipped_asset += 1
        if to_amount is None:
            skipped_amount += 1

    return results, skipped_amount, skipped_asset


# ----------------------
# Adapters (async)
# ----------------------


async def _fetch_integration_activities(
    integration: Integration,
    *,
    since: datetime,
    limit: int,
) -> List[Any]:
    exchange_name = _normalize_exchange_name(integration.exchange_id.name)
    raw = integration.extra_params or {}

    if exchange_name in {"binance"}:
        from app.integrations.Binance.adapter import BinanceAdapter

        adapter = BinanceAdapter(
            api_key=integration.api_key or "",
            api_secret=integration.api_secret or "",
            testnet=bool(raw.get("testnet", False)),
            recv_window=int(raw.get("recv_window", 5000)),
            extra_params=_pick_client_params(raw),
        )
        return await adapter.fetch_activities(
            since=since,
            limit=limit,
            quote_assets=_normalize_list(raw.get("quote_assets")),
            spot_symbols=_normalize_list(raw.get("spot_symbols")),
            um_symbols=_normalize_list(raw.get("um_symbols")),
            cm_symbols=_normalize_list(raw.get("cm_symbols")),
        )

    if exchange_name in {"bybit"}:
        from app.integrations.Bybit.adapter import BybitAdapter

        adapter = BybitAdapter(
            api_key=integration.api_key or "",
            api_secret=integration.api_secret or "",
            testnet=bool(raw.get("testnet", False)),
            recv_window=int(raw.get("recv_window", 5000)),
            extra_params=dict(raw.get("client_params") or {}),
        )
        return await adapter.fetch_activities(
            since=since,
            limit=limit,
            quote_assets=_normalize_list(raw.get("quote_assets")),
        )

    if exchange_name in {"okx"}:
        from app.integrations.OKX.adapter import OKXAdapter

        adapter = OKXAdapter(
            api_key=integration.api_key or "",
            api_secret=integration.api_secret or "",
            passphrase=integration.passphrase or "",
            testnet=bool(raw.get("testnet", False)),
            flag=_normalize_str(raw.get("flag")),
            use_server_time=bool(raw.get("use_server_time", False)),
            extra_params=dict(raw.get("client_params") or {}),
        )
        return await adapter.fetch_activities(
            since=since,
            limit=limit,
            quote_assets=_normalize_list(raw.get("quote_assets")),
            inst_types=_normalize_list(raw.get("inst_types")) or ["SPOT", "SWAP", "FUTURES"],
            inst_ids=_normalize_list(raw.get("inst_ids")),
        )

    if exchange_name in {"t", "tinkoff", "t-bank", "tbank"}:
        from app.integrations.T.adapter import TAdapter

        token = integration.token or integration.access_token or integration.api_key or ""
        adapter = TAdapter(
            token=token,
            account_id=integration.account_id,
            app_name=_normalize_str(raw.get("app_name")),
            extra_params=_pick_client_params(raw),
        )
        return await adapter.fetch_activities(
            since=since,
            limit=limit,
        )

    if exchange_name in {"bcs"}:
        from app.integrations.BCS.adapter import BcsAdapter

        adapter = BcsAdapter(
            access_token=integration.access_token,
            refresh_token=integration.refresh_token or integration.token,
            client_id=integration.client_id or "trade-api-read",
            access_expires_at=integration.token_expires_at,
            refresh_expires_at=integration.refresh_expires_at,
            token_margin_s=int(raw.get("token_margin_s", 300)),
            base_url=raw.get("base_url") or BcsAdapter.DEFAULT_BASE_URL,
            timeout_s=float(raw.get("timeout_s", 20.0)),
            extra_headers=_normalize_dict(raw.get("extra_headers")),
            verify_tls=bool(raw.get("verify_tls", True)),
        )
        try:
            return await adapter.fetch_activities(since=since, limit=limit)
        finally:
            await adapter.aclose()

    if exchange_name in {"finam"}:
        from app.integrations.Finam.adapter import FinamAdapter

        secret = integration.secret or integration.api_secret or integration.token or ""
        adapter = FinamAdapter(
            secret=secret,
            account_id=integration.account_id,
            extra_params=_pick_client_params(raw),
        )
        try:
            return await adapter.fetch_activities(
                account_id=integration.account_id,
                since=since,
                limit=limit,
            )
        finally:
            await adapter.aclose()

    if exchange_name in {"ton"}:
        from app.integrations.TON.adapter import TONAdapter

        addresses = await sync_to_async(list)(
            WalletAddress.objects.filter(integration_id=integration.id, is_active=True)
            .values_list("address", flat=True)
        )
        addresses = _normalize_address_list(addresses)
        if not addresses:
            return []

        adapter = TONAdapter(
            toncenter_api_key=_normalize_str(raw.get("toncenter_api_key")),
            tonapi_api_key=_normalize_str(raw.get("tonapi_api_key")),
            toncenter_base_url=raw.get("toncenter_base_url")
            or TONAdapter.DEFAULT_TONCENTER_URL,
            tonapi_base_url=raw.get("tonapi_base_url", TONAdapter.DEFAULT_TONAPI_URL),
            timeout_s=float(raw.get("timeout_s", TONAdapter.DEFAULT_TIMEOUT_S)),
            verify_tls=bool(raw.get("verify_tls", True)),
            extra_headers=_normalize_dict(raw.get("extra_headers")),
        )
        try:
            results: List[Any] = []
            for address in addresses:
                results.extend(await adapter.fetch_activities(address=address, since=since, limit=limit))
            return results
        finally:
            await adapter.aclose()

    return []


# ----------------------
# Mapping helpers
# ----------------------


def _map_activity_to_transaction_type(activity: Any) -> Optional[str]:
    activity_type = _normalize_str(getattr(activity, "activity_type", None))
    side = _normalize_str(getattr(activity, "side", None))

    if activity_type is None:
        return None

    if "conversion" in activity_type:
        return "conversion"

    if "futures" in activity_type and "trade" in activity_type:
        if side == "buy":
            return "futures_buy"
        if side == "sell":
            return "futures_sell"

    if activity_type in {"spot_trade", "trade", "order"}:
        if side == "buy":
            return "buy"
        if side == "sell":
            return "sell"

    if "deposit" in activity_type or activity_type.endswith("_in") or side == "in":
        return "deposit"

    if "withdraw" in activity_type or activity_type.endswith("_out") or side == "out":
        return "withdrawal"

    if "buy" in activity_type:
        return "buy"
    if "sell" in activity_type:
        return "sell"

    if "input" in activity_type or "cash_in" in activity_type:
        return "deposit"
    if "output" in activity_type or "cash_out" in activity_type:
        return "withdrawal"

    return None


def _asset_symbol_for_activity(activity: Any, *, tx_type: str) -> Optional[str]:
    base_asset = _normalize_upper(getattr(activity, "base_asset", None))
    symbol = _normalize_upper(getattr(activity, "symbol", None))
    quote_asset = _normalize_upper(getattr(activity, "quote_asset", None))

    if base_asset:
        return base_asset
    if symbol:
        return symbol
    if tx_type in {"deposit", "withdrawal", "conversion"} and quote_asset:
        return quote_asset
    return None


# ----------------------
# Asset resolution
# ----------------------


def _resolve_asset(symbol: Optional[str], *, exchange_kind: str) -> Optional[Asset]:
    if not symbol:
        return None
    symbol = symbol.strip().upper()

    if exchange_kind in {"exchange", "wallet", "blockchain"}:
        return _get_or_create_asset(symbol, asset_type_code="crypto", market_prefix=exchange_kind)

    asset = Asset.objects.filter(symbol=symbol).first()
    if asset is not None:
        return asset

    if _looks_like_currency(symbol):
        return _get_or_create_asset(symbol, asset_type_code="currency", market_prefix="currency")

    return None


def _get_or_create_asset(
    symbol: str,
    *,
    asset_type_code: str,
    market_prefix: str,
) -> Optional[Asset]:
    asset = Asset.objects.filter(symbol=symbol, asset_type__code=asset_type_code).first()
    if asset is not None:
        return asset

    asset_type = AssetType.objects.filter(code=asset_type_code).first()
    if asset_type is None:
        return None

    return Asset.objects.create(
        name=symbol,
        symbol=symbol,
        asset_type=asset_type,
        market_url=f"{market_prefix}:{symbol}",
        currency=symbol,
    )


def _looks_like_currency(symbol: str) -> bool:
    if not symbol:
        return False
    if not symbol.isalpha():
        return False
    return 2 <= len(symbol) <= 6


# ----------------------
# Dedupe
# ----------------------


def _build_dedupe_key(
    *,
    integration_id: int,
    activity: Any,
    tx_type: str,
    asset_symbol: Optional[str],
    amount: Optional[Decimal],
    price: Optional[Decimal],
    price_currency: Optional[str],
    executed_at: Optional[datetime],
) -> str:
    raw = getattr(activity, "raw", None)
    payload = {
        "integration_id": integration_id,
        "tx_type": tx_type,
        "asset": asset_symbol,
        "amount": _decimal_str(amount),
        "price": _decimal_str(price),
        "price_currency": price_currency,
        "executed_at": _dt_str(executed_at),
        "activity_type": getattr(activity, "activity_type", None),
        "side": getattr(activity, "side", None),
        "raw_id": _extract_raw_id(raw),
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _extract_raw_id(raw: Any) -> Optional[str]:
    if not isinstance(raw, dict):
        return None
    for key in (
        "id",
        "orderId",
        "order_id",
        "tradeId",
        "trade_id",
        "txId",
        "tx_id",
        "hash",
        "transferId",
        "transfer_id",
        "withdrawOrderId",
        "withdraw_order_id",
        "depositId",
        "deposit_id",
        "clientOrderId",
        "client_order_id",
        "uid",
    ):
        value = raw.get(key)
        if value is not None and str(value).strip():
            return str(value)
    return None


# ----------------------
# Date helpers
# ----------------------


def _start_of_day(target_date: date) -> datetime:
    tz = timezone.get_current_timezone()
    return timezone.make_aware(datetime.combine(target_date, time.min), timezone=tz)


def _is_activity_in_date(activity: Any, target_date: date) -> bool:
    ts = _ensure_aware(getattr(activity, "timestamp", None))
    if ts is None:
        return True
    local = timezone.localtime(ts).date()
    return local == target_date


def _ensure_aware(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if timezone.is_aware(value):
        return value
    return timezone.make_aware(value, timezone=timezone.utc)


# ----------------------
# Utils
# ----------------------


def _normalize_str(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    value = str(value).strip()
    if not value:
        return None
    return value.lower()


def _normalize_upper(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    value = str(value).strip()
    if not value:
        return None
    return value.upper()


def _normalize_exchange_name(value: Optional[str]) -> str:
    return (_normalize_str(value) or "").replace(" ", "").replace("_", "").replace("-", "")


def _normalize_list(values: Optional[Iterable[Any]]) -> Optional[List[str]]:
    if not values:
        return None
    out: List[str] = []
    for item in values:
        if item is None:
            continue
        value = str(item).strip()
        if value:
            out.append(value)
    return out or None


def _normalize_address_list(values: Optional[Iterable[str]]) -> List[str]:
    if not values:
        return []
    return [str(item).strip() for item in values if item and str(item).strip()]


def _normalize_dict(value: Any) -> Optional[Dict[str, Any]]:
    if isinstance(value, dict):
        return dict(value)
    return None


def _pick_client_params(raw: dict) -> dict:
    client_params = raw.get("client_params")
    if isinstance(client_params, dict):
        return dict(client_params)
    filtered = {
        k: v
        for k, v in raw.items()
        if k
        not in {
            "testnet",
            "recv_window",
            "account_type",
            "quote_assets",
            "spot_symbols",
            "um_symbols",
            "cm_symbols",
        }
    }
    return filtered


def _to_decimal(value: Optional[float | Decimal]) -> Optional[Decimal]:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _decimal_str(value: Optional[Decimal]) -> Optional[str]:
    if value is None:
        return None
    return format(value, "f")


def _dt_str(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    return value.isoformat()
