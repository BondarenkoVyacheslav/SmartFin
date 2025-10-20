from typing import Optional, List
from .models import PortfolioSnapshot

def get_latest_snapshot(portfolio_id: int) -> Optional[PortfolioSnapshot]:
    return (PortfolioSnapshot.objects
            .filter(portfolio_id=portfolio_id)
            .order_by("-as_of")
            .first())

def get_snapshots_range(portfolio_id: int, limit: int=30) -> List[PortfolioSnapshot]:
    return list(PortfolioSnapshot.objects.filter(portfolio_id=portfolio_id).order_by("-as_of")[:limit])
