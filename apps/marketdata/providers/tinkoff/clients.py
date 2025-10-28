from __future__ import annotations
from datetime import date, datetime
from typing import List, Optional

# Интерфейсы тонких клиентов. Реализацию можно подключить позже (SDK/WS/grpcio)

class TinkoffRestClient:
    def __init__(self, token: str, base_url: str = "https://invest-public-api.tinkoff.ru"):
        self.token = token
        self.base_url = base_url
        # Подключать httpx по месту (опц.), чтобы не тащить зависимость:
        # import httpx; self._http = httpx.Client(timeout=10.0, headers={...})

    def get_quotes(self, symbols: List[str]) -> List[dict]:
        """
        TODO: Реализовать REST вызовы под нужные эндпоинты (когда определишь конкретный маршрут).
        Возвращай список словарей: {'symbol': str, 'last': float|None, 'bid': float|None, 'ask': float|None, 'ts': datetime}
        """
        raise NotImplementedError("REST client not yet implemented")

    def get_candles(self, symbol: str, interval: str, start: date, end: Optional[date]) -> List[dict]:
        """TODO: Реализовать исторические свечи через REST (если доступны / или proxied)."""
        raise NotImplementedError("REST client not yet implemented")

class TinkoffGrpcClient:
    def __init__(self, token: str, endpoint: str = "invest-public-api.tinkoff.ru:443"):
        self.token = token
        self.endpoint = endpoint
        # Подключение после установки grpcio + сгенерированных stubs:
        # import grpc, tinkoff.invest as invest
        # self.channel = grpc.secure_channel(endpoint, grpc.ssl_channel_credentials())
        # self.md = [('authorization', f'Bearer {token}')]

    def stream_quotes_subscribe(self, symbols: List[str]):
        """
        TODO: Подписка на стрим котировок (best bid/ask/last) — вернуть итератор/генератор событий.
        """
        raise NotImplementedError("gRPC streaming not yet implemented")

    def get_candles(self, symbol: str, interval: str, start: date, end: Optional[date]):
        """TODO: unary gRPC запрос исторических свечей."""
        raise NotImplementedError("gRPC candles not yet implemented")

class TinkoffWsClient:
    def __init__(self, token: str, ws_url: str = "wss://invest-public-api.tinkoff.ru/ws"):
        self.token = token
        self.ws_url = ws_url
        # Можно использовать websockets/asyncio — привяжем позже.

    def stream_quotes(self, symbols: List[str]):
        """
        TODO: Реализовать вебсокет-подписку; вернуть генератор событий котировок.
        """
        raise NotImplementedError("WebSocket client not yet implemented")
