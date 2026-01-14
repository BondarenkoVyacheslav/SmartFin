from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, List, Optional

import strawberry

from apps.marketdata.services.redis_json import RedisJSON


# =========================
# Helpers
# =========================

def _idx(columns: List[str]) -> Dict[str, int]:
    return {c: i for i, c in enumerate(columns or [])}


def _get(row: List[Any], m: Dict[str, int], col: str) -> Any:
    i = m.get(col)
    if i is None:
        return None
    if not isinstance(row, list) or i >= len(row):
        return None
    return row[i]


def _to_str(x: Any) -> Optional[str]:
    if x is None:
        return None
    if isinstance(x, str):
        return x
    return str(x)


def _to_int(x: Any) -> Optional[int]:
    if x is None:
        return None
    try:
        # на MOEX иногда числа приходят как float/str
        return int(float(x)) if isinstance(x, (float, str)) else int(x)
    except (TypeError, ValueError):
        return None


def _to_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _to_date(x: Any) -> Optional[date]:
    s = _to_str(x)
    if not s:
        return None
    try:
        # "YYYY-MM-DD"
        return date.fromisoformat(s)
    except ValueError:
        return None


def _to_datetime(x: Any) -> Optional[datetime]:
    s = _to_str(x)
    if not s:
        return None
    try:
        # "YYYY-MM-DD HH:MM:SS" (как в примере)
        return datetime.fromisoformat(s)
    except ValueError:
        return None


# =========================
# DTO: securities
# =========================

@strawberry.type
class MOEXSndxSecurity:
    secid: str
    boardid: str

    name: Optional[str] = None
    decimals: Optional[int] = None
    shortname: Optional[str] = None

    annual_high: Optional[float] = None
    annual_low: Optional[float] = None

    currency_id: Optional[str] = None
    calc_mode: Optional[str] = None


def parse_moex_sndx_securities_table(section: Dict[str, Any]) -> List[MOEXSndxSecurity]:
    if not isinstance(section, dict):
        return []

    columns = section.get("columns") or []
    data = section.get("data") or []
    if not isinstance(columns, list) or not isinstance(data, list):
        return []

    m = _idx(columns)
    out: List[MOEXSndxSecurity] = []

    for row in data:
        if not isinstance(row, list):
            continue

        secid = _to_str(_get(row, m, "SECID"))
        boardid = _to_str(_get(row, m, "BOARDID"))
        if not secid or not boardid:
            continue

        out.append(
            MOEXSndxSecurity(
                secid=secid,
                boardid=boardid,
                name=_to_str(_get(row, m, "NAME")),
                decimals=_to_int(_get(row, m, "DECIMALS")),
                shortname=_to_str(_get(row, m, "SHORTNAME")),
                annual_high=_to_float(_get(row, m, "ANNUALHIGH")),
                annual_low=_to_float(_get(row, m, "ANNUALLOW")),
                currency_id=_to_str(_get(row, m, "CURRENCYID")),
                calc_mode=_to_str(_get(row, m, "CALCMODE")),
            )
        )

    return out


# =========================
# DTO: marketdata
# =========================

@strawberry.type
class MOEXSndxMarketData:
    secid: str
    boardid: str

    last_value: Optional[float] = None
    open_value: Optional[float] = None
    current_value: Optional[float] = None

    last_change: Optional[float] = None
    last_change_to_open_prc: Optional[float] = None
    last_change_to_open: Optional[float] = None

    update_time: Optional[str] = None          # "HH:MM:SS"
    last_change_prc: Optional[float] = None

    val_today: Optional[float] = None
    month_change_prc: Optional[float] = None
    year_change_prc: Optional[float] = None

    seqnum: Optional[int] = None
    sys_time: Optional[datetime] = None        # "YYYY-MM-DD HH:MM:SS"
    time: Optional[str] = None                 # "HH:MM:SS"

    val_today_usd: Optional[float] = None

    last_change_bp: Optional[float] = None
    month_change_bp: Optional[float] = None
    year_change_bp: Optional[float] = None

    capitalization: Optional[float] = None
    capitalization_usd: Optional[float] = None

    high: Optional[float] = None
    low: Optional[float] = None

    trade_date: Optional[date] = None
    trading_session: Optional[str] = None

    vol_today: Optional[float] = None
    trade_session_date: Optional[date] = None


