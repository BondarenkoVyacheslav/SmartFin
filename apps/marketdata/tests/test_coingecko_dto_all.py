from __future__ import annotations

import asyncio
import json
from dataclasses import asdict
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict

from django.test import SimpleTestCase

from apps.marketdata.providers.Crypto.CoinGecko.redis_json import RedisJSON

# --- DTO imports ---

from apps.marketdata.providers.Crypto.CoinGecko.dto.simple_price import (
    ListSimplePricesEntry,
    SimplePriceEntry,
    parse_list_simple_price,
)
from apps.marketdata.providers.Crypto.CoinGecko.dto.simpl_token_price import (
    SimpleTokenPriceEntry,
    SimpleTokenPricesList,
    parse_simple_token_prices,
)
from apps.marketdata.providers.Crypto.CoinGecko.dto.supported_vs_currencies import (
    SupportedVSCurrencies,
    parse_supported_vs_currencies,
)
from apps.marketdata.providers.Crypto.CoinGecko.dto.coins_list import (
    Coin,
    CoinsList,
    parse_coins_list,
)
from apps.marketdata.providers.Crypto.CoinGecko.dto.coins_markets import (
    CoinsMarket,
    Coin as CoinMarket,
    parse_coins_markets,
)
from apps.marketdata.providers.Crypto.CoinGecko.dto.coin_history import (
    CoinHistory,
    parse_coin_history,
)
from apps.marketdata.providers.Crypto.CoinGecko.dto.exchanges import (
    Exchanges,
    Exchange,
    parse_exchanges,
)
from apps.marketdata.providers.Crypto.CoinGecko.dto.exchanges_list import (
    ExchangesList,
    Exchange as ExchangeListItem,
    parse_exchanges_list,
)
from apps.marketdata.providers.Crypto.CoinGecko.dto.exchange_rates import (
    ExchangeRates,
    ExchangeRate as Rate,
    parse_exchange_rates,
)
from apps.marketdata.providers.Crypto.CoinGecko.dto.exchange_volume_chart import (
    ExchangeVolumeChart as ExchangeVolumeChartData,
    ExchangeVolumePoint,
    parse_exchange_volume_chart,
)
from apps.marketdata.providers.Crypto.CoinGecko.dto.global_data import (
    GlobalData,
    parse_global as parse_global_data,
)
from apps.marketdata.providers.Crypto.CoinGecko.dto.global_defi import (
    GlobalDefiData,
    parse_global_defi_data,
)
from apps.marketdata.providers.Crypto.CoinGecko.dto.search import (
    SearchResult,
    parse_search_result,
)
from apps.marketdata.providers.Crypto.CoinGecko.dto.search_trending import (
    SearchTrendingResult,
    parse_search_trending,
)
from apps.marketdata.providers.Crypto.CoinGecko.dto.ping import (
    Ping,
    parser_ping,
)


class RedisJsonBaseTests(SimpleTestCase):
    """
    Базовые sanity-чек тесты самого RedisJSON — чтобы убедиться,
    что to_redis_value / from_redis_value работают как договаривались.
    """

    class DummyDto(RedisJSON):
        value: int

    def test_from_redis_none_returns_none(self):
        self.assertIsNone(self.DummyDto.from_redis_value(None))

    def test_from_redis_dict(self):
        raw = {"value": 42}
        dto = self.DummyDto.from_redis_value(raw)
        self.assertIsInstance(dto, self.DummyDto)
        self.assertEqual(dto.value, 42)

    def test_from_redis_json_string(self):
        raw = json.dumps({"value": 7})
        dto = self.DummyDto.from_redis_value(raw)
        self.assertIsInstance(dto, self.DummyDto)
        self.assertEqual(dto.value, 7)

    def test_from_redis_bytes(self):
        raw = json.dumps({"value": 13}).encode("utf-8")
        dto = self.DummyDto.from_redis_value(raw)
        self.assertIsInstance(dto, self.DummyDto)
        self.assertEqual(dto.value, 13)

    def test_from_redis_invalid_type_raises(self):
        with self.assertRaises(TypeError):
            self.DummyDto.from_redis_value(123)  # type: ignore[arg-type]


