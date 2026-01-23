# apps/marketdata/providers/StockMarketRussia/MOEX/dto/currency_selt_metl_securities.py
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
class MoexSeltMetlSecuritiesRow:
    SECID: str
    BOARDID: str
    SHORTNAME: Optional[str]
    LOTSIZE: Optional[int]
    SETTLEDATE: Optional[date]
    DECIMALS: Optional[int]
    FACEVALUE: Optional[float]
    MARKETCODE: Optional[str]
    MINSTEP: Optional[float]
    PREVDATE: Optional[date]
    SECNAME: Optional[str]
    REMARKS: Optional[str]
    STATUS: Optional[str]
    FACEUNIT: Optional[str]
    PREVPRICE: Optional[float]
    PREVWAPRICE: Optional[float]
    CURRENCYID: Optional[str]
    LATNAME: Optional[str]
    LOTDIVIDER: Optional[int]

    @classmethod
    def from_moex_row(cls, r: Dict[str, Any]) -> "MoexSeltMetlSecuritiesRow":
        return cls(
            SECID=str(r.get("SECID") or ""),
            BOARDID=str(r.get("BOARDID") or ""),
            SHORTNAME=(r.get("SHORTNAME") if r.get("SHORTNAME") is not None else None),
            LOTSIZE=_to_int(r.get("LOTSIZE")),
            SETTLEDATE=_parse_date(r.get("SETTLEDATE")),
            DECIMALS=_to_int(r.get("DECIMALS")),
            FACEVALUE=_to_float(r.get("FACEVALUE")),
            MARKETCODE=(r.get("MARKETCODE") if r.get("MARKETCODE") is not None else None),
            MINSTEP=_to_float(r.get("MINSTEP")),
            PREVDATE=_parse_date(r.get("PREVDATE")),
            SECNAME=(r.get("SECNAME") if r.get("SECNAME") is not None else None),
            REMARKS=(r.get("REMARKS") if r.get("REMARKS") is not None else None),
            STATUS=(r.get("STATUS") if r.get("STATUS") is not None else None),
            FACEUNIT=(r.get("FACEUNIT") if r.get("FACEUNIT") is not None else None),
            PREVPRICE=_to_float(r.get("PREVPRICE")),
            PREVWAPRICE=_to_float(r.get("PREVWAPRICE")),
            CURRENCYID=(r.get("CURRENCYID") if r.get("CURRENCYID") is not None else None),
            LATNAME=(r.get("LATNAME") if r.get("LATNAME") is not None else None),
            LOTDIVIDER=_to_int(r.get("LOTDIVIDER")),
        )


