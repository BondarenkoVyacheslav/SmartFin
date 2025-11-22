# apps/marketdata/providers/Crypto/CoinGecko/tests/test_schema_simple_price.py

import json

import pytest
import strawberry

from apps.marketdata.providers.Crypto.CoinGecko.schema import CoinGeckoQuery
from apps.marketdata.providers.Crypto.CoinGecko.cache_keys import CoinGeckoCacheKeys
from apps.marketdata.providers.Crypto.CoinGecko.coingecko import CoinGeckoProvider
from apps.marketdata.providers.Crypto.CoinGecko.dto.simple_price import (
    SimplePriceEntry,
    ListSimplePricesEntry,
)


@pytest.fixture
def anyio_backend():
    # Специально для этого файла: гоняем тесты только на asyncio,
    # потому что Strawberry / GraphQL используют asyncio внутри.
    return "asyncio"

class FakeRedisCache:
    """
    Простейший in-memory кеш с тем же интерфейсом, что RedisCacheService:
    get/set async, без реального Redis.
    """

    def __init__(self) -> None:
        self.data: dict[str, object] = {}

    async def get(self, key: str):
        return self.data.get(key)

    async def set(self, key: str, value, ttl: int | None = None):
        self.data[key] = value
        # как RedisCacheService.set — не возвращаем значение, просто успешно отработали
        return True


class FakeCoinGeckoProvider:
    """
    Фейковый провайдер, чтобы:
    - подставлять заранее готовый DTO;
    - проверять, вызывался ли simple_price.
    """

    def __init__(self, simple_price_result: ListSimplePricesEntry | None):
        self.simple_price_result = simple_price_result
        self.simple_price_called = False
        self.simple_price_call_args = None
        self.simple_price_call_kwargs = None

    async def ping(self):
        return None  # для полноты, но в этих тестах не используется

    async def simple_price(self, *args, **kwargs) -> ListSimplePricesEntry:
        self.simple_price_called = True
        self.simple_price_call_args = args
        self.simple_price_call_kwargs = kwargs
        return self.simple_price_result


def build_schema() -> strawberry.Schema:
    """
    Собираем схему поверх CoinGeckoQuery.
    """
    return strawberry.Schema(query=CoinGeckoQuery)


def build_simple_price_key(
    ids: list[str],
    vs_currencies: list[str],
    include_market_cap: bool,
    include_24h_vol: bool,
    include_24h_change: bool,
    include_last_updated_at: bool,
) -> str:
    """
    Строим ключ ТАК ЖЕ, как это делает CoinGeckoQuery.simple_price.
    """

    ids_csv = CoinGeckoProvider.csv(ids)
    vs_csv = CoinGeckoProvider.csv(vs_currencies)

    opts_sig = CoinGeckoProvider.sig(
        "mc" if include_market_cap else "nomc",
        "vol" if include_24h_vol else "novol",
        "chg" if include_24h_change else "nochg",
        "ts" if include_last_updated_at else "nots",
    )

    key = CoinGeckoCacheKeys.simple_price(
        ids_sig=CoinGeckoProvider.sig(ids_csv),
        vs_sig=CoinGeckoProvider.sig(vs_csv),
        opts_sig=opts_sig,
    )
    return key


# ---------- Тест: cache hit ----------

