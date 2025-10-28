from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
import threading
import time

class Transport(Enum):
    WS = "ws"
    GRPC = "grpc"
    REST = "rest"

@dataclass
class TransportPrefs:
    # порядок предпочтения транспорта при запросах котировок/свечей
    quotes_order: tuple[Transport, ...] = (Transport.WS, Transport.GRPC, Transport.REST)
    candles_order: tuple[Transport, ...] = (Transport.GRPC, Transport.REST)

@dataclass
class TinkoffCreds:
    token: str | None = None  # прод-токен
    sandbox_token: str | None = None  # если надо

class InMemoryRateLimiter:
    """Простой token-bucket без Redis. Можно потом заменить на Redis."""
    def __init__(self, rate_per_sec: float, capacity: int | None = None):
        self.rate = rate_per_sec
        self.capacity = capacity or max(1, int(rate_per_sec * 2))
        self.tokens = self.capacity
        self.lock = threading.Lock()
        self.last = time.monotonic()

    def acquire(self, cost: int = 1):
        with self.lock:
            now = time.monotonic()
            elapsed = now - self.last
            self.last = now
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            if self.tokens >= cost:
                self.tokens -= cost
                return True
            return False

    def wait(self, cost: int = 1):
        while not self.acquire(cost):
            time.sleep(0.02)
