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
        return date.fromisoformat(s)  # "YYYY-MM-DD"
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
class MOEXTQBRSecurity:
    secid: str
    boardid: str

    shortname: Optional[str] = None
    prev_price: Optional[float] = None
    lot_size: Optional[int] = None
    face_value: Optional[float] = None
    status: Optional[str] = None
    board_name: Optional[str] = None
    decimals: Optional[int] = None
    sec_name: Optional[str] = None
    remarks: Optional[str] = None
    market_code: Optional[str] = None
    instr_id: Optional[str] = None
    sector_id: Optional[str] = None
    min_step: Optional[float] = None
    prev_waprice: Optional[float] = None
    face_unit: Optional[str] = None
    prev_date: Optional[date] = None
    issue_size: Optional[int] = None
    isin: Optional[str] = None
    lat_name: Optional[str] = None
    reg_number: Optional[str] = None
    prev_legal_close_price: Optional[float] = None
    currency_id: Optional[str] = None
    sec_type: Optional[str] = None
    list_level: Optional[int] = None
    settle_date: Optional[date] = None


def parse_moex_tqbr_securities_table(section: Dict[str, Any]) -> List[MOEXTQBRSecurity]:
    if not isinstance(section, dict):
        return []

    columns = section.get("columns") or []
    data = section.get("data") or []
    if not isinstance(columns, list) or not isinstance(data, list):
        return []

    m = _idx(columns)
    out: List[MOEXTQBRSecurity] = []

    for row in data:
        if not isinstance(row, list):
            continue

        secid = _to_str(_get(row, m, "SECID"))
        boardid = _to_str(_get(row, m, "BOARDID"))
        if not secid or not boardid:
            continue

        out.append(
            MOEXTQBRSecurity(
                secid=secid,
                boardid=boardid,
                shortname=_to_str(_get(row, m, "SHORTNAME")),
                prev_price=_to_float(_get(row, m, "PREVPRICE")),
                lot_size=_to_int(_get(row, m, "LOTSIZE")),
                face_value=_to_float(_get(row, m, "FACEVALUE")),
                status=_to_str(_get(row, m, "STATUS")),
                board_name=_to_str(_get(row, m, "BOARDNAME")),
                decimals=_to_int(_get(row, m, "DECIMALS")),
                sec_name=_to_str(_get(row, m, "SECNAME")),
                remarks=_to_str(_get(row, m, "REMARKS")),
                market_code=_to_str(_get(row, m, "MARKETCODE")),
                instr_id=_to_str(_get(row, m, "INSTRID")),
                sector_id=_to_str(_get(row, m, "SECTORID")),
                min_step=_to_float(_get(row, m, "MINSTEP")),
                prev_waprice=_to_float(_get(row, m, "PREVWAPRICE")),
                face_unit=_to_str(_get(row, m, "FACEUNIT")),
                prev_date=_to_date(_get(row, m, "PREVDATE")),
                issue_size=_to_int(_get(row, m, "ISSUESIZE")),
                isin=_to_str(_get(row, m, "ISIN")),
                lat_name=_to_str(_get(row, m, "LATNAME")),
                reg_number=_to_str(_get(row, m, "REGNUMBER")),
                prev_legal_close_price=_to_float(_get(row, m, "PREVLEGALCLOSEPRICE")),
                currency_id=_to_str(_get(row, m, "CURRENCYID")),
                sec_type=_to_str(_get(row, m, "SECTYPE")),
                list_level=_to_int(_get(row, m, "LISTLEVEL")),
                settle_date=_to_date(_get(row, m, "SETTLEDATE")),
            )
        )

    return out


# =========================
# DTO: marketdata
# =========================

@strawberry.type
class MOEXTQBRMarketData:
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

    waprice: Optional[float] = None
    last_cng_to_last_waprice: Optional[float] = None
    wap_to_prev_waprice_prcnt: Optional[float] = None
    wap_to_prev_waprice: Optional[float] = None

    close_price: Optional[float] = None
    market_price_today: Optional[float] = None
    market_price: Optional[float] = None
    last_to_prev_price: Optional[float] = None

    num_trades: Optional[int] = None
    vol_today: Optional[int] = None
    val_today: Optional[int] = None
    val_today_usd: Optional[int] = None

    etf_settle_price: Optional[float] = None

    trading_status: Optional[str] = None
    update_time: Optional[str] = None  # "HH:MM:SS"

    last_bid: Optional[float] = None
    last_offer: Optional[float] = None

    l_close_price: Optional[float] = None
    l_current_price: Optional[float] = None
    market_price2: Optional[float] = None

    num_bids: Optional[int] = None
    num_offers: Optional[int] = None

    change: Optional[float] = None
    time: Optional[str] = None  # "HH:MM:SS"

    high_bid: Optional[float] = None
    low_offer: Optional[float] = None

    price_minus_prev_waprice: Optional[float] = None
    open_period_price: Optional[float] = None

    seqnum: Optional[int] = None
    sys_time: Optional[datetime] = None  # "YYYY-MM-DD HH:MM:SS"

    closing_auction_price: Optional[float] = None
    closing_auction_volume: Optional[float] = None

    issue_capitalization: Optional[float] = None
    issue_capitalization_update_time: Optional[str] = None  # "HH:MM:SS"

    etf_settle_currency: Optional[str] = None

    val_today_rur: Optional[int] = None
    trading_session: Optional[str] = None
    trend_issue_capitalization: Optional[float] = None


