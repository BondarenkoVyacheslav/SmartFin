from __future__ import annotations

from decimal import Decimal
from typing import Iterable, Optional

from app.marketdata import market_data_api


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
