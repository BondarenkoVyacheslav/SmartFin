# graphql/schema.py (вариант без автопоиска)
import strawberry
from strawberry.tools import merge_types
from apps.account.schema import Query as AccountQ, Mutation as AccountM
from apps.portfolio.schema import Query as PortfolioQ, Mutation as PortfolioM
from apps.analytics.schema import Query as AnalyticsQ, Mutation as AnalyticsM

Query = merge_types("Query", (AccountQ, PortfolioQ, AnalyticsQ))
Mutation = merge_types("Mutation", (AccountM, PortfolioM, AnalyticsM))
schema = strawberry.Schema(query=Query, mutation=Mutation)
