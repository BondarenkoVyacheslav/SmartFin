from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import strawberry

from app.marketdata.services.redis_json import RedisJSON


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, (int, float)):
        dt = datetime.fromtimestamp(float(value), tz=timezone.utc)
    elif isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(s)
        except ValueError:
            return None
    else:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _get_section(payload: Dict[str, Any], camel: str, snake: str) -> Optional[Dict[str, Any]]:
    section = payload.get(camel)
    if isinstance(section, dict):
        return section
    section = payload.get(snake)
    if isinstance(section, dict):
        return section
    return None


@strawberry.type
@dataclass
class AlpacaStockQuote(RedisJSON):
    symbol: str
    last: Optional[float]
    bid: Optional[float]
    ask: Optional[float]
    ts: datetime
    trade_ts: Optional[datetime] = None
    quote_ts: Optional[datetime] = None
    currency: Optional[str] = None
    feed: Optional[str] = None


def _parse_snapshot(
    symbol: str,
    payload: Dict[str, Any],
    *,
    feed: Optional[str] = None,
    currency: Optional[str] = None,
) -> Optional[AlpacaStockQuote]:
    if not isinstance(payload, dict):
        return None

    symbol = (symbol or payload.get("symbol") or "").strip().upper()
    if not symbol:
        return None

    latest_trade = _get_section(payload, "latestTrade", "latest_trade")
    latest_quote = _get_section(payload, "latestQuote", "latest_quote")
    minute_bar = _get_section(payload, "minuteBar", "minute_bar")
    daily_bar = _get_section(payload, "dailyBar", "daily_bar")
    prev_daily_bar = _get_section(payload, "prevDailyBar", "prev_daily_bar")

    last = _to_float(latest_trade.get("p")) if latest_trade else None
    if last is None:
        for bar in (minute_bar, daily_bar, prev_daily_bar):
            if not bar:
                continue
            last = _to_float(bar.get("c"))
            if last is not None:
                break

    bid = _to_float(latest_quote.get("bp")) if latest_quote else None
    ask = _to_float(latest_quote.get("ap")) if latest_quote else None

    trade_ts = _to_datetime(latest_trade.get("t")) if latest_trade else None
    quote_ts = _to_datetime(latest_quote.get("t")) if latest_quote else None

    bar_ts = None
    for bar in (minute_bar, daily_bar, prev_daily_bar):
        if not bar:
            continue
        bar_ts = _to_datetime(bar.get("t"))
        if bar_ts is not None:
            break

    ts = trade_ts or quote_ts or bar_ts or datetime.now(timezone.utc)

    return AlpacaStockQuote(
        symbol=symbol,
        last=last,
        bid=bid,
        ask=ask,
        ts=ts,
        trade_ts=trade_ts,
        quote_ts=quote_ts,
        currency=currency,
        feed=feed,
    )


def parse_alpaca_snapshots(
    raw: Dict[str, Any],
    *,
    feed: Optional[str] = None,
    currency: Optional[str] = None,
) -> List[AlpacaStockQuote]:
    if not isinstance(raw, dict):
        return []

    payload = raw
    if isinstance(raw.get("snapshots"), dict):
        payload = raw.get("snapshots")

    if any(k in payload for k in ("latestTrade", "latest_trade", "latestQuote", "latest_quote")):
        quote = _parse_snapshot(
            payload.get("symbol") or "",
            payload,
            feed=feed,
            currency=currency,
        )
        return [quote] if quote is not None else []

    quotes: List[AlpacaStockQuote] = []
    for symbol, snapshot in payload.items():
        if not isinstance(snapshot, dict):
            continue
        quote = _parse_snapshot(symbol, snapshot, feed=feed, currency=currency)
        if quote is not None:
            quotes.append(quote)
    return quotes
