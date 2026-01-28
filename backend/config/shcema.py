import strawberry
from app.analytics.schema import PortfolioSnapshotsQueries
from app.assets.schema import AssetQuery, AssetMutation
from app.integrations.schema import IntegrationQuery, IntegrationMutation
from app.portfolio.schema import PortfolioQuery, PortfolioMutation
from app.transaction.schema import TransactionQuery, TransactionMutation
from app.llm.schema import LLMChatQuery, LLMChatMutation


@strawberry.type
class Query(
    AssetQuery,
    PortfolioQuery,
    TransactionQuery,
    PortfolioSnapshotsQueries,
    LLMChatQuery,
    IntegrationQuery,
):
    pass


@strawberry.type
class Mutation(
    AssetMutation,
    PortfolioMutation,
    TransactionMutation,
    LLMChatMutation,
    IntegrationMutation,
):
    pass


schema = strawberry.Schema(query=Query, mutation=Mutation)
