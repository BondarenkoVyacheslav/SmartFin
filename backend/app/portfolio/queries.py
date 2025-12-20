import strawberry
from typing import List
from strawberry import auto
from app.assets.queries import AssetTypeGQL
from .models import Portfolio, PortfolioAsset


@strawberry.django.type(Portfolio)
class PortfolioType:
    id: auto
    user_id: auto
    name: auto
    created_at: auto
    portfolio_asset: List[AssetTypeGQL]


@strawberry.django.type(PortfolioAsset)
class PortfolioAssetType:
    id: auto
    asset: AssetTypeGQL
    portfolio: PortfolioType
    quantity: auto
    avg_price: auto
    updated_at: auto

@strawberry.type
class PortfolioQueries:
    portfolios: List[PortfolioType] = strawberry.django.field()
    portfolio_assets: List[PortfolioAssetType] = strawberry.django.field()