class SimplePriceDtoTests(SimpleTestCase):
    def test_parse_list_simple_price(self):
        ts = 1_700_000_000
        raw = {
            "bitcoin": {"usd": 123.45, "last_updated_at": ts},
            "ethereum": {"usd": "200.01"},
        }

        dto = parse_list_simple_price(raw, vs_currency="usd")

        self.assertIsInstance(dto, ListSimplePricesEntry)
        self.assertEqual(dto.vs_currency, "usd")
        self.assertEqual(len(dto.prices), 2)

        btc = dto.prices[0]
        self.assertEqual(btc.id, "bitcoin")
        self.assertEqual(btc.vs_currency, "usd")
        self.assertEqual(btc.price, Decimal("123.45"))
        self.assertIsInstance(btc.last_updated_at, datetime)
        self.assertEqual(int(btc.last_updated_at.timestamp()), ts)

    def test_list_simple_prices_entry_redis_roundtrip(self):
        entry = SimplePriceEntry(
            id="bitcoin",
            vs_currency="usd",
            price=Decimal("1.23"),
            last_updated_at=datetime.fromtimestamp(1_700_000_000),
        )
        dto = ListSimplePricesEntry(prices=[entry], vs_currency="usd")

        dumped = dto.to_redis_value()
        self.assertIsInstance(dumped, str)

        restored = ListSimplePricesEntry.from_redis_value(dumped)
        self.assertIsInstance(restored, ListSimplePricesEntry)
        self.assertEqual(restored.vs_currency, "usd")
        self.assertEqual(len(restored.prices), 1)
        self.assertEqual(restored.prices[0].price, Decimal("1.23"))


class SimpleTokenPriceDtoTests(SimpleTestCase):
    def test_parse_simple_token_prices(self):
        raw = {
            "0xToken": {
                "usd": 1.23,
                "usd_market_cap": 1000.0,
                "usd_24h_vol": 50.0,
                "usd_24h_change": -0.5,
                "last_updated_at": 1_700_000_100,
            }
        }

        dto = parse_simple_token_prices(raw, vs_currency="usd")

        self.assertIsInstance(dto, SimpleTokenPricesList)
        self.assertEqual(dto.vs_currency, "usd")
        self.assertEqual(len(dto.prices), 1)

        token = dto.prices[0]
        self.assertEqual(token.id, "0xToken")
        self.assertEqual(token.vs_currency, "usd")
        self.assertEqual(token.price, Decimal("1.23"))

    def test_simple_token_prices_redis_roundtrip(self):
        entry = SimpleTokenPriceEntry(
            id="0xToken",
            vs_currency="usd",
            price=Decimal("1.23"),
            last_updated_at=datetime.fromtimestamp(1_700_000_000),
        )
        dto = SimpleTokenPricesList(prices=[entry], vs_currency="usd")

        dumped = dto.to_redis_value()
        restored = SimpleTokenPricesList.from_redis_value(dumped)

        self.assertIsInstance(restored, SimpleTokenPricesList)
        self.assertEqual(restored.vs_currency, "usd")
        self.assertEqual(len(restored.prices), 1)
        self.assertEqual(restored.prices[0].id, "0xToken")


class SupportedVsCurrenciesDtoTests(SimpleTestCase):
    def test_parse_supported_vs_currencies_normalizes_and_sorts(self):
        raw = ["USD", "btc", "Eth", 123, None]
        dto = parse_supported_vs_currencies(raw)

        self.assertIsInstance(dto, SupportedVSCurrencies)
        # ожидаем нормализацию в lower + фильтр мусора + сортировка
        self.assertEqual(dto.vs_currencies, ["btc", "eth", "usd"])

    def test_supported_vs_currencies_redis_roundtrip(self):
        dto = SupportedVSCurrencies(vs_currencies=["usd", "eur"])

        dumped = dto.to_redis_value()
        restored = SupportedVSCurrencies.from_redis_value(dumped)

        self.assertIsInstance(restored, SupportedVSCurrencies)
        self.assertEqual(restored.vs_currencies, ["usd", "eur"])

        # dict → from_redis_value
        restored2 = SupportedVSCurrencies.from_redis_value(
            {"vs_currencies": ["usd", "eur"]}
        )
        self.assertEqual(restored2.vs_currencies, ["usd", "eur"])

        # bytes → from_redis_value
        restored3 = SupportedVSCurrencies.from_redis_value(dumped.encode("utf-8"))
        self.assertEqual(restored3.vs_currencies, ["usd", "eur"])


