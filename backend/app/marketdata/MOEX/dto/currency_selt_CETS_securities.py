from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

import strawberry
from strawberry.scalars import JSON

from app.marketdata.services.redis_json import RedisJSON


@strawberry.type
class MOEXCETSSection:
    columns: List[str] = strawberry.field(default_factory=list)
    data: JSON = strawberry.field(default_factory=list)
    metadata: Optional[JSON] = None


@strawberry.type
class MOEXCETSDataVersion:
    data_version: Optional[int] = None
    seqnum: Optional[int] = None
    trade_date: Optional[date] = None
    trade_session_date: Optional[date] = None


@strawberry.type
class MOEXCurrencySeltCETSSecurities(RedisJSON):
    securities: Optional[MOEXCETSSection] = None
    marketdata: Optional[MOEXCETSSection] = None
    dataversion: Optional[MOEXCETSDataVersion] = None


def _to_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_date(value: Any) -> Optional[date]:
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _parse_section(section: Dict[str, Any]) -> MOEXCETSSection:
    if not isinstance(section, dict):
        return MOEXCETSSection()

    columns = section.get("columns") or []
    data = section.get("data") or []
    metadata = section.get("metadata")

    if not isinstance(columns, list):
        columns = []
    if not isinstance(data, list):
        data = []

    return MOEXCETSSection(
        columns=columns,
        data=data,
        metadata=metadata,
    )


def _parse_dataversion(section: Dict[str, Any]) -> Optional[MOEXCETSDataVersion]:
    if not isinstance(section, dict):
        return None

    columns = section.get("columns") or []
    data = section.get("data") or []
    if not isinstance(columns, list) or not isinstance(data, list) or not data:
        return None

    index_by_name = {str(name): idx for idx, name in enumerate(columns)}
    row = data[0]
    if not isinstance(row, list):
        return None

    def get(col: str) -> Any:
        idx = index_by_name.get(col)
        if idx is None or idx >= len(row):
            return None
        return row[idx]

    return MOEXCETSDataVersion(
        data_version=_to_int(get("data_version")),
        seqnum=_to_int(get("seqnum")),
        trade_date=_to_date(get("trade_date")),
        trade_session_date=_to_date(get("trade_session_date")),
    )


def parse_moex_currency_selt_cets_securities_response(
    raw: Dict[str, Any],
) -> MOEXCurrencySeltCETSSecurities:
    if not isinstance(raw, dict):
        return MOEXCurrencySeltCETSSecurities()

    return MOEXCurrencySeltCETSSecurities(
        securities=_parse_section(raw.get("securities") or {}),
        marketdata=_parse_section(raw.get("marketdata") or {}),
        dataversion=_parse_dataversion(raw.get("dataversion") or {}),
    )
