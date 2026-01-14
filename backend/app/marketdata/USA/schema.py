from __future__ import annotations

from typing import List, Optional, Sequence

import strawberry

from app.marketdata.USA.cache_keys import USAStockCacheKeys
from app.marketdata.USA.dto.quote import USAStockQuote
from app.marketdata.USA.usa import USAStockProvider
from app.marketdata.services.redis_cache import RedisCacheService


@strawberry.type
class USAStockQuery:
    def __init__(self, usa_provider: USAStockProvider, cache: Optional[RedisCacheService] = None):
        self.usa_provider = usa_provider
        self.cache = cache or usa_provider.cache

    @staticmethod
    def _normalize_symbols(symbols: Sequence[str]) -> List[str]:
        seen = set()
        ordered: List[str] = []
        for symbol in symbols:
            if not symbol:
                continue
            normalized = symbol.strip().upper()
            if normalized and normalized not in seen:
                seen.add(normalized)
                ordered.append(normalized)
        return ordered

    @strawberry.field
    async def quote(self, symbol: str) -> Optional[USAStockQuote]:
        symbol = symbol.strip().upper()
        if not symbol:
            return None

        key = USAStockCacheKeys.quote(symbol)
        cached = await self.cache.get(key)
        dto = USAStockQuote.from_redis_value(cached)
        if dto is not None:
            return dto

        return await self.usa_provider.quote(symbol)

    @strawberry.field
    async def quotes(self, symbols: List[str]) -> List[USAStockQuote]:
        normalized = self._normalize_symbols(symbols)
        if not normalized:
            return []

        keys = [USAStockCacheKeys.quote(symbol) for symbol in normalized]
        cached = await self.cache.get_many(keys)

        cached_quotes: dict[str, USAStockQuote] = {}
        missing: List[str] = []

        for symbol in normalized:
            key = USAStockCacheKeys.quote(symbol)
            dto = USAStockQuote.from_redis_value(cached.get(key))
            if dto is not None:
                cached_quotes[symbol] = dto
            else:
                missing.append(symbol)

        fresh_quotes = await self.usa_provider.quotes(missing)

        merged = {**cached_quotes, **{q.symbol: q for q in fresh_quotes}}
        return [merged[symbol] for symbol in normalized if symbol in merged]
