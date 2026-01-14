from __future__ import annotations

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
        if isinstance(x, bool):
            return int(x)
        if isinstance(x, int):
            return x
        if isinstance(x, float):
            return int(x)
        if isinstance(x, str):
            s = x.strip()
            if not s:
                return None
            # Если это целое без точки/экспоненты — парсим как int напрямую (без потерь точности)
            if s.lstrip("+-").isdigit():
                return int(s)
            return int(float(s))
        return int(x)
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
        # Иногда MOEX отдаёт "0000-00-00" — это невалидная дата, поэтому вернём None
        return date.fromisoformat(s)
    except ValueError:
        return None


def _to_datetime(x: Any) -> Optional[datetime]:
    s = _to_str(x)
    if not s:
        return None
    try:
        # MOEX обычно отдаёт "YYYY-MM-DD HH:MM:SS"
        return datetime.fromisoformat(s)
    except ValueError:
        return None


# =========================
# DTO: securities
# =========================


@strawberry.type
class MOEXStockBondsTQCBSecurity:
    secid: str
    boardid: str

    shortname: Optional[str] = None
    prev_waprice: Optional[float] = None
    yield_at_prev_waprice: Optional[float] = None

    coupon_value: Optional[float] = None
    coupon_percent: Optional[float] = None
    next_coupon: Optional[date] = None
    coupon_period: Optional[int] = None

    accrued_int: Optional[float] = None

    prev_price: Optional[float] = None
    prev_legal_close_price: Optional[float] = None
    prev_date: Optional[date] = None

    lot_size: Optional[int] = None
    lot_value: Optional[float] = None

    face_value: Optional[float] = None
    face_unit: Optional[str] = None
    face_value_on_settle_date: Optional[float] = None

    status: Optional[str] = None
    board_name: Optional[str] = None

    mat_date: Optional[date] = None
    decimals: Optional[int] = None

    issue_size: Optional[int] = None
    issue_size_placed: Optional[int] = None

    sec_name: Optional[str] = None
    remarks: Optional[str] = None

    market_code: Optional[str] = None
    instr_id: Optional[str] = None
    sector_id: Optional[str] = None
    min_step: Optional[float] = None

    buyback_price: Optional[float] = None
    buyback_date: Optional[date] = None

    isin: Optional[str] = None
    lat_name: Optional[str] = None
    reg_number: Optional[str] = None

    currency_id: Optional[str] = None

    list_level: Optional[int] = None
    sec_type: Optional[str] = None

    offer_date: Optional[date] = None
    settle_date: Optional[date] = None

    call_option_date: Optional[date] = None
    put_option_date: Optional[date] = None
    date_yield_from_issuer: Optional[date] = None

    bond_type: Optional[str] = None
    bond_subtype: Optional[str] = None


