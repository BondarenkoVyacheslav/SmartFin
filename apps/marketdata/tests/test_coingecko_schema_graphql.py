import pytest
import strawberry

from apps.marketdata.providers.Crypto.CoinGecko.schema import CoinGeckoQuery
from apps.marketdata.providers.Crypto.CoinGecko.dto.simple_price import (
    ListSimplePricesEntry,
    SimplePriceEntry,
)


class FakeRedisCache:
    def __init__(self):
        self.data = {}

    async def get(self, key):
        return self.data.get(key)

    async def set(self, key, value, ttl=None):
        self.data[key] = value


class FakeProvider:
    def __init__(self):
        self.simple_price_called = False

    async def ping(self):
        return None

    async def simple_price(
        self,
        ids,
        vs_currencies,
        include_market_cap=False,
        include_24hr_vol=False,
        include_24hr_change=False,
        include_last_updated_at=False,
    ):
        self.simple_price_called = True
        dto = ListSimplePricesEntry(
            entries=[
                SimplePriceEntry(
                    id="bitcoin",
                    vs_currency="usd",
                    price=50000.0,
                    market_cap=None,
                    volume_24h=None,
                    price_change_24h=None,
                    last_updated_at=None,
                )
            ]
        )
        return dto


@pytest.mark.asyncio
async def test_simple_price_cache_hit():
    fake_cache = FakeRedisCache()
    fake_provider = FakeProvider()

    # заранее кладём DTO в кеш
    dto = ListSimplePricesEntry(
        entries=[
            SimplePriceEntry(
                id="bitcoin",
                vs_currency="usd",
                price=50000.0,
                market_cap=None,
                volume_24h=None,
                price_change_24h=None,
                last_updated_at=None,
            )
        ]
    )
    fake_cache.data["coingecko:simple_price:some_sig"] = dto.to_redis_value()

    schema = strawberry.Schema(query=CoinGeckoQuery)
    root_value = CoinGeckoQuery(coin_gecko_provider=fake_provider, cache=fake_cache)

    query = """
    query {
      simplePrice(
        ids: ["bitcoin"],
        vsCurrencies: ["usd"]
      ) {
        entries {
          id
          vsCurrency
          price
        }
      }
    }
    """

    result = await schema.execute(query, root_value=root_value)
    assert result.errors is None
    data = result.data["simplePrice"]["entries"][0]
    assert data["id"] == "bitcoin"
    assert data["price"] == 50000.0

    # при hit мы ожидаем, что провайдер не был вызван
    assert fake_provider.simple_price_called is False
