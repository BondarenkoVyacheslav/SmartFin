from typing import List, Optional, Sequence, Mapping, Any

import strawberry

from apps.marketdata.providers.Crypto.CoinGecko.dto.redis_json import RedisJSON


@strawberry.type
class DerivativesExchange:
    """
    Одна деривативная биржа из /derivatives/exchanges.
    """
    id: str
    name: str

    # В CoinGecko это числа / строки, в DTO приводим к float/int
    open_interest_btc: float                  # общий OI в BTC
    trade_volume_24h_btc: float               # 24h volume в BTC

    number_of_perpetual_pairs: int
    number_of_futures_pairs: int

    image: Optional[str] = None
    year_established: Optional[int] = None
    country: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None




@strawberry.type
class DerivativesExchangesPage(RedisJSON):
    """
    Обёртка над списком деривативных бирж.
    Удобно, чтобы знать, какой page мы закэшировали.
    """
    page: int
    exchanges: List[DerivativesExchange]


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_derivatives_exchanges(
    raw: Sequence[Mapping[str, Any]],
    *,
    page: int,
) -> DerivativesExchangesPage:
    """
    Нормализует ответ /derivatives/exchanges (массив бирж)
    в DTO DerivativesExchangesPage.
    """
    exchanges: List[DerivativesExchange] = []

    for item in raw:
        if not isinstance(item, Mapping):
            continue

        exchange = DerivativesExchange(
            id=str(item.get("id", "")),
            name=str(item.get("name", "")),
            open_interest_btc=_to_float(item.get("open_interest_btc")),
            trade_volume_24h_btc=_to_float(item.get("trade_volume_24h_btc")),
            number_of_perpetual_pairs=_to_int(item.get("number_of_perpetual_pairs")),
            number_of_futures_pairs=_to_int(item.get("number_of_futures_pairs")),
            image=item.get("image"),
            year_established=(
                _to_int(item.get("year_established"))
                if item.get("year_established") is not None
                else None
            ),
            country=item.get("country"),
            description=item.get("description"),
            url=item.get("url"),
        )

        exchanges.append(exchange)

    return DerivativesExchangesPage(
        page=page,
        exchanges=exchanges,
    )
