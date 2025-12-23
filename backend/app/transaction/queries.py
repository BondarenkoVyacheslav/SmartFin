import strawberry
from typing import List
from strawberry import auto
from .models import Transaction
from app.assets.queries import AssetTypeGQL
from app.portfolio.queries import PortfolioType


@strawberry.django.type(Transaction)
class TransactionType:
    id: auto
    portfolio: PortfolioType
    asset: AssetTypeGQL
    transaction_type: auto
    amount: auto
    price: auto
    price_currency: auto
    created_at: auto


@strawberry.type
class TransactionQueries:
    transactions: List[TransactionType] = strawberry.django.field()
