from decimal import Decimal
from datetime import datetime, timezone
from django.db import transaction
from .models import PortfolioSnapshot

# Заглушки — сюда подмешаешь реальные селекторы marketdata/portfolios:
def _compute_total_value(portfolio_id: int) -> Decimal:
    # 1) получаем все позиции портфеля
    # 2) для каждой тянем последнюю цену (в валюте портфеля)
    # 3) суммируем qty * price
    return Decimal("0")

def _compute_pnl(portfolio_id: int, days: int) -> Decimal:
    # рассчитываешь PnL за окно N дней
    return Decimal("0")

@transaction.atomic
def materialize_snapshot(portfolio_id: int, as_of: datetime | None = None) -> PortfolioSnapshot:
    if as_of is None:
        as_of = datetime.now(timezone.utc)
    snap = PortfolioSnapshot.objects.create(
        portfolio_id=portfolio_id,
        as_of=as_of,
        total_value=_compute_total_value(portfolio_id),
        pnl_1d=_compute_pnl(portfolio_id, 1),
        pnl_7d=_compute_pnl(portfolio_id, 7),
        pnl_30d=_compute_pnl(portfolio_id, 30),
    )
    return snap
