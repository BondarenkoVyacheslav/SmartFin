from __future__ import annotations
from datetime import datetime, date
from typing import List, Optional, Iterable

from apps.marketdata.providers.base import Provider, Quote, Candle
from apps.marketdata.providers.transports import Transport, TransportPrefs, TinkoffCreds, InMemoryRateLimiter
from .clients import TinkoffRestClient, TinkoffGrpcClient, TinkoffWsClient

class TinkoffProvider(Provider):
    code = "tinkoff"
    name = "Tinkoff Invest API (multi-transport)"

    def __init__(
        self,
        creds: TinkoffCreds,
        prefs: TransportPrefs | None = None,
        rps_rest: float = 5.0,
        rps_grpc: float = 10.0,
        rps_ws: float = 50.0,  # по факту стрим не ограничивается RPS, но ограничим send/subscribe
    ):
        if not creds or not (creds.token or creds.sandbox_token):
            raise ValueError("TinkoffProvider: token is required")

        self.creds = creds
        self.prefs = prefs or TransportPrefs()

        # ленивые клиенты
        self._rest: Optional[TinkoffRestClient] = None
        self._grpc: Optional[TinkoffGrpcClient] = None
        self._ws: Optional[TinkoffWsClient] = None

        # простые лимитеры
        self._lim_rest = InMemoryRateLimiter(rps_rest)
        self._lim_grpc = InMemoryRateLimiter(rps_grpc)
        self._lim_ws = InMemoryRateLimiter(rps_ws)

    # -- Lazy clients
    @property
    def rest(self) -> TinkoffRestClient:
        if self._rest is None:
            self._rest = TinkoffRestClient(token=self.creds.token or self.creds.sandbox_token)  # type: ignore
        return self._rest

    @property
    def grpc(self) -> TinkoffGrpcClient:
        if self._grpc is None:
            self._grpc = TinkoffGrpcClient(token=self.creds.token or self.creds.sandbox_token)  # type: ignore
        return self._grpc

    @property
    def ws(self) -> TinkoffWsClient:
        if self._ws is None:
            self._ws = TinkoffWsClient(token=self.creds.token or self.creds.sandbox_token)  # type: ignore
        return self._ws

    # -- Public API
    def get_quotes(self, symbols: List[str]) -> List[Quote]:
        # идем по порядку предпочтений транспорта
        for transport in self.prefs.quotes_order:
            try:
                if transport == Transport.WS:
                    if self._lim_ws.acquire():
                        # ожидается, что stream_quotes отдаст «снэпшоты»/события; для снэпшота можно взять первую пачку
                        events = self._consume_quotes_once(self.ws.stream_quotes(symbols))
                        if events:
                            return events
                elif transport == Transport.GRPC:
                    if self._lim_grpc.acquire():
                        # аналогично — либо короткая подписка, либо unary для last price
                        events = self._grpc_fetch_quotes_once(symbols)
                        if events:
                            return events
                elif transport == Transport.REST:
                    if self._lim_rest.acquire():
                        rows = self.rest.get_quotes(symbols)
                        if rows:
                            return [Quote(
                                symbol=r["symbol"], last=r.get("last"), bid=r.get("bid"), ask=r.get("ask"),
                                ts=r.get("ts") or datetime.utcnow()
                            ) for r in rows]
            except NotImplementedError:
                continue
            except Exception:
                # логирование по месту
                continue
        return []

    def get_candles(self, symbol: str, interval: str, start: date, end: Optional[date] = None) -> List[Candle]:
        for transport in self.prefs.candles_order:
            try:
                if transport == Transport.GRPC:
                    if self._lim_grpc.acquire():
                        rows = self.grpc.get_candles(symbol, interval, start, end)
                        if rows:
                            return [Candle(**row) for row in rows]  # ожидаем нормализованный dict
                elif transport == Transport.REST:
                    if self._lim_rest.acquire():
                        rows = self.rest.get_candles(symbol, interval, start, end)
                        if rows:
                            return [Candle(**row) for row in rows]
            except NotImplementedError:
                continue
            except Exception:
                continue
        return []

    # -- Helpers (one-shot consumption for streams)
    def _consume_quotes_once(self, stream: Iterable[dict], limit: int = 50) -> List[Quote]:
        out: List[Quote] = []
        try:
            for i, event in enumerate(stream):
                if "symbol" not in event:
                    continue
                out.append(Quote(
                    symbol=event["symbol"],
                    last=event.get("last"),
                    bid=event.get("bid"),
                    ask=event.get("ask"),
                    ts=event.get("ts") or datetime.utcnow(),
                ))
                if i + 1 >= limit:
                    break
        except NotImplementedError:
            raise
        except Exception:
            return []
        return out

    def _grpc_fetch_quotes_once(self, symbols: List[str]) -> List[Quote]:
        """
        Заглушка для unary/grpc-«снэпшота».
        Реализуешь через конкретный метод gRPC (например, получение последней цены по figi).
        """
        raise NotImplementedError("gRPC quotes snapshot not yet implemented")
