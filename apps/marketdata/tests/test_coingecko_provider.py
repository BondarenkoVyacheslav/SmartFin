# apps/marketdata/tests/test_coingecko_provider.py

import asyncio
from typing import Any, Dict, Optional

import httpx
import pytest
import respx

from apps.marketdata.providers.Crypto.CoinGecko.coingecko import CoinGeckoProvider
from apps.marketdata.providers.Crypto.CoinGecko.dto.simple_price import ListSimplePricesEntry
from apps.marketdata.providers.Crypto.CoinGecko.dto.supported_vs_currencies import SupportedVSCurrencies


class FakeRedisCache:
    """
    Простейший in-memory кеш с async интерфейсом как у RedisCacheService:
    get / set / delete.

    Ничего не сериализует — это важно: мы проверяем, что CoinGeckoProvider
    кладёт в кеш уже готовое значение, с которым потом справится
    ListSimplePricesEntry.from_redis_value / SupportedVSCurrencies.from_redis_value.
    """

    def __init__(self) -> None:
        self.data: Dict[str, Any] = {}

    async def get(self, key: str) -> Optional[Any]:
        return self.data.get(key)

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        # ttl игнорируем, он нам не нужен для тестов
        self.data[key] = value

    async def delete(self, key: str) -> None:
        self.data.pop(key, None)



@pytest.fixture
def fake_cache() -> FakeRedisCache:
    return FakeRedisCache()


@pytest.fixture
def coingecko_provider(fake_cache: FakeRedisCache) -> CoinGeckoProvider:
    """
    ВАЖНО: тут подстрой конструктор под свой CoinGeckoProvider.

    Я предполагаю примерно такое:
        CoinGeckoProvider(cache_service=fake_cache)
    или
        CoinGeckoProvider(redis_cache=fake_cache)
    или
        CoinGeckoProvider(cache=fake_cache)

    Если что – просто переименуй аргумент.
    """
    return CoinGeckoProvider(cache_service=fake_cache)  # <--- подправь, если нужно


@respx.mock
@pytest.mark.asyncio
async def test_simple_price_builds_correct_request_and_caches(
    coingecko_provider: CoinGeckoProvider,
    fake_cache: FakeRedisCache,
):
    # --- подготовка мок-ответа CoinGecko /simple/price ---
    api_json = {
        "bitcoin": {
            "usd": 42000.5,
            "usd_market_cap": 1_000_000.0,
            "usd_24h_vol": 500_000.0,
            "usd_24h_change": -1.5,
            "last_updated_at": 1700000000,
        },
        "ethereum": {
            "usd": 3000.0,
            "usd_market_cap": 500_000.0,
            "usd_24h_vol": 100_000.0,
            "usd_24h_change": 2.5,
            "last_updated_at": 1700000001,
        },
    }

    # Если в провайдере BASE_URL другой – поправь тут путь
    route = respx.get("https://api.coingecko.com/api/v3/simple/price").mock(
        return_value=httpx.Response(200, json=api_json)
    )

    # --- вызов провайдера ---
    result = await coingecko_provider.simple_price(
        ids=["bitcoin", "ethereum"],
        vs_currencies=["usd"],
        include_market_cap=True,
        include_24h_vol=True,
        include_24h_change=True,
        include_last_updated_at=True,
    )

    # --- 1) Проверяем, что запрос ушёл по нужному URL ---
    assert route.called, "CoinGeckoProvider.simple_price не сделал HTTP-запрос"
    request = route.calls[0].request

    assert request.method == "GET"
    # пути типа "/api/v3/simple/price" или "simple/price" – страхуемся обо всё сразу
    assert "simple/price" in str(request.url.path)

    # --- 2) Проверяем query-параметры ---
    params = request.url.params

    # ids и vs_currencies должны быть CSV через запятую
    assert params["ids"] == "bitcoin,ethereum"
    assert params["vs_currencies"] == "usd"

    # Булевые параметры — по идее "true"/"false", но на всякий случай не завязываемся жёстко на регистр
    def _bool_str(v: str) -> bool:
        return v.lower() in ("true", "1", "yes")

    assert _bool_str(params.get("include_market_cap", "false"))
    assert _bool_str(params.get("include_24h_vol", "false"))
    assert _bool_str(params.get("include_24h_change", "false"))
    assert _bool_str(params.get("include_last_updated_at", "false"))

    # --- 3) Проверяем маппинг JSON -> DTO ---
    assert isinstance(result, ListSimplePricesEntry)
    assert len(result.simple_prices) == 2

    btc = next(p for p in result.simple_prices if p.coin_id == "bitcoin")
    eth = next(p for p in result.simple_prices if p.coin_id == "ethereum")

    assert btc.vs_currency == "usd"
    assert btc.price == 42000.5
    assert btc.market_cap == 1_000_000.0
    assert btc.vol_24h == 500_000.0
    assert btc.change_24h == -1.5
    assert btc.last_updated_at == 1700000000

    assert eth.vs_currency == "usd"
    assert eth.price == 3000.0

    # --- 4) Проверяем, что провайдер что-то положил в кеш ---
    assert fake_cache.data, "После simple_price кеш пуст – провайдер не пишет в RedisCacheService"

    # Берём единственный ключ/значение из кеша
    cache_key, cache_value = next(iter(fake_cache.data.items()))

    # Ключ можешь проверить как хочешь, я оставлю мягкую проверку:
    assert "simple_price" in cache_key

    # --- 5) Проверяем, что значение в кеше съедобно для ListSimplePricesEntry.from_redis_value ---
    restored = ListSimplePricesEntry.from_redis_value(cache_value)
    assert isinstance(restored, ListSimplePricesEntry)
    assert len(restored.simple_prices) == len(result.simple_prices)

    restored_btc = next(p for p in restored.simple_prices if p.coin_id == "bitcoin")
    assert restored_btc.price == btc.price
    assert restored_btc.market_cap == btc.market_cap
    assert restored_btc.last_updated_at == btc.last_updated_at


@respx.mock
@pytest.mark.asyncio
async def test_supported_vs_currencies_request_and_caching(
    coingecko_provider: CoinGeckoProvider,
    fake_cache: FakeRedisCache,
):
    # Мок-ответ CoinGecko /simple/supported_vs_currencies
    # Специально кладём "грязные" строки – проверим логику parse_supported_vs_currencies
    api_json = ["usd", "eur", "USD", " eur ", "rub"]

    route = respx.get("https://api.coingecko.com/api/v3/simple/supported_vs_currencies").mock(
        return_value=httpx.Response(200, json=api_json)
    )

    result = await coingecko_provider.simple_supported_vs_currencies()

    # --- 1) HTTP-запрос ---
    assert route.called, "simple_supported_vs_currencies не сделал HTTP-запрос"
    request = route.calls[0].request

    assert request.method == "GET"
    assert "supported_vs_currencies" in str(request.url.path)

    # --- 2) Маппинг в DTO ---
    assert isinstance(result, SupportedVSCurrencies)
    # parse_supported_vs_currencies должен:
    # - привести к lower
    # - обрезать пробелы
    # - удалить дубли
    assert result.currencies == ["usd", "eur", "rub"]

    # --- 3) Кеш ---
    assert fake_cache.data, "После simple_supported_vs_currencies кеш пуст"

    cache_key, cache_value = next(iter(fake_cache.data.items()))
    assert "supported_vs_currencies" in cache_key

    restored = SupportedVSCurrencies.from_redis_value(cache_value)
    assert isinstance(restored, SupportedVSCurrencies)
    assert restored.currencies == result.currencies
