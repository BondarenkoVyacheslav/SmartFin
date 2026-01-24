from datetime import date, timedelta
from decimal import Decimal
from enum import Enum
from typing import List, Optional

import strawberry
from strawberry import auto

from django.db.models import Sum
from django.utils import timezone

from app.analytics.models import (
    PortfolioAssetDailySnapshot,
    PortfolioDailySnapshot,
    PortfolioPositionDaily,
    PortfolioValuationDaily,
)
from backend.app.analytics.utils import _build_fx_rates, _normalize_currency, _to_decimal
from app.assets.models import AssetType
from app.assets.queries import AssetTypeGQL
from app.portfolio.models import Portfolio
from app.portfolio.queries import PortfolioType
from app.transaction.models import Transaction


@strawberry.django.type(PortfolioDailySnapshot)
class PortfolioDailySnapshotGQL:
    id: auto
    portfolio: PortfolioType
    snapshot_date: auto
    capital: auto
    created_at: auto
    margin: auto

@strawberry.django.type(PortfolioAssetDailySnapshot)
class PortfolioAssetDailySnapshotGQL:
    id: auto
    portfolio: PortfolioType
    asset_type: AssetTypeGQL
    snapshot_date: auto
    snapshot: auto
    margin: auto


@strawberry.django.type(PortfolioValuationDaily)
class PortfolioValuationDailyGQL:
    id: auto
    portfolio: PortfolioType
    snapshot_date: auto
    base_currency: auto
    value_base: auto
    net_flow_base: auto
    pnl_base: auto
    created_at: auto


@strawberry.django.type(PortfolioPositionDaily)
class PortfolioPositionDailyGQL:
    id: auto
    portfolio: PortfolioType
    asset: AssetTypeGQL
    snapshot_date: auto
    quantity: auto
    price_base: auto
    value_base: auto
    created_at: auto


@strawberry.type
class PortfolioDailyPnlGQL:
    portfolio_id: int
    snapshot_date: date
    base_currency: str
    value_base: float
    prev_value_base: float
    net_flow_base: float
    pnl_base: float


@strawberry.type
class PortfolioPeriodPnlGQL:
    portfolio_id: int
    date_from: date
    date_to: date
    base_currency: str
    value_start_base: float
    value_end_base: float
    net_flow_base: float
    pnl_base: float


@strawberry.enum
class AssetTypePnlPeriod(Enum):
    DAY = "1d"
    WEEK = "7d"
    MONTH = "30d"
    YEAR = "1y"


@strawberry.type
class PortfolioAssetTypePeriodPnlGQL:
    portfolio_id: int
    asset_type_id: int
    asset_type_code: str
    date_from: date
    date_to: date
    base_currency: str
    value_start_base: float
    value_end_base: float
    net_flow_base: float
    pnl_base: float
    pnl_percent: Optional[float]


@strawberry.type
class PortfolioTopPositionPnlGQL:
    portfolio_id: int
    snapshot_date: date
    base_currency: str
    asset: AssetTypeGQL
    quantity: float
    price_base: Optional[float]
    value_base: Optional[float]
    prev_value_base: Optional[float]
    cash_flow_base: Optional[float]
    pnl_base: Optional[float]
    growth_percent: Optional[float]


@strawberry.type
class PortfolioAssetTypeTopPositionsGQL:
    portfolio_id: int
    snapshot_date: date
    base_currency: str
    asset_type_id: int
    asset_type_code: str
    asset_type_name: str
    positions: List[PortfolioTopPositionPnlGQL]


@strawberry.type
class PortfolioDailyBestWorstPositionsGQL:
    portfolio_id: int
    snapshot_date: date
    base_currency: str
    best_positions: List[PortfolioTopPositionPnlGQL]
    worst_positions: List[PortfolioTopPositionPnlGQL]


def _require_portfolio(info, portfolio_id: int) -> Portfolio:
    user = info.context.request.user
    if not user or not user.is_authenticated:
        raise ValueError("Authentication required")
    try:
        portfolio = Portfolio.objects.only("id", "user_id").get(id=portfolio_id)
    except Portfolio.DoesNotExist as exc:
        raise ValueError("Portfolio not found") from exc
    if portfolio.user_id != user.id:
        raise ValueError("Portfolio not found")
    return portfolio


