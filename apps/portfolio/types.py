import strawberry
from typing import Optional, List
from decimal import Decimal
from gql.scalars import DecimalScalar, DateTimeTZ

@strawberry.type
class TradeType:
    id: strawberry.ID
    asset_id: int
    qty: DecimalScalar
    price: DecimalScalar
    ts: DateTimeTZ

@strawberry.type
class PositionType:
    asset_id: int
    qty: DecimalScalar
    cost_basis: DecimalScalar
    updated_at: DateTimeTZ

@strawberry.type
class PortfolioType:
    id: strawberry.ID
    name: str
    base_currency: str

@strawberry.input
class CreatePortfolioInput:
    name: str
    base_currency: str = "USD"

@strawberry.input
class AddTradeInput:
    portfolio_id: strawberry.ID
    asset_id: int
    qty: DecimalScalar
    price: DecimalScalar
    ts: DateTimeTZ
