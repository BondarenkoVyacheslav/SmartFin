from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, date
from typing import Any, Dict, List, Optional
from app.marketdata.services.redis_cache import RedisCacheService

class Provider(ABC):
    code: str
    name: str
    _cache_service: Optional[RedisCacheService] = None
    _redis_url: Optional[str] = None

    def __init__(
            self,
            cache_service: Optional[RedisCacheService] = None,
            *,
            redis_url: Optional[str] = None,
    ) -> None:
        if cache_service and redis_url:
            raise ValueError(
                "Pass either an existing RedisCacheService instance or redis "
                "URL, not both."
            )

        self._cache_service = cache_service
        self._redis_url = redis_url

    def _get_cache(self) -> RedisCacheService:
        if self._cache_service is None:
            self._cache_service = RedisCacheService(
                redis_url=self._redis_url or "redis://localhost:6379/0",
            )
        return self._cache_service

    @property
    def cache(self) -> RedisCacheService:
        return self._get_cache()

    @property
    def redis(self) -> RedisCacheService:
        return self._get_cache()