@strawberry.type
class MoexSeltMetlMarketdataRow:
    BOARDID: str
    SECID: str

    HIGHBID: Optional[float]
    BIDDEPTH: Optional[int]
    LOWOFFER: Optional[float]
    OFFERDEPTH: Optional[int]

    SPREAD: Optional[float]
    HIGH: Optional[float]
    LOW: Optional[float]
    OPEN: Optional[float]
    LAST: Optional[float]
    LASTCNGTOLASTWAPRICE: Optional[float]

    VALTODAY: Optional[int]
    VOLTODAY: Optional[float]
    VALTODAY_USD: Optional[int]

    WAPRICE: Optional[float]
    WAPTOPREVWAPRICE: Optional[float]
    CLOSEPRICE: Optional[float]
    NUMTRADES: Optional[int]

    TRADINGSTATUS: Optional[str]
    UPDATETIME: Optional[time]

    WAPTOPREVWAPRICEPRCNT: Optional[float]

    BID: Optional[float]
    BIDDEPTHT: Optional[int]
    NUMBIDS: Optional[int]
    OFFER: Optional[float]
    OFFERDEPTHT: Optional[int]
    NUMOFFERS: Optional[int]

    CHANGE: Optional[float]
    LASTCHANGEPRCNT: Optional[float]
    VALUE: Optional[float]
    VALUE_USD: Optional[float]
    SEQNUM: Optional[int]
    QTY: Optional[int]
    TIME: Optional[time]

    PRICEMINUSPREVWAPRICE: Optional[float]
    LASTCHANGE: Optional[float]
    LASTTOPREVPRICE: Optional[float]
    VALTODAY_RUR: Optional[int]
    SYSTIME: Optional[datetime]

    MARKETPRICE: Optional[float]
    MARKETPRICETODAY: Optional[float]
    MARKETPRICE2: Optional[float]
    ADMITTEDQUOTE: Optional[float]
    LOPENPRICE: Optional[float]

    @classmethod
    def from_moex_row(cls, r: Dict[str, Any]) -> "MoexSeltMetlMarketdataRow":
        return cls(
            BOARDID=str(r.get("BOARDID") or ""),
            SECID=str(r.get("SECID") or ""),
            HIGHBID=_to_float(r.get("HIGHBID")),
            BIDDEPTH=_to_int(r.get("BIDDEPTH")),
            LOWOFFER=_to_float(r.get("LOWOFFER")),
            OFFERDEPTH=_to_int(r.get("OFFERDEPTH")),
            SPREAD=_to_float(r.get("SPREAD")),
            HIGH=_to_float(r.get("HIGH")),
            LOW=_to_float(r.get("LOW")),
            OPEN=_to_float(r.get("OPEN")),
            LAST=_to_float(r.get("LAST")),
            LASTCNGTOLASTWAPRICE=_to_float(r.get("LASTCNGTOLASTWAPRICE")),
            VALTODAY=_to_int(r.get("VALTODAY")),
            VOLTODAY=_to_float(r.get("VOLTODAY")),
            VALTODAY_USD=_to_int(r.get("VALTODAY_USD")),
            WAPRICE=_to_float(r.get("WAPRICE")),
            WAPTOPREVWAPRICE=_to_float(r.get("WAPTOPREVWAPRICE")),
            CLOSEPRICE=_to_float(r.get("CLOSEPRICE")),
            NUMTRADES=_to_int(r.get("NUMTRADES")),
            TRADINGSTATUS=(r.get("TRADINGSTATUS") if r.get("TRADINGSTATUS") is not None else None),
            UPDATETIME=_parse_time(r.get("UPDATETIME")),
            WAPTOPREVWAPRICEPRCNT=_to_float(r.get("WAPTOPREVWAPRICEPRCNT")),
            BID=_to_float(r.get("BID")),
            BIDDEPTHT=_to_int(r.get("BIDDEPTHT")),
            NUMBIDS=_to_int(r.get("NUMBIDS")),
            OFFER=_to_float(r.get("OFFER")),
            OFFERDEPTHT=_to_int(r.get("OFFERDEPTHT")),
            NUMOFFERS=_to_int(r.get("NUMOFFERS")),
            CHANGE=_to_float(r.get("CHANGE")),
            LASTCHANGEPRCNT=_to_float(r.get("LASTCHANGEPRCNT")),
            VALUE=_to_float(r.get("VALUE")),
            VALUE_USD=_to_float(r.get("VALUE_USD")),
            SEQNUM=_to_int(r.get("SEQNUM")),
            QTY=_to_int(r.get("QTY")),
            TIME=_parse_time(r.get("TIME")),
            PRICEMINUSPREVWAPRICE=_to_float(r.get("PRICEMINUSPREVWAPRICE")),
            LASTCHANGE=_to_float(r.get("LASTCHANGE")),
            LASTTOPREVPRICE=_to_float(r.get("LASTTOPREVPRICE")),
            VALTODAY_RUR=_to_int(r.get("VALTODAY_RUR")),
            SYSTIME=_parse_datetime(r.get("SYSTIME")),
            MARKETPRICE=_to_float(r.get("MARKETPRICE")),
            MARKETPRICETODAY=_to_float(r.get("MARKETPRICETODAY")),
            MARKETPRICE2=_to_float(r.get("MARKETPRICE2")),
            ADMITTEDQUOTE=_to_float(r.get("ADMITTEDQUOTE")),
            LOPENPRICE=_to_float(r.get("LOPENPRICE")),
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
class MoexSeltMetlMarketdataYieldsRow:
    # В ответе по вашему примеру только boardid/secid и пустой data, но DTO сделаем совместимым.
    SECID: str
    BOARDID: str

    @classmethod
    def from_moex_row(cls, r: Dict[str, Any]) -> "MoexSeltMetlMarketdataYieldsRow":
        secid = r.get("SECID")
        if secid is None:
            secid = r.get("secid")
        boardid = r.get("BOARDID")
        if boardid is None:
            boardid = r.get("boardid")
        return cls(
            SECID=str(secid or ""),
            BOARDID=str(boardid or ""),
        )


@strawberry.type
class MOEXCurrencySeltMETLSecuritiesResponse(RedisJSON):
    securities: List[MoexSeltMetlSecuritiesRow]
    marketdata: List[MoexSeltMetlMarketdataRow]
    dataversion: Optional[MoexDataversionRow]
    marketdata_yields: List[MoexSeltMetlMarketdataYieldsRow]

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "MOEXCurrencySeltMETLSecuritiesResponse":
        return cls(
            securities=_parse_table(payload, "securities", MoexSeltMetlSecuritiesRow),
            marketdata=_parse_table(payload, "marketdata", MoexSeltMetlMarketdataRow),
            dataversion=_parse_single(payload, "dataversion", MoexDataversionRow),
            marketdata_yields=_parse_table(payload, "marketdata_yields", MoexSeltMetlMarketdataYieldsRow),
        )


# Backward-compatible alias expected by MOEX provider import.
class MOEXCurrencySeltCETSSecurities(MOEXCurrencySeltMETLSecuritiesResponse):
    pass


def parse_moex_currency_selt_cets_securities_response(
    payload: Dict[str, Any],
) -> MOEXCurrencySeltCETSSecurities:
    return MOEXCurrencySeltCETSSecurities.from_payload(payload)