class CoinsListDtoTests(SimpleTestCase):
    def test_parse_coins_list(self):
        raw = [
            {
                "id": "bitcoin",
                "symbol": "btc",
                "name": "Bitcoin",
                "platforms": {"ethereum": "0x123", "bad": 123},
            }
        ]
        dto = parse_coins_list(raw)

        self.assertIsInstance(dto, CoinsList)
        self.assertEqual(len(dto.coins), 1)

        coin = dto.coins[0]
        self.assertIsInstance(coin, Coin)
        self.assertEqual(coin.id, "bitcoin")
        self.assertEqual(coin.symbol, "btc")
        self.assertEqual(coin.name, "Bitcoin")
        self.assertEqual(coin.platforms, {"ethereum": "0x123"})

    def test_coins_list_redis_roundtrip(self):
        dto = CoinsList(
            coins=[
                Coin(
                    id="bitcoin",
                    symbol="btc",
                    name="Bitcoin",
                    platforms={"ethereum": "0x123"},
                )
            ]
        )

        dumped = dto.to_redis_value()
        restored = CoinsList.from_redis_value(dumped)

        self.assertIsInstance(restored, CoinsList)
        self.assertEqual(len(restored.coins), 1)
        self.assertEqual(restored.coins[0].id, "bitcoin")


class CoinsMarketsDtoTests(SimpleTestCase):
    def test_parse_coins_markets_basic(self):
        raw = [
            {
                "id": "bitcoin",
                "symbol": "btc",
                "name": "Bitcoin",
                "current_price": 100.5,
                "market_cap": 1_000_000,
                "total_volume": 50_000,
                "ath": 200.0,
                "atl": 10.0,
                "last_updated": "2024-01-01T12:00:00Z",
            }
        ]

        dto = parse_coins_markets(raw, vs_currency="usd")

        self.assertIsInstance(dto, CoinsMarket)
        self.assertEqual(dto.vs_currency, "usd")
        self.assertEqual(len(dto.coins), 1)

        coin = dto.coins[0]
        self.assertIsInstance(coin, CoinMarket)
        self.assertEqual(coin.id, "bitcoin")
        self.assertEqual(coin.symbol, "btc")
        self.assertEqual(coin.current_price, Decimal("100.5"))

    def test_coins_markets_redis_roundtrip(self):
        market_coin = CoinMarket(
            id="bitcoin",
            symbol="btc",
            name="Bitcoin",
            current_price=Decimal("100.5"),
            market_cap=Decimal("1000000"),
            total_volume=Decimal("50000"),
        )
        dto = CoinsMarket(coins=[market_coin], vs_currency="usd")

        dumped = dto.to_redis_value()
        restored = CoinsMarket.from_redis_value(dumped)

        self.assertIsInstance(restored, CoinsMarket)
        self.assertEqual(restored.vs_currency, "usd")
        self.assertEqual(len(restored.coins), 1)
        self.assertEqual(restored.coins[0].id, "bitcoin")


class CoinHistoryDtoTests(SimpleTestCase):
    def test_parse_coin_history(self):
        raw: Dict[str, Any] = {
            "market_data": {
                "current_price": {"usd": 100.0},
                "market_cap": {"usd": 1_000_000},
                "total_volume": {"usd": 50_000},
            },
            "id": "bitcoin",
            "symbol": "btc",
            "name": "Bitcoin",
        }

        dto = parse_coin_history(raw)

        self.assertIsInstance(dto, CoinHistory)
        self.assertEqual(dto.id, "bitcoin")
        self.assertEqual(dto.symbol, "btc")
        self.assertEqual(dto.current_price_usd, Decimal("100.0"))


