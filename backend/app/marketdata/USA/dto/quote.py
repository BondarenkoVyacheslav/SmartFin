from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import strawberry

from app.marketdata.services.redis_json import RedisJSON


@strawberry.type
@dataclass
class USAStockQuote(RedisJSON):
    symbol: str
    last: Optional[float]
    bid: Optional[float]
    ask: Optional[float]
    ts: datetime
    currency: Optional[str] = None
    exchange: Optional[str] = None
    short_name: Optional[str] = None
    long_name: Optional[str] = None
