from typing import Sequence
import strawberry

from apps.marketdata.services.redis_json import RedisJSON


@strawberry.type
class SupportedVSCurrencies(RedisJSON):
    currencies: list[str]


def parse_supported_vs_currencies(raw: Sequence[str]) -> SupportedVSCurrencies:
    # Мягкая валидация + нормализация
    cleaned: list[str] = []
    seen = set()
    for x in raw:
        if isinstance(x, str):
            s = x.strip().lower()
            if s and s not in seen:
                seen.add(s)
                cleaned.append(s)

    return SupportedVSCurrencies(currencies=cleaned)