class ExchangesDtoTests(SimpleTestCase):
    def test_parse_exchanges_basic(self):
        raw = [
            {
                "id": "binance",
                "name": "Binance",
                "year_established": 2017,
                "country": "Cayman Islands",
                "url": "https://www.binance.com/",
            }
        ]

        dto = parse_exchanges(raw)

        self.assertIsInstance(dto, Exchanges)
        self.assertEqual(len(dto.exchanges), 1)

        ex = dto.exchanges[0]
        self.assertIsInstance(ex, Exchange)
        self.assertEqual(ex.id, "binance")
        self.assertEqual(ex.name, "Binance")
        self.assertEqual(ex.country, "Cayman Islands")

    def test_exchanges_redis_roundtrip(self):
        ex = Exchange(id="binance", name="Binance")
        dto = Exchanges(exchanges=[ex])

        dumped = dto.to_redis_value()
        restored = Exchanges.from_redis_value(dumped)

        self.assertIsInstance(restored, Exchanges)
        self.assertEqual(len(restored.exchanges), 1)
        self.assertEqual(restored.exchanges[0].id, "binance")


class ExchangesListDtoTests(SimpleTestCase):
    def test_parse_exchanges_list_basic(self):
        raw = [
            {
                "id": "binance",
                "name": "Binance",
            }
        ]

        dto = parse_exchanges_list(raw)

        self.assertIsInstance(dto, ExchangesList)
        self.assertEqual(len(dto.exchanges), 1)

        ex = dto.exchanges[0]
        self.assertIsInstance(ex, ExchangeListItem)
        self.assertEqual(ex.id, "binance")
        self.assertEqual(ex.name, "Binance")

    def test_exchanges_list_redis_roundtrip(self):
        ex = ExchangeListItem(id="binance", name="Binance")
        dto = ExchangesList(exchanges=[ex])

        dumped = dto.to_redis_value()
        restored = ExchangesList.from_redis_value(dumped)

        self.assertIsInstance(restored, ExchangesList)
        self.assertEqual(len(restored.exchanges), 1)
        self.assertEqual(restored.exchanges[0].id, "binance")


class ExchangeRatesDtoTests(SimpleTestCase):
    def test_parse_exchange_rates(self):
        raw = {
            "rates": {
                "btc": {"name": "Bitcoin", "unit": "BTC", "value": 1.0, "type": "crypto"},
                "usd": {
                    "name": "US Dollar",
                    "unit": "USD",
                    "value": "36000",
                    "type": "fiat",
                },
                "bad": "ignore_me",
            }
        }

        dto = parse_exchange_rates(raw)

        self.assertIsInstance(dto, ExchangeRates)
        self.assertIn("btc", dto.exchange_rates)
        self.assertIn("usd", dto.exchange_rates)
        self.assertNotIn("bad", dto.exchange_rates)

        btc_rate = dto.exchange_rates["btc"]
        self.assertIsInstance(btc_rate, Rate)
        self.assertEqual(btc_rate.unit, "BTC")
        self.assertEqual(btc_rate.value, Decimal("1"))

    def test_exchange_rates_redis_roundtrip(self):
        dto = ExchangeRates(
            exchange_rates={
                "btc": Rate(name="Bitcoin", unit="BTC", value=Decimal("1"), type="crypto")
            }
        )

        dumped = dto.to_redis_value()
        restored = ExchangeRates.from_redis_value(dumped)

        self.assertIsInstance(restored, ExchangeRates)
        self.assertIn("btc", restored.exchange_rates)
        self.assertEqual(restored.exchange_rates["btc"].value, Decimal("1"))


class ExchangeVolumeChartDtoTests(SimpleTestCase):
    def test_parse_exchange_volume_chart(self):
        raw = [
            [1_700_000_000, 123.45],
            [1_700_000_100, "200.00"],
        ]

        dto = parse_exchange_volume_chart(raw)

        self.assertIsInstance(dto, ExchangeVolumeChartData)
        self.assertEqual(len(dto.points), 2)

        p0 = dto.points[0]
        self.assertIsInstance(p0, ExchangeVolumePoint)
        self.assertEqual(p0.timestamp, 1_700_000_000)
        self.assertEqual(p0.volume, Decimal("123.45"))