def parse_moex_tqcb_securities_table(section: Dict[str, Any]) -> List[MOEXStockBondsTQCBSecurity]:
    if not isinstance(section, dict):
        return []

    columns = section.get("columns") or []
    data = section.get("data") or []
    if not isinstance(columns, list) or not isinstance(data, list):
        return []

    m = _idx(columns)
    out: List[MOEXStockBondsTQCBSecurity] = []

    for row in data:
        if not isinstance(row, list):
            continue

        secid = _to_str(_get(row, m, "SECID"))
        boardid = _to_str(_get(row, m, "BOARDID"))
        if not secid or not boardid:
            continue

        out.append(
            MOEXStockBondsTQCBSecurity(
                secid=secid,
                boardid=boardid,
                shortname=_to_str(_get(row, m, "SHORTNAME")),
                prev_waprice=_to_float(_get(row, m, "PREVWAPRICE")),
                yield_at_prev_waprice=_to_float(_get(row, m, "YIELDATPREVWAPRICE")),
                coupon_value=_to_float(_get(row, m, "COUPONVALUE")),
                coupon_percent=_to_float(_get(row, m, "COUPONPERCENT")),
                next_coupon=_to_date(_get(row, m, "NEXTCOUPON")),
                coupon_period=_to_int(_get(row, m, "COUPONPERIOD")),
                accrued_int=_to_float(_get(row, m, "ACCRUEDINT")),
                prev_price=_to_float(_get(row, m, "PREVPRICE")),
                prev_legal_close_price=_to_float(_get(row, m, "PREVLEGALCLOSEPRICE")),
                prev_date=_to_date(_get(row, m, "PREVDATE")),
                lot_size=_to_int(_get(row, m, "LOTSIZE")),
                lot_value=_to_float(_get(row, m, "LOTVALUE")),
                face_value=_to_float(_get(row, m, "FACEVALUE")),
                face_unit=_to_str(_get(row, m, "FACEUNIT")),
                face_value_on_settle_date=_to_float(_get(row, m, "FACEVALUEONSETTLEDATE")),
                status=_to_str(_get(row, m, "STATUS")),
                board_name=_to_str(_get(row, m, "BOARDNAME")),
                mat_date=_to_date(_get(row, m, "MATDATE")),
                decimals=_to_int(_get(row, m, "DECIMALS")),
                issue_size=_to_int(_get(row, m, "ISSUESIZE")),
                issue_size_placed=_to_int(_get(row, m, "ISSUESIZEPLACED")),
                sec_name=_to_str(_get(row, m, "SECNAME")),
                remarks=_to_str(_get(row, m, "REMARKS")),
                market_code=_to_str(_get(row, m, "MARKETCODE")),
                instr_id=_to_str(_get(row, m, "INSTRID")),
                sector_id=_to_str(_get(row, m, "SECTORID")),
                min_step=_to_float(_get(row, m, "MINSTEP")),
                buyback_price=_to_float(_get(row, m, "BUYBACKPRICE")),
                buyback_date=_to_date(_get(row, m, "BUYBACKDATE")),
                isin=_to_str(_get(row, m, "ISIN")),
                lat_name=_to_str(_get(row, m, "LATNAME")),
                reg_number=_to_str(_get(row, m, "REGNUMBER")),
                currency_id=_to_str(_get(row, m, "CURRENCYID")),
                list_level=_to_int(_get(row, m, "LISTLEVEL")),
                sec_type=_to_str(_get(row, m, "SECTYPE")),
                offer_date=_to_date(_get(row, m, "OFFERDATE")),
                settle_date=_to_date(_get(row, m, "SETTLEDATE")),
                call_option_date=_to_date(_get(row, m, "CALLOPTIONDATE")),
                put_option_date=_to_date(_get(row, m, "PUTOPTIONDATE")),
                date_yield_from_issuer=_to_date(_get(row, m, "DATEYIELDFROMISSUER")),
                bond_type=_to_str(_get(row, m, "BONDTYPE")),
                bond_subtype=_to_str(_get(row, m, "BONDSUBTYPE")),
            )
        )

    return out


# =========================
# DTO: marketdata
# =========================


@strawberry.type
class MOEXStockBondsTQCBMarketData:
    secid: str
    boardid: str

    bid: Optional[float] = None
    bid_depth: Optional[float] = None
    offer: Optional[float] = None
    offer_depth: Optional[float] = None
    spread: Optional[float] = None

    bid_depth_t: Optional[int] = None
    offer_depth_t: Optional[int] = None

    open: Optional[float] = None
    low: Optional[float] = None
    high: Optional[float] = None
    last: Optional[float] = None

    last_change: Optional[float] = None
    last_change_prcnt: Optional[float] = None

    qty: Optional[int] = None
    value: Optional[float] = None
    value_usd: Optional[float] = None

    yield_: Optional[float] = None

    waprice: Optional[float] = None
    last_cng_to_last_waprice: Optional[float] = None
    wap_to_prev_waprice_prcnt: Optional[float] = None
    wap_to_prev_waprice: Optional[float] = None

    yield_at_waprice: Optional[float] = None
    yield_to_prev_yield: Optional[float] = None
    close_yield: Optional[float] = None

    close_price: Optional[float] = None
    market_price_today: Optional[float] = None
    market_price: Optional[float] = None
    last_to_prev_price: Optional[float] = None

    num_trades: Optional[int] = None
    vol_today: Optional[int] = None
    val_today: Optional[int] = None
    val_today_usd: Optional[int] = None

    trading_status: Optional[str] = None
    update_time: Optional[str] = None  # "HH:MM:SS"

    duration: Optional[float] = None

    num_bids: Optional[int] = None
    num_offers: Optional[int] = None

    change: Optional[float] = None
    time: Optional[str] = None  # "HH:MM:SS"

    high_bid: Optional[float] = None
    low_offer: Optional[float] = None

    price_minus_prev_waprice: Optional[float] = None
    last_bid: Optional[float] = None
    last_offer: Optional[float] = None

    l_current_price: Optional[float] = None
    l_close_price: Optional[float] = None
    market_price2: Optional[float] = None
    open_period_price: Optional[float] = None

    seqnum: Optional[int] = None
    sys_time: Optional[datetime] = None  # "YYYY-MM-DD HH:MM:SS"

    val_today_rur: Optional[int] = None

    iricpi_close: Optional[float] = None
    bei_close: Optional[float] = None
    cbr_close: Optional[float] = None

    yield_to_offer: Optional[float] = None
    yield_last_coupon: Optional[float] = None
    trading_session: Optional[str] = None

    call_option_yield: Optional[float] = None
    call_option_duration: Optional[float] = None

    zspread: Optional[float] = None
    zspread_at_waprice: Optional[float] = None


