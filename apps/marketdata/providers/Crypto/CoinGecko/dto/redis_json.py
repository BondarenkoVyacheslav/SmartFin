from __future__ import annotations

import dataclasses
import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any


def _redis_default_encoder(obj: Any) -> Any:
    """
    Специальный encoder для json.dumps:
    - Decimal -> str (без потери точности)
    - datetime/date -> ISO-строка
    - dataclass -> dict
    """
    if isinstance(obj, Decimal):
        # Через str, чтобы не ловить двоичную погрешность float
        return str(obj)

    if isinstance(obj, (datetime, date)):
        # ISO 8601, например: "2025-11-21T18:42:10+00:00"
        return obj.isoformat()

    if dataclasses.is_dataclass(obj):
        # Рекурсивно раскрываем dataclass в dict
        return dataclasses.asdict(obj)

    # Пусть json сам бросит TypeError, если встретится что-то экзотическое
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


class RedisJSON:
    """
    Миксин с единым to_redis_value() для всех наших DTO.

    Работает с любыми strawberry-типами, потому что strawberry.type под капотом
    делает dataclass.
    """

    def to_redis_value(self) -> str:
        return json.dumps(
            self,
            ensure_ascii=False,
            separators=(",", ":"),  # как у тебя везде
            default=_redis_default_encoder,
        )
