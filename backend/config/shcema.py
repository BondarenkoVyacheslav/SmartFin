import strawberry
from app.analytics.schema import PortfolioSnapshotsQueries
from app.assets.schema import AssetQuery, AssetMutation
from app.portfolio.schema import PortfolioQuery, PortfolioMutation
from app.transaction.schema import TransactionQuery, TransactionMutation


@strawberry.type
class Query(AssetQuery, PortfolioQuery, TransactionQuery, PortfolioSnapshotsQueries):
    pass


@strawberry.type
class Mutation(AssetMutation, PortfolioMutation, TransactionMutation):
    pass


schema = strawberry.Schema(query=Query, mutation=Mutation)