@pytest.mark.anyio
async def test_simple_price_cache_hit_returns_data_from_cache():
    """
    Сценарий:
    - в FakeRedisCache уже лежит JSON, совместимый с ListSimplePricesEntry;
    - GraphQL запрос simplePrice;
    - провайдер НЕ вызывается;
    - в ответе данные ровно из кеша.
    """

    # Входные аргументы GraphQL
    ids = ["bitcoin"]
    vs_currencies = ["usd"]
    include_market_cap = True
    include_24h_vol = True
    include_24h_change = True
    include_last_updated_at = True

    # Ожидаемое содержимое
    entry_dict = {
        "coin_id": "bitcoin",
        "vs_currency": "usd",
        "price": 42000.5,
        "market_cap": 1_000_000.0,
        "vol_24h": 10_000.0,
        "change_24h": 0.5,
        "last_updated_at": 1_700_000_000,
    }
    cached_payload = {
        # как dataclasses.asdict(ListSimplePricesEntry)
        "simple_prices": [entry_dict],
    }
    cached_json = json.dumps(cached_payload, ensure_ascii=False, separators=(",", ":"))

    fake_cache = FakeRedisCache()
    fake_provider = FakeCoinGeckoProvider(simple_price_result=None)

    # Кладём "готовый" кеш по тому же ключу, что использует резолвер
    key = build_simple_price_key(
        ids=ids,
        vs_currencies=vs_currencies,
        include_market_cap=include_market_cap,
        include_24h_vol=include_24h_vol,
        include_24h_change=include_24h_change,
        include_last_updated_at=include_last_updated_at,
    )
    await fake_cache.set(key, cached_json)

    # Собираем схему и root_value
    schema = build_schema()
    root_value = CoinGeckoQuery(coin_gecko_provider=fake_provider, cache=fake_cache)

    # GraphQL-запрос:
    # Если у тебя выключен auto_camel_case, поменяй simplePrice→simple_price и т.п.
    query = """
    query SimplePriceFromCache {
      simplePrice(
        ids: ["bitcoin"]
        vsCurrencies: ["usd"]
        includeMarketCap: true
        include24hrVol: true
        include24hrChange: true
        includeLastUpdatedAt: true
      ) {
        simplePrices {
          coinId
          vsCurrency
          price
          marketCap
          vol24h
          change24h
          lastUpdatedAt
        }
      }
    }
    """

    result = await schema.execute(query, root_value=root_value)

    assert result.errors is None, result.errors
    assert "simplePrice" in result.data

    data = result.data["simplePrice"]
    rows = data["simplePrices"]
    assert len(rows) == 1

    row = rows[0]
    assert row["coinId"] == "bitcoin"
    assert row["vsCurrency"] == "usd"
    assert row["price"] == 42000.5
    assert row["marketCap"] == 1_000_000.0
    assert row["vol24h"] == 10_000.0
    assert row["change24h"] == 0.5
    assert row["lastUpdatedAt"] == 1_700_000_000

    # Главное: провайдер не должен был вызываться при cache hit
    assert fake_provider.simple_price_called is False


# ---------- Тест: cache miss ----------

@pytest.mark.anyio
async def test_simple_price_cache_miss_calls_provider_and_returns_dto():
    """
    Сценарий:
    - в кеше нет ключа;
    - FakeCoinGeckoProvider.simple_price возвращает DTO ListSimplePricesEntry;
    - GraphQL запрос simplePrice;
    - провайдер вызывается, данные в ответе совпадают с DTO.
    """

    ids = ["bitcoin"]
    vs_currencies = ["usd"]

    include_market_cap = True
    include_24h_vol = True
    include_24h_change = True
    include_last_updated_at = True

    # Готовим DTO, который вернёт провайдер
    dto = ListSimplePricesEntry(
        simple_prices=[
            SimplePriceEntry(
                coin_id="bitcoin",
                vs_currency="usd",
                price=42000.5,
                market_cap=1_000_000.0,
                vol_24h=10_000.0,
                change_24h=0.5,
                last_updated_at=1_700_000_000,
            )
        ]
    )

    fake_cache = FakeRedisCache()  # пустой кеш => cache miss
    fake_provider = FakeCoinGeckoProvider(simple_price_result=dto)

    schema = build_schema()
    root_value = CoinGeckoQuery(coin_gecko_provider=fake_provider, cache=fake_cache)

    query = """
    query SimplePriceFromProvider {
      simplePrice(
        ids: ["bitcoin"]
        vsCurrencies: ["usd"]
        includeMarketCap: true
        include24hrVol: true
        include24hrChange: true
        includeLastUpdatedAt: true
      ) {
        simplePrices {
          coinId
          vsCurrency
          price
          marketCap
          vol24h
          change24h
          lastUpdatedAt
        }
      }
    }
    """

    result = await schema.execute(query, root_value=root_value)

    assert result.errors is None, result.errors
    assert "simplePrice" in result.data

    data = result.data["simplePrice"]
    rows = data["simplePrices"]
    assert len(rows) == 1

    row = rows[0]
    assert row["coinId"] == "bitcoin"
    assert row["vsCurrency"] == "usd"
    assert row["price"] == 42000.5
    assert row["marketCap"] == 1_000_000.0
    assert row["vol24h"] == 10_000.0
    assert row["change24h"] == 0.5
    assert row["lastUpdatedAt"] == 1_700_000_000

    # Здесь наоборот — провайдер обязан был вызваться
    assert fake_provider.simple_price_called is True
