from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Sequence

import httpx

from .cache_keys import AlpacaCacheKeys
from .dto.quote import AlpacaStockQuote, parse_alpaca_snapshots
from app.marketdata.provider import Provider
from app.marketdata.services.redis_cache import RedisCacheService


class AlpacaProvider(Provider):
    """
    Alpaca Market Data provider (REST snapshots endpoint).
    - REST via httpx
    - caches per-symbol quotes in Redis

    For indices use ETF proxies (SPY, QQQ, DIA, IWM, ONEQ, ...).
    """

    Keys = AlpacaCacheKeys
    KP = Keys.KP

    TTL_QUOTE = 5
    TTL_INDEX_QUOTE = 5

    DATA_URL = "https://data.alpaca.markets"

    def __init__(
        self,
        cache: Optional[RedisCacheService] = None,
        *,
        redis_url: Optional[str] = None,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        feed: Optional[str] = None,
        currency: Optional[str] = None,
        timeout_s: float = 10.0,
        user_agent: str = "SmartFin/AlpacaProvider/1.0",
    ) -> None:
        super().__init__(
            cache_service=cache,
            redis_url=redis_url,
        )

        self.api_key = api_key or os.getenv("ALPACA_API_KEY")
        self.api_secret = api_secret or os.getenv("ALPACA_API_SECRET")

        self.feed = (feed or os.getenv("ALPACA_DATA_FEED") or "iex").lower()
        self.currency = (currency or os.getenv("ALPACA_DATA_CURRENCY") or "USD").upper()

        self._data_http = httpx.AsyncClient(
            base_url=self.DATA_URL,
            timeout=timeout_s,
            headers={"User-Agent": user_agent},
        )

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

    async def _auth_headers(self) -> Dict[str, str]:
        if not self.api_key or not self.api_secret:
            raise ValueError("Alpaca api_key/api_secret are required")
        return {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.api_secret,
        }

    async def _get(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        backoff = [0.2, 0.5, 1.0, 2.0]
        last_exc: Optional[BaseException] = None

        for attempt, delay in enumerate(backoff, start=1):
            try:
                headers = await self._auth_headers()
                resp = await self._data_http.get(path, params=params, headers=headers)

                if resp.status_code == 429 and attempt < len(backoff):
                    retry_after = resp.headers.get("Retry-After")
                    try:
                        sleep_for = float(retry_after) if retry_after is not None else delay
                    except (TypeError, ValueError):
                        sleep_for = delay
                    await asyncio.sleep(sleep_for)
                    continue

                resp.raise_for_status()
                return resp.json()

            except httpx.HTTPStatusError as exc:
                last_exc = exc
                if exc.response.status_code >= 500 and attempt < len(backoff):
                    await asyncio.sleep(delay)
                    continue
                raise
            except httpx.RequestError as exc:
                last_exc = exc
                if attempt < len(backoff):
                    await asyncio.sleep(delay)
                    continue
                raise

        if last_exc is not None:
            raise last_exc
        raise RuntimeError("AlpacaProvider._get: unreachable")

    async def _fetch_snapshots(
        self,
        symbols: Sequence[str],
        *,
        feed: str,
        currency: str,
    ) -> List[AlpacaStockQuote]:
        if not symbols:
            return []

        params: Dict[str, Any] = {"symbols": ",".join(symbols)}
        if feed:
            params["feed"] = feed
        if currency:
            params["currency"] = currency

        data = await self._get("/v2/stocks/snapshots", params=params)
        return parse_alpaca_snapshots(data, feed=feed, currency=currency)

    async def quotes(
        self,
        symbols: Sequence[str],
        *,
        feed: Optional[str] = None,
        currency: Optional[str] = None,
    ) -> List[AlpacaStockQuote]:
        normalized = self._normalize_symbols(symbols)
        if not normalized:
            return []

        feed = (feed or self.feed).lower()
        currency = (currency or self.currency).upper()

        keys = [self.Keys.stock_quote(symbol, feed, currency) for symbol in normalized]
        cached = await self.cache.get_many(keys)

        cached_quotes: Dict[str, AlpacaStockQuote] = {}
        missing: List[str] = []

        for symbol in normalized:
            key = self.Keys.stock_quote(symbol, feed, currency)
            dto = AlpacaStockQuote.from_redis_value(cached.get(key))
            if dto is not None and dto.last is not None:
                cached_quotes[symbol] = dto
            else:
                missing.append(symbol)

        fresh_quotes = await self._fetch_snapshots(missing, feed=feed, currency=currency)

        if fresh_quotes:
            payload = {
                self.Keys.stock_quote(q.symbol, feed, currency): q for q in fresh_quotes
            }
            await self.cache.set_many(payload, ttl=self.TTL_QUOTE)

        merged: Dict[str, AlpacaStockQuote] = {
            **cached_quotes,
            **{q.symbol: q for q in fresh_quotes},
        }
        return [merged[symbol] for symbol in normalized if symbol in merged]

    async def quote(
        self,
        symbol: str,
        *,
        feed: Optional[str] = None,
        currency: Optional[str] = None,
    ) -> Optional[AlpacaStockQuote]:
        quotes = await self.quotes([symbol], feed=feed, currency=currency)
        return quotes[0] if quotes else None

    async def index_quotes(
        self,
        symbols: Sequence[str],
        *,
        feed: Optional[str] = None,
        currency: Optional[str] = None,
    ) -> List[AlpacaStockQuote]:
        normalized = self._normalize_symbols(symbols)
        if not normalized:
            return []

        feed = (feed or self.feed).lower()
        currency = (currency or self.currency).upper()

        keys = [self.Keys.index_quote(symbol, feed, currency) for symbol in normalized]
        cached = await self.cache.get_many(keys)

        cached_quotes: Dict[str, AlpacaStockQuote] = {}
        missing: List[str] = []

        for symbol in normalized:
            key = self.Keys.index_quote(symbol, feed, currency)
            dto = AlpacaStockQuote.from_redis_value(cached.get(key))
            if dto is not None and dto.last is not None:
                cached_quotes[symbol] = dto
            else:
                missing.append(symbol)

        fresh_quotes = await self._fetch_snapshots(missing, feed=feed, currency=currency)

        if fresh_quotes:
            payload = {
                self.Keys.index_quote(q.symbol, feed, currency): q for q in fresh_quotes
            }
            await self.cache.set_many(payload, ttl=self.TTL_INDEX_QUOTE)

        merged: Dict[str, AlpacaStockQuote] = {
            **cached_quotes,
            **{q.symbol: q for q in fresh_quotes},
        }
        return [merged[symbol] for symbol in normalized if symbol in merged]

    async def index_quote(
        self,
        symbol: str,
        *,
        feed: Optional[str] = None,
        currency: Optional[str] = None,
    ) -> Optional[AlpacaStockQuote]:
        quotes = await self.index_quotes([symbol], feed=feed, currency=currency)
        return quotes[0] if quotes else None

    async def latest_price(
        self,
        symbol: str,
        *,
        feed: Optional[str] = None,
        currency: Optional[str] = None,
    ) -> Optional[float]:
        quote = await self.quote(symbol, feed=feed, currency=currency)
        if quote is None:
            return None
        return quote.last

    async def aclose(self) -> None:
        await self._data_http.aclose()
