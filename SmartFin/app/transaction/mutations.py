import strawberry
from .models import Transaction
from app.portfolio.models import Portfolio
from app.assets.models import Asset
from .queries import TransactionType


@strawberry.type
class TransactionMutations:
    @strawberry.mutation
    def create_transaction(self, portfolio_id: int, asset_id: int, transaction_type: str, amount: float,
                           price: float = None) -> TransactionType:
        portfolio = Portfolio.objects.get(id=portfolio_id)
        asset = Asset.objects.get(id=asset_id)
        return Transaction.objects.create(
            portfolio=portfolio,
            asset=asset,
            transaction_type=transaction_type,
            amount=amount,
            price=price
        )
