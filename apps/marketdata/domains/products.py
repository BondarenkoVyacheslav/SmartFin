from apps.marketdata.domains.domain import Domain

from typing import (
    Iterable, Sequence, List, Optional, Dict, Any, Literal
)
from datetime import date, datetime
from apps.marketdata.providers.provider import Quote, Candle

class Products(Domain):
    """Товары/коммодитиз: золото, нефть и пр."""
    def get_quotes(self, symbols: Sequence[str]) -> List[Quote]:
        # TODO: cache + provider.get_quotes(...)
        return []

    def get_candles(self, symbol: str, interval: str,
                    since: Optional[date] = None, till: Optional[date] = None) -> List[Candle]:
        # TODO
        return []