class GlobalDataDtoTests(SimpleTestCase):
    def test_parse_global_data(self):
        raw = {
            "data": {
                "active_cryptocurrencies": 100,
                "upcoming_icos": 2,
                "ongoing_icos": 3,
                "ended_icos": 4,
                "markets": 12,
                "total_market_cap": {"usd": 100.1},
                "total_volume": {"usd": 3.3},
                "market_cap_percentage": {"btc": 50.0, "eth": 20.0},
                "market_cap_change_percentage_24h_usd": 1.23,
                "updated_at": 1_763_208_398,
            }
        }

        dto = parse_global_data(raw)

        self.assertIsInstance(dto, GlobalData)
        self.assertEqual(dto.active_cryptocurrencies, 100)
        self.assertEqual(dto.markets, 12)
        self.assertIn("usd", dto.total_market_cap)
        self.assertEqual(dto.total_market_cap["usd"], Decimal("100.1"))

    def test_global_data_redis_roundtrip(self):
        dto = GlobalData(
            active_cryptocurrencies=1,
            upcoming_icos=2,
            ongoing_icos=3,
            ended_icos=4,
            markets=5,
            total_market_cap={"usd": Decimal("1")},
            total_volume={"usd": Decimal("2")},
            market_cap_percentage={"btc": 50.0},
            market_cap_change_percentage_24h_usd=1.23,
            updated_at=1_700_000_000,
        )

        dumped = dto.to_redis_value()
        restored = GlobalData.from_redis_value(dumped)

        self.assertIsInstance(restored, GlobalData)
        self.assertEqual(restored.active_cryptocurrencies, 1)
        self.assertEqual(restored.total_volume["usd"], Decimal("2"))


class GlobalDefiDtoTests(SimpleTestCase):
    def test_parse_global_defi_data(self):
        raw = {
            "data": {
                "defi_market_cap": "1000000",
                "eth_market_data": "500000",
                "defi_to_eth_ratio": "2.0",
                "trading_volume_24h": "12345",
                "defi_dominance": "10%",
                "top_coin_name": "Uniswap",
                "top_coin_defi_dominance": "25.5",
            }
        }

        dto = parse_global_defi_data(raw)

        self.assertIsInstance(dto, GlobalDefiData)
        self.assertEqual(dto.defi_market_cap, "1000000")
        self.assertEqual(dto.top_coin_name, "Uniswap")

    def test_global_defi_redis_roundtrip(self):
        dto = GlobalDefiData(
            defi_market_cap="1",
            eth_market_data="2",
            defi_to_eth_ratio="0.5",
            trading_volume_24h="10",
            defi_dominance="5%",
            top_coin_name="Uniswap",
            top_coin_defi_dominance=Decimal("25.5"),
        )

        dumped = dto.to_redis_value()
        restored = GlobalDefiData.from_redis_value(dumped)

        self.assertIsInstance(restored, GlobalDefiData)
        self.assertEqual(restored.top_coin_name, "Uniswap")
        self.assertEqual(restored.top_coin_defi_dominance, Decimal("25.5"))


class SearchDtoTests(SimpleTestCase):
    def test_parse_search_result(self):
        raw = {
            "coins": [
                {
                    "id": "bitcoin",
                    "name": "Bitcoin",
                    "api_symbol": "bitcoin",
                    "symbol": "BTC",
                    "market_cap_rank": 1,
                }
            ],
            "exchanges": [
                {
                    "id": "binance",
                    "name": "Binance",
                    "market_type": "spot",
                }
            ],
            "icos": [{"id": "ico1", "name": "ICO 1", "symbol": "ICO"}],
            "categories": [{"id": "defi", "name": "DeFi"}],
            "nfts": [{"id": "nft1", "name": "Cool NFT", "symbol": "NFT"}],
        }

        dto = parse_search_result(raw)

        self.assertIsInstance(dto, SearchResult)
        self.assertEqual(len(dto.coins), 1)
        self.assertEqual(dto.coins[0].id, "bitcoin")
        self.assertEqual(dto.exchanges[0].id, "binance")
        self.assertEqual(dto.categories[0].name, "DeFi")

    def test_search_result_redis_roundtrip(self):
        dto = SearchResult(
            coins=[],
            exchanges=[],
            icos=[],
            categories=[],
            nfts=[],
        )

        dumped = dto.to_redis_value()
        restored = SearchResult.from_redis_value(dumped)

        self.assertIsInstance(restored, SearchResult)
        self.assertEqual(len(restored.coins), 0)
        self.assertEqual(len(restored.nfts), 0)


