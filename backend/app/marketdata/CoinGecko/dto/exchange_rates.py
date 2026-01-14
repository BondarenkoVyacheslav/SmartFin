import enum
from typing import Any, Dict, List

import strawberry

from app.marketdata.services.redis_json import RedisJSON


@strawberry.enum
class ExchangeRateType(enum.Enum):
    CRYPTO = "crypto"
    FIAT = "fiat"
    COMMODITY = "commodity"


@strawberry.type
class ExchangeRate:
    """
    Одна запись курса из /exchange_rates.

    Пример: код "btc", name="Bitcoin", unit="BTC", value=1.0, type=CRYPTO.
    """
    code: str          # ключ в словаре rates: "btc", "eth", "usd", ...
    name: str
    unit: str
    value: float
    type: ExchangeRateType


@strawberry.type
class ExchangeRates(RedisJSON):
    """
    Нормализованный ответ /exchange_rates:
    исходный rates: {code -> {...}} превращаем в список ExchangeRate.
    """
    rates: List[ExchangeRate]


def parse_exchange_rates(raw: Dict[str, Any]) -> ExchangeRates:
    """
    Превращает сырой ответ CoinGecko /exchange_rates в DTO ExchangeRates.

    Ожидаемый формат raw:
    {
      "rates": {
        "btc": {"name": "...", "unit": "...", "value": 1.0, "type": "crypto"},
        "usd": {"name": "...", "unit": "$", "value": 95726.799, "type": "fiat"},
        ...
      }
    }
    """
    rates_field = raw.get("rates") or {}
    rates: List[ExchangeRate] = []

    if not isinstance(rates_field, dict):
        return ExchangeRates(rates=[])

    for code, payload in rates_field.items():
        if not isinstance(payload, dict):
            continue

        name = payload.get("name")
        unit = payload.get("unit")
        value = payload.get("value")
        type_str = payload.get("type")

        # Базовая валидация типов
        if not isinstance(code, str):
            continue
        if not isinstance(name, str) or not isinstance(unit, str):
            continue
        if not isinstance(value, (int, float)):
            continue
        if not isinstance(type_str, str):
            continue

        # Маппинг типа в enum; неизвестные типы просто скипаем
        try:
            rate_type = ExchangeRateType(type_str)
        except ValueError:
            continue

        rates.append(
            ExchangeRate(
                code=code,
                name=name,
                unit=unit,
                value=float(value),
                type=rate_type,
            )
        )

    return ExchangeRates(rates=rates)
