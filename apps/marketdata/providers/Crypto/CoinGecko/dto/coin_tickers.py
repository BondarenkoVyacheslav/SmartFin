from typing import Optional, Any

import strawberry

from apps.marketdata.providers.Crypto.CoinGecko.redis_json import RedisJSON


@strawberry.type
class Converted3:
    btc: Optional[float] = None
    eth: Optional[float] = None
    usd: Optional[float] = None


@strawberry.type
class MarketRef:
    name: str | None = None
    identifier: str | None = None
    has_trading_incentive: bool | None = None

    logo: str | None = None


@strawberry.type
class Ticker:
    # пара
    base: Optional[str] = None
    target: Optional[str] = None

    # биржа
    market: Optional[MarketRef] = None

    # цены/объёмы
    last: Optional[float] = None
    volume: Optional[float] = None

    # из depth=true
    cost_to_move_up_usd: Optional[float] = None
    cost_to_move_down_usd: Optional[float] = None

    # конвертированные значения (CoinGecko)
    converted_last: Optional[Converted3] = None
    converted_volume: Optional[Converted3] = None

    # качество/ликвидность
    trust_score: Optional[str] = None
    bid_ask_spread_percentage: Optional[float] = None

    # таймстемпы (ISO8601 строки от CoinGecko)
    timestamp: Optional[str] = None
    last_traded_at: Optional[str] = None
    last_fetch_at: Optional[str] = None

    # статусы
    is_anomaly: Optional[bool] = None
    is_stale: Optional[bool] = None

    # ссылки/мета
    trade_url: Optional[str] = None
    token_info_url: Optional[str] = None

    # id монет по базе CoinGecko (могут быть как для base, так и для target)
    coin_id: Optional[str] = None
    target_coin_id: Optional[str] = None

    # оценка капы базовой монеты в USD (если отдают)
    coin_mcap_usd: Optional[float] = None


@strawberry.type
class CoinTickers(RedisJSON):
    name: str | None = None
    tickers: list[Ticker] = strawberry.field(default_factory=list)


def _to_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _parse_converted3(raw: Any) -> Optional[Converted3]:
    if not isinstance(raw, dict):
        return None
    return Converted3(
        btc=_to_float(raw.get("btc")),
        eth=_to_float(raw.get("eth")),
        usd=_to_float(raw.get("usd")),
    )


def _parse_market(raw: Any) -> Optional[MarketRef]:
    if not isinstance(raw, dict):
        return None
    return MarketRef(
        name=raw.get("name"),
        identifier=raw.get("identifier"),
        has_trading_incentive=raw.get("has_trading_incentive"),
        logo=raw.get("logo"),
    )


def _parse_ticker(t: Any) -> Ticker | None:
    if not isinstance(t, dict):
        return None

    return Ticker(
        base=t.get("base"),
        target=t.get("target"),
        market=_parse_market(t.get("market")),
        last=_to_float(t.get("last")),
        volume=_to_float(t.get("volume")),
        cost_to_move_up_usd=_to_float(t.get("cost_to_move_up_usd")),
        cost_to_move_down_usd=_to_float(t.get("cost_to_move_down_usd")),
        converted_last=_parse_converted3(t.get("converted_last")),
        converted_volume=_parse_converted3(t.get("converted_volume")),
        trust_score=t.get("trust_score"),
        bid_ask_spread_percentage=_to_float(t.get("bid_ask_spread_percentage")),
        timestamp=t.get("timestamp"),
        last_traded_at=t.get("last_traded_at"),
        last_fetch_at=t.get("last_fetch_at"),
        is_anomaly=t.get("is_anomaly"),
        is_stale=t.get("is_stale"),
        trade_url=t.get("trade_url"),
        token_info_url=t.get("token_info_url"),
        coin_id=t.get("coin_id"),
        target_coin_id=t.get("target_coin_id"),
        coin_mcap_usd=_to_float(t.get("coin_mcap_usd")),
    )


def parse_coin_tickers(raw: dict[str, Any]) -> CoinTickers:
    """Принимает JSON от /coins/{id}/tickers и нормализует в DTO."""
    name = raw.get("name")
    tickers_raw = raw.get("tickers") or []
    parsed = []
    for t in tickers_raw:
        dt = _parse_ticker(t)
        if dt is not None:
            parsed.append(dt)

    return CoinTickers(name=name, tickers=parsed)
