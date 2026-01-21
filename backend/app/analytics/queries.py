from datetime import date, timedelta
from decimal import Decimal
from typing import List

import strawberry
from strawberry import auto

from app.analytics.models import (
    PortfolioAssetDailySnapshot,
    PortfolioDailySnapshot,
    PortfolioPositionDaily,
    PortfolioValuationDaily,
)
from app.assets.queries import AssetTypeGQL
from app.portfolio.models import Portfolio
from app.portfolio.queries import PortfolioType


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
