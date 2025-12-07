from decimal import Decimal
from typing import Sequence, Any
import strawberry
from datetime import datetime

from apps.marketdata.services.redis_json import RedisJSON


@strawberry.type(name="DerivativesDerivative")
class Derivative:
    market: str | None
    symbol: str | None
    index_id: str | None
    price: str | None
    price_percentage_change_24h: Decimal | None
    contract_type: str | None
    index: float | None
    basis: Decimal | None
    spread: float | None
    funding_rate: Decimal | None
    open_interest: float | None
    volume_24h: float | None
    last_traded_at: int | None
    expired_at: str | None = None


@strawberry.type
class Derivatives(RedisJSON):
    derivatives: list[Derivative] = strawberry.field(default_factory=list)


def _to_dec(x) -> Decimal | None:
    if x is None:
        return None
    return Decimal(str(x))

def _to_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    return datetime.fromisoformat(s.replace('Z', '+00:00'))


def parse_derivatives(raw: Sequence[dict[str, Any]]) -> Derivatives:
    derivatives: Derivatives = Derivatives()

    for derivative in raw:
        derivatives.derivatives.append(
            Derivative(
                market=derivative.get("market"),
                symbol=derivative.get("symbol"),
                index_id=derivative.get("index_id"),
                price=derivative.get("price"),
                price_percentage_change_24h=_to_dec(derivative.get("price_percentage_change_24h")),
                contract_type=derivative.get("contract_type"),
                index=derivative.get("index"),
                basis=_to_dec(derivative.get("basis")),
                spread=derivative.get("spread"),
                funding_rate=_to_dec(derivative.get("funding_rate")),
                open_interest=derivative.get("open_interest"),
                volume_24h=derivative.get("volume_24h"),
                last_traded_at=derivative.get("last_traded_at"),
                expired_at=derivative.get("expired_at")
            )
        )

    return derivatives