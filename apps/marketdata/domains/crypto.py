from apps.marketdata.domains.domain import Domain
from typing import (
    Iterable, Sequence, List, Optional, Dict, Any, Literal
)
from datetime import date, datetime
from apps.marketdata.providers.provider import Quote, Candle

class Crypto(Domain):
    """Крипторынок: котировки, свечи, стаканы, сделки, funding/OI/liquidations."""
    def get_quotes(self, symbols: Sequence[str]) -> List[Quote]:
        # TODO: cache + provider.get_quotes(symbols)
        return []

    def get_candles(self, symbol: str, interval: str,
                    since: Optional[date] = None, till: Optional[date] = None) -> List[Candle]:
        # TODO: cache + provider.get_candles(symbol, interval, since, till)
        return []

    def get_orderbook(self, symbol: str, depth: int = 20, level: Literal[1, 2] = 2) -> Dict[str, Any]:
        # TODO: cache + provider.get_orderbook(...)
        return {}

    def get_trades(self, symbol: str, limit: int = 100,
                   since: Optional[datetime] = None, till: Optional[datetime] = None) -> List[Dict[str, Any]]:
        # TODO: provider.get_trades(...)
        return []

    def get_funding_rate(self, symbol: str) -> Optional[float]:
        # TODO: provider.get_funding_rate(...)
        return None

    def get_open_interest(self, symbol: str) -> Optional[float]:
        # TODO: provider.get_open_interest(...)
        return None

    def get_liquidations(self, symbol: Optional[str] = None,
                         since: Optional[datetime] = None, till: Optional[datetime] = None) -> List[Dict[str, Any]]:
        # TODO: provider.get_liquidations(...)
        return []