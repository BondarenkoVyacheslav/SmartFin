from __future__ import annotations

import dataclasses
import enum
import json
from dataclasses import is_dataclass, fields
from datetime import date, datetime
from decimal import Decimal
from typing import (
    Any,
    Dict,
    List,
    MutableSequence,
    Sequence,
    Type,
    TypeVar,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)

T = TypeVar("T", bound="RedisJSONMixin")


def _redis_default_encoder(obj: Any) -> Any:
    """
    encoder для json.dumps именно наших DTO:
    - Decimal -> str (без потери точности)
    - datetime/date -> ISO-строка
    - Enum -> значение enum-а
    - dataclass -> dict (рекурсивно)
    """
    if isinstance(obj, Decimal):
        return str(obj)

    if isinstance(obj, (datetime, date)):
        return obj.isoformat()

    if isinstance(obj, enum.Enum):
        return obj.value

    if is_dataclass(obj):
        return dataclasses.asdict(obj)

    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _convert_value(value: Any, annotation: Any) -> Any:
    """
    Преобразует значение из json.loads обратно в тип,
    который указан в аннотации поля нашего DTO.

    Работает для:
    - Decimal, datetime, date, Enum
    - dataclass
    - list[T], Sequence[T]
    - dict[K, V]
    - Optional[T] / Union[T, None]
    """
    if value is None:
        return None

    origin = get_origin(annotation)
    args = get_args(annotation)

    # Прямые типы
    if annotation is Decimal:
        # value пришёл из _redis_default_encoder как строка
        return Decimal(value)

    if annotation is datetime:
        return datetime.fromisoformat(value)

    if annotation is date:
        return date.fromisoformat(value)

    # Enum
    if isinstance(annotation, type) and issubclass(annotation, enum.Enum):
        return annotation(value)

    # dataclass
    if isinstance(annotation, type) and is_dataclass(annotation):
        if not isinstance(value, dict):
            raise TypeError(f"Expected dict for {annotation}, got {type(value)}")
        return _build_dataclass(annotation, value)

    # Optional[T] / Union[T, None]
    if origin is Union:
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1:
            return _convert_value(value, non_none[0])
        # более сложные Union-ы при необходимости можно досвернуть
        return value

    # list[T] / Sequence[T]
    if origin in (list, List, Sequence, MutableSequence):
        (item_type,) = args or (Any,)
        if value is None:
            return None
        return [_convert_value(item, item_type) for item in value]

    # dict[K, V]
    if origin in (dict, Dict):
        key_type, val_type = args or (Any, Any)
        if value is None:
            return None
        return {
            _convert_value(k, key_type): _convert_value(v, val_type)
            for k, v in value.items()
        }

    # Базовый случай — str, int, float, bool, Any и т.п.
    return value


def _build_dataclass(cls: Type[T], data: dict[str, Any]) -> T:
    """
    Рекурсивно собирает dataclass cls из dict data,
    используя type hints, которые ты описал в DTO.
    """
    if not is_dataclass(cls):
        raise TypeError(f"{cls} is not a dataclass")

    # Учитываем from __future__ import annotations
    type_hints = get_type_hints(cls, include_extras=True)

    kwargs: dict[str, Any] = {}
    for f in fields(cls):
        raw_value = data.get(f.name)
        field_type = type_hints.get(f.name, f.type)
        kwargs[f.name] = _convert_value(raw_value, field_type)

    return cls(**kwargs)  # type: ignore[arg-type]


class RedisJSON:
    """
    Миксин с едиными:
    - to_redis_value()  -> str
    - from_redis_value(value) -> DTO | None

    Ориентирован на то, что в Redis лежит JSON,
    полученный из наших DTO (через этот же миксин или dataclasses.asdict + dumps).
    """

    def to_redis_value(self) -> str:
        """
        Сериализация DTO в JSON-строку для Redis.
        """
        # На всякий случай: если класс вдруг не dataclass, всё равно сработает через default
        payload: Any = self
        if is_dataclass(self):
            payload = dataclasses.asdict(self)

        return json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            default=_redis_default_encoder,
        )

    @classmethod
    def from_redis_value(cls: Type[T], value: Any) -> T | None:
        """
        Универсальное восстановление DTO из значения из Redis.

        Ожидаемые варианты:
        - None                       -> None
        - str / bytes json           -> json.loads -> dict -> dataclass
        - уже dict (если кэш так настроен) -> сразу dataclass

        Важно: здесь НЕТ вызова parse_*,
        т.к. мы работаем уже с json от наших DTO, а не с сырой CoinGecko-ответкой.
        """
        if value is None:
            return None

        if isinstance(value, (bytes, bytearray)):
            value = value.decode("utf-8")

        if isinstance(value, str):
            data = json.loads(value)
        else:
            data = value  # вдруг RedisCacheService сам делает json.loads

        if data is None:
            return None

        if not isinstance(data, dict):
            raise TypeError(
                f"Expected dict JSON for {cls.__name__}, got {type(data)}"
            )

        return _build_dataclass(cls, data)
