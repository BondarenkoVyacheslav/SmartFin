import strawberry
from strawberry.types import Info
from typing import List, Optional
from asgiref.sync import sync_to_async
from gql.context import RequestContext
from gql.directives import IsAuthenticated
from .types import PortfolioType, PositionType, TradeType, CreatePortfolioInput, AddTradeInput
from .selectors import get_portfolios_by_user, get_portfolio_by_id_for_user, get_trades_for_portfolio
from .services import create_portfolio, add_trade

@strawberry.type
class Query:
    @strawberry.field(permission_classes=[IsAuthenticated])
    async def my_portfolios(self, info: Info[RequestContext, None]) -> List[PortfolioType]:
        user = info.context.user
        items = await sync_to_async(get_portfolios_by_user)(user.id)
        return [PortfolioType(id=str(p.id), name=p.name, base_currency=p.base_currency) for p in items]

    @strawberry.field(permission_classes=[IsAuthenticated])
    async def portfolio(self, info: Info[RequestContext, None], id: strawberry.ID) -> Optional[PortfolioType]:
        user = info.context.user
        pf = await sync_to_async(get_portfolio_by_id_for_user)(user.id, int(id))
        if not pf:
            return None
        return PortfolioType(id=str(pf.id), name=pf.name, base_currency=pf.base_currency)

    @strawberry.field(permission_classes=[IsAuthenticated])
    async def trades(self, info: Info[RequestContext, None], portfolio_id: strawberry.ID) -> List[TradeType]:
        items = await sync_to_async(get_trades_for_portfolio)(int(portfolio_id))
        return [TradeType(id=str(t.id), asset_id=t.asset_id, qty=t.qty, price=t.price, ts=t.ts) for t in items]

@strawberry.type
class Mutation:
    @strawberry.mutation(permission_classes=[IsAuthenticated])
    async def create_portfolio(self, info: Info[RequestContext, None], input: CreatePortfolioInput) -> PortfolioType:
        user = info.context.user
        pf = await sync_to_async(create_portfolio)(user.id, input.name, input.base_currency)
        return PortfolioType(id=str(pf.id), name=pf.name, base_currency=pf.base_currency)

    @strawberry.mutation(permission_classes=[IsAuthenticated])
    async def add_trade(self, info: Info[RequestContext, None], input: AddTradeInput) -> TradeType:
        user = info.context.user
        t = await sync_to_async(add_trade)(
            user.id, int(input.portfolio_id), input.asset_id, input.qty, input.price, input.ts
        )
        return TradeType(id=str(t.id), asset_id=t.asset_id, qty=t.qty, price=t.price, ts=t.ts)

Subscription = None