def _resolve_asset_type(asset_type_id: Optional[int], asset_type_code: Optional[str]) -> AssetType:
    if asset_type_id is not None:
        try:
            return AssetType.objects.get(id=asset_type_id)
        except AssetType.DoesNotExist as exc:
            raise ValueError("Asset type not found") from exc
    if asset_type_code:
        try:
            return AssetType.objects.get(code=asset_type_code)
        except AssetType.DoesNotExist as exc:
            raise ValueError("Asset type not found") from exc
    raise ValueError("asset_type_id or asset_type_code is required")


def _asset_type_net_flow_base(
    portfolio_id: int,
    asset_type_id: int,
    date_from: date,
    date_to: date,
    base_currency: str,
) -> Decimal:
    flow_types = ("deposit", "withdrawal")
    flow_qs = Transaction.objects.filter(
        portfolio_id=portfolio_id,
        transaction_type__in=flow_types,
        asset__asset_type_id=asset_type_id,
    )
    flow_executed = list(
        flow_qs.filter(executed_at__date__gte=date_from, executed_at__date__lte=date_to)
    )
    flow_created = list(
        flow_qs.filter(executed_at__isnull=True, created_at__date__gte=date_from, created_at__date__lte=date_to)
    )
    flows = flow_executed + flow_created

    fx_currencies = {
        _normalize_currency(tx.asset.currency)
        for tx in flows
        if _normalize_currency(tx.asset.currency) not in {None, base_currency}
    }
    fx_rates = _build_fx_rates(fx_currencies, base_currency)

    def resolve_rate(currency: Optional[str]) -> Optional[Decimal]:
        normalized = _normalize_currency(currency)
        if not normalized:
            return None
        if normalized == base_currency:
            return Decimal("1")
        return fx_rates.get(f"{normalized}/{base_currency}".upper())

    net_flow = Decimal("0")
    for tx in flows:
        rate = resolve_rate(tx.asset.currency)
        amount = _to_decimal(tx.amount) or Decimal("0")
        if rate is None:
            continue
        signed_amount = amount if tx.transaction_type == "deposit" else -amount
        net_flow += signed_amount * rate

    return net_flow


def _positions_cash_flow_base(
    portfolio_id: int,
    asset_ids: List[int],
    snapshot_date: date,
    base_currency: str,
) -> dict[int, Decimal]:
    flow_types = ("deposit", "withdrawal", "buy", "sell")
    flow_qs = Transaction.objects.filter(
        portfolio_id=portfolio_id,
        transaction_type__in=flow_types,
        asset_id__in=asset_ids,
    )
    flow_executed = list(flow_qs.filter(executed_at__date=snapshot_date))
    flow_created = list(flow_qs.filter(executed_at__isnull=True, created_at__date=snapshot_date))
    flows = flow_executed + flow_created

    fx_currencies = set()
    for tx in flows:
        if tx.price is None and tx.transaction_type in {"deposit", "withdrawal"}:
            currency = _normalize_currency(tx.asset.currency)
        else:
            currency = _normalize_currency(tx.price_currency) or _normalize_currency(tx.asset.currency)
        if currency not in {None, base_currency}:
            fx_currencies.add(currency)
    fx_rates = _build_fx_rates(fx_currencies, base_currency)

    def resolve_rate(currency: Optional[str]) -> Optional[Decimal]:
        normalized = _normalize_currency(currency)
        if not normalized:
            return None
        if normalized == base_currency:
            return Decimal("1")
        return fx_rates.get(f"{normalized}/{base_currency}".upper())

    cashflows: dict[int, Decimal] = {asset_id: Decimal("0") for asset_id in asset_ids}
    inflow_types = {"deposit", "buy"}
    for tx in flows:
        amount = _to_decimal(tx.amount) or Decimal("0")
        if tx.price is None and tx.transaction_type in {"deposit", "withdrawal"}:
            value = amount
            currency = _normalize_currency(tx.asset.currency)
        else:
            price = _to_decimal(tx.price)
            if price is None:
                continue
            value = amount * price
            currency = _normalize_currency(tx.price_currency) or _normalize_currency(tx.asset.currency)

        rate = resolve_rate(currency)
        if rate is None:
            continue
        signed_value = value if tx.transaction_type in inflow_types else -value
        cashflows[tx.asset_id] = cashflows.get(tx.asset_id, Decimal("0")) + signed_value * rate

    return cashflows


