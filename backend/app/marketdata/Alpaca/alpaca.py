from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence

import httpx

from app.marketdata.Alpaca.cache_keys import AlpacaCacheKeys
from app.marketdata.Alpaca.dto.quote import AlpacaStockQuote, parse_alpaca_snapshots
from app.marketdata.provider import Provider
from app.marketdata.services.redis_cache import RedisCacheService


class AlpacaProvider(Provider):
    """
    Alpaca Market Data provider (REST snapshots endpoint).
    - OAuth2 client_credentials (authx.alpaca.markets)
    - REST via httpx
    - caches per-symbol quotes in Redis

    For indices use ETF proxies (SPY, QQQ, DIA, IWM, ONEQ, ...).
    """

    Keys = AlpacaCacheKeys
    KP = Keys.KP

    TTL_QUOTE = 5
    TTL_INDEX_QUOTE = 5

    AUTH_URL = "https://authx.alpaca.markets"
    DATA_URL = "https://data.alpaca.markets"

    def __init__(
        self,
        cache: Optional[RedisCacheService] = None,
        *,
        redis_url: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        feed: Optional[str] = None,
        currency: Optional[str] = None,
        timeout_s: float = 10.0,
        user_agent: str = "SmartFin/AlpacaProvider/1.0",
        token_skew_s: int = 30,
    ) -> None:
        super().__init__(
            cache_service=cache,
            redis_url=redis_url,
        )

        self.client_id = (
            client_id
            or os.getenv("ALPACA_CLIENT_ID")
            or os.getenv("ALPACA_API_KEY")
        )
        self.client_secret = (
            client_secret
            or os.getenv("ALPACA_CLIENT_SECRET")
            or os.getenv("ALPACA_API_SECRET")
        )

        self.feed = (feed or os.getenv("ALPACA_DATA_FEED") or "iex").lower()
        self.currency = (currency or os.getenv("ALPACA_DATA_CURRENCY") or "USD").upper()

        self._token_skew_s = token_skew_s
        self._access_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None
        self._token_lock = asyncio.Lock()

        self._auth_http = httpx.AsyncClient(
            base_url=self.AUTH_URL,
            timeout=timeout_s,
            headers={"User-Agent": user_agent},
        )
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

    def _token_valid(self) -> bool:
        if not self._access_token:
            return False
        if self._token_expires_at is None:
            return True
        now = datetime.now(timezone.utc) + timedelta(seconds=self._token_skew_s)
        return self._token_expires_at > now

    @staticmethod
    def _parse_expiry(value: Any) -> Optional[datetime]:
        if value is None:
            return None
        if isinstance(value, datetime):
            dt = value
        elif isinstance(value, (int, float)):
            dt = datetime.fromtimestamp(float(value), tz=timezone.utc)
        elif isinstance(value, str):
            s = value.strip()
            if not s:
                return None
            if s.endswith("Z"):
                s = s[:-1] + "+00:00"
            try:
                dt = datetime.fromisoformat(s)
            except ValueError:
                if s.isdigit():
                    dt = datetime.fromtimestamp(float(s), tz=timezone.utc)
                else:
                    return None
        else:
            return None

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    async def _fetch_token(self) -> str:
        if not self.client_id or not self.client_secret:
            raise ValueError("Alpaca client_id/client_secret are required")

        resp = await self._auth_http.post(
            "/v1/oauth2/token",
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
        )
        resp.raise_for_status()
        payload = resp.json()

        token = payload.get("access_token")
        if not token:
            raise RuntimeError("Alpaca auth response missing access_token")

        expires_at = self._parse_expiry(payload.get("expires_at"))
        if expires_at is None:
            expires_in = payload.get("expires_in")
            try:
                expires_in = int(expires_in)
            except (TypeError, ValueError):
                expires_in = None
            if expires_in:
                expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

        self._access_token = token
        self._token_expires_at = expires_at
        return token

    async def _get_access_token(self) -> str:
        if self._token_valid():
            return self._access_token  # type: ignore[return-value]

        async with self._token_lock:
            if self._token_valid():
                return self._access_token  # type: ignore[return-value]
            return await self._fetch_token()

    async def _auth_headers(self) -> Dict[str, str]:
        token = await self._get_access_token()
        return {"Authorization": f"Bearer {token}"}

    async def _get(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        backoff = [0.2, 0.5, 1.0, 2.0]
        tried_refresh = False
        last_exc: Optional[BaseException] = None

        for attempt, delay in enumerate(backoff, start=1):
            try:
                headers = await self._auth_headers()
                resp = await self._data_http.get(path, params=params, headers=headers)

                if resp.status_code == 401 and not tried_refresh:
                    self._access_token = None
                    self._token_expires_at = None
                    tried_refresh = True
                    continue

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
        await self._auth_http.aclose()
        await self._data_http.aclose()
