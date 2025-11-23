from __future__ import annotations

import os
import logging

import strawberry
from strawberry.asgi import GraphQL
from starlette.requests import Request

from apps.marketdata.providers.Crypto.CoinGecko.schema import CoinGeckoQuery
from apps.marketdata.providers.Crypto.CoinGecko.coingecko import CoinGeckoProvider
from apps.marketdata.services.redis_cache import RedisCacheService

logger = logging.getLogger(__name__)

schema = strawberry.Schema(query=CoinGeckoQuery)


class SmartFinGraphQL(GraphQL):
    async def get_root_value(
        self,
        request: Request,
    ) -> CoinGeckoQuery:
        # URL Redis берём из окружения докер-контейнера
        redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")

        cache = RedisCacheService(
            redis_url=redis_url,
            default_ttl=60,  # для тестов можно сделать маленький TTL
        )

        provider = CoinGeckoProvider(cache=cache)

        # root_value — это экземпляр CoinGeckoQuery с конкретным провайдером и кешом
        return CoinGeckoQuery(coin_gecko_provider=provider, cache=cache)


graphql_app = SmartFinGraphQL(schema)

# Это ASGI-приложение, которое понимает uvicorn / hypercorn
app = graphql_app
