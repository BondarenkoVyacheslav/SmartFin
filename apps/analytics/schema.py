import strawberry
from strawberry.types import Info
from typing import Optional
from asgiref.sync import sync_to_async
from gql.context import RequestContext
from gql.directives import IsAuthenticated
from .types import PortfolioMetrics
from .selectors import get_latest_snapshot
from .services import materialize_snapshot

def _map_snap(s) -> PortfolioMetrics:
    return PortfolioMetrics(
        portfolio_id=str(s.portfolio_id),
        as_of=s.as_of,
        total_value=s.total_value,
        pnl_1d=s.pnl_1d,
        pnl_7d=s.pnl_7d,
        pnl_30d=s.pnl_30d,
    )

@strawberry.type
class Query:
    @strawberry.field(permission_classes=[IsAuthenticated])
    async def portfolio_metrics(self, info: Info[RequestContext, None], portfolio_id: strawberry.ID) -> Optional[PortfolioMetrics]:
        snap = await sync_to_async(get_latest_snapshot)(int(portfolio_id))
        return _map_snap(snap) if snap else None

@strawberry.type
class Mutation:
    @strawberry.mutation(permission_classes=[IsAuthenticated])
    async def refresh_portfolio_metrics(self, info: Info[RequestContext, None], portfolio_id: strawberry.ID) -> PortfolioMetrics:
        snap = await sync_to_async(materialize_snapshot)(int(portfolio_id))
        return _map_snap(snap)

Subscription = None
