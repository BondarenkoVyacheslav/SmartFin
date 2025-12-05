from decimal import Decimal
from typing import Sequence, Any

import strawberry

from apps.marketdata.providers.Crypto.CoinGecko.redis_json import RedisJSON


@strawberry.type(name="ExchangeExchange")
class Exchange:
    id: str | None
    name: str | None
    year_established: int | None
    country: str | None
    description: str | None
    url: str | None
    image: str | None
    has_trading_incentive: bool | None
    trust_score: int | None
    trust_score_rank: int | None
    trade_volume_24h_btc: Decimal | None


@strawberry.type(name="ExchangesExchanges")
class Exchanges(RedisJSON):
    exchanges: list[Exchange]

def _to_dec(x) -> Decimal | None:
    if x is None:
        return None
    # через str(x) чтобы не ловить двоичную погрешность float
    return Decimal(str(x))

def _to_year(x: Any) -> int | None:
    """
    Парсим year_established как год.
    CoinGecko обычно отдаёт int (например, 2017), но подстрахуемся под строки.
    """
    if x is None:
        return None

    if isinstance(x, int):
        return x

    if isinstance(x, str):
        x = x.strip()
        if not x:
            return None
        try:
            return int(x)
        except ValueError:
            return None

    # если вдруг прилетело что-то странное — просто None
    return None


def parse_exchanges(raw: Sequence[dict[str, Any]]) -> Exchanges:
    exchanges: Exchanges = Exchanges(exchanges=list())

    for exchange in raw:
        exchanges.exchanges.append(
            Exchange(
                id=exchange.get("id"),
                name=exchange.get("name"),
                year_established=_to_year(exchange.get("year_established")),
                country=exchange.get("country"),
                description=exchange.get("description"),
                url=exchange.get("url"),
                image=exchange.get("image"),
                has_trading_incentive=exchange.get("has_trading_incentive"),
                trust_score=exchange.get("trust_score"),
                trust_score_rank=exchange.get("trust_score_rank"),
                trade_volume_24h_btc=_to_dec(exchange.get("trade_volume_24h_btc")),
            )
        )

    return exchanges