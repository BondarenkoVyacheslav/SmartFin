from typing import List

import strawberry
from strawberry import auto

from app.assets.models import AssetType, Asset


@strawberry.django.type(AssetType)
class AssetTypeType:
    id: auto
    name: auto
    description: auto


@strawberry.django.type(Asset)
class AssetTypeGQL:
    id: auto
    name: auto
    symbol: auto
    asset_type: AssetTypeType
    market_url: auto
    currency: auto


@strawberry.type
class AssetQueries:
    asset_types: List[AssetTypeType] = strawberry.django.field()
    assets: List[AssetTypeGQL] = strawberry.django.field()