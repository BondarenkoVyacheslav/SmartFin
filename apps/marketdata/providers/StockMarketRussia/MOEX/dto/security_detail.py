# apps/marketdata/providers/StockMarketRussia/MOEX/dto/security_details.py
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

import strawberry
from strawberry.scalars import JSON

from apps.marketdata.providers.Crypto.CoinGecko.redis_json import RedisJSON


# --- Вспомогательные конвертеры ---


def _to_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_date(value: Any) -> Optional[date]:
    """
    MOEX для дат отдаёт строки 'YYYY-MM-DD' или null.
    Держим это как Date-скаляр в GraphQL.
    """
    if value in (None, ""):
        return None

    if isinstance(value, date):
        return value

    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None

    return None


def _build_index(columns: List[Any]) -> Dict[str, int]:
    """
    name -> index для columns.
    """
    return {str(name): idx for idx, name in enumerate(columns or [])}


def _get(row: List[Any], index_by_name: Dict[str, int], col: str) -> Any:
    idx = index_by_name.get(col)
    if idx is None or idx >= len(row):
        return None
    return row[idx]


# --- DTO для description ---


@strawberry.type
class MOEXSecurityDescriptionRow:
    """
    Одна строка из секции `description.data` ISS для /iss/securities/{secid}.
    Колонки жёстко соответствуют ISS: name, title, value, type, sort_order, is_hidden, precision.
    """
    name: str

    title: Optional[str] = None
    value: Optional[str] = None
    type: Optional[str] = None
    sort_order: Optional[int] = None
    is_hidden: Optional[int] = None
    precision: Optional[int] = None


# --- DTO для boards ---


@strawberry.type
class MOEXSecurityBoard:
    """
    Одна строка из секции `boards.data` ISS для /iss/securities/{secid}.
    Поля максимально повторяют названия колонок.
    """
    secid: str
    boardid: str

    title: Optional[str] = None

    board_group_id: Optional[int] = None
    market_id: Optional[int] = None
    market: Optional[str] = None

    engine_id: Optional[int] = None
    engine: Optional[str] = None

    is_traded: Optional[int] = None
    decimals: Optional[int] = None

    history_from: Optional[date] = None
    history_till: Optional[date] = None
    listed_from: Optional[date] = None
    listed_till: Optional[date] = None

    is_primary: Optional[int] = None
    currencyid: Optional[str] = None
    unit: Optional[str] = None


# --- Корневой DTO (для кеша и GraphQL) ---


@strawberry.type
class MOEXSecurityDetails(RedisJSON):
    """
    Обёртка над ответом /iss/securities/{secid} с секциями
    `description` и `boards`.

    Без Dict-полей в схеме:
    - description_items / boards_items — типизированные строки
    - *_columns — имена колонок секций (как в ISS)
    - *_metadata — ISS-метаданные как JSON-скаляр (если вдруг пригодится)
    """
    description_items: List[MOEXSecurityDescriptionRow] = strawberry.field(
        default_factory=list
    )
    boards_items: List[MOEXSecurityBoard] = strawberry.field(
        default_factory=list
    )

    description_columns: List[str] = strawberry.field(default_factory=list)
    boards_columns: List[str] = strawberry.field(default_factory=list)

    description_metadata: Optional[JSON] = None
    boards_metadata: Optional[JSON] = None


# --- Парсер сырых данных ISS -> DTO ---


def _parse_description_section(section: Dict[str, Any]) -> tuple[
    List[MOEXSecurityDescriptionRow],
    List[str],
    Optional[JSON],
]:
    columns = section.get("columns") or []
    data = section.get("data") or []
    metadata = section.get("metadata")

    if not isinstance(columns, list):
        columns = []

    index_by_name = _build_index(columns)
    items: List[MOEXSecurityDescriptionRow] = []

    for row in data or []:
        if not isinstance(row, list):
            continue

        name = _get(row, index_by_name, "name")
        if name is None:
            # без name строка мало полезна
            continue

        item = MOEXSecurityDescriptionRow(
            name=str(name),
            title=_get(row, index_by_name, "title"),
            # value оставляем строкой, даже если type=number/date/boolean:
            # так DTO остаётся стабильным независимо от типов в ISS
            value=_get(row, index_by_name, "value"),
            type=_get(row, index_by_name, "type"),
            sort_order=_to_int(_get(row, index_by_name, "sort_order")),
            is_hidden=_to_int(_get(row, index_by_name, "is_hidden")),
            precision=_to_int(_get(row, index_by_name, "precision")),
        )
        items.append(item)

    return items, columns, metadata


