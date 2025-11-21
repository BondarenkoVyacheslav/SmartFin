import strawberry
from decimal import Decimal
from datetime import datetime

from apps.marketdata.providers.Crypto.CoinGecko.dto.redis_json import RedisJSON


@strawberry.type
class ROI:
    times: float | None = None         # напр. 44.0173
    currency: str | None = None        # 'btc' | 'usd' | ...
    percentage: float | None = None    # напр. 4401.7396

@strawberry.type
class Coin:
    # идентификация
    id: str
    symbol: str
    name: str
    image: str | None

    # цена/капитализация/объёмы (в vs_currency)
    current_price: Decimal | None
    market_cap: Decimal | None
    market_cap_rank: int | None
    fully_diluted_valuation: Decimal | None
    total_volume: Decimal | None

    # 24ч экстремумы и изменения
    high_24h: Decimal | None
    low_24h: Decimal | None
    price_change_24h: float | None
    price_change_percentage_24h: float | None
    market_cap_change_24h: Decimal | None
    market_cap_change_percentage_24h: float | None

    # предложение
    circulating_supply: float | None
    total_supply: float | None
    max_supply: float | None

    # ATH/ATL
    ath: Decimal | None
    ath_change_percentage: float | None
    ath_date: datetime | None
    atl: Decimal | None
    atl_change_percentage: float | None
    atl_date: datetime | None

    # прочее
    roi: ROI | None
    last_updated: datetime | None

    # добавляется, если запрошено price_change_percentage=1h
    price_change_percentage_1h_in_currency: float | None



@strawberry.type
class CoinsMarket(RedisJSON):
    vs_currency: str | None
    items: list[Coin]


def _to_dec(x) -> Decimal | None:
    if x is None:
        return None
    # через str(x) чтобы не ловить двоичную погрешность float
    return Decimal(str(x))

def _to_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    # CoinGecko даёт ISO с 'Z' → приведём к +00:00
    return datetime.fromisoformat(s.replace('Z', '+00:00'))

def parse_roi(raw: dict | None) -> ROI | None:
    if not isinstance(raw, dict):
        return None
    return ROI(
        times = float(raw["times"]) if raw.get("times") is not None else None,
        currency = raw.get("currency"),
        percentage = float(raw["percentage"]) if raw.get("percentage") is not None else None,
    )


def parse_coin(raw: dict) -> Coin:
    return Coin(
        id = raw.get("id", ""),
        symbol = raw.get("symbol", ""),
        name = raw.get("name", ""),
        image = raw.get("image"),

        current_price = _to_dec(raw.get("current_price")),
        market_cap = _to_dec(raw.get("market_cap")),
        market_cap_rank = raw.get("market_cap_rank"),
        fully_diluted_valuation = _to_dec(raw.get("fully_diluted_valuation")),
        total_volume = _to_dec(raw.get("total_volume")),

        high_24h = _to_dec(raw.get("high_24h")),
        low_24h = _to_dec(raw.get("low_24h")),
        price_change_24h = float(raw["price_change_24h"]) if raw.get("price_change_24h") is not None else None,
        price_change_percentage_24h = float(raw["price_change_percentage_24h"]) if raw.get("price_change_percentage_24h") is not None else None,
        market_cap_change_24h = _to_dec(raw.get("market_cap_change_24h")),
        market_cap_change_percentage_24h = float(raw["market_cap_change_percentage_24h"]) if raw.get("market_cap_change_percentage_24h") is not None else None,

        circulating_supply = float(raw["circulating_supply"]) if raw.get("circulating_supply") is not None else None,
        total_supply = float(raw["total_supply"]) if raw.get("total_supply") is not None else None,
        max_supply = float(raw["max_supply"]) if raw.get("max_supply") is not None else None,

        ath = _to_dec(raw.get("ath")),
        ath_change_percentage = float(raw["ath_change_percentage"]) if raw.get("ath_change_percentage") is not None else None,
        ath_date = _to_dt(raw.get("ath_date")),
        atl = _to_dec(raw.get("atl")),
        atl_change_percentage = float(raw["atl_change_percentage"]) if raw.get("atl_change_percentage") is not None else None,
        atl_date = _to_dt(raw.get("atl_date")),

        roi = parse_roi(raw.get("roi")),
        last_updated = _to_dt(raw.get("last_updated")),

        price_change_percentage_1h_in_currency = float(raw["price_change_percentage_1h_in_currency"]) if raw.get("price_change_percentage_1h_in_currency") is not None else None,
    )

def parse_coins_markets(payload: list, vs_currency: str | None = None) -> CoinsMarket:
    coins = [parse_coin(item) for item in payload if isinstance(item, dict)]
    return CoinsMarket(vs_currency=vs_currency, items=coins)