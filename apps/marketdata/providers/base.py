from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, date
from typing import List, Optional

@dataclass
class Quote:
    symbol: str
    last: Optional[float]
    bid: Optional[float]
    ask: Optional[float]
    ts: datetime

@dataclass
class Candle:
    symbol: str
    interval: str  # '1m','5m','1h','1d'...
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

class Provider(ABC):
    code: str
    name: str

    @abstractmethod
    def get_quotes(self, symbols: List[str]) -> List[Quote]:
        ...

    @abstractmethod
    def get_candles(self, symbol: str, interval: str, start: date, end: Optional[date] = None) -> List[Candle]:
        ...