def parse_moex_tqcb_marketdata_table(section: Dict[str, Any]) -> List[MOEXStockBondsTQCBMarketData]:
    if not isinstance(section, dict):
        return []

    columns = section.get("columns") or []
    data = section.get("data") or []
    if not isinstance(columns, list) or not isinstance(data, list):
        return []

    m = _idx(columns)
    out: List[MOEXStockBondsTQCBMarketData] = []

    for row in data:
        if not isinstance(row, list):
            continue

        secid = _to_str(_get(row, m, "SECID"))
        boardid = _to_str(_get(row, m, "BOARDID"))
        if not secid or not boardid:
            continue

        out.append(
            MOEXStockBondsTQCBMarketData(
                secid=secid,
                boardid=boardid,
                bid=_to_float(_get(row, m, "BID")),
                bid_depth=_to_float(_get(row, m, "BIDDEPTH")),
                offer=_to_float(_get(row, m, "OFFER")),
                offer_depth=_to_float(_get(row, m, "OFFERDEPTH")),
                spread=_to_float(_get(row, m, "SPREAD")),
                bid_depth_t=_to_int(_get(row, m, "BIDDEPTHT")),
                offer_depth_t=_to_int(_get(row, m, "OFFERDEPTHT")),
                open=_to_float(_get(row, m, "OPEN")),
                low=_to_float(_get(row, m, "LOW")),
                high=_to_float(_get(row, m, "HIGH")),
                last=_to_float(_get(row, m, "LAST")),
                last_change=_to_float(_get(row, m, "LASTCHANGE")),
                last_change_prcnt=_to_float(_get(row, m, "LASTCHANGEPRCNT")),
                qty=_to_int(_get(row, m, "QTY")),
                value=_to_float(_get(row, m, "VALUE")),
                yield_=_to_float(_get(row, m, "YIELD")),
                value_usd=_to_float(_get(row, m, "VALUE_USD")),
                waprice=_to_float(_get(row, m, "WAPRICE")),
                last_cng_to_last_waprice=_to_float(_get(row, m, "LASTCNGTOLASTWAPRICE")),
                wap_to_prev_waprice_prcnt=_to_float(_get(row, m, "WAPTOPREVWAPRICEPRCNT")),
                wap_to_prev_waprice=_to_float(_get(row, m, "WAPTOPREVWAPRICE")),
                yield_at_waprice=_to_float(_get(row, m, "YIELDATWAPRICE")),
                yield_to_prev_yield=_to_float(_get(row, m, "YIELDTOPREVYIELD")),
                close_yield=_to_float(_get(row, m, "CLOSEYIELD")),
                close_price=_to_float(_get(row, m, "CLOSEPRICE")),
                market_price_today=_to_float(_get(row, m, "MARKETPRICETODAY")),
                market_price=_to_float(_get(row, m, "MARKETPRICE")),
                last_to_prev_price=_to_float(_get(row, m, "LASTTOPREVPRICE")),
                num_trades=_to_int(_get(row, m, "NUMTRADES")),
                vol_today=_to_int(_get(row, m, "VOLTODAY")),
                val_today=_to_int(_get(row, m, "VALTODAY")),
                val_today_usd=_to_int(_get(row, m, "VALTODAY_USD")),
                trading_status=_to_str(_get(row, m, "TRADINGSTATUS")),
                update_time=_to_str(_get(row, m, "UPDATETIME")),
                duration=_to_float(_get(row, m, "DURATION")),
                num_bids=_to_int(_get(row, m, "NUMBIDS")),
                num_offers=_to_int(_get(row, m, "NUMOFFERS")),
                change=_to_float(_get(row, m, "CHANGE")),
                time=_to_str(_get(row, m, "TIME")),
                high_bid=_to_float(_get(row, m, "HIGHBID")),
                low_offer=_to_float(_get(row, m, "LOWOFFER")),
                price_minus_prev_waprice=_to_float(_get(row, m, "PRICEMINUSPREVWAPRICE")),
                last_bid=_to_float(_get(row, m, "LASTBID")),
                last_offer=_to_float(_get(row, m, "LASTOFFER")),
                l_current_price=_to_float(_get(row, m, "LCURRENTPRICE")),
                l_close_price=_to_float(_get(row, m, "LCLOSEPRICE")),
                market_price2=_to_float(_get(row, m, "MARKETPRICE2")),
                open_period_price=_to_float(_get(row, m, "OPENPERIODPRICE")),
                seqnum=_to_int(_get(row, m, "SEQNUM")),
                sys_time=_to_datetime(_get(row, m, "SYSTIME")),
                val_today_rur=_to_int(_get(row, m, "VALTODAY_RUR")),
                iricpi_close=_to_float(_get(row, m, "IRICPICLOSE")),
                bei_close=_to_float(_get(row, m, "BEICLOSE")),
                cbr_close=_to_float(_get(row, m, "CBRCLOSE")),
                yield_to_offer=_to_float(_get(row, m, "YIELDTOOFFER")),
                yield_last_coupon=_to_float(_get(row, m, "YIELDLASTCOUPON")),
                trading_session=_to_str(_get(row, m, "TRADINGSESSION")),
                call_option_yield=_to_float(_get(row, m, "CALLOPTIONYIELD")),
                call_option_duration=_to_float(_get(row, m, "CALLOPTIONDURATION")),
                zspread=_to_float(_get(row, m, "ZSPREAD")),
                zspread_at_waprice=_to_float(_get(row, m, "ZSPREADATWAPRICE")),
            )
        )

    return out