def parse_moex_sndx_marketdata_table(section: Dict[str, Any]) -> List[MOEXSndxMarketData]:
    if not isinstance(section, dict):
        return []

    columns = section.get("columns") or []
    data = section.get("data") or []
    if not isinstance(columns, list) or not isinstance(data, list):
        return []

    m = _idx(columns)
    out: List[MOEXSndxMarketData] = []

    for row in data:
        if not isinstance(row, list):
            continue

        secid = _to_str(_get(row, m, "SECID"))
        boardid = _to_str(_get(row, m, "BOARDID"))
        if not secid or not boardid:
            continue

        out.append(
            MOEXSndxMarketData(
                secid=secid,
                boardid=boardid,
                last_value=_to_float(_get(row, m, "LASTVALUE")),
                open_value=_to_float(_get(row, m, "OPENVALUE")),
                current_value=_to_float(_get(row, m, "CURRENTVALUE")),
                last_change=_to_float(_get(row, m, "LASTCHANGE")),
                last_change_to_open_prc=_to_float(_get(row, m, "LASTCHANGETOOPENPRC")),
                last_change_to_open=_to_float(_get(row, m, "LASTCHANGETOOPEN")),
                update_time=_to_str(_get(row, m, "UPDATETIME")),
                last_change_prc=_to_float(_get(row, m, "LASTCHANGEPRC")),
                val_today=_to_float(_get(row, m, "VALTODAY")),
                month_change_prc=_to_float(_get(row, m, "MONTHCHANGEPRC")),
                year_change_prc=_to_float(_get(row, m, "YEARCHANGEPRC")),
                seqnum=_to_int(_get(row, m, "SEQNUM")),
                sys_time=_to_datetime(_get(row, m, "SYSTIME")),
                time=_to_str(_get(row, m, "TIME")),
                val_today_usd=_to_float(_get(row, m, "VALTODAY_USD")),
                last_change_bp=_to_float(_get(row, m, "LASTCHANGEBP")),
                month_change_bp=_to_float(_get(row, m, "MONTHCHANGEBP")),
                year_change_bp=_to_float(_get(row, m, "YEARCHANGEBP")),
                capitalization=_to_float(_get(row, m, "CAPITALIZATION")),
                capitalization_usd=_to_float(_get(row, m, "CAPITALIZATION_USD")),
                high=_to_float(_get(row, m, "HIGH")),
                low=_to_float(_get(row, m, "LOW")),
                trade_date=_to_date(_get(row, m, "TRADEDATE")),
                trading_session=_to_str(_get(row, m, "TRADINGSESSION")),
                vol_today=_to_float(_get(row, m, "VOLTODAY")),
                trade_session_date=_to_date(_get(row, m, "TRADE_SESSION_DATE")),
            )
        )

    return out


# =========================
# DTO: dataversion
# =========================

@strawberry.type
class MOEXSndxDataVersion:
    data_version: Optional[int] = None
    seqnum: Optional[int] = None
    trade_date: Optional[date] = None
    trade_session_date: Optional[date] = None


def parse_moex_sndx_dataversion(section: Dict[str, Any]) -> Optional[MOEXSndxDataVersion]:
    if not isinstance(section, dict):
        return None

    columns = section.get("columns") or []
    data = section.get("data") or []
    if not isinstance(columns, list) or not isinstance(data, list) or not data:
        return None

    m = _idx(columns)
    row = data[0]
    if not isinstance(row, list):
        return None

    return MOEXSndxDataVersion(
        data_version=_to_int(_get(row, m, "data_version")),
        seqnum=_to_int(_get(row, m, "seqnum")),
        trade_date=_to_date(_get(row, m, "trade_date")),
        trade_session_date=_to_date(_get(row, m, "trade_session_date")),
    )


# =========================
# Response DTO (обёртка)
# =========================

@strawberry.type
class MOEXStockIndexSndxSecurities(RedisJSON):
    securities: List[MOEXSndxSecurity] = strawberry.field(default_factory=list)
    marketdata: List[MOEXSndxMarketData] = strawberry.field(default_factory=list)
    dataversion: Optional[MOEXSndxDataVersion] = None


def parse_moex_sndx_securities_response(raw: Dict[str, Any]) -> MOEXStockIndexSndxSecurities:
    """
    Ожидает реальный формат MOEX (без metadata):
    {
      "securities": {"columns": [...], "data": [...]},
      "marketdata": {"columns": [...], "data": [...]},
      "dataversion": {"columns": [...], "data": [...]}
    }
    """
    if not isinstance(raw, dict):
        return MOEXStockIndexSndxSecurities()

    sec = parse_moex_sndx_securities_table(raw.get("securities") or {})
    md = parse_moex_sndx_marketdata_table(raw.get("marketdata") or {})
    dv = parse_moex_sndx_dataversion(raw.get("dataversion") or {})

    return MOEXStockIndexSndxSecurities(
        securities=sec,
        marketdata=md,
        dataversion=dv,
    )
