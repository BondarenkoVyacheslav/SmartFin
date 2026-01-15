from __future__ import annotations

from typing import Any, Dict, List, Optional

import strawberry
from strawberry.scalars import JSON

from app.marketdata.services.redis_json import RedisJSON


@strawberry.type
class MOEXEngineMarket:
    """
    Одна строка из секции `markets.data` ISS для /iss/engines/{engine}/markets.
    Поля максимально повторяют смысл колонок.
    """
    id: int
    name: str

    title: Optional[str] = None


@strawberry.type
class MOEXEngineMarkets(RedisJSON):
    """
    Обёртка над ответом `markets` из ISS:
    - items   — список рынков движка
    - columns — исходные имена колонок
    - metadata — «сырая» ISS-мета (если пригодится на фронте/отладке)
    """
    items: List[MOEXEngineMarket] = strawberry.field(default_factory=list)
    columns: List[str] = strawberry.field(default_factory=list)
    metadata: JSON | None = None

def _to_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_moex_markets(raw: Dict[str, Any]) -> MOEXEngineMarkets:
    """
    MOEX /iss/engines/{engine}/markets.json -> MOEXMarkets.

    Сюда можно передавать либо весь ответ целиком,
    либо уже raw["markets"] — оба варианта поддерживаются.
    """
    if not isinstance(raw, dict):
        return MOEXEngineMarkets()

    # Если пришёл полный ответ: {"markets": {...}}
    section = raw.get("markets") if "markets" in raw else raw
    if not isinstance(section, dict):
        return MOEXEngineMarkets()

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

    items: List[MOEXEngineMarket] = []

    for row in data or []:
        if not isinstance(row, list):
            continue

        market_id = _to_int(get(row, "id"))

        # В ответе колонка называется "NAME", но на всякий случай
        # делаем fallback на "name".
        raw_name = get(row, "NAME")
        if raw_name is None:
            raw_name = get(row, "name")

        if market_id is None or raw_name is None:
            # Без id или name запись не очень полезна — пропускаем.
            continue

        item = MOEXEngineMarket(
            id=market_id,
            name=str(raw_name),
            title=get(row, "title"),
        )
        items.append(item)

    return MOEXEngineMarkets(
        items=items,
        columns=columns,
        metadata=metadata,
    )
