import json
from typing import Optional, Dict, Any
import strawberry

from apps.marketdata.providers.Crypto.CoinGecko.redis_json import RedisJSON


@strawberry.type
class SimpleTokenPriceEntry:
    """
    Одна запись /simple/token_price/{id}:
    - один токен (по контракту)
    - одна валюта котирования
    """
    contract_address: str      # "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599"
    vs_currency: str           # "usd", "eur", ...

    price: float               # 90134.5030123555

    market_cap: Optional[float] = None      # usd_market_cap / eur_market_cap
    vol_24h: Optional[float] = None         # usd_24h_vol / eur_24h_vol
    change_24h: Optional[float] = None      # usd_24h_change / eur_24h_change
    last_updated_at: Optional[int] = None   # Unix timestamp, если включён include_last_updated_at


@strawberry.type
class SimpleTokenPricesList(RedisJSON):
    """
    Обёртка над списком SimpleTokenPriceEntry.
    Удобна для кеша (to_redis_value) и для GraphQL.
    """
    simple_token_prices: list[SimpleTokenPriceEntry] = strawberry.field(
        default_factory=list
    )

    @classmethod
    def from_redis_value(cls, value: str) -> "SimpleTokenPricesList":
        """
        Обратная операция — из JSON в SimpleTokenPricesList.
        """
        data = json.loads(value)
        raw_items = data.get("simple_token_prices") or []

        items: list[SimpleTokenPriceEntry] = []
        for item in raw_items:
            if not isinstance(item, dict):
                continue

            items.append(
                SimpleTokenPriceEntry(
                    contract_address=str(item.get("contract_address", "")),
                    vs_currency=str(item.get("vs_currency", "")),
                    price=float(item.get("price", 0.0)),
                    market_cap=item.get("market_cap"),
                    vol_24h=item.get("vol_24h"),
                    change_24h=item.get("change_24h"),
                    last_updated_at=item.get("last_updated_at"),
                )
            )

        return cls(simple_token_prices=items)


def _to_float(x) -> Optional[float]:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def parse_simple_token_prices(
    raw: Dict[str, Dict[str, Any]]
) -> SimpleTokenPricesList:
    """
    Парсер ответа /simple/token_price/ethereum:

    Пример raw:
    {
      "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599": {
        "usd": 90134.5030123555,
        "usd_market_cap": 11427702762.367313,
        "usd_24h_vol": 440970070.3501562,
        "usd_24h_change": 0.19833570530050507,
        "eur": 78236.29794220951,
        "eur_market_cap": 9912869339.593428,
        "eur_24h_vol": 382759816.2135838,
        "eur_24h_change": 0.41872599905586805,
        "last_updated_at": 1763653973
      }
    }

    На выходе — SimpleTokenPricesList с набором SimpleTokenPriceEntry
    по всем контрактам и всем валютам.
    """
    if not isinstance(raw, dict):
        return SimpleTokenPricesList()

    result = SimpleTokenPricesList()
    flag_suffixes = ("_market_cap", "_24h_vol", "_24h_change")

    for contract_address, payload in raw.items():
        if not isinstance(payload, dict):
            continue

        # last_updated_at (если включён параметром include_last_updated_at)
        ts = payload.get("last_updated_at")
        ts = int(ts) if isinstance(ts, (int, float)) else None

        # Map ключей в lowercase для поиска флагов без учёта регистра
        lower_map = {str(k).lower(): v for k, v in payload.items()}

        # Валюты — все ключи, которые не *_market_cap, *_24h_vol, *_24h_change, last_updated_at
        for k, v in payload.items():
            kl = str(k).lower()
            if kl == "last_updated_at" or any(kl.endswith(suf) for suf in flag_suffixes):
                continue

            vs_code = kl  # "usd", "eur", ...
            price = _to_float(v)
            if price is None:
                continue

            mc = _to_float(lower_map.get(f"{vs_code}_market_cap"))
            vol = _to_float(lower_map.get(f"{vs_code}_24h_vol"))
            chg = _to_float(lower_map.get(f"{vs_code}_24h_change"))

            result.simple_token_prices.append(
                SimpleTokenPriceEntry(
                    contract_address=str(contract_address),
                    vs_currency=vs_code,
                    price=price,
                    market_cap=mc,
                    vol_24h=vol,
                    change_24h=chg,
                    last_updated_at=ts,
                )
            )

    return result
