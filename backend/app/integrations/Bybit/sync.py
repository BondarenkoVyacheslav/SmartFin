from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Sequence, Tuple

from django.db import transaction

from app.assets.models import Asset, AssetType
from app.integrations.Bybit.adapter import ActivityLine, BybitAdapter, BybitSnapshot
from app.integrations.models import Integration
from app.transaction.models import Transaction


@dataclass(frozen=True)
class BybitSettings:
    testnet: bool = False
    recv_window: int = 5000
    client_params: Dict[str, Any] = field(default_factory=dict)
    account_type: str = "UNIFIED"
    categories: List[str] = field(default_factory=lambda: ["linear", "inverse"])
    quote_assets: Optional[List[str]] = None

    @classmethod
    def from_integration(cls, integration: Integration) -> "BybitSettings":
        raw = integration.extra_params or {}
        return cls(
            testnet=bool(raw.get("testnet", False)),
            recv_window=int(raw.get("recv_window", 5000)),
            client_params=dict(raw.get("client_params") or {}),
            account_type=_normalize_str(raw.get("account_type")) or "UNIFIED",
            categories=_normalize_list(raw.get("categories")) or ["linear", "inverse"],
            quote_assets=_normalize_list(raw.get("quote_assets")),
        )


@dataclass(frozen=True)
class SyncResult:
    created: int
    skipped_missing_asset: int
    skipped_missing_amount: int


async def sync_bybit_integration(
    integration_id: int,
    *,
    since: Optional[datetime] = None,
    limit: int = 200,
) -> SyncResult:
    integration = Integration.objects.select_related("portfolio_id").get(id=integration_id)
    settings = BybitSettings.from_integration(integration)

    adapter = _build_adapter(integration, settings)
    activities = await adapter.fetch_activities(
        since=since,
        limit=limit,
        quote_assets=settings.quote_assets,
    )

    to_create: List[Transaction] = []
    skipped_missing_asset = 0
    skipped_missing_amount = 0

    for activity in activities:
        tx_type = _map_activity_to_transaction_type(activity)
        if tx_type is None:
            continue

        if activity.activity_type == "conversion":
            created, skipped_amount, skipped_asset = _build_conversion_transactions(
                integration=integration,
                activity=activity,
            )
            to_create.extend(created)
            skipped_missing_amount += skipped_amount
            skipped_missing_asset += skipped_asset
            continue

        amount = _to_decimal(activity.amount)
        if amount is None:
            skipped_missing_amount += 1
            continue

        asset_symbol = _asset_symbol_for_activity(activity)
        if asset_symbol is None:
            skipped_missing_asset += 1
            continue

        asset = _get_or_create_crypto_asset(asset_symbol)
        price = _to_decimal(activity.price)
        price_currency = activity.quote_asset

        to_create.append(
            Transaction(
                portfolio=integration.portfolio_id,
                asset=asset,
                transaction_type=tx_type,
                amount=amount,
                price=price,
                price_currency=price_currency,
                executed_at=activity.timestamp,
                source="INTEGRATION",
            )
        )

    with transaction.atomic():
        Transaction.objects.bulk_create(to_create)

    return SyncResult(
        created=len(to_create),
        skipped_missing_asset=skipped_missing_asset,
        skipped_missing_amount=skipped_missing_amount,
    )


async def fetch_bybit_snapshot(
    integration_id: int,
    *,
    since: Optional[datetime] = None,
    limit: int = 200,
) -> BybitSnapshot:
    integration = Integration.objects.select_related("portfolio_id").get(id=integration_id)
    settings = BybitSettings.from_integration(integration)

    adapter = _build_adapter(integration, settings)
    return await adapter.fetch_snapshot(
        account_type=settings.account_type,
        categories=settings.categories,
        since=since,
        limit=limit,
        quote_assets=settings.quote_assets,
    )


def _build_adapter(integration: Integration, settings: BybitSettings) -> BybitAdapter:
    return BybitAdapter(
        api_key=integration.api_key,
        api_secret=integration.api_secret,
        testnet=settings.testnet,
        recv_window=settings.recv_window,
        extra_params=settings.client_params,
    )


def _map_activity_to_transaction_type(activity: ActivityLine) -> Optional[str]:
    if activity.activity_type == "spot_trade":
        side = (activity.side or "").lower()
        if side == "buy":
            return "buy"
        if side == "sell":
            return "sell"
        return None
    if activity.activity_type == "futures_trade":
        side = (activity.side or "").lower()
        if side == "buy":
            return "futures_buy"
        if side == "sell":
            return "futures_sell"
        return None
    if activity.activity_type == "deposit":
        return "deposit"
    if activity.activity_type == "withdrawal":
        return "withdrawal"
    if activity.activity_type == "conversion":
        return "conversion"
    return None


def _asset_symbol_for_activity(activity: ActivityLine) -> Optional[str]:
    if activity.base_asset:
        return activity.base_asset.upper()
    if activity.symbol:
        return activity.symbol.upper()
    return None


def _get_or_create_crypto_asset(symbol: str) -> Asset:
    asset = Asset.objects.filter(symbol=symbol, asset_type__code="crypto").first()
    if asset is not None:
        return asset

    asset_type = AssetType.objects.filter(code="crypto").first()
    if asset_type is None:
        asset_type = AssetType.objects.create(
            name="Криптовалюты",
            code="crypto",
            description="Крипта и стейблкоины",
        )

    return Asset.objects.create(
        name=symbol,
        symbol=symbol,
        asset_type=asset_type,
        market_url=f"bybit:{symbol}",
        currency=symbol,
    )


def _build_conversion_transactions(
    *,
    integration: Integration,
    activity: ActivityLine,
) -> Tuple[List[Transaction], int, int]:
    from_symbol = (activity.base_asset or "").upper()
    to_symbol = (activity.quote_asset or "").upper()
    from_amount = _to_decimal(activity.amount)
    to_amount = _to_decimal(activity.price)

    results: List[Transaction] = []
    skipped_amount = 0
    skipped_asset = 0

    if from_symbol and from_amount is not None:
        from_asset = _get_or_create_crypto_asset(from_symbol)
        results.append(
            Transaction(
                portfolio=integration.portfolio_id,
                asset=from_asset,
                transaction_type="conversion",
                amount=from_amount,
                price=to_amount,
                price_currency=to_symbol or None,
                executed_at=activity.timestamp,
                source="INTEGRATION",
            )
        )
    else:
        if not from_symbol:
            skipped_asset += 1
        if from_amount is None:
            skipped_amount += 1

    if to_symbol and to_amount is not None:
        to_asset = _get_or_create_crypto_asset(to_symbol)
        results.append(
            Transaction(
                portfolio=integration.portfolio_id,
                asset=to_asset,
                transaction_type="conversion",
                amount=to_amount,
                price=from_amount,
                price_currency=from_symbol or None,
                executed_at=activity.timestamp,
                source="INTEGRATION",
            )
        )
    else:
        if not to_symbol:
            skipped_asset += 1
        if to_amount is None:
            skipped_amount += 1

    return results, skipped_amount, skipped_asset


def _to_decimal(value: Any) -> Optional[Decimal]:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _normalize_list(value: Any) -> Optional[List[str]]:
    if value is None:
        return None
    if isinstance(value, list):
        return [str(v) for v in value if v]
    if isinstance(value, (tuple, set)):
        return [str(v) for v in value if v]
    return [str(value)]


def _normalize_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
