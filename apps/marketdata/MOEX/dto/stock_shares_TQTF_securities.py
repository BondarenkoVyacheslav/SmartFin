from __future__ import annotations

"""
MOEX ISS DTO for:
  /iss/securities/[security]

Чаще всего в ответе присутствуют таблицы:
  - description
  - boards
  - dataversion (опционально)

Пример:
  https://iss.moex.com/iss/securities/SBER.json?iss.meta=off&iss.only=description,boards
"""

from datetime import date, datetime
from typing import Any, Dict, List, Optional

import strawberry

from apps.marketdata.services.redis_json import RedisJSON


# -------------------------
# Helpers (same style)
# -------------------------

def _idx(columns: List[str]) -> Dict[str, int]:
    return {c: i for i, c in enumerate(columns) if isinstance(c, str)}


def _get(row: List[Any], i: Optional[int]) -> Any:
    if i is None:
        return None
    if i < 0 or i >= len(row):
        return None
    return row[i]


def _to_str(x: Any) -> Optional[str]:
    if x is None:
        return None
    if isinstance(x, str):
        return x
    return str(x)


def _to_int(x: Any) -> Optional[int]:
    if x is None or x == "":
        return None
    try:
        return int(x)
    except Exception:
        return None


def _to_float(x: Any) -> Optional[float]:
    if x is None or x == "":
        return None
    try:
        return float(x)
    except Exception:
        return None


def _to_date(x: Any) -> Optional[date]:
    if x is None or x == "":
        return None
    if isinstance(x, date) and not isinstance(x, datetime):
        return x
    if isinstance(x, datetime):
        return x.date()
    if isinstance(x, str):
        try:
            # MOEX обычно возвращает "YYYY-MM-DD"
            if "T" in x:
                return datetime.fromisoformat(x.replace("Z", "+00:00")).date()
            return date.fromisoformat(x)
        except Exception:
            return None
    return None


def _to_datetime(x: Any) -> Optional[datetime]:
    if x is None or x == "":
        return None
    if isinstance(x, datetime):
        return x
    if isinstance(x, str):
        try:
            return datetime.fromisoformat(x.replace("Z", "+00:00"))
        except Exception:
            return None
    return None


# -------------------------
# Strawberry DTOs
# -------------------------

@strawberry.type
class MOEXSecurityDescriptionItem:
    name: Optional[str] = None
    title: Optional[str] = None
    value: Optional[str] = None
    type: Optional[str] = None
    sort_order: Optional[int] = None
    is_hidden: Optional[int] = None
    precision: Optional[int] = None


def parse_moex_security_description_row(row: List[Any], cols: Dict[str, int]) -> MOEXSecurityDescriptionItem:
    return MOEXSecurityDescriptionItem(
        name=_to_str(_get(row, cols.get("name"))),
        title=_to_str(_get(row, cols.get("title"))),
        value=_to_str(_get(row, cols.get("value"))),
        type=_to_str(_get(row, cols.get("type"))),
        sort_order=_to_int(_get(row, cols.get("sort_order"))),
        is_hidden=_to_int(_get(row, cols.get("is_hidden"))),
        precision=_to_int(_get(row, cols.get("precision"))),
    )


def parse_moex_security_description_table(table: Dict[str, Any]) -> List[MOEXSecurityDescriptionItem]:
    if not isinstance(table, dict):
        return []
    columns = table.get("columns") or []
    data = table.get("data") or []
    if not isinstance(columns, list) or not isinstance(data, list):
        return []
    cols = _idx(columns)
    return [parse_moex_security_description_row(r, cols) for r in data if isinstance(r, list)]


@strawberry.type
class MOEXSecurityBoard:
    secid: Optional[str] = None
    boardid: Optional[str] = None
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