# =========================
# DTO: marketdata_yields
# =========================


@strawberry.type
class MOEXStockBondsTQCBMarketDataYield:
    secid: str
    boardid: str

    price: Optional[float] = None
    yield_date: Optional[date] = None
    zcyc_moment: Optional[datetime] = None
    yield_date_type: Optional[str] = None

    effective_yield: Optional[float] = None
    duration: Optional[int] = None

    zspread_bp: Optional[int] = None
    gspread_bp: Optional[int] = None

    waprice: Optional[float] = None
    effective_yield_waprice: Optional[float] = None
    duration_waprice: Optional[int] = None

    ir: Optional[float] = None
    icpi: Optional[float] = None
    bei: Optional[float] = None
    cbr: Optional[float] = None

    yield_to_offer: Optional[float] = None
    yield_last_coupon: Optional[float] = None

    trade_moment: Optional[datetime] = None
    seqnum: Optional[int] = None
    sys_time: Optional[datetime] = None


def parse_moex_tqcb_marketdata_yields_table(section: Dict[str, Any]) -> List[MOEXStockBondsTQCBMarketDataYield]:
    if not isinstance(section, dict):
        return []

    columns = section.get("columns") or []
    data = section.get("data") or []
    if not isinstance(columns, list) or not isinstance(data, list):
        return []

    m = _idx(columns)
    out: List[MOEXStockBondsTQCBMarketDataYield] = []

    for row in data:
        if not isinstance(row, list):
            continue

        secid = _to_str(_get(row, m, "SECID"))
        boardid = _to_str(_get(row, m, "BOARDID"))
        if not secid or not boardid:
            continue

        out.append(
            MOEXStockBondsTQCBMarketDataYield(
                secid=secid,
                boardid=boardid,
                price=_to_float(_get(row, m, "PRICE")),
                yield_date=_to_date(_get(row, m, "YIELDDATE")),
                zcyc_moment=_to_datetime(_get(row, m, "ZCYCMOMENT")),
                yield_date_type=_to_str(_get(row, m, "YIELDDATETYPE")),
                effective_yield=_to_float(_get(row, m, "EFFECTIVEYIELD")),
                duration=_to_int(_get(row, m, "DURATION")),
                zspread_bp=_to_int(_get(row, m, "ZSPREADBP")),
                gspread_bp=_to_int(_get(row, m, "GSPREADBP")),
                waprice=_to_float(_get(row, m, "WAPRICE")),
                effective_yield_waprice=_to_float(_get(row, m, "EFFECTIVEYIELDWAPRICE")),
                duration_waprice=_to_int(_get(row, m, "DURATIONWAPRICE")),
                ir=_to_float(_get(row, m, "IR")),
                icpi=_to_float(_get(row, m, "ICPI")),
                bei=_to_float(_get(row, m, "BEI")),
                cbr=_to_float(_get(row, m, "CBR")),
                yield_to_offer=_to_float(_get(row, m, "YIELDTOOFFER")),
                yield_last_coupon=_to_float(_get(row, m, "YIELDLASTCOUPON")),
                trade_moment=_to_datetime(_get(row, m, "TRADEMOMENT")),
                seqnum=_to_int(_get(row, m, "SEQNUM")),
                sys_time=_to_datetime(_get(row, m, "SYSTIME")),
            )
        )

    return out


