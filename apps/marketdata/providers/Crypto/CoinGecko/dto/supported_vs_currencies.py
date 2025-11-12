import dataclasses
import json
from typing import Sequence, Self
import strawberry

@strawberry.type
class SupportedVSCurrencies:
    currencies: list[str]

    def to_redis_value(self) -> str:
        return json.dumps(dataclasses.asdict(self), ensure_ascii=False, separators=(",", ":"))

    @classmethod
    def from_redis_value(cls, value: str) -> Self:
        data = json.loads(value)

        raw: Sequence[str] = data.get("currencies", [])
        return parse_supported_vs_currencies(raw)


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