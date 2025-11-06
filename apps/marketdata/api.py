# apps/marketdata/api.py
from __future__ import annotations
from typing import Iterable, List, Optional
from dataclasses import asdict
from apps.marketdata.providers.registry import get_provider
from apps.marketdata.providers.Provider import Quote, Candle
from apps.marketdata.services.redis_cache import RedisCacheService
from django.conf import settings

DEFAULT_TTLS = {
    "quotes:crypto": 30,
    "quotes:stock": 60,
    "candles:intra": 60,
    "candles:daily": 300,
}

class MarketDataAPI:
    """
    Фасад для чтения котировок/свечей из кэша и через провайдеров с failover.
    Все ответы нормализованы в DTO (Quote/Candle).
    """

    def __init__(self,
                 redis_url: Optional[str] = None,
                 default_ttls: Optional[dict] = None):
        redis_url = redis_url or getattr(settings, "REDIS_URL", "redis://localhost:6379/0")
        self.cache = RedisCacheService(redis_url=redis_url, default_ttl=60)
        self.ttls = {**DEFAULT_TTLS, **(default_ttls or {})}

    # ---------- Public API ----------

    def get_quotes(self,
                   symbols: Iterable[str],
                   asset_class: str,
                   prefer: Optional[List[str]] = None,
                   use_cache: bool = True) -> List[Quote]:
        """
        asset_class: 'crypto' | 'stock-ru' | 'stock-us' | 'fx'
        prefer: порядок провайдеров по приоритету, например ['bybit','okx'] для crypto
        """
        symbols = list(symbols)
        if not symbols:
            return []

        cache_key = self._k_quotes(asset_class, symbols)
        if use_cache:
            cached = self.cache.get(cache_key)
            if cached:
                return [Quote(**q) for q in cached]

        for prov_code in self._providers_for(asset_class, prefer):
            provider = get_provider(prov_code)
            try:
                quotes = provider.get_quotes(symbols)
                if quotes:
                    self.cache.set(cache_key, [asdict(q) for q in quotes],
                                   ttl=self._ttl_for("quotes", asset_class))
                    return quotes
            except Exception:
                # логируй через стандартный логгер/аудит
                continue

        return []

    def get_candles(self,
                    symbol: str,
                    interval: str,
                    asset_class: str,
                    prefer: Optional[List[str]] = None,
                    use_cache: bool = True) -> List[Candle]:
        cache_key = self._k_candles(asset_class, symbol, interval)
        if use_cache:
            cached = self.cache.get(cache_key)
            if cached:
                return [Candle(**c) for c in cached]

        for prov_code in self._providers_for(asset_class, prefer):
            provider = get_provider(prov_code)
            try:
                candles = provider.get_candles(symbol, interval)
                if candles:
                    ttl_key = "daily" if interval.lower() in ("1d", "1w", "1m", "d", "w", "m") else "intra"
                    self.cache.set(cache_key, [asdict(c) for c in candles],
                                   ttl=self._ttl_for("candles", asset_class, ttl_key))
                    return candles
            except Exception:
                continue

        return []

    def health(self) -> dict:
        return self.cache.health_check()

    # ---------- Helpers ----------

    def _providers_for(self, asset_class: str, prefer: Optional[List[str]]) -> List[str]:
        if prefer:
            return prefer
        if asset_class == "crypto":
            return ["bybit", "okx"]
        if asset_class == "stock-ru":
            return ["moex", "tinkoff"]
        if asset_class == "stock-us":
            # позже: polygon/tiingo/alpha-vantage/… 
            return ["tradingview"]
        if asset_class == "fx":
            return ["tradingview"]
        return []

    def _k_quotes(self, asset_class: str, symbols: List[str]) -> str:
        return f"v1:md:{asset_class}:quotes:{','.join(sorted(symbols))}"

    def _k_candles(self, asset_class: str, symbol: str, interval: str) -> str:
        return f"v1:md:{asset_class}:candles:{symbol}:{interval}"

    def _ttl_for(self, kind: str, asset_class: str, sub: Optional[str] = None) -> int:
        if kind == "quotes" and asset_class == "crypto":
            return self.ttls["quotes:crypto"]
        if kind == "quotes":
            return self.ttls["quotes:stock"]
        if kind == "candles" and sub == "daily":
            return self.ttls["candles:daily"]
        return self.ttls["candles:intra"]
