# bybit_provider.py
from __future__ import annotations

import json
import threading
import time
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from apps.marketdata.providers.provider import Provider
from apps.marketdata.services.redis_cache import RedisCacheService

import httpx
from pybit.unified_trading import WebSocket  # офиц. SDK V5


# === Провайдер Bybit ===
class BybitProvider(Provider):
    """
    Гибридный провайдер под твою архитектуру:
    - REST (httpx) для справочников и медленных метрик
    - WS (pybit) для тикеров и сделок в реальном времени
    - Все только пишет/читает из кэша; домены дергают публичные методы
    """

    # ====== Константы TTL (сек) — можно переопределять из Domain ======
    TTL_SERVER_TIME = 5
    TTL_INSTRUMENTS = 3600  # 1 час (можно 12-24h)
    TTL_TICKER = 5
    TTL_TRADES = 5
    TTL_FUNDING = 900  # 15 минут
    TTL_HV = 3600  # 1 час
    TTL_LSR = 900  # 15 минут
    TTL_INSURANCE = 1800  # 30 минут
    TTL_PRICE_LIMIT = 30
    TTL_ADL_ALERT = 60

    # ====== Базовый префикс ключей ======
    KP = "v1:md:crypto:bybit"

    def __init__(self,
                 cache: RedisCacheService,
                 testnet: bool = False,
                 timeout_s: int = 10,
                 user_agent: str = "SmartFin/BybitProvider/1.0"):
        super().__init__(cache)
        self.base_url = "https://api-testnet.bybit.com" if testnet else "https://api.bybit.com"
        self.http = httpx.Client(
            base_url=self.base_url,
            timeout=timeout_s,
            headers={"User-Agent": user_agent}
        )

        # WS — создаем по мере подписок (разные публичные каналы по категориям)
        self._ws: Dict[str, WebSocket] = {}  # key: category (spot|linear|inverse|option)
        self._ws_lock = threading.Lock()
        self._ws_threads: List[threading.Thread] = []
        self._ws_running = False
        self._is_testnet = testnet

    # ---------- Ключи кэша ----------
    @staticmethod
    def _csv(symbols: Sequence[str]) -> str:
        return ",".join(sorted({s.upper() for s in symbols}))

    def k_server_time(self) -> str:
        return f"{self.KP}:server_time"

    def k_instruments(self, category: str) -> str:
        return f"{self.KP}:{category}:instruments"

    def k_ticker(self, category: str, symbol: str) -> str:
        return f"{self.KP}:{category}:ticker:{symbol.upper()}"

    def k_trades(self, category: str, symbol: str) -> str:
        return f"{self.KP}:{category}:trades:{symbol.upper()}"

    def k_funding(self, symbol: str) -> str:
        return f"{self.KP}:funding_history:{symbol.upper()}"

    def k_hv(self, base_coin: str, range_key: str) -> str:
        return f"{self.KP}:hv:{base_coin.upper()}:{range_key}"

    def k_lsr(self, symbol: str, period: str) -> str:
        return f"{self.KP}:long_short_ratio:{symbol.upper()}:{period}"

    def k_insurance(self, coin: Optional[str]) -> str:
        return f"{self.KP}:insurance:{(coin or 'ALL').upper()}"

    def k_price_limit(self, category: str, symbol: str) -> str:
        return f"{self.KP}:{category}:price_limit:{symbol.upper()}"

    def k_adl_alert(self, symbol: Optional[str]) -> str:
        return f"{self.KP}:adl_alert:{(symbol or 'ALL').upper()}"

    # ====== REST helper с простым бэкоффом ======
    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        backoff = [0.2, 0.5, 1.0, 2.0]
        for i, delay in enumerate(backoff):
            try:
                r = self.http.get(path, params=params)
                r.raise_for_status()
                payload = r.json()
                # Формат Bybit: {"retCode":0, "result": {...}}
                if payload.get("retCode") != 0:
                    raise httpx.HTTPError(
                        f"Bybit retCode={payload.get('retCode')} retMsg={payload.get('retMsg')}"
                    )
                return payload.get("result", payload)
            except Exception:
                if i == len(backoff) - 1:
                    raise
                time.sleep(delay)
        raise RuntimeError("unreachable")

    # ====== Справочная информация ======
    def fetch_server_time(self) -> Dict[str, Any]:
        res = self._get("/v5/market/time")
        self.cache.set(self.k_server_time(), res, ttl=self.TTL_SERVER_TIME)
        return res

    def fetch_instruments_info(self, category: str, **filters) -> List[Dict[str, Any]]:
        params = {"category": category, **filters}
        out: List[Dict[str, Any]] = []
        cursor = None
        while True:
            if cursor:
                params["cursor"] = cursor
            chunk = self._get("/v5/market/instruments-info", params)
            out.extend(chunk.get("list", []))
            cursor = chunk.get("nextPageCursor")
            if not cursor:
                break
        self.cache.set(self.k_instruments(category), out, ttl=self.TTL_INSTRUMENTS)
        return out

    # ====== Снапшоты цен и сделок (REST) ======
    def fetch_tickers_snapshot(
            self, category: str, symbols: Optional[Sequence[str]] = None
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"category": category}
        if symbols and len(symbols) == 1:
            params["symbol"] = symbols[0].upper()
        res = self._get("/v5/market/tickers", params)
        rows: List[Dict[str, Any]] = res.get("list", [])

        # пишем по-символьно (удобно фронту/домену получать выборки)
        kv: Dict[str, Any] = {}
        for item in rows:
            sym = item.get("symbol", "").upper()
            if not sym:
                continue
            if symbols and len(symbols) > 1 and sym not in {s.upper() for s in symbols}:
                continue
            kv[self.k_ticker(category, sym)] = item
        if kv:
            self.cache.set_many(kv, ttl=self.TTL_TICKER)
        return rows

    def fetch_recent_trades(
            self, category: str, symbol: str, limit: int = 200
    ) -> List[Dict[str, Any]]:
        params = {"category": category, "symbol": symbol.upper(), "limit": limit}
        res = self._get("/v5/market/recent-trade", params)
        trades: List[Dict[str, Any]] = res.get("list", [])
        self.cache.set(self.k_trades(category, symbol), trades, ttl=self.TTL_TRADES)
        return trades

    # ====== Деривативные метрики (REST) ======
    def fetch_funding_rate_history(
            self, category: str, symbol: str, *, startTime: Optional[int] = None, endTime: Optional[int] = None,
            limit: int = 200
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"category": category, "symbol": symbol.upper(), "limit": limit}
        if startTime and endTime:
            params.update({"startTime": startTime, "endTime": endTime})
        res = self._get("/v5/market/history-fund-rate", params)
        rows = res.get("list", [])
        self.cache.set(self.k_funding(symbol), rows, ttl=self.TTL_FUNDING)
        return rows

    def fetch_historical_volatility(
            self, baseCoin: str, *, startTime: Optional[int] = None, endTime: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"baseCoin": baseCoin.upper()}
        if startTime and endTime:
            params.update({"startTime": startTime, "endTime": endTime})
        res = self._get("/v5/market/historical-volatility", params)
        rows = res.get("list", [])
        range_key = f"{startTime or 'auto'}-{endTime or 'auto'}"
        self.cache.set(self.k_hv(baseCoin, range_key), rows, ttl=self.TTL_HV)
        return rows

    def fetch_long_short_ratio(
            self, category: str, symbol: str, *, period: str = "1h", limit: int = 50
    ) -> List[Dict[str, Any]]:
        params = {"category": category, "symbol": symbol.upper(), "period": period, "limit": limit}
        res = self._get("/v5/market/account-ratio", params)
        rows = res.get("list", [])
        self.cache.set(self.k_lsr(symbol, period), rows, ttl=self.TTL_LSR)
        return rows

    # ====== Риск / страхование (REST) ======
    def fetch_insurance_pool(self, coin: Optional[str] = None) -> List[Dict[str, Any]]:
        params = {"coin": coin.upper()} if coin else None
        res = self._get("/v5/market/insurance", params)
        rows = res.get("list", [])
        self.cache.set(self.k_insurance(coin), rows, ttl=self.TTL_INSURANCE)
        return rows

    def fetch_order_price_limit(self, category: str, symbol: str) -> Dict[str, Any]:
        params = {"category": category, "symbol": symbol.upper()}
        res = self._get("/v5/market/price-limit", params)
        self.cache.set(self.k_price_limit(category, symbol), res, ttl=self.TTL_PRICE_LIMIT)
        return res

    def fetch_adl_alert(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        params = {"symbol": symbol.upper()} if symbol else None
        res = self._get("/v5/market/adlAlert", params)
        self.cache.set(self.k_adl_alert(symbol), res, ttl=self.TTL_ADL_ALERT)
        return res

    # ====== WebSocket (тикеры + сделки в real-time) ======
    def _ensure_ws(self, category: str) -> WebSocket:
        with self._ws_lock:
            ws = self._ws.get(category)
            if ws:
                return ws

            # channel_type принимает: "spot" | "linear" | "inverse" | "option"
            ws = WebSocket(testnet=self._is_testnet, channel_type=category)

            # Колбэк для тикеров
            def on_ticker(msg: Dict[str, Any]):
                data = msg.get("data")
                if not data:
                    return
                items = data if isinstance(data, list) else [data]
                for item in items:
                    sym = (item.get("symbol") or item.get("s"))
                    if not sym:
                        continue
                    self.cache.set(self.k_ticker(category, sym), item, ttl=self.TTL_TICKER)

            # Колбэк для сделок
            def on_trade(msg: Dict[str, Any]):
                data = msg.get("data")
                if not data:
                    return
                items = data if isinstance(data, list) else [data]
                if not items:
                    return
                sym = (items[0].get("symbol") or items[0].get("s"))
                if not sym:
                    return
                self.cache.set(self.k_trades(category, sym), items, ttl=self.TTL_TRADES)

            # Подключаем стримы; подписка на символы ниже
            ws.ticker_stream(callback=on_ticker)
            ws.trade_stream(callback=on_trade)

            self._ws[category] = ws
            return ws

    def start_ws(self, subscriptions: Dict[str, Iterable[str]]) -> None:
        """
        Пример:
        {
          "spot":   ["BTCUSDT","ETHUSDT"],
          "linear": ["BTCUSDT"],
          "inverse": [],
          "option": []
        }
        """
        if self._ws_running:
            return
        self._ws_running = True

        def worker(category: str, symbols: List[str]):
            ws = self._ensure_ws(category)
            # pybit позволяет указывать список символов в subscribe-методах.
            # Если у тебя другая версия pybit — можно заменить на ws.subscribe([...])
            try:
                ws.subscribe([f"tickers.{s}" for s in symbols])
                ws.subscribe([f"publicTrade.{s}" for s in symbols])
            except Exception:
                # Бэкап, если метод subscribe недоступен в твоей версии:
                try:
                    ws.ticker_stream(callback=lambda *_: None, symbol=symbols)  # no-op; подписка через аргументы
                    ws.trade_stream(callback=lambda *_: None, symbol=symbols)
                except Exception:
                    pass

            while self._ws_running:
                time.sleep(0.2)

        for cat, syms in (subscriptions or {}).items():
            if not syms:
                continue
            t = threading.Thread(target=worker, args=(cat, list(syms)), daemon=True)
            t.start()
            self._ws_threads.append(t)

    def stop_ws(self) -> None:
        self._ws_running = False
        for t in self._ws_threads:
            t.join(timeout=1.0)
        self._ws_threads.clear()
        with self._ws_lock:
            for ws in self._ws.values():
                try:
                    ws.exit()
                except Exception:
                    pass
            self._ws.clear()