# =========================
# DTO: dataversion
# =========================


@strawberry.type
class MOEXStockBondsTQCBDataVersion:
    data_version: Optional[int] = None
    seqnum: Optional[int] = None
    trade_date: Optional[date] = None
    trade_session_date: Optional[date] = None


def parse_moex_tqcb_dataversion(section: Dict[str, Any]) -> Optional[MOEXStockBondsTQCBDataVersion]:
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

    return MOEXStockBondsTQCBDataVersion(
        data_version=_to_int(_get(row, m, "data_version")),
        seqnum=_to_int(_get(row, m, "seqnum")),
        trade_date=_to_date(_get(row, m, "trade_date")),
        trade_session_date=_to_date(_get(row, m, "trade_session_date")),
    )


# =========================
# Response DTO (обёртка)
# =========================


@strawberry.type
class MOEXStockBondsTQCBSecurities(RedisJSON):
    securities: List[MOEXStockBondsTQCBSecurity] = strawberry.field(default_factory=list)
    marketdata: List[MOEXStockBondsTQCBMarketData] = strawberry.field(default_factory=list)
    marketdata_yields: List[MOEXStockBondsTQCBMarketDataYield] = strawberry.field(default_factory=list)
    dataversion: Optional[MOEXStockBondsTQCBDataVersion] = None


def parse_moex_bonds_tqcb_securities_response(raw: Dict[str, Any]) -> MOEXStockBondsTQCBSecurities:
    """
    Ожидает реальный формат MOEX (без metadata):
    {
      "securities": {"columns": [...], "data": [...]},
      "marketdata": {"columns": [...], "data": [...]},
      "marketdata_yields": {"columns": [...], "data": [...]},
      "dataversion": {"columns": [...], "data": [...]}
    }
    """
    if not isinstance(raw, dict):
        return MOEXStockBondsTQCBSecurities()

    sec = parse_moex_tqcb_securities_table(raw.get("securities") or {})
    md = parse_moex_tqcb_marketdata_table(raw.get("marketdata") or {})
    mdy = parse_moex_tqcb_marketdata_yields_table(raw.get("marketdata_yields") or {})
    dv = parse_moex_tqcb_dataversion(raw.get("dataversion") or {})

    return MOEXStockBondsTQCBSecurities(
        securities=sec,
        marketdata=md,
        marketdata_yields=mdy,
        dataversion=dv,
    )
