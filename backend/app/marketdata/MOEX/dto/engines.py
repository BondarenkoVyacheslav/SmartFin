from __future__ import annotations

from typing import Any, Dict, List, Optional

import strawberry
from strawberry.scalars import JSON

from app.marketdata.services.redis_json import RedisJSON


@strawberry.type
class MOEXEngine:
    """
    Одна строка из секции `engines.data` ISS.
    Поля максимально повторяют названия колонок.
    """
    id: int
    name: str

    title: Optional[str] = None


@strawberry.type
class MOEXEngines(RedisJSON):
    """
    Обёртка над ответом `engines` из ISS:
    - items   — список доступных торговых систем
    - columns — исходные имена колонок
    - metadata — «сырая» ISS-мета (если пригодится на фронте/отладке)
    """
    items: List[MOEXEngine] = strawberry.field(default_factory=list)
    columns: List[str] = strawberry.field(default_factory=list)
    metadata: Optional[JSON] = None


def _to_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_moex_engines(raw: Dict[str, Any]) -> MOEXEngines:
    """
    MOEX /iss/engines.json -> MOEXEngines.

    Сюда можно передавать либо весь ответ целиком,
    либо уже raw["engines"] — оба варианта поддерживаются.
    """
    if not isinstance(raw, dict):
        return MOEXEngines()

    # Если пришёл полный ответ: {"engines": {.}}
    section = raw.get("engines") if "engines" in raw else raw
    if not isinstance(section, dict):
        return MOEXEngines()

    columns = section.get("columns") or []
    data = section.get("data") or []
    metadata = section.get("metadata")

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

    items: List[MOEXEngine] = []

    for row in data or []:
        if not isinstance(row, list):
            continue

        engine_id = _to_int(get(row, "id"))
        name = get(row, "name")

        # Без id или name запись мало полезна — пропускаем.
        if engine_id is None or name is None:
            continue

        item = MOEXEngine(
            id=engine_id,
            name=str(name),
            title=get(row, "title"),
        )
        items.append(item)

    return MOEXEngines(
        items=items,
        columns=columns,
        metadata=metadata,
    )
