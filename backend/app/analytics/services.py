from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Iterable, Optional

from django.db import transaction as db_transaction

from app.marketdata import market_data_api
from app.portfolio.models import Portfolio, PortfolioAsset
from app.transaction.models import Transaction

from .models import PortfolioPositionDaily, PortfolioValuationDaily


def _normalize_currency(code: Optional[str]) -> Optional[str]:
    if not code:
        return None
    return code.strip().upper()


def _to_decimal(value: Optional[float | Decimal]) -> Optional[Decimal]:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _build_fx_rates(currencies: Iterable[str], base_currency: str) -> dict[str, Decimal]:
    pairs = [f"{ccy}/{base_currency}" for ccy in sorted(set(currencies))]
    if not pairs:
        return {}
    rates = market_data_api.get_fx_rates(pairs) or {}
    normalized: dict[str, Decimal] = {}
    for pair, rate in rates.items():
        rate_dec = _to_decimal(rate)
        if rate_dec is None:
            continue
        normalized[pair.upper()] = rate_dec
    return normalized


def build_portfolio_daily_snapshot(portfolio_id: int, snapshot_date: date) -> PortfolioValuationDaily:
    portfolio = Portfolio.objects.select_related().get(id=portfolio_id)
    base_currency = _normalize_currency(portfolio.base_currency) or "USD"

    positions = list(
        PortfolioAsset.objects.select_related("asset")
        .filter(portfolio_id=portfolio_id)
    )

    symbols = [p.asset.symbol for p in positions if p.asset.symbol]
    quotes = market_data_api.get_quotes_by_symbols(symbols)
    price_by_symbol = {
        (q.symbol or "").strip().upper(): _to_decimal(q.last)
        for q in quotes
        if q.symbol
    }

    flow_types = ("deposit", "withdrawal")
    flow_qs = Transaction.objects.filter(
        portfolio_id=portfolio_id,
        transaction_type__in=flow_types,
    )
    flow_executed = list(flow_qs.filter(executed_at__date=snapshot_date))
    flow_created = list(flow_qs.filter(executed_at__isnull=True, created_at__date=snapshot_date))
    flows = flow_executed + flow_created

    fx_currencies = {
        _normalize_currency(p.asset.currency)
        for p in positions
        if _normalize_currency(p.asset.currency) not in {None, base_currency}
    }
    fx_currencies.update(
        {
            _normalize_currency(t.asset.currency)
            for t in flows
            if _normalize_currency(t.asset.currency) not in {None, base_currency}
        }
    )
    fx_rates = _build_fx_rates(fx_currencies, base_currency)

    def resolve_rate(currency: Optional[str]) -> Optional[Decimal]:
        normalized = _normalize_currency(currency)
        if not normalized:
            return None
        if normalized == base_currency:
            return Decimal("1")
        return fx_rates.get(f"{normalized}/{base_currency}".upper())

    total_value = Decimal("0")
    with db_transaction.atomic():
        for position in positions:
            asset = position.asset
            quantity = _to_decimal(position.quantity) or Decimal("0")
            currency = _normalize_currency(asset.currency)
            rate = resolve_rate(currency)
            price = price_by_symbol.get((asset.symbol or "").strip().upper())

            price_base: Optional[Decimal] = None
            value_base: Optional[Decimal] = None
            if price is not None and rate is not None:
                price_base = price * rate
                value_base = quantity * price_base
                total_value += value_base

            PortfolioPositionDaily.objects.update_or_create(
                portfolio_id=portfolio_id,
                asset_id=asset.id,
                snapshot_date=snapshot_date,
                defaults={
                    "quantity": quantity,
                    "price_base": price_base,
                    "value_base": value_base,
                },
            )

        net_flow = Decimal("0")
        for tx in flows:
            rate = resolve_rate(tx.asset.currency)
            amount = _to_decimal(tx.amount) or Decimal("0")
            if rate is None:
                continue
            signed_amount = amount if tx.transaction_type == "deposit" else -amount
            net_flow += signed_amount * rate

        prev_snapshot = PortfolioValuationDaily.objects.filter(
            portfolio_id=portfolio_id,
            snapshot_date=snapshot_date - timedelta(days=1),
        ).first()
        prev_value = prev_snapshot.value_base if prev_snapshot else Decimal("0")
        pnl_base = total_value - prev_value - net_flow

        valuation, _ = PortfolioValuationDaily.objects.update_or_create(
            portfolio_id=portfolio_id,
            snapshot_date=snapshot_date,
            defaults={
                "base_currency": base_currency,
                "value_base": total_value,
                "net_flow_base": net_flow,
                "pnl_base": pnl_base,
            },
        )

        PortfolioPositionDaily.objects.filter(
            portfolio_id=portfolio_id,
            snapshot_date__lt=snapshot_date - timedelta(days=1),
        ).delete()

    return valuation
