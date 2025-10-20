from decimal import Decimal
from django.db import transaction
from .models import Portfolio, Position, Trade

@transaction.atomic
def create_portfolio(user_id: int, name: str, base_currency: str="USD") -> Portfolio:
    return Portfolio.objects.create(user_id=user_id, name=name, base_currency=base_currency)

def _recalc_cost_basis(old_qty: Decimal, old_cb: Decimal, trade_qty: Decimal, trade_price: Decimal) -> tuple[Decimal, Decimal]:
    """возвращает (new_qty, new_cost_basis)"""
    new_qty = old_qty + trade_qty
    if new_qty == 0:
        return Decimal(0), Decimal(0)
    if trade_qty > 0:
        total_cost = old_cb * old_qty + trade_price * trade_qty
        return new_qty, total_cost / new_qty
    # продажа: qty уменьшается, cost_basis не меняем (FIFO/AVG — выбери свою политику)
    return new_qty, old_cb

@transaction.atomic
def add_trade(user_id: int, portfolio_id: int, asset_id: int, qty: Decimal, price: Decimal, ts) -> Trade:
    # проверка владения портфелем
    pf = Portfolio.objects.select_for_update().get(id=portfolio_id, user_id=user_id)

    trade = Trade.objects.create(
        portfolio_id=pf.id, asset_id=asset_id, qty=qty, price=price, ts=ts
    )
    pos, _ = Position.objects.select_for_update().get_or_create(portfolio_id=pf.id, asset_id=asset_id)
    pos.qty, pos.cost_basis = _recalc_cost_basis(pos.qty, pos.cost_basis, qty, price)
    pos.save()

    from django.db import transaction as tx
    tx.on_commit(lambda: None)  # тут можно дернуть пересчёт метрик/событие
    return trade
