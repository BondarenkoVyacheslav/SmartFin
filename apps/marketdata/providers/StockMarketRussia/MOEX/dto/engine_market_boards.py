from __future__ import annotations

from typing import Any, Dict, List, Optional

import strawberry

from apps.marketdata.services.redis_json import RedisJSON


@strawberry.type
class MOEXBoard:
    """
    Одна строка из секции `boards.data` ISS для
    /iss/engines/{engine}/markets/{market}/boards.

    Поля максимально повторяют названия колонок:
    id, board_group_id, boardid, title, is_traded.
    """
    id: int
    boardid: str

    board_group_id: Optional[int] = None
    title: Optional[str] = None
    is_traded: Optional[int] = None  # 1/0, оставляем как int


@strawberry.type
class MOEXBoards(RedisJSON):
    """
    Обёртка над секцией `boards`:
    - items   — список режимов торгов рынка
    - columns — имена колонок секции (как в ISS)

    metadata намеренно не храним.
    """
    items: List[MOEXBoard] = strawberry.field(default_factory=list)
    columns: List[str] = strawberry.field(default_factory=list)


def _to_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_moex_boards(raw: Dict[str, Any]) -> MOEXBoards:
    """
    MOEX /iss/engines/{engine}/markets/{market}/boards.json -> MOEXBoards.

    Можно передавать:
    - весь ответ целиком: {"boards": {...}}
    - или только секцию boards: {"columns": [...], "data": [...]}
    """
    if not isinstance(raw, dict):
        return MOEXBoards()

    # Если пришёл полный ответ: {"boards": {...}}
    section = raw.get("boards") if "boards" in raw else raw
    if not isinstance(section, dict):
        return MOEXBoards()

    columns = section.get("columns") or []
    data = section.get("data") or []

    if not isinstance(columns, list):
        columns = []

    # name -> index
    index_by_name: Dict[str, int] = {
        str(name): idx for idx, name in enumerate(columns)
    }

    def get(row: List[Any], col: str) -> Any:
        idx = index_by_name.get(col)
        if idx is None or idx >= len(row):
            return None
        return row[idx]

    items: List[MOEXBoard] = []

    for row in data or []:
        if not isinstance(row, list):
            continue

        row_id = _to_int(get(row, "id"))
        raw_boardid = get(row, "boardid")

        # Без id или boardid запись считаем бесполезной
        if row_id is None or raw_boardid is None:
            continue

        item = MOEXBoard(
            id=row_id,
            boardid=str(raw_boardid),
            board_group_id=_to_int(get(row, "board_group_id")),
            title=get(row, "title"),
            is_traded=_to_int(get(row, "is_traded")),
        )
        items.append(item)

    return MOEXBoards(
        items=items,
        columns=columns,
    )
