from __future__ import annotations

import asyncio
import os
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

import httpx

from app.marketdata.USA.cache_keys import USAStockCacheKeys
from app.marketdata.USA.dto.quote import USAStockQuote
from app.marketdata.provider import Provider, Quote
from app.marketdata.services.redis_cache import RedisCacheService


class USAStockProvider(Provider):
    """
    US stock quotes provider backed by Yahoo Finance.
    - REST via httpx
    - caches quotes in Redis
    """

    Keys = USAStockCacheKeys

    TTL_QUOTE = 15

    BASE_URL = "https://query1.finance.yahoo.com"

    def __init__(
        self,
        cache: RedisCacheService | None = None,
        *,
        redis_url: Optional[str] = None,
        base_url: str = BASE_URL,
        timeout_s: float = 10.0,
        user_agent: str = "SmartFin/USAStockProvider/1.0",
    ) -> None:
        super().__init__(
            cache_service=cache,
            redis_url=redis_url,
        )
        self.base_url = base_url.rstrip("/")
        user_agent = os.getenv(
            "MARKETDATA_USA_USER_AGENT",
            user_agent,
        )
        self.http = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout_s,
            headers={"User-Agent": user_agent},
        )

    async def _get(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        resp = await self.http.get(path, params=params)
        resp.raise_for_status()
        return resp.json()

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

    def _parse_quote(self, raw: Dict[str, Any]) -> USAStockQuote:
        symbol = (raw.get("symbol") or "").upper()
        ts_raw = raw.get("regularMarketTime") or raw.get("postMarketTime") or raw.get("preMarketTime")
        ts = datetime.fromtimestamp(ts_raw, tz=timezone.utc) if ts_raw else datetime.now(timezone.utc)

        return USAStockQuote(
            symbol=symbol,
            last=raw.get("regularMarketPrice"),
            bid=raw.get("bid"),
            ask=raw.get("ask"),
            ts=ts,
            currency=raw.get("currency"),
            exchange=raw.get("fullExchangeName") or raw.get("exchange"),
            short_name=raw.get("shortName"),
            long_name=raw.get("longName"),
        )

    async def _fetch_quotes(self, symbols: Sequence[str]) -> List[USAStockQuote]:
        if not symbols:
            return []

        data = await self._get(
            "/v7/finance/quote",
            params={"symbols": ",".join(symbols)},
        )
        items = data.get("quoteResponse", {}).get("result", []) or []
        quotes = [self._parse_quote(item) for item in items if isinstance(item, dict)]
        return quotes

    async def quote(self, symbol: str) -> Optional[USAStockQuote]:
        normalized = self._normalize_symbols([symbol])
        if not normalized:
            return None

        key = self.Keys.quote(normalized[0])
        cached = await self.cache.get(key)
        dto = USAStockQuote.from_redis_value(cached)
        if dto is not None:
            return dto

        quotes = await self._fetch_quotes(normalized)
        if not quotes:
            return None

        await self.cache.set(self.Keys.quote(quotes[0].symbol), quotes[0], ttl=self.TTL_QUOTE)
        return quotes[0]

    async def quotes(self, symbols: Sequence[str]) -> List[USAStockQuote]:
        normalized = self._normalize_symbols(symbols)
        if not normalized:
            return []

        keys = [self.Keys.quote(symbol) for symbol in normalized]
        cached = await self.cache.get_many(keys)

        cached_quotes: Dict[str, USAStockQuote] = {}
        missing: List[str] = []

        for symbol in normalized:
            cache_key = self.Keys.quote(symbol)
            dto = USAStockQuote.from_redis_value(cached.get(cache_key))
            if dto is not None:
                cached_quotes[symbol] = dto
            else:
                missing.append(symbol)

        fresh_quotes = await self._fetch_quotes(missing)

        if fresh_quotes:
            payload = {self.Keys.quote(q.symbol): q for q in fresh_quotes}
            await self.cache.set_many(payload, ttl=self.TTL_QUOTE)

        merged: Dict[str, USAStockQuote] = {**cached_quotes, **{q.symbol: q for q in fresh_quotes}}
        return [merged[symbol] for symbol in normalized if symbol in merged]

    async def latest_price(self, symbol: str) -> Optional[float]:
        quote = await self.quote(symbol)
        if quote is None:
            return None
        return quote.last

    async def aclose(self) -> None:
        await self.http.aclose()
        