def parse_moex_tqbr_marketdata_table(section: Dict[str, Any]) -> List[MOEXTQBRMarketData]:
    if not isinstance(section, dict):
        return []

    columns = section.get("columns") or []
    data = section.get("data") or []
    if not isinstance(columns, list) or not isinstance(data, list):
        return []

    m = _idx(columns)
    out: List[MOEXTQBRMarketData] = []

    for row in data:
        if not isinstance(row, list):
            continue

        secid = _to_str(_get(row, m, "SECID"))
        boardid = _to_str(_get(row, m, "BOARDID"))
        if not secid or not boardid:
            continue

        out.append(
            MOEXTQBRMarketData(
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
                value_usd=_to_float(_get(row, m, "VALUE_USD")),
                waprice=_to_float(_get(row, m, "WAPRICE")),
                last_cng_to_last_waprice=_to_float(_get(row, m, "LASTCNGTOLASTWAPRICE")),
                wap_to_prev_waprice_prcnt=_to_float(_get(row, m, "WAPTOPREVWAPRICEPRCNT")),
                wap_to_prev_waprice=_to_float(_get(row, m, "WAPTOPREVWAPRICE")),
                close_price=_to_float(_get(row, m, "CLOSEPRICE")),
                market_price_today=_to_float(_get(row, m, "MARKETPRICETODAY")),
                market_price=_to_float(_get(row, m, "MARKETPRICE")),
                last_to_prev_price=_to_float(_get(row, m, "LASTTOPREVPRICE")),
                num_trades=_to_int(_get(row, m, "NUMTRADES")),
                vol_today=_to_int(_get(row, m, "VOLTODAY")),
                val_today=_to_int(_get(row, m, "VALTODAY")),
                val_today_usd=_to_int(_get(row, m, "VALTODAY_USD")),
                etf_settle_price=_to_float(_get(row, m, "ETFSETTLEPRICE")),
                trading_status=_to_str(_get(row, m, "TRADINGSTATUS")),
                update_time=_to_str(_get(row, m, "UPDATETIME")),
                last_bid=_to_float(_get(row, m, "LASTBID")),
                last_offer=_to_float(_get(row, m, "LASTOFFER")),
                l_close_price=_to_float(_get(row, m, "LCLOSEPRICE")),
                l_current_price=_to_float(_get(row, m, "LCURRENTPRICE")),
                market_price2=_to_float(_get(row, m, "MARKETPRICE2")),
                num_bids=_to_int(_get(row, m, "NUMBIDS")),
                num_offers=_to_int(_get(row, m, "NUMOFFERS")),
                change=_to_float(_get(row, m, "CHANGE")),
                time=_to_str(_get(row, m, "TIME")),
                high_bid=_to_float(_get(row, m, "HIGHBID")),
                low_offer=_to_float(_get(row, m, "LOWOFFER")),
                price_minus_prev_waprice=_to_float(_get(row, m, "PRICEMINUSPREVWAPRICE")),
                open_period_price=_to_float(_get(row, m, "OPENPERIODPRICE")),
                seqnum=_to_int(_get(row, m, "SEQNUM")),
                sys_time=_to_datetime(_get(row, m, "SYSTIME")),
                closing_auction_price=_to_float(_get(row, m, "CLOSINGAUCTIONPRICE")),
                closing_auction_volume=_to_float(_get(row, m, "CLOSINGAUCTIONVOLUME")),
                issue_capitalization=_to_float(_get(row, m, "ISSUECAPITALIZATION")),
                issue_capitalization_update_time=_to_str(_get(row, m, "ISSUECAPITALIZATION_UPDATETIME")),
                etf_settle_currency=_to_str(_get(row, m, "ETFSETTLECURRENCY")),
                val_today_rur=_to_int(_get(row, m, "VALTODAY_RUR")),
                trading_session=_to_str(_get(row, m, "TRADINGSESSION")),
                trend_issue_capitalization=_to_float(_get(row, m, "TRENDISSUECAPITALIZATION")),
            )
        )

    return out


# =========================
# DTO: dataversion
# =========================

@strawberry.type
class MOEXTQBRDataVersion:
    data_version: Optional[int] = None
    seqnum: Optional[int] = None
    trade_date: Optional[date] = None
    trade_session_date: Optional[date] = None


def parse_moex_tqbr_dataversion(section: Dict[str, Any]) -> Optional[MOEXTQBRDataVersion]:
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

    return MOEXTQBRDataVersion(
        data_version=_to_int(_get(row, m, "data_version")),
        seqnum=_to_int(_get(row, m, "seqnum")),
        trade_date=_to_date(_get(row, m, "trade_date")),
        trade_session_date=_to_date(_get(row, m, "trade_session_date")),
    )


# =========================
# Response DTO (обёртка)
# =========================

@strawberry.type
class MOEXSharesTQBRSecurities(RedisJSON):
    securities: List[MOEXTQBRSecurity] = strawberry.field(default_factory=list)
    marketdata: List[MOEXTQBRMarketData] = strawberry.field(default_factory=list)
    dataversion: Optional[MOEXTQBRDataVersion] = None


def parse_moex_shares_tqbr_securities_response(raw: Dict[str, Any]) -> MOEXSharesTQBRSecurities:
    """
    Ожидает реальный формат MOEX (без metadata):
    {
      "securities": {"columns": [...], "data": [...]},
      "marketdata": {"columns": [...], "data": [...]},
      "dataversion": {"columns": [...], "data": [...]}
    }
    """
    if not isinstance(raw, dict):
        return MOEXSharesTQBRSecurities()

    sec = parse_moex_tqbr_securities_table(raw.get("securities") or {})
    md = parse_moex_tqbr_marketdata_table(raw.get("marketdata") or {})
    dv = parse_moex_tqbr_dataversion(raw.get("dataversion") or {})

    return MOEXSharesTQBRSecurities(
        securities=sec,
        marketdata=md,
        dataversion=dv,
    )
