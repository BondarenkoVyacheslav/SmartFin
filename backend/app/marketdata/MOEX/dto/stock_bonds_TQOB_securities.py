# apps/marketdata/providers/StockMarketRussia/MOEX/dto/stock_bonds_TQOB_securities.py

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any, Dict, List, Optional, Type, TypeVar

import strawberry

from app.marketdata.services.redis_json import RedisJSON

T = TypeVar("T")


def _parse_date(v: Any) -> Optional[date]:
    if v is None:
        return None
    if isinstance(v, date) and not isinstance(v, datetime):
        return v
    if isinstance(v, str):
        if v in ("", "0000-00-00"):
            return None
        try:
            return date.fromisoformat(v)
        except ValueError:
            return None
    return None


def _parse_time(v: Any) -> Optional[time]:
    if v is None:
        return None
    if isinstance(v, time):
        return v
    if isinstance(v, str):
        if v == "":
            return None
        try:
            return time.fromisoformat(v)
        except ValueError:
            return None
    return None


def _parse_datetime(v: Any) -> Optional[datetime]:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v
    if isinstance(v, str):
        if v == "":
            return None
        try:
            # MOEX often uses "YYYY-MM-DD HH:MM:SS"
            return datetime.fromisoformat(v)
        except ValueError:
            return None
    return None


def _to_int(v: Any) -> Optional[int]:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _to_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _rows_as_dicts(table: Dict[str, Any]) -> List[Dict[str, Any]]:
    cols: List[str] = table.get("columns") or []
    data: List[List[Any]] = table.get("data") or []
    out: List[Dict[str, Any]] = []
    for row in data:
        d = {cols[i]: row[i] for i in range(min(len(cols), len(row)))}
        out.append(d)
    return out


def _parse_table(payload: Dict[str, Any], key: str, cls: Type[T]) -> List[T]:
    table = payload.get(key) or {}
    rows = _rows_as_dicts(table)
    return [cls.from_moex_row(r) for r in rows]  # type: ignore[attr-defined]


def _parse_single(payload: Dict[str, Any], key: str, cls: Type[T]) -> Optional[T]:
    items = _parse_table(payload, key, cls)
    return items[0] if items else None


@strawberry.type
class MoexBondSecuritiesRow:
    SECID: str
    BOARDID: str
    SHORTNAME: Optional[str]
    SECNAME: Optional[str]
    ISIN: Optional[str]
    FACEUNIT: Optional[str]
    CURRENCYID: Optional[str]
    LOTSIZE: Optional[int]
    FACEVALUE: Optional[float]
    MATDATE: Optional[date]
    COUPONVALUE: Optional[float]
    COUPONPERCENT: Optional[float]
    COUPONPERIOD: Optional[int]
    NEXTCOUPON: Optional[date]
    ACCRUEDINT: Optional[float]
    OFFERDATE: Optional[date]
    SETTLEDATE: Optional[date]
    STATUS: Optional[str]
    LISTLEVEL: Optional[int]
    SECTYPE: Optional[str]
    BONDTYPE: Optional[str]
    BONDSUBTYPE: Optional[str]

    @classmethod
    def from_moex_row(cls, r: Dict[str, Any]) -> "MoexBondSecuritiesRow":
        return cls(
            SECID=str(r.get("SECID") or ""),
            BOARDID=str(r.get("BOARDID") or ""),
            SHORTNAME=(r.get("SHORTNAME") if r.get("SHORTNAME") is not None else None),
            SECNAME=(r.get("SECNAME") if r.get("SECNAME") is not None else None),
            ISIN=(r.get("ISIN") if r.get("ISIN") is not None else None),
            FACEUNIT=(r.get("FACEUNIT") if r.get("FACEUNIT") is not None else None),
            CURRENCYID=(r.get("CURRENCYID") if r.get("CURRENCYID") is not None else None),
            LOTSIZE=_to_int(r.get("LOTSIZE")),
            FACEVALUE=_to_float(r.get("FACEVALUE")),
            MATDATE=_parse_date(r.get("MATDATE")),
            COUPONVALUE=_to_float(r.get("COUPONVALUE")),
            COUPONPERCENT=_to_float(r.get("COUPONPERCENT")),
            COUPONPERIOD=_to_int(r.get("COUPONPERIOD")),
            NEXTCOUPON=_parse_date(r.get("NEXTCOUPON")),
            ACCRUEDINT=_to_float(r.get("ACCRUEDINT")),
            OFFERDATE=_parse_date(r.get("OFFERDATE")),
            SETTLEDATE=_parse_date(r.get("SETTLEDATE")),
            STATUS=(r.get("STATUS") if r.get("STATUS") is not None else None),
            LISTLEVEL=_to_int(r.get("LISTLEVEL")),
            SECTYPE=(r.get("SECTYPE") if r.get("SECTYPE") is not None else None),
            BONDTYPE=(r.get("BONDTYPE") if r.get("BONDTYPE") is not None else None),
            BONDSUBTYPE=(r.get("BONDSUBTYPE") if r.get("BONDSUBTYPE") is not None else None),
        )


