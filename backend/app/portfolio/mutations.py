import strawberry
from .models import Portfolio
from app.assets.models import Asset
from app.portfolio.models import PortfolioAsset
from .queries import PortfolioType, PortfolioAssetType


@strawberry.type
class PortfolioMutations:
    @strawberry.mutation
    def create_portfolio(self, user_id: int, name: str) -> PortfolioType:
        return Portfolio.objects.create(user_id=user_id, name=name)

    @strawberry.mutation
    def add_asset_to_portfolio(self, portfolio_id: int, asset_id: int, quantity: float,
                               avg_price: float, avg_price_currency: str = "USD") -> PortfolioAssetType:
        portfolio = Portfolio.objects.get(id=portfolio_id)
        asset = Asset.objects.get(id=asset_id)
        return PortfolioAsset.objects.create(portfolio=portfolio, asset=asset, quantity=quantity, avg_price=avg_price,
                                             avg_price_currency=avg_price_currency)
