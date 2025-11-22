from __future__ import annotations
from abc import ABC
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional
from apps.marketdata.services.redis_cache import RedisCacheService


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
    _cache_service: Any
    _redis_url: Optional[str] = None
    _redis_options: Optional[Dict[str, Any]] = None

    def __init__(
            self,
            cache_service: Any,
            *,
            redis_url: Optional[str] = None,
            redis_options: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Base provider initialisation.

        Args:
            cache_service: Pre-configured Redis cache service instance.
            redis_url: URL that will be used to instantiate :class:`RedisCacheService`
                when ``cache_service`` is not provided.
            redis_options: Additional keyword arguments passed to
                :class:`RedisCacheService` when it is created internally.
        """

        if cache_service and (redis_url or redis_options):
            raise ValueError(
                "Pass either an existing RedisCacheService instance or redis "
                "configuration parameters, not both."
            )

        self._cache_service = cache_service
        self._redis_url = redis_url
        self._redis_options = dict(redis_options or {})

    def _get_cache(self) -> RedisCacheService:
        if self._cache_service is None:
            options = self._redis_options or {}
            self._cache_service = RedisCacheService(
                redis_url=self._redis_url or "redis://localhost:6379/0",
                **options,
            )
        return self._cache_service

    @property
    def cache(self) -> RedisCacheService:
        """Return configured Redis cache service instance."""

        return self._get_cache()

    @property
    def redis(self) -> RedisCacheService:
        """Backward compatible alias for :attr:`cache`."""

        return self._get_cache()
