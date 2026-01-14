import strawberry
from strawberry import auto
from typing import List
from app.analytics.models import PortfolioDailySnapshot, PortfolioAssetDailySnapshot
from app.portfolio.queries import PortfolioType
from app.assets.queries import AssetTypeGQL


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

@strawberry.type
class PortfolioSnapshotsQueries:
    portfolio_daily_snapshot: List[PortfolioDailySnapshotGQL] = strawberry.django.field()
    portfolio_asset_daily_snapshot: List[PortfolioAssetDailySnapshotGQL] = strawberry.django.field()
