from __future__ import annotations
from datetime import datetime, date
from typing import List, Optional, Dict

import httpx

from apps.marketdata.providers.base import Provider, Quote, Candle

# Базовая конфигурация MOEX ISS
DEFAULT_BASE_URL = "https://iss.moex.com/iss"
# Простейшая маппа таймфреймов для свечей ISS
MOEX_INTERVALS = {
    "1m": 1,
    "10m": 10,
    "1h": 60,   # у ISS "60" = час
    "1d": 24,   # у ISS "24" = день
}

def _f(x):
    try:
        return float(x) if x is not None else None
    except Exception:
        return None

class MoexISSProvider(Provider):
    """
    Провайдер для официального ISS API Мосбиржи (REST, pull-модель).
    - get_quotes: пакетные котировки по тикерам из заданного board (по умолчанию акции T+ — TQBR)
    - get_candles: исторические свечи по одному инструменту
    """
    code = "moex"
    name = "MOEX ISS"

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout_s: float = 12.0,
        # По умолчанию акции T+ на TQBR. Для облигаций/ETF можно создать второй инстанс с другим board.
        engine: str = "stock",
        market: str = "shares",
        board: str = "TQBR",
    ):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_s
        self._engine = engine
        self._market = market
        self._board = board

    # -------- Quotes --------
    def get_quotes(self, symbols: List[str]) -> List[Quote]:
        if not symbols:
            return []
        params = {
            "securities": ",".join(symbols),
            "iss.only": "marketdata",
            "iss.meta": "off",
        }
        url = (
            f"{self._base_url}/engines/{self._engine}/markets/{self._market}"
            f"/boards/{self._board}/securities.json"
        )
        with httpx.Client(timeout=self._timeout) as c:
            r = c.get(url, params=params)
            r.raise_for_status()
            payload = r.json()

        table = payload.get("marketdata", {})
        columns: List[str] = table.get("columns", [])
        data = table.get("data", [])
        col = {name: i for i, name in enumerate(columns)}

        now = datetime.utcnow()
        out: List[Quote] = []
        for row in data:
            secid = row[col.get("SECID")] if "SECID" in col else None
            if not secid:
                continue
            last = _f(row[col.get("LAST")]) if "LAST" in col else None
            bid  = _f(row[col.get("BID")])  if "BID" in col else None
            ask  = _f(row[col.get("OFFER")]) if "OFFER" in col else None
            out.append(Quote(symbol=str(secid), last=last, bid=bid, ask=ask, ts=now))
        return out

    # -------- Candles --------
    def get_candles(
        self,
        symbol: str,
        interval: str,
        start: date,
        end: Optional[date] = None,
    ) -> List[Candle]:
        iv = MOEX_INTERVALS.get(interval)
        if iv is None:
            raise ValueError(f"Unsupported MOEX interval: {interval}. Use one of {list(MOEX_INTERVALS)}")

        params = {
            "from": start.isoformat(),
            "till": (end or start).isoformat(),
            "interval": iv,
            "iss.meta": "off",
        }
        url = (
            f"{self._base_url}/engines/{self._engine}/markets/{self._market}"
            f"/boards/{self._board}/securities/{symbol}/candles.json"
        )
        with httpx.Client(timeout=self._timeout) as c:
            r = c.get(url, params=params)
            r.raise_for_status()
            payload = r.json()

        table = payload.get("candles", {})
        columns: List[str] = table.get("columns", [])
        data = table.get("data", [])
        idx = {name: i for i, name in enumerate(columns)}

        out: List[Candle] = []
        for row in data:
            ts = row[idx["begin"]]
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            out.append(
                Candle(
                    symbol=symbol,
                    interval=interval,
                    ts=ts,
                    open=float(row[idx["open"]]),
                    high=float(row[idx["high"]]),
                    low=float(row[idx["low"]]),
                    close=float(row[idx["close"]]),
                    volume=float(row[idx["volume"]]) if "volume" in idx else 0.0,
                )
            )
        return out
