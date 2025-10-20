from typing import Iterable, List, Optional
from django.db.models import Prefetch
from .models import Portfolio, Position, Trade

def get_portfolios_by_user(user_id: int) -> List[Portfolio]:
    return list(Portfolio.objects.filter(user_id=user_id).order_by("id"))

def get_portfolio_by_id_for_user(user_id: int, portfolio_id: int) -> Optional[Portfolio]:
    try:
        return (Portfolio.objects
                .filter(user_id=user_id, id=portfolio_id)
                .get())
    except Portfolio.DoesNotExist:
        return None

def get_positions_by_portfolio_ids(ids: Iterable[int]) -> List[List[Position]]:
    qs = Position.objects.filter(portfolio_id__in=list(ids)).order_by("asset_id")
    by_portfolio = {}
    for p in qs:
        by_portfolio.setdefault(p.portfolio_id, []).append(p)
    return [by_portfolio.get(pid, []) for pid in ids]

def get_trades_for_portfolio(portfolio_id: int) -> List[Trade]:
    return list(Trade.objects.filter(portfolio_id=portfolio_id).order_by("-ts"))
