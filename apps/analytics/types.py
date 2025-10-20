import strawberry
from gql.scalars import DecimalScalar, DateTimeTZ

@strawberry.type
class PortfolioMetrics:
    portfolio_id: strawberry.ID
    as_of: DateTimeTZ
    total_value: DecimalScalar
    pnl_1d: DecimalScalar
    pnl_7d: DecimalScalar
    pnl_30d: DecimalScalar