def _parse_boards_section(section: Dict[str, Any]) -> tuple[
    List[MOEXSecurityBoard],
    List[str],
    Optional[JSON],
]:
    columns = section.get("columns") or []
    data = section.get("data") or []
    metadata = section.get("metadata")

    if not isinstance(columns, list):
        columns = []

    index_by_name = _build_index(columns)
    items: List[MOEXSecurityBoard] = []

    for row in data or []:
        if not isinstance(row, list):
            continue

        secid = _get(row, index_by_name, "secid")
        boardid = _get(row, index_by_name, "boardid")
        if secid is None or boardid is None:
            # Без secid/boardid смысла нет
            continue

        item = MOEXSecurityBoard(
            secid=str(secid),
            boardid=str(boardid),

            title=_get(row, index_by_name, "title"),
            board_group_id=_to_int(_get(row, index_by_name, "board_group_id")),
            market_id=_to_int(_get(row, index_by_name, "market_id")),
            market=_get(row, index_by_name, "market"),
            engine_id=_to_int(_get(row, index_by_name, "engine_id")),
            engine=_get(row, index_by_name, "engine"),
            is_traded=_to_int(_get(row, index_by_name, "is_traded")),
            decimals=_to_int(_get(row, index_by_name, "decimals")),

            history_from=_to_date(_get(row, index_by_name, "history_from")),
            history_till=_to_date(_get(row, index_by_name, "history_till")),
            listed_from=_to_date(_get(row, index_by_name, "listed_from")),
            listed_till=_to_date(_get(row, index_by_name, "listed_till")),

            is_primary=_to_int(_get(row, index_by_name, "is_primary")),
            currencyid=_get(row, index_by_name, "currencyid"),
            unit=_get(row, index_by_name, "unit"),
        )
        items.append(item)

    return items, columns, metadata


def parse_moex_security_details(raw: Dict[str, Any]) -> MOEXSecurityDetails:
    """
    MOEX /iss/securities/{secid}.json -> MOEXSecurityDetails.

    Поддерживает два варианта:
    1) полный ответ:
       {
         "description": {...},
         "boards": {...}
       }

    2) «голую» секцию (например только description или только boards),
       если парсер используют точечно.
    """
    if not isinstance(raw, dict):
        return MOEXSecurityDetails()

    # --- description ---
    description_section: Optional[Dict[str, Any]] = None
    if isinstance(raw.get("description"), dict):
        description_section = raw["description"]
    # если передали сразу секцию (columns/data/metadata)
    elif "columns" in raw and "data" in raw and "name" in (
        raw.get("metadata") or {}
    ):
        # это очень специфичная проверка — можешь убрать или упростить;
        # оставил как пример, если будешь парсить секцию отдельно
        description_section = raw  # type: ignore[assignment]

    desc_items: List[MOEXSecurityDescriptionRow] = []
    desc_columns: List[str] = []
    desc_metadata: Optional[JSON] = None

    if isinstance(description_section, dict):
        desc_items, desc_columns, desc_metadata = _parse_description_section(
            description_section
        )

    # --- boards ---
    boards_section: Optional[Dict[str, Any]] = None
    if isinstance(raw.get("boards"), dict):
        boards_section = raw["boards"]
    # вариант «голой» секции boards
    elif "columns" in raw and "data" in raw and "secid" in (
        (raw.get("metadata") or {}).get("columns", {})
        if isinstance(raw.get("metadata"), dict)
        else {}
    ):
        boards_section = raw  # type: ignore[assignment]

    boards_items: List[MOEXSecurityBoard] = []
    boards_columns: List[str] = []
    boards_metadata: Optional[JSON] = None

    if isinstance(boards_section, dict):
        boards_items, boards_columns, boards_metadata = _parse_boards_section(
            boards_section
        )

    return MOEXSecurityDetails(
        description_items=desc_items,
        boards_items=boards_items,
        description_columns=desc_columns,
        boards_columns=boards_columns,
        description_metadata=desc_metadata,
        boards_metadata=boards_metadata,
    )
