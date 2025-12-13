from decimal import Decimal
import strawberry
from typing import Optional, Any

from apps.marketdata.services.redis_json import RedisJSON


@strawberry.type(name="ExchangeDetailConverted3")
class Converted3:
    btc: Optional[float] = None
    eth: Optional[float] = None
    usd: Optional[float] = None


@strawberry.type(name="ExchangeTickersMarketRef")
class MarketRef:
    name: str | None = None
    identifier: str | None = None
    has_trading_incentive: bool | None = None

    logo: str | None = None

@strawberry.type(name="ExchangeDetailTicker")
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

@strawberry.type(name="ExchangeDetailExchange")
class Exchange(RedisJSON):
    id: str | None
    name: str | None
    year_established: int | None
    country: str | None
    description: str | None
    url: str | None
    image: str | None
    facebook_url: str | None
    reddit_url: str | None
    telegram_url: str | None
    slack_url: str | None
    other_url_1: str | None
    other_url_2: str | None
    twitter_handle: str | None
    has_trading_incentive: bool | None
    centralized: bool | None
    public_notice: str | None
    alert_notice: str | None
    trust_score: int | None
    trust_score_rank: int | None
    trade_volume_24h_btc: Decimal | None
    coins: int | None
    pairs: int | None
    tickers: list[Ticker] | None


def _to_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None

def _to_dec(x) -> Decimal | None:
    if x is None:
        return None
    # через str(x) чтобы не ловить двоичную погрешность float
    return Decimal(str(x))

def _to_year(x: Any) -> int | None:
    """
    Парсим year_established как год.
    CoinGecko обычно отдаёт int (например, 2017), но подстрахуемся под строки.
    """
    if x is None:
        return None

    if isinstance(x, int):
        return x

    if isinstance(x, str):
        x = x.strip()
        if not x:
            return None
        try:
            return int(x)
        except ValueError:
            return None

    # если вдруг прилетело что-то странное — просто None
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


def _parse_tickers(raw: Any) -> list[Ticker] | None:
    """
    CoinGecko отдаёт tickers как список словарей.
    Превращаем в список Ticker, либо None если ничего адекватного нет.
    """
    if not isinstance(raw, list):
        return None

    result: list[Ticker] = []
    for item in raw:
        t = _parse_ticker(item)
        if t is not None:
            result.append(t)

    return result or None


def parse_exchange(raw: dict[str, Any]) -> Exchange:
    return Exchange(
            id=raw.get("id"),
            name=raw.get("name"),
            year_established=_to_year(raw.get("year_established")),
            country=raw.get("country"),
            description=raw.get("description"),
            url=raw.get("url"),
            image=raw.get("image"),
            facebook_url=raw.get("facebook_url"),
            reddit_url=raw.get("reddit_url"),
            telegram_url=raw.get("telegram_url"),
            slack_url=raw.get("slack_url"),
            other_url_1=raw.get("other_url_1"),
            other_url_2=raw.get("other_url_2"),
            twitter_handle=raw.get("twitter_handle"),
            has_trading_incentive=raw.get("has_trading_incentive"),
            centralized=raw.get("centralized"),
            public_notice=raw.get("public_notice"),
            alert_notice=raw.get("alert_notice"),
            trust_score=raw.get("trust_score"),
            trust_score_rank=raw.get("trust_score_rank"),
            trade_volume_24h_btc=_to_dec(raw.get("trade_volume_24h_btc")),
            coins=raw.get("coins"),
            pairs=raw.get("pairs"),
            tickers=_parse_tickers(raw.get("tickers")),
        )