@strawberry.type
class PortfolioSnapshotsQueries:
    portfolio_daily_snapshot: List[PortfolioDailySnapshotGQL] = strawberry.django.field()
    portfolio_asset_daily_snapshot: List[PortfolioAssetDailySnapshotGQL] = strawberry.django.field()
    portfolio_valuation_daily: List[PortfolioValuationDailyGQL] = strawberry.django.field()
    portfolio_position_daily: List[PortfolioPositionDailyGQL] = strawberry.django.field()

    @strawberry.field
    def portfolio_daily_pnl(self, info, portfolio_id: int, snapshot_date: date) -> PortfolioDailyPnlGQL:
        _require_portfolio(info, portfolio_id)
        valuation = PortfolioValuationDaily.objects.filter(
            portfolio_id=portfolio_id,
            snapshot_date=snapshot_date,
        ).first()
        if valuation is None:
            raise ValueError("Snapshot not found")

        prev_snapshot = PortfolioValuationDaily.objects.filter(
            portfolio_id=portfolio_id,
            snapshot_date=snapshot_date - timedelta(days=1),
        ).first()
        prev_value = prev_snapshot.value_base if prev_snapshot else Decimal("0")

        return PortfolioDailyPnlGQL(
            portfolio_id=portfolio_id,
            snapshot_date=snapshot_date,
            base_currency=valuation.base_currency,
            value_base=float(valuation.value_base),
            prev_value_base=float(prev_value),
            net_flow_base=float(valuation.net_flow_base),
            pnl_base=float(valuation.pnl_base),
        )

    @strawberry.field
    def portfolio_period_pnl(
        self,
        info,
        portfolio_id: int,
        date_from: date,
        date_to: date,
    ) -> PortfolioPeriodPnlGQL:
        if date_to < date_from:
            raise ValueError("date_to must be >= date_from")
        _require_portfolio(info, portfolio_id)

        end_snapshot = PortfolioValuationDaily.objects.filter(
            portfolio_id=portfolio_id,
            snapshot_date=date_to,
        ).first()
        if end_snapshot is None:
            raise ValueError("Snapshot not found")

        start_snapshot = PortfolioValuationDaily.objects.filter(
            portfolio_id=portfolio_id,
            snapshot_date=date_from - timedelta(days=1),
        ).first()
        start_value = start_snapshot.value_base if start_snapshot else Decimal("0")

        flows = (
            PortfolioValuationDaily.objects.filter(
                portfolio_id=portfolio_id,
                snapshot_date__gte=date_from,
                snapshot_date__lte=date_to,
            )
            .aggregate(total=Sum("net_flow_base"))
        )
        net_flow = flows.get("total") or Decimal("0")

        pnl_base = end_snapshot.value_base - start_value - net_flow

        return PortfolioPeriodPnlGQL(
            portfolio_id=portfolio_id,
            date_from=date_from,
            date_to=date_to,
            base_currency=end_snapshot.base_currency,
            value_start_base=float(start_value),
            value_end_base=float(end_snapshot.value_base),
            net_flow_base=float(net_flow),
            pnl_base=float(pnl_base),
        )

    @strawberry.field
    def portfolio_asset_type_period_pnl(
        self,
        info,
        portfolio_id: int,
        period: AssetTypePnlPeriod,
        asset_type_id: Optional[int] = None,
        asset_type_code: Optional[str] = None,
        date_to: Optional[date] = None,
    ) -> PortfolioAssetTypePeriodPnlGQL:
        _require_portfolio(info, portfolio_id)
        asset_type = _resolve_asset_type(asset_type_id, asset_type_code)

        date_to = date_to or timezone.localdate()
        period_days = {
            AssetTypePnlPeriod.DAY: 1,
            AssetTypePnlPeriod.WEEK: 7,
            AssetTypePnlPeriod.MONTH: 30,
            AssetTypePnlPeriod.YEAR: 365,
        }[period]
        date_from = date_to - timedelta(days=period_days - 1)

        end_snapshot = PortfolioValuationDaily.objects.filter(
            portfolio_id=portfolio_id,
            snapshot_date=date_to,
        ).first()
        if end_snapshot is None:
            raise ValueError("Snapshot not found")

        end_value = (
            PortfolioPositionDaily.objects.filter(
                portfolio_id=portfolio_id,
                snapshot_date=date_to,
                asset__asset_type_id=asset_type.id,
            )
            .aggregate(total=Sum("value_base"))
            .get("total")
            or Decimal("0")
        )

        start_value = (
            PortfolioPositionDaily.objects.filter(
                portfolio_id=portfolio_id,
                snapshot_date=date_from - timedelta(days=1),
                asset__asset_type_id=asset_type.id,
            )
            .aggregate(total=Sum("value_base"))
            .get("total")
            or Decimal("0")
        )

        net_flow = _asset_type_net_flow_base(
            portfolio_id=portfolio_id,
            asset_type_id=asset_type.id,
            date_from=date_from,
            date_to=date_to,
            base_currency=end_snapshot.base_currency,
        )
        pnl_base = end_value - start_value - net_flow
        pnl_percent = None
        if start_value != 0:
            pnl_percent = float((pnl_base / start_value) * Decimal("100"))

        return PortfolioAssetTypePeriodPnlGQL(
            portfolio_id=portfolio_id,
            asset_type_id=asset_type.id,
            asset_type_code=asset_type.code,
            date_from=date_from,
            date_to=date_to,
            base_currency=end_snapshot.base_currency,
            value_start_base=float(start_value),
            value_end_base=float(end_value),
            net_flow_base=float(net_flow),
            pnl_base=float(pnl_base),
            pnl_percent=pnl_percent,
        )

    @strawberry.field
    def portfolio_top_positions_daily_pnl(
        self,
        info,
        portfolio_id: int,
        snapshot_date: Optional[date] = None,
        limit: int = 10,
    ) -> List[PortfolioTopPositionPnlGQL]:
        _require_portfolio(info, portfolio_id)
        snapshot_date = snapshot_date or timezone.localdate()
        if limit < 1:
            raise ValueError("limit must be >= 1")
        limit = min(limit, 10)

        valuation = PortfolioValuationDaily.objects.filter(
            portfolio_id=portfolio_id,
            snapshot_date=snapshot_date,
        ).first()
        if valuation is None:
            raise ValueError("Snapshot not found")

        positions = list(
            PortfolioPositionDaily.objects.select_related("asset", "asset__asset_type")
            .filter(
                portfolio_id=portfolio_id,
                snapshot_date=snapshot_date,
                value_base__isnull=False,
            )
            .order_by("-value_base")[:limit]
        )

        asset_ids = [p.asset_id for p in positions]
        cashflows = _positions_cash_flow_base(
            portfolio_id=portfolio_id,
            asset_ids=asset_ids,
            snapshot_date=snapshot_date,
            base_currency=valuation.base_currency,
        )
        prev_positions = {
            p.asset_id: p
            for p in PortfolioPositionDaily.objects.filter(
                portfolio_id=portfolio_id,
                snapshot_date=snapshot_date - timedelta(days=1),
                asset_id__in=asset_ids,
            )
        }

        results: List[PortfolioTopPositionPnlGQL] = []
        for position in positions:
            prev = prev_positions.get(position.asset_id)
            prev_value = prev.value_base if prev else None
            curr_value = position.value_base
            cash_flow = cashflows.get(position.asset_id)
            pnl_base = None
            growth_percent = None
            if curr_value is not None and prev_value is not None and cash_flow is not None:
                pnl_base = curr_value - prev_value - cash_flow
                if prev_value != 0:
                    growth_percent = float((pnl_base / prev_value) * Decimal("100"))

            results.append(
                PortfolioTopPositionPnlGQL(
                    portfolio_id=portfolio_id,
                    snapshot_date=snapshot_date,
                    base_currency=valuation.base_currency,
                    asset=position.asset,
                    quantity=float(position.quantity),
                    price_base=float(position.price_base) if position.price_base is not None else None,
                    value_base=float(curr_value) if curr_value is not None else None,
                    prev_value_base=float(prev_value) if prev_value is not None else None,
                    cash_flow_base=float(cash_flow) if cash_flow is not None else None,
                    pnl_base=float(pnl_base) if pnl_base is not None else None,
                    growth_percent=growth_percent,
                )
            )

        return results

    @strawberry.field
    def portfolio_asset_type_top_positions_daily_pnl(
        self,
        info,
        portfolio_id: int,
        snapshot_date: Optional[date] = None,
        limit: int = 10,
    ) -> List[PortfolioAssetTypeTopPositionsGQL]:
        _require_portfolio(info, portfolio_id)
        snapshot_date = snapshot_date or timezone.localdate()
        if limit < 1:
            raise ValueError("limit must be >= 1")
        limit = min(limit, 10)

        valuation = PortfolioValuationDaily.objects.filter(
            portfolio_id=portfolio_id,
            snapshot_date=snapshot_date,
        ).first()
        if valuation is None:
            raise ValueError("Snapshot not found")

        asset_type_ids = list(
            PortfolioPositionDaily.objects.filter(
                portfolio_id=portfolio_id,
                snapshot_date=snapshot_date,
                value_base__isnull=False,
            )
            .values_list("asset__asset_type_id", flat=True)
            .distinct()
        )
        if not asset_type_ids:
            return []

        asset_type_map = {
            asset_type.id: asset_type
            for asset_type in AssetType.objects.filter(id__in=asset_type_ids)
        }

        all_asset_ids: List[int] = []
        positions_by_type: dict[int, List[PortfolioPositionDaily]] = {}
        for asset_type_id in asset_type_ids:
            positions = list(
                PortfolioPositionDaily.objects.select_related("asset", "asset__asset_type")
                .filter(
                    portfolio_id=portfolio_id,
                    snapshot_date=snapshot_date,
                    asset__asset_type_id=asset_type_id,
                    value_base__isnull=False,
                )
                .order_by("-value_base")[:limit]
            )
            positions_by_type[asset_type_id] = positions
            all_asset_ids.extend([p.asset_id for p in positions])

        if not all_asset_ids:
            return []

        cashflows = _positions_cash_flow_base(
            portfolio_id=portfolio_id,
            asset_ids=all_asset_ids,
            snapshot_date=snapshot_date,
            base_currency=valuation.base_currency,
        )
        prev_positions = {
            p.asset_id: p
            for p in PortfolioPositionDaily.objects.filter(
                portfolio_id=portfolio_id,
                snapshot_date=snapshot_date - timedelta(days=1),
                asset_id__in=all_asset_ids,
            )
        }

        results: List[PortfolioAssetTypeTopPositionsGQL] = []
        for asset_type_id in asset_type_ids:
            asset_type = asset_type_map.get(asset_type_id)
            if asset_type is None:
                continue
            positions = positions_by_type.get(asset_type_id, [])
            if not positions:
                continue

            position_items: List[PortfolioTopPositionPnlGQL] = []
            for position in positions:
                prev = prev_positions.get(position.asset_id)
                prev_value = prev.value_base if prev else None
                curr_value = position.value_base
                cash_flow = cashflows.get(position.asset_id)
                pnl_base = None
                growth_percent = None
                if curr_value is not None and prev_value is not None and cash_flow is not None:
                    pnl_base = curr_value - prev_value - cash_flow
                    if prev_value != 0:
                        growth_percent = float((pnl_base / prev_value) * Decimal("100"))

                position_items.append(
                    PortfolioTopPositionPnlGQL(
                        portfolio_id=portfolio_id,
                        snapshot_date=snapshot_date,
                        base_currency=valuation.base_currency,
                        asset=position.asset,
                        quantity=float(position.quantity),
                        price_base=float(position.price_base) if position.price_base is not None else None,
                        value_base=float(curr_value) if curr_value is not None else None,
                        prev_value_base=float(prev_value) if prev_value is not None else None,
                        cash_flow_base=float(cash_flow) if cash_flow is not None else None,
                        pnl_base=float(pnl_base) if pnl_base is not None else None,
                        growth_percent=growth_percent,
                    )
                )

            results.append(
                PortfolioAssetTypeTopPositionsGQL(
                    portfolio_id=portfolio_id,
                    snapshot_date=snapshot_date,
                    base_currency=valuation.base_currency,
                    asset_type_id=asset_type.id,
                    asset_type_code=asset_type.code,
                    asset_type_name=asset_type.name,
                    positions=position_items,
                )
            )

        return results

    @strawberry.field
    def portfolio_daily_best_worst_positions(
        self,
        info,
        portfolio_id: int,
        snapshot_date: Optional[date] = None,
        limit: int = 10,
    ) -> PortfolioDailyBestWorstPositionsGQL:
        _require_portfolio(info, portfolio_id)
        snapshot_date = snapshot_date or timezone.localdate()
        if limit < 1:
            raise ValueError("limit must be >= 1")
        limit = min(limit, 10)

        valuation = PortfolioValuationDaily.objects.filter(
            portfolio_id=portfolio_id,
            snapshot_date=snapshot_date,
        ).first()
        if valuation is None:
            raise ValueError("Snapshot not found")

        positions = list(
            PortfolioPositionDaily.objects.select_related("asset", "asset__asset_type")
            .filter(
                portfolio_id=portfolio_id,
                snapshot_date=snapshot_date,
                value_base__isnull=False,
            )
        )
        asset_ids = [p.asset_id for p in positions]
        cashflows = _positions_cash_flow_base(
            portfolio_id=portfolio_id,
            asset_ids=asset_ids,
            snapshot_date=snapshot_date,
            base_currency=valuation.base_currency,
        )
        prev_positions = {
            p.asset_id: p
            for p in PortfolioPositionDaily.objects.filter(
                portfolio_id=portfolio_id,
                snapshot_date=snapshot_date - timedelta(days=1),
                asset_id__in=asset_ids,
            )
        }

        scored: List[PortfolioTopPositionPnlGQL] = []
        for position in positions:
            prev = prev_positions.get(position.asset_id)
            prev_value = prev.value_base if prev else None
            curr_value = position.value_base
            cash_flow = cashflows.get(position.asset_id)
            pnl_base = None
            growth_percent = None
            if curr_value is not None and prev_value is not None and cash_flow is not None:
                pnl_base = curr_value - prev_value - cash_flow
                if prev_value != 0:
                    growth_percent = float((pnl_base / prev_value) * Decimal("100"))

            scored.append(
                PortfolioTopPositionPnlGQL(
                    portfolio_id=portfolio_id,
                    snapshot_date=snapshot_date,
                    base_currency=valuation.base_currency,
                    asset=position.asset,
                    quantity=float(position.quantity),
                    price_base=float(position.price_base) if position.price_base is not None else None,
                    value_base=float(curr_value) if curr_value is not None else None,
                    prev_value_base=float(prev_value) if prev_value is not None else None,
                    cash_flow_base=float(cash_flow) if cash_flow is not None else None,
                    pnl_base=float(pnl_base) if pnl_base is not None else None,
                    growth_percent=growth_percent,
                )
            )

        scored_with_pnl = [item for item in scored if item.pnl_base is not None]
        best_positions = sorted(scored_with_pnl, key=lambda item: item.pnl_base, reverse=True)[:limit]
        worst_positions = sorted(scored_with_pnl, key=lambda item: item.pnl_base)[:limit]

        return PortfolioDailyBestWorstPositionsGQL(
            portfolio_id=portfolio_id,
            snapshot_date=snapshot_date,
            base_currency=valuation.base_currency,
            best_positions=best_positions,
            worst_positions=worst_positions,
        )