def parse_moex_security_board_row(row: List[Any], cols: Dict[str, int]) -> MOEXSecurityBoard:
    return MOEXSecurityBoard(
        secid=_to_str(_get(row, cols.get("secid"))),
        boardid=_to_str(_get(row, cols.get("boardid"))),
        title=_to_str(_get(row, cols.get("title"))),

        board_group_id=_to_int(_get(row, cols.get("board_group_id"))),
        market_id=_to_int(_get(row, cols.get("market_id"))),
        market=_to_str(_get(row, cols.get("market"))),
        engine_id=_to_int(_get(row, cols.get("engine_id"))),
        engine=_to_str(_get(row, cols.get("engine"))),

        is_traded=_to_int(_get(row, cols.get("is_traded"))),
        decimals=_to_int(_get(row, cols.get("decimals"))),

        history_from=_to_date(_get(row, cols.get("history_from"))),
        history_till=_to_date(_get(row, cols.get("history_till"))),
        listed_from=_to_date(_get(row, cols.get("listed_from"))),
        listed_till=_to_date(_get(row, cols.get("listed_till"))),

        is_primary=_to_int(_get(row, cols.get("is_primary"))),
        currencyid=_to_str(_get(row, cols.get("currencyid"))),
        unit=_to_str(_get(row, cols.get("unit"))),
    )


def parse_moex_security_boards_table(table: Dict[str, Any]) -> List[MOEXSecurityBoard]:
    if not isinstance(table, dict):
        return []
    columns = table.get("columns") or []
    data = table.get("data") or []
    if not isinstance(columns, list) or not isinstance(data, list):
        return []
    cols = _idx(columns)
    return [parse_moex_security_board_row(r, cols) for r in data if isinstance(r, list)]


@strawberry.type
class MOEXStockSharesTQTFDataVersion:
    data_version: Optional[int] = None
    seqnum: Optional[int] = None
    trade_date: Optional[date] = None
    trade_session_date: Optional[date] = None


def parse_moex_security_detail_dataversion(table: Dict[str, Any]) -> Optional[MOEXStockSharesTQTFDataVersion]:
    if not isinstance(table, dict):
        return None
    columns = table.get("columns") or []
    data = table.get("data") or []
    if not isinstance(columns, list) or not isinstance(data, list) or not data:
        return None
    cols = _idx(columns)
    row = data[0] if isinstance(data[0], list) else None
    if row is None:
        return None

    return MOEXStockSharesTQTFDataVersion(
        data_version=_to_int(_get(row, cols.get("data_version"))),
        seqnum=_to_int(_get(row, cols.get("seqnum"))),
        trade_date=_to_date(_get(row, cols.get("trade_date"))),
        trade_session_date=_to_date(_get(row, cols.get("trade_session_date"))),
    )


# -------------------------
# Redis JSON DTO (same style)
# -------------------------

@strawberry.type
class MOEXStockSharesTQTFSecurities(RedisJSON):
    description: List[MOEXSecurityDescriptionItem] = strawberry.field(default_factory=list)
    boards: List[MOEXSecurityBoard] = strawberry.field(default_factory=list)
    dataversion: Optional[MOEXStockSharesTQTFDataVersion] = None


def parse_moex_security_detail_response(raw: Dict[str, Any]) -> MOEXStockSharesTQTFSecurities:
    """
    Ожидает реальный формат MOEX (без metadata):
    {
      "description": {"columns": [...], "data": [...]},
      "boards": {"columns": [...], "data": [...]},
      "dataversion": {"columns": [...], "data": [...]}
    }
    """
    if not isinstance(raw, dict):
        return MOEXStockSharesTQTFSecurities()

    description = parse_moex_security_description_table(raw.get("description") or {})
    boards = parse_moex_security_boards_table(raw.get("boards") or {})
    dv = parse_moex_security_detail_dataversion(raw.get("dataversion") or {})

    return MOEXStockSharesTQTFSecurities(
        description=description,
        boards=boards,
        dataversion=dv,
    )