@strawberry.type
class MoexBondMarketdataRow:
    SECID: str
    BOARDID: str
    TRADINGSTATUS: Optional[str]
    UPDATETIME: Optional[time]
    LAST: Optional[float]
    WAPRICE: Optional[float]
    YIELD: Optional[float]
    YIELDATWAPRICE: Optional[float]
    CLOSEPRICE: Optional[float]
    MARKETPRICE: Optional[float]
    MARKETPRICETODAY: Optional[float]
    NUMTRADES: Optional[int]
    VOLTODAY: Optional[int]
    VALTODAY: Optional[int]

    @classmethod
    def from_moex_row(cls, r: Dict[str, Any]) -> "MoexBondMarketdataRow":
        return cls(
            SECID=str(r.get("SECID") or ""),
            BOARDID=str(r.get("BOARDID") or ""),
            TRADINGSTATUS=(r.get("TRADINGSTATUS") if r.get("TRADINGSTATUS") is not None else None),
            UPDATETIME=_parse_time(r.get("UPDATETIME")),
            LAST=_to_float(r.get("LAST")),
            WAPRICE=_to_float(r.get("WAPRICE")),
            YIELD=_to_float(r.get("YIELD")),
            YIELDATWAPRICE=_to_float(r.get("YIELDATWAPRICE")),
            CLOSEPRICE=_to_float(r.get("CLOSEPRICE")),
            MARKETPRICE=_to_float(r.get("MARKETPRICE")),
            MARKETPRICETODAY=_to_float(r.get("MARKETPRICETODAY")),
            NUMTRADES=_to_int(r.get("NUMTRADES")),
            VOLTODAY=_to_int(r.get("VOLTODAY")),
            VALTODAY=_to_int(r.get("VALTODAY")),
        )


@strawberry.type
class MoexDataversionRow:
    data_version: int
    seqnum: int
    trade_date: date
    trade_session_date: date

    @classmethod
    def from_moex_row(cls, r: Dict[str, Any]) -> "MoexDataversionRow":
        dv = _to_int(r.get("data_version"))
        seq = _to_int(r.get("seqnum"))
        td = _parse_date(r.get("trade_date"))
        tsd = _parse_date(r.get("trade_session_date"))
        return cls(
            data_version=dv if dv is not None else 0,
            seqnum=seq if seq is not None else 0,
            trade_date=td if td is not None else date.min,
            trade_session_date=tsd if tsd is not None else date.min,
        )


@strawberry.type
class MoexBondMarketdataYieldsRow:
    SECID: str
    BOARDID: str
    PRICE: Optional[float]
    YIELDDATE: Optional[date]
    YIELDDATETYPE: Optional[str]
    EFFECTIVEYIELD: Optional[float]
    DURATION: Optional[int]
    ZSPREADBP: Optional[int]
    GSPREADBP: Optional[int]
    WAPRICE: Optional[float]
    EFFECTIVEYIELDWAPRICE: Optional[float]
    DURATIONWAPRICE: Optional[int]
    SEQNUM: Optional[int]
    SYSTIME: Optional[datetime]

    @classmethod
    def from_moex_row(cls, r: Dict[str, Any]) -> "MoexBondMarketdataYieldsRow":
        return cls(
            SECID=str(r.get("SECID") or ""),
            BOARDID=str(r.get("BOARDID") or ""),
            PRICE=_to_float(r.get("PRICE")),
            YIELDDATE=_parse_date(r.get("YIELDDATE")),
            YIELDDATETYPE=(r.get("YIELDDATETYPE") if r.get("YIELDDATETYPE") is not None else None),
            EFFECTIVEYIELD=_to_float(r.get("EFFECTIVEYIELD")),
            DURATION=_to_int(r.get("DURATION")),
            ZSPREADBP=_to_int(r.get("ZSPREADBP")),
            GSPREADBP=_to_int(r.get("GSPREADBP")),
            WAPRICE=_to_float(r.get("WAPRICE")),
            EFFECTIVEYIELDWAPRICE=_to_float(r.get("EFFECTIVEYIELDWAPRICE")),
            DURATIONWAPRICE=_to_int(r.get("DURATIONWAPRICE")),
            SEQNUM=_to_int(r.get("SEQNUM")),
            SYSTIME=_parse_datetime(r.get("SYSTIME")),
        )


@strawberry.type
class MOEXStockBondsTQOBSecuritiesResponse(RedisJSON):
    securities: List[MoexBondSecuritiesRow]
    marketdata: List[MoexBondMarketdataRow]
    dataversion: Optional[MoexDataversionRow]
    marketdata_yields: List[MoexBondMarketdataYieldsRow]

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "MOEXStockBondsTQOBSecuritiesResponse":
        return cls(
            securities=_parse_table(payload, "securities", MoexBondSecuritiesRow),
            marketdata=_parse_table(payload, "marketdata", MoexBondMarketdataRow),
            dataversion=_parse_single(payload, "dataversion", MoexDataversionRow),
            marketdata_yields=_parse_table(payload, "marketdata_yields", MoexBondMarketdataYieldsRow),
        )
