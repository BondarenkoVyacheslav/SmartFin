# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import time
from dataclasses import asdict
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

import httpx

# Подстрой пути импортов под свой проект:
from apps.marketdata.providers.base import Provider, Quote, Candle
from apps.marketdata.services.redis_cache import RedisCacheService


TD_BASE_URL = os.getenv("TD_BASE_URL", "https://api.twelvedata.com")
TD_API_KEY  = os.getenv("TWELVE_DATA_API_KEY", "")  # положи ключ в ENV
TD_TIMEOUT  = float(os.getenv("TD_TIMEOUT_S", "1.0"))   # «жёсткие» дефолты
TD_RETRIES  = int(os.getenv("TD_RETRIES", "2"))         # можно переопределять из YAML/БД

# простейший экспоненциальный backoff с джиттером
def _sleep_backoff(attempt: int) -> None:
    base = 0.15 * (2 ** attempt)
    jitter = min(0.3, base * 0.25)
    time.sleep(base + (jitter * (0.5 - os.urandom(1)[0] / 255.0)))


class TwelveDataProvider(Provider):
    """
    Единый адаптер Twelve Data.
    Поддерживает: Stocks (US), Forex, Crypto; технические индикаторы; фундаментальные данные.
    Документация Twelve Data по REST/индикаторам/символам в источниках к ответу.
    """
    code = "twelve"
    name = "Twelve Data"

    def __init__(
        self,
        api_key: Optional[str] = None,
        redis_url: Optional[str] = None,
        default_ttl: int = 60,
        timeout_s: Optional[float] = None,
        retries: Optional[int] = None,
    ):
        self.api_key = api_key or TD_API_KEY
        if not self.api_key:
            raise RuntimeError("TWELVE_DATA_API_KEY is not set")

        self.timeout = timeout_s or TD_TIMEOUT
        self.retries = retries if retries is not None else TD_RETRIES

        self.base_url = TD_BASE_URL.rstrip("/")
        self.cache = RedisCacheService(redis_url or "redis://localhost:6379/0", default_ttl=default_ttl)

        self._client = httpx.Client(
            base_url=self.base_url,
            headers={"User-Agent": "SmartFin/marketdata.twelve"},
            timeout=self.timeout,
        )

    # ---------------------- ПУБЛИЧНЫЙ КОНТРАКТ ----------------------

    def get_quotes(self, symbols: Iterable[str]) -> List[Quote]:
        """
        Квоты для множества символов одним запросом (/quote?symbol=AAPL,MSFT,EUR/USD,BTC/USD)
        Stocks/Forex/Crypto — единый формат у Twelve Data.
        """
        syms = _norm_symbols(symbols)
        if not syms:
            return []

        # Кэш-ключ агрегированный (для скорости UI-виджетов)
        cache_key = f"v1:md:twelve:quotes:{','.join(syms)}"
        cached = self.cache.get(cache_key)
        if cached:
            return [Quote(**q) for q in cached]

        payload = {"symbol": ",".join(syms)}
        data = self._get("/quote", payload)

        # Ответ у TwelveData может быть объектом (1 символ) или { "data": [ ... ] } при bulk
        rows = []
        if isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
            rows = data["data"]
        elif isinstance(data, dict):
            rows = [data]
        else:
            rows = []

        now = datetime.utcnow()
        out: List[Quote] = []
        for row in rows:
            sym = row.get("symbol")
            # у Twelve Data часто есть цена в "price" и/или "close"
            last = _f(row.get("price") or row.get("close"))
            out.append(Quote(symbol=sym, last=last, bid=None, ask=None, ts=now))

        # TTL для US-акций чуть больше, чем для crypto/FX — можно разделять политикой выше
        self.cache.set(cache_key, [asdict(q) for q in out], ttl=60)
        return out

    def get_candles(
        self,
        symbol: str,
        interval: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        outputsize: Optional[int] = None,
        exchange: Optional[str] = None,
        timezone: Optional[str] = None,
    ) -> List[Candle]:
        """
        Исторические свечи через /time_series.
        interval: 1min,5min,15min,30min,45min,1h,2h,4h,8h,1day,1week,1month (подтв. в доках)
        """
        cache_key = f"v1:md:twelve:candles:{symbol}:{interval}:{start or ''}:{end or ''}:{outputsize or ''}"
        cached = self.cache.get(cache_key)
        if cached:
            return [Candle(**c) for c in cached]

        params = {
            "symbol": symbol,
            "interval": interval,
        }
        if exchange:
            params["exchange"] = exchange
        if outputsize:
            params["outputsize"] = outputsize
        if start:
            params["start_date"] = _dt(start)
        if end:
            params["end_date"] = _dt(end)
        if timezone:
            params["timezone"] = timezone

        data = self._get("/time_series", params)

        values = []
        if isinstance(data, dict) and "values" in data and isinstance(data["values"], list):
            values = data["values"]

        # Twelve Data отдаёт "values" в порядке от новых к старым — развернём для удобства
        out: List[Candle] = []
        for row in reversed(values):
            ts = _pdt(row.get("datetime"))
            out.append(
                Candle(
                    symbol=symbol,
                    interval=interval,
                    ts=ts,
                    open=_f(row.get("open")),
                    high=_f(row.get("high")),
                    low=_f(row.get("low")),
                    close=_f(row.get("close")),
                    volume=_f(row.get("volume")) or 0.0,
                )
            )

        ttl = 300 if interval.lower() in ("1day", "1week", "1month", "d", "w", "m") else 60
        self.cache.set(cache_key, [asdict(c) for c in out], ttl=ttl)
        return out

    # ---------- Технические индикаторы (универсальный вызов) ----------

    def get_indicator(
        self,
        symbol: str,
        name: str,
        interval: str,
        **params: Any,
    ) -> Dict[str, Any]:
        """
        Любой индикатор ‘по имени’ (RSI/MACD/EMA/BBANDS/…): /{indicator}
        Примеры:
          get_indicator("AAPL", "rsi", "1day", time_period=14)
          get_indicator("AAPL", "macd", "1day", fast_period=12, slow_period=26, signal_period=9)
        """
        endpoint = f"/{name.lower()}"
        q = {"symbol": symbol, "interval": interval}
        q.update(params)

        cache_key = f"v1:md:twelve:ti:{name.lower()}:{symbol}:{interval}:{sorted(q.items())}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached

        data = self._get(endpoint, q)
        # возвращаем «как есть», фронт/сервис выше сам адаптирует
        self.cache.set(cache_key, data, ttl=120)
        return data

    # ---------- Фундаментальные данные ----------

    def get_company_profile(self, symbol: str) -> Dict[str, Any]:
        return self._fundamentals_cached("/profile", symbol, ttl=3600)

    def get_income_statement(self, symbol: str, period: str = "annual") -> Dict[str, Any]:
        return self._fundamentals_cached("/income_statement", symbol, ttl=3600, period=period)

    def get_balance_sheet(self, symbol: str, period: str = "annual") -> Dict[str, Any]:
        return self._fundamentals_cached("/balance_sheet", symbol, ttl=3600, period=period)

    def get_cash_flow(self, symbol: str, period: str = "annual") -> Dict[str, Any]:
        return self._fundamentals_cached("/cash_flow", symbol, ttl=3600, period=period)

    def get_earnings(self, symbol: str) -> Dict[str, Any]:
        return self._fundamentals_cached("/earnings", symbol, ttl=3600)

    # ---------------------- НИЖЕЛЕЖАЩИЕ ВСПОМОГАТЕЛЬНЫЕ ----------------------

    def _fundamentals_cached(self, endpoint: str, symbol: str, ttl: int = 1800, **extra) -> Dict[str, Any]:
        cache_key = f"v1:md:twelve:fund:{endpoint}:{symbol}:{extra}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        q = {"symbol": symbol}
        q.update(extra)
        data = self._get(endpoint, q)
        self.cache.set(cache_key, data, ttl=ttl)
        return data

    def _get(self, endpoint: str, params: Dict[str, Any]) -> Any:
        """GET с ретраями и backoff+jitter. Добавляет apikey, обрабатывает bulk-ответы Twelve Data."""
        if not endpoint.startswith("/"):
            endpoint = "/" + endpoint

        params = dict(params or {})
        params["apikey"] = self.api_key

        last_exc: Optional[Exception] = None
        for attempt in range(self.retries + 1):
            try:
                resp = self._client.get(endpoint, params=params)
                if resp.status_code >= 500:
                    raise httpx.HTTPStatusError("5xx from provider", request=resp.request, response=resp)
                resp.raise_for_status()
                data = resp.json()
                # Некоторые ответы Twelve Data при ошибке содержат {'code':..., 'message':...}
                if isinstance(data, dict) and data.get("code"):
                    raise RuntimeError(f"TwelveData error {data.get('code')}: {data.get('message')}")
                return data
            except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError, RuntimeError) as e:
                last_exc = e
                if attempt < self.retries:
                    _sleep_backoff(attempt)
                    continue
                raise

# ------------------------- ВСПОМОГАТЕЛЬНЫЕ УТИЛИТЫ -------------------------

def _f(v: Any) -> Optional[float]:
    try:
        return float(v) if v is not None else None
    except Exception:
        return None

def _dt(d: datetime) -> str:
    # ISO8601 без таймзоны — Twelve Data принимает 'YYYY-MM-DD' или 'YYYY-MM-DD HH:MM:SS'
    return d.strftime("%Y-%m-%d %H:%M:%S")

def _pdt(s: Optional[str]) -> datetime:
    # Twelve Data присылает 'YYYY-MM-DD' или 'YYYY-MM-DD HH:MM:SS' (по докам/клиентам)
    if not s:
        return datetime.utcnow()
    try:
        if " " in s:
            return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
        return datetime.strptime(s, "%Y-%m-%d")
    except Exception:
        return datetime.utcnow()

def _norm_symbols(symbols: Iterable[str]) -> List[str]:
    out = []
    for s in symbols:
        if not s:
            continue
        s = str(s).strip()
        # Twelve Data поддерживает: "AAPL", "EUR/USD", "BTC/USD", а также "SBIN:NSE" (exchange suffix)
        out.append(s)
    return out
