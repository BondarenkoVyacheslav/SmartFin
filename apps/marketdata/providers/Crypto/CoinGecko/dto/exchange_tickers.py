from typing import List, Optional, Dict, Any

import strawberry

from apps.marketdata.services.redis_json import RedisJSON


@strawberry.type
class ExchangeMarket:
    """
    Биржа, с которой приходит тикер (в ответе это поле market).
    """
    name: str
    identifier: str
    has_trading_incentive: bool


@strawberry.type
class ExchangeTickerConvertedValues:
    """
    converted_last / converted_volume:
    значения, переведённые в BTC, ETH и USD.
    """
    btc: Optional[float] = None
    eth: Optional[float] = None
    usd: Optional[float] = None


@strawberry.type
class ExchangeTicker:
    """
    Один тикер из массива tickers.
    """
    base: str
    target: str
    market: ExchangeMarket

    last: float                # последняя цена в target
    volume: float              # объём в target за 24ч (raw)

    converted_last: ExchangeTickerConvertedValues
    converted_volume: ExchangeTickerConvertedValues

    trust_score: Optional[str] = None            # "green", "yellow", ...
    bid_ask_spread_percentage: Optional[float] = None

    timestamp: Optional[str] = None              # ISO-строка
    last_traded_at: Optional[str] = None
    last_fetch_at: Optional[str] = None

    is_anomaly: Optional[bool] = None
    is_stale: Optional[bool] = None

    trade_url: Optional[str] = None
    token_info_url: Optional[str] = None

    coin_id: Optional[str] = None
    target_coin_id: Optional[str] = None
    coin_mcap_usd: Optional[float] = None


@strawberry.type
class ExchangeTickers(RedisJSON):
    """
    Обёртка над ответом /exchanges/{id}/tickers.
    """
    exchange_id: str          # "binance" (из URL, а не из тела ответа)
    exchange_name: str        # "Binance" (из поля name в ответе)
    tickers: List[ExchangeTicker]


def _to_optional_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_converted_values(
    raw: Optional[Dict[str, Any]],
) -> ExchangeTickerConvertedValues:
    if not isinstance(raw, dict):
        return ExchangeTickerConvertedValues()

    return ExchangeTickerConvertedValues(
        btc=_to_optional_float(raw.get("btc")),
        eth=_to_optional_float(raw.get("eth")),
        usd=_to_optional_float(raw.get("usd")),
    )


def parse_exchange_tickers(
    exchange_id: str,
    raw: Dict[str, Any],
) -> ExchangeTickers:
    """
    Нормализует ответ /exchanges/{id}/tickers в DTO ExchangeTickers.

    raw — dict из CoinGecko:
      {
        "name": "Binance",
        "tickers": [ {...}, {...}, ... ]
      }
    """
    exchange_name: str = raw.get("name", exchange_id)
    raw_tickers = raw.get("tickers") or []

    tickers: List[ExchangeTicker] = []

    for t in raw_tickers:
        market_raw = t.get("market") or {}

        market = ExchangeMarket(
            name=market_raw.get("name", ""),
            identifier=market_raw.get("identifier", ""),
            has_trading_incentive=bool(
                market_raw.get("has_trading_incentive", False)
            ),
        )

        converted_last = _parse_converted_values(t.get("converted_last"))
        converted_volume = _parse_converted_values(t.get("converted_volume"))

        ticker = ExchangeTicker(
            base=t.get("base", ""),
            target=t.get("target", ""),
            market=market,
            last=float(t.get("last", 0.0)),
            volume=float(t.get("volume", 0.0)),
            converted_last=converted_last,
            converted_volume=converted_volume,
            trust_score=t.get("trust_score"),
            bid_ask_spread_percentage=_to_optional_float(
                t.get("bid_ask_spread_percentage")
            ),
            timestamp=t.get("timestamp"),
            last_traded_at=t.get("last_traded_at"),
            last_fetch_at=t.get("last_fetch_at"),
            is_anomaly=t.get("is_anomaly"),
            is_stale=t.get("is_stale"),
            trade_url=t.get("trade_url"),
            token_info_url=t.get("token_info_url"),
            coin_id=t.get("coin_id"),
            target_coin_id=t.get("target_coin_id"),
            coin_mcap_usd=_to_optional_float(t.get("coin_mcap_usd")),
        )

        tickers.append(ticker)

    return ExchangeTickers(
        exchange_id=exchange_id,
        exchange_name=exchange_name,
        tickers=tickers,
    )

