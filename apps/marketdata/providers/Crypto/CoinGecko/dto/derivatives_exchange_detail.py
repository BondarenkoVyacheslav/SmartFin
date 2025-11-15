from typing import Optional, List, Any, Dict, Sequence
import strawberry


# --- Вложенные структуры для converted_* ---

@strawberry.type
class DerivativeConvertedValue:
    """
    Нормализованное представление скаляров inside converted_last / converted_volume.
    Храним как строки, чтобы не терять точность и не зависеть от float.
    """
    btc: Optional[str] = None
    eth: Optional[str] = None
    usd: Optional[str] = None


# --- DTO для тикера фьючерса/перпетуала ---

@strawberry.type
class DerivativeTicker:
    """
    Один деривативный тикер на фьючерсной бирже (Binance Futures).
    """
    # Идентификаторы инструмента
    symbol: str
    base: str
    target: str

    coin_id: Optional[str] = None
    target_coin_id: Optional[str] = None

    trade_url: Optional[str] = None

    # Тип контракта: 'perpetual', 'futures', и т.п.
    contract_type: Optional[str] = None

    # Основные рыночные параметры
    last: Optional[float] = None  # последняя цена
    h24_percentage_change: Optional[float] = None

    index: Optional[float] = None
    index_basis_percentage: Optional[float] = None

    bid_ask_spread: Optional[float] = None

    funding_rate: Optional[float] = None

    open_interest_usd: Optional[float] = None
    h24_volume: Optional[float] = None

    # Конвертации в BTC/ETH/USD
    converted_volume: Optional[DerivativeConvertedValue] = None
    converted_last: Optional[DerivativeConvertedValue] = None

    # Время торговли / экспирации
    last_traded: Optional[int] = None          # unix-timestamp (seconds)
    expired_at: Optional[int] = None           # unix-timestamp или None для perpetual


# --- DTO для биржи деривативов, возвращаемой эндпоинтом ---

@strawberry.type
class DerivativesExchangeDetails:
    """
    Детальное описание деривативной биржи (пример: Binance (Futures))
    вместе со списком тикеров.
    """
    name: str

    open_interest_btc: Optional[float] = None
    trade_volume_24h_btc: Optional[str] = None  # CoinGecko отдает это как строку

    number_of_perpetual_pairs: Optional[int] = None
    number_of_futures_pairs: Optional[int] = None

    image: Optional[str] = None
    year_established: Optional[int] = None
    country: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None

    tickers: List[DerivativeTicker] = strawberry.field(default_factory=list)



def _parse_converted_value(raw: Optional[Dict[str, Any]]) -> Optional[DerivativeConvertedValue]:
    if not isinstance(raw, dict):
        return None

    # приводим к строкам, если значения есть
    def to_str(v: Any) -> Optional[str]:
        if v is None:
            return None
        return str(v)

    return DerivativeConvertedValue(
        btc=to_str(raw.get("btc")),
        eth=to_str(raw.get("eth")),
        usd=to_str(raw.get("usd")),
    )


def _parse_ticker(raw: Dict[str, Any]) -> DerivativeTicker:
    return DerivativeTicker(
        symbol=raw.get("symbol") or "",
        base=raw.get("base") or "",
        target=raw.get("target") or "",
        coin_id=raw.get("coin_id"),
        target_coin_id=raw.get("target_coin_id"),
        trade_url=raw.get("trade_url"),
        contract_type=raw.get("contract_type"),
        last=raw.get("last"),
        h24_percentage_change=raw.get("h24_percentage_change"),
        index=raw.get("index"),
        index_basis_percentage=raw.get("index_basis_percentage"),
        bid_ask_spread=raw.get("bid_ask_spread"),
        funding_rate=raw.get("funding_rate"),
        open_interest_usd=raw.get("open_interest_usd"),
        h24_volume=raw.get("h24_volume"),
        converted_volume=_parse_converted_value(raw.get("converted_volume")),
        converted_last=_parse_converted_value(raw.get("converted_last")),
        last_traded=raw.get("last_traded"),
        expired_at=raw.get("expired_at"),
    )


def parse_derivatives_exchange_details(raw: Dict[str, Any]) -> DerivativesExchangeDetails:
    """
    Нормализует ответ /derivatives/exchanges/{id}?include_tickers=all
    в DTO DerivativesExchangeDetails.
    """
    tickers_raw = raw.get("tickers") or []
    tickers: list[DerivativeTicker] = []

    if isinstance(tickers_raw, Sequence):
        for item in tickers_raw:
            if isinstance(item, dict):
                tickers.append(_parse_ticker(item))

    return DerivativesExchangeDetails(
        name=raw.get("name") or "",
        open_interest_btc=raw.get("open_interest_btc"),
        trade_volume_24h_btc=raw.get("trade_volume_24h_btc"),
        number_of_perpetual_pairs=raw.get("number_of_perpetual_pairs"),
        number_of_futures_pairs=raw.get("number_of_futures_pairs"),
        image=raw.get("image"),
        year_established=raw.get("year_established"),
        country=raw.get("country"),
        description=raw.get("description"),
        url=raw.get("url"),
        tickers=tickers,
    )
