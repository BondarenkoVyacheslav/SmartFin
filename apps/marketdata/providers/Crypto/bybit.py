# apps/marketdata/providers/Crypto/bybit.py
from __future__ import annotations
from typing import List, Optional
from datetime import datetime
from pybit.unified_trading import HTTP
from apps.marketdata.providers.provider import Provider, Quote, Candle
from apps.marketdata.services.redis_cache import RedisCacheService  # ПРАВИЛЬНЫЙ импорт

class BybitProvider(Provider):
    code = "bybit"
    name = "Bybit"

    def __init__(self,
                 redis_url: Optional[str] = None,
                 api_key: Optional[str] = None,
                 api_secret: Optional[str] = None,
                 testnet: bool = False):
        self.cache = RedisCacheService(redis_url or "redis://localhost:6379/0", default_ttl=60)
        self.http = HTTP(testnet=testnet, api_key=api_key, api_secret=api_secret)

    def get_quotes(self, symbols: List[str]) -> List[Quote]:
        # Bybit не даёт пакет за раз по разным символам для spot/linear одинаково удобно,
        # поэтому возьмём get_tickers(category="spot") и отфильтруем.
        resp = self.http.get_tickers(category="spot", limit=1000)
        if not resp or resp.get("retCode") != 0:
            return []
        wanted = set(s.upper() for s in symbols)
        out: List[Quote] = []
        now = datetime.utcnow()
        for row in resp["result"]["list"]:
            sym = row.get("symbol", "").upper()
            if sym in wanted:
                last = float(row["lastPrice"]) if row.get("lastPrice") else None
                bid  = float(row["bid1Price"]) if row.get("bid1Price") else None
                ask  = float(row["ask1Price"]) if row.get("ask1Price") else None
                out.append(Quote(symbol=sym, last=last, bid=bid, ask=ask, ts=now))
        return out

    def get_candles(self, symbol: str, interval: str, start=None, end=None) -> List[Candle]:
        # Для MVP игнорируем start/end (Bybit ограничивает лимиты), берём последние N
        resp = self.http.get_kline(category="spot", symbol=symbol, interval=interval, limit=200)
        if not resp or resp.get("retCode") != 0:
            return []
        out: List[Candle] = []
        for ts, open_, high, low, close, volume, *_ in resp["result"]["list"]:
            # Bybit отдаёт строки; ts — epoch ms
            dt = datetime.utcfromtimestamp(int(ts) / 1000)
            out.append(Candle(
                symbol=symbol, interval=interval, ts=dt,
                open=float(open_), high=float(high), low=float(low),
                close=float(close), volume=float(volume or 0)
            ))
        return out
