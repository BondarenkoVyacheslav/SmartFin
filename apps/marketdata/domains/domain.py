# apps/marketdata/api.py
from __future__ import annotations

from typing import (
    Iterable, Sequence, List, Optional
)
from datetime import date

from apps.marketdata.services.redis_cache import RedisCacheService




class Domain:
    """База для доменных классов: общий кэш, вспомогалки и провайдерный реестр."""
    def __init__(self, cache: RedisCacheService):
        self.cache = cache

    # -- Вспомогательные ключи кэша (каждый домен может расширять) --
    def _k_quotes(self, scope: str, symbols: Sequence[str]) -> str:
        return f"v1:md:{scope}:quotes:{','.join(sorted(symbols))}"

    def _k_candles(self, scope: str, symbol: str, interval: str,
                   since: Optional[date] = None, till: Optional[date] = None) -> str:
        rng = ""
        if since or till:
            rng = f":{since or ''}:{till or ''}"
        return f"v1:md:{scope}:candles:{symbol}:{interval}{rng}"

    def _k_orderbook(self, scope: str, symbol: str, depth: int, level: int) -> str:
        return f"v1:md:{scope}:orderbook:{symbol}:L{level}:D{depth}"

    def _k_list(self, scope: str, name: str, *parts: str) -> str:
        tail = ":".join([p for p in parts if p])
        return f"v1:md:{scope}:{name}:{tail}"

    # -- Опционально: домены могут иметь собственный роутинг по провайдерам --
    def _providers_for(self, purpose: str, prefer: Optional[List[str]] = None) -> List[str]:
        # TODO: implement per-domain provider routing
        return prefer or []