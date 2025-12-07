# apps/marketdata/providers/StockMarketRussia/MOEX/dto/securities.py
from __future__ import annotations

from typing import Any, Dict, List, Optional

import strawberry
from strawberry.scalars import JSON

from apps.marketdata.services.redis_json import RedisJSON


@strawberry.type
class MOEXSecurity:
    """
    Одна строка из секции `securities.data` ISS.
    Поля максимально повторяют названия колонок.
    """
    secid: str

    shortname: Optional[str] = None
    regnumber: Optional[str] = None
    name: Optional[str] = None
    isin: Optional[str] = None

    is_traded: Optional[int] = None
    emitent_id: Optional[int] = None
    emitent_title: Optional[str] = None
    emitent_inn: Optional[str] = None
    emitent_okpo: Optional[str] = None

    # тип инструмента и «группа» по ISS
    type: Optional[str] = None
    group: Optional[str] = None

    primary_boardid: Optional[str] = None
    marketprice_boardid: Optional[str] = None


@strawberry.type
class MOEXSecurities(RedisJSON):
    """
    Обёртка над ответом `securities` из ISS:
    - items   — список типизированных бумаг
    - columns — исходные имена колонок
    - metadata — «сырая» ISS-мета (если пригодится на фронте/отладке)
    """
    items: List[MOEXSecurity] = strawberry.field(default_factory=list)
    columns: List[str] = strawberry.field(default_factory=list)
    metadata: Optional[JSON] = None


def _to_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_moex_securities(raw: Dict[str, Any]) -> MOEXSecurities:
    """
    MOEX /iss/securities.json -> MOEXSecurities.

    Сюда можно передавать либо весь ответ целиком,
    либо уже raw["securities"] — оба варианта поддерживаются.
    """
    if not isinstance(raw, dict):
        return MOEXSecurities()

    # Если пришёл полный ответ: {"securities": {...}}
    section = raw.get("securities") if "securities" in raw else raw
    if not isinstance(section, dict):
        return MOEXSecurities()

    columns = section.get("columns") or []
    data = section.get("data") or []
    metadata = section.get("metadata")

    if not isinstance(columns, list):
        columns = []

    # name -> index
    index_by_name: Dict[str, int] = {name: idx for idx, name in enumerate(columns)}

    def get(row: List[Any], col: str) -> Any:
        idx = index_by_name.get(col)
        if idx is None or idx >= len(row):
            return None
        return row[idx]

    items: List[MOEXSecurity] = []

    for row in data or []:
        if not isinstance(row, list):
            continue

        secid = get(row, "secid")
        if secid is None:
            # Без кода бумаги запись особо не нужна — пропускаем.
            continue

        item = MOEXSecurity(
            secid=str(secid),

            shortname=get(row, "shortname"),
            regnumber=get(row, "regnumber"),
            name=get(row, "name"),
            isin=get(row, "isin"),

            is_traded=_to_int(get(row, "is_traded")),
            emitent_id=_to_int(get(row, "emitent_id")),
            emitent_title=get(row, "emitent_title"),
            emitent_inn=get(row, "emitent_inn"),
            emitent_okpo=get(row, "emitent_okpo"),

            type=get(row, "type"),
            group=get(row, "group"),

            primary_boardid=get(row, "primary_boardid"),
            marketprice_boardid=get(row, "marketprice_boardid"),
        )
        items.append(item)

    return MOEXSecurities(
        items=items,
        columns=columns,
        metadata=metadata,
    )
