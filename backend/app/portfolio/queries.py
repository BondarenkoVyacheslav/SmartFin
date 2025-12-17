import strawberry
from typing import List
from django.db.models import DecimalField, ExpressionWrapper, F, Sum
from django.db.models.functions import Coalesce
from strawberry import auto
from app.assets.models import AssetType
from app.assets.queries import AssetTypeGQL, AssetTypeType
from .models import Portfolio, PortfolioAsset

from decimal import Decimal


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
    update_at: auto


@strawberry.type
class PortfolioAssetSummaryType:
    asset_type: AssetTypeType
    total_quantity: float
    total_value: float
    percentage: float


@strawberry.type
class PortfolioAssetsSummary:
    portfolio_asset_summary_types: List[PortfolioAssetSummaryType]
    total_quantity: float
    total_value: float
    currency: str


@strawberry.type
class PortfolioQueries:
    portfolios: List[PortfolioType] = strawberry.django.field()
    portfolio_assets: List[PortfolioAssetType] = strawberry.django.field()

    @strawberry.field
    def portfolio_asset_summary(self, portfolio_id: int) -> PortfolioAssetsSummary:
        """
        Returns grouped totals for the given portfolio:
        - total quantity per asset type
        - total value in the asset's currency (quantity * avg_price)
        - share of the portfolio by value in percent
        """
        value_expression = ExpressionWrapper(
            F("quantity") * Coalesce(F("avg_price"), Decimal('0.0')),
            output_field=DecimalField(max_digits=38, decimal_places=8)
        )


        aggregates = list(
            PortfolioAsset.objects
            .filter(portfolio_id=portfolio_id)
            .values("asset__asset_type_id")
            .annotate(
                total_quantity=Coalesce(Sum("quantity"), Decimal("0")),
                total_value=Coalesce(Sum(value_expression), Decimal("0")),
            )
        )

        portfolio_total = sum((row["total_value"] for row in aggregates), Decimal("0"))
        asset_types = AssetType.objects.in_bulk([row["asset__asset_type_id"] for row in aggregates])
        currency = Portfolio.objects.get(id=portfolio_id).base_currency

        return PortfolioAssetsSummary(
                portfolio_asset_summary_types=[
                    PortfolioAssetSummaryType(
                        asset_type=asset_types.get(row["asset__asset_type_id"]),
                        total_quantity=float(row["total_quantity"]),
                        total_value=float(row["total_value"]),
                        percentage=float((row["total_value"] / portfolio_total * Decimal("100")) if portfolio_total else Decimal("0")),
                    )
                    for row in aggregates
                ],
                total_quantity=float(sum(row["total_quantity"] for row in aggregates)),
                total_value=float(portfolio_total),
                currency=currency,
            )