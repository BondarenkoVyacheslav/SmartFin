import strawberry
from app.assets.schema import AssetQuery, AssetMutation
from app.portfolio.schema import PortfolioQuery, PortfolioMutation
from app.transaction.schema import TransactionQuery, TransactionMutation
from app.account.schema import UserQuery, UserMutation


@strawberry.type
class Query(AssetQuery, PortfolioQuery, TransactionQuery, UserQuery):
    pass


@strawberry.type
class Mutation(AssetMutation, PortfolioMutation, TransactionMutation, UserMutation):
    pass


schema = strawberry.Schema(query=Query, mutation=Mutation)
