import strawberry
from .models import Asset, AssetType
from .queries import AssetTypeType, AssetTypeGQL


@strawberry.type
class AssetMutations:
    @strawberry.mutation
    def create_asset_type(self, name: str, description: str | None = None) -> AssetTypeType:
        return AssetType.objects.create(name=name, description=description)

    @strawberry.mutation
    def create_asset(
            self,
            name: str,
            symbol: str,
            asset_type_id: int,
            market_url: str,
            currency: str
    ) -> AssetTypeGQL:
        asset_type = AssetType.objects.get(id=asset_type_id)
        return Asset.objects.create(
            name=name,
            symbol=symbol,
            asset_type=asset_type,
            market_url=market_url,
            currency=currency,
        )