class SearchTrendingDtoTests(SimpleTestCase):
    def test_parse_search_trending(self):
        raw = {
            "coins": [
                {
                    "item": {
                        "id": "zcash",
                        "coin_id": 486,
                        "name": "Zcash",
                        "symbol": "ZEC",
                        "market_cap_rank": 17,
                        "thumb": "thumb.png",
                        "small": "small.png",
                        "large": "large.png",
                        "slug": "zcash",
                        "price_btc": "0.0069",
                        "score": 0,
                        "data": {
                            "price": 665.6136,
                            "market_cap": 1000000.0,
                            "market_cap_rank": 23,
                            "24h_volume": "12345",
                            "price_change_percentage_24h": {"usd": 1.23},
                        },
                    }
                }
            ],
            "categories": [
                {
                    "name": "DeFi",
                    "market_cap": 1234.56,
                    "market_cap_change_24h": 1.0,
                    "top_3_coins": ["uniswap", "aave", "curve"],
                }
            ],
        }

        dto = parse_search_trending(raw)

        self.assertIsInstance(dto, SearchTrendingResult)
        self.assertEqual(len(dto.coins), 1)
        coin = dto.coins[0]
        self.assertEqual(coin.id, "zcash")
        self.assertEqual(coin.coin_id, 486)
        self.assertEqual(coin.symbol, "ZEC")

        self.assertEqual(len(dto.categories), 1)
        cat = dto.categories[0]
        self.assertEqual(cat.name, "DeFi")
        self.assertEqual(cat.top_3_coins[0], "uniswap")

    def test_search_trending_redis_roundtrip(self):
        dto = SearchTrendingResult(coins=[], categories=[])

        dumped = dto.to_redis_value()
        restored = SearchTrendingResult.from_redis_value(dumped)

        self.assertIsInstance(restored, SearchTrendingResult)
        self.assertEqual(len(restored.coins), 0)
        self.assertEqual(len(restored.categories), 0)


class PingDtoTests(SimpleTestCase):
    def test_parser_ping_direct(self):
        raw = {"gecko_says": "(meow)"}
        dto = asyncio.run(parser_ping(raw))

        self.assertIsInstance(dto, Ping)
        self.assertEqual(dto.gecko_says, "(meow)")

    def test_parser_ping_nested_status(self):
        raw = {"status": {"gecko_says": "pong"}}
        dto = asyncio.run(parser_ping(raw))

        self.assertIsInstance(dto, Ping)
        self.assertEqual(dto.gecko_says, "pong")

    def test_parser_ping_invalid_returns_none(self):
        raw = {"foo": "bar"}
        dto = asyncio.run(parser_ping(raw))

        self.assertIsNone(dto)


class RedisJsonRoundtripSmokeTests(SimpleTestCase):
    """
    Дополнительный «дымовый» тест — проверяем, что несколько ключевых DTO
    нормально проходят round-trip через RedisJSON (to_redis_value / from_redis_value)
    с вложенными структурами и Decimal/datetime.
    """

    def _assert_roundtrip(self, dto: RedisJSON):
        dumped = dto.to_redis_value()
        restored = type(dto).from_redis_value(dumped)
        self.assertEqual(asdict(dto), asdict(restored))

    def test_roundtrip_search_result_struct(self):
        dto = SearchResult(
            coins=[],
            exchanges=[],
            icos=[],
            categories=[],
            nfts=[],
        )
        self._assert_roundtrip(dto)

    def test_roundtrip_list_simple_prices(self):
        dto = ListSimplePricesEntry(
            prices=[
                SimplePriceEntry(
                    id="bitcoin",
                    vs_currency="usd",
                    price=Decimal("1.0"),
                    last_updated_at=datetime.fromtimestamp(1_700_000_000),
                )
            ],
            vs_currency="usd",
        )
        self._assert_roundtrip(dto)

    def test_roundtrip_global_data(self):
        dto = GlobalData(
            active_cryptocurrencies=1,
            upcoming_icos=0,
            ongoing_icos=0,
            ended_icos=0,
            markets=1,
            total_market_cap={"usd": Decimal("1")},
            total_volume={"usd": Decimal("2")},
            market_cap_percentage={"btc": 50.0},
            market_cap_change_percentage_24h_usd=1.0,
            updated_at=1_700_000_000,
        )
        self._assert_roundtrip(dto)
