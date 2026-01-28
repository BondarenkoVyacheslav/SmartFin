from typing import Optional, Dict, Any
import strawberry

from app.marketdata.services.redis_json import RedisJSON


@strawberry.type
class SimpleBySymbolsPriceEntry:
    symbol: str
    vs_currency: str
    price: float

@strawberry.type
class ListSimpleBySymbolsPricesEntry(RedisJSON):
    simple_prices_by_symbols: list[SimpleBySymbolsPriceEntry] = strawberry.field(
        default_factory=list
    )


def _to_float(x) -> Optional[float]:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def parse_list_simple_price_by_symbols(
    raw: Dict[str, Dict[str, Any]]
) -> ListSimpleBySymbolsPricesEntry:
    """
    /simple/price (symbols=...) -> ListSimpleBySymbolsPricesEntry
    - parse all symbols and all quote currencies
    - keep last_updated_at as-is (if present), without conversions
    """
    if not isinstance(raw, dict):
        return ListSimpleBySymbolsPricesEntry()

    rows: ListSimpleBySymbolsPricesEntry = ListSimpleBySymbolsPricesEntry()

    for symbol, payload in raw.items():
        if not isinstance(payload, dict):
            continue

        for k, v in payload.items():
            kl = str(k).lower()
            if kl == "last_updated_at":
                continue

            vs_code = kl
            price = _to_float(v)
            if price is None:
                continue
            rows.simple_prices_by_symbols.append(
                SimpleBySymbolsPriceEntry(
                    symbol=str(symbol),
                    vs_currency=vs_code,
                    price=price,
                )
            )

    return rows
