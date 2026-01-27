# apps/marketdata/schema.py
import strawberry
from strawberry.scalars import JSON
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from app.marketdata import market_data_api
from enum import Enum

@strawberry.enum
class AssetClass(Enum):
    CRYPTO = "crypto"
    STOCK_US = "stock-us"
    STOCK_RU = "stock-ru"
    PRODUCTS = "products"

@strawberry.type
class QuoteGQL:
    symbol: str
    last: Optional[float]
    bid: Optional[float]
    ask: Optional[float]
    ts: datetime

@strawberry.type
class CandleGQL:
    symbol: str
    interval: str
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

@strawberry.type
class FxRateGQL:
    pair: str
    rate: float

@strawberry.type
class Query:
    health: JSON = strawberry.field(resolver=lambda: market_data_api.health())

    @strawberry.field
    def quotes(self, symbols: List[str], asset_class: AssetClass) -> List[QuoteGQL]:
        items = market_data_api.get_quotes(symbols, asset_class.value)
        return [QuoteGQL(**q.__dict__) for q in items]

    @strawberry.field
    def candles(self, symbol: str, interval: str, asset_class: AssetClass,
                since: Optional[date] = None, till: Optional[date] = None) -> List[CandleGQL]:
        items = market_data_api.get_candles(symbol, interval, asset_class.value, since, till)
        return [CandleGQL(**c.__dict__) for c in items]

    @strawberry.field
    def fx_rates(self, pairs: List[str], source: Optional[str] = None) -> List[FxRateGQL]:
        m = market_data_api.get_fx_rates(pairs, source)
        return [FxRateGQL(pair=k, rate=v) for k, v in (m or {}).items()]

@strawberry.type
class Mutation:
    @strawberry.mutation
    def refreshCrypto(self, symbols: List[str]) -> bool:
        market_data_api.crypto.refresh_quotes(symbols)
        return True

schema = strawberry.Schema(query=Query, mutation=Mutation)
