from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, date
from decimal import Decimal
from typing import Any, Dict

from django.test import SimpleTestCase

from apps.marketdata.providers.Crypto.CoinGecko.redis_json import RedisJSON

from apps.marketdata.providers.Crypto.CoinGecko.dto.simple_price import (
    ListSimplePricesEntry,
    SimplePriceEntry,
    parse_list_simple_price,
)
from apps.marketdata.providers.Crypto.CoinGecko.dto.simple_token_price import (
    SimpleTokenPricesList,
    SimpleTokenPriceEntry,
    parse_simple_token_prices,
)
from apps.marketdata.providers.Crypto.CoinGecko.dto.supported_vs_currencies import (
    SupportedVSCurrencies,
    parse_supported_vs_currencies,
)
from apps.marketdata.providers.Crypto.CoinGecko.dto.coins_list import (
    Coin as CoinsListItem,
    CoinsList,
    parse_coins_list,
)
from apps.marketdata.providers.Crypto.CoinGecko.dto.exchange_rates import (
    ExchangeRate,
    ExchangeRateType,
    ExchangeRates,
    parse_exchange_rates,
)
from apps.marketdata.providers.Crypto.CoinGecko.dto.coin_history import (
    CoinHistory,
    CoinHistoryMarketData,
    parse_coin_history,
)
from apps.marketdata.providers.Crypto.CoinGecko.dto.exchanges import (
    Exchange,
    Exchanges,
    parse_exchanges,
)
from apps.marketdata.providers.Crypto.CoinGecko.dto.exchanges_list import (
    ExchangeListItem,
    ExchangesList,
    parse_exchanges_list,
)
from apps.marketdata.providers.Crypto.CoinGecko.dto.global_data import (
    GlobalData,
    GlobalMarketCapEntry,
    GlobalVolumeEntry,
    GlobalMarketCapPercentageEntry,
    parse_global_data,
)
from apps.marketdata.providers.Crypto.CoinGecko.dto.search_trending import (
    SearchTrendingResult,
    parse_search_trending,
)


# =============================================================================
#  RedisJSON — базовое поведение
# =============================================================================


class RedisJsonBaseTests(SimpleTestCase):
    @dataclass
    class DummyDto(RedisJSON):
        value: int

    def test_to_redis_and_back(self) -> None:
        dto = self.DummyDto(value=42)
        dumped = dto.to_redis_value()
        self.assertIsInstance(dumped, str)

        restored = self.DummyDto.from_redis_value(dumped)
        self.assertIsInstance(restored, self.DummyDto)
        self.assertEqual(restored.value, 42)

    def test_from_redis_none(self) -> None:
        self.assertIsNone(self.DummyDto.from_redis_value(None))

    def test_from_redis_dict(self) -> None:
        restored = self.DummyDto.from_redis_value({"value": 10})
        self.assertEqual(restored.value, 10)

    def test_from_redis_json_string(self) -> None:
        restored = self.DummyDto.from_redis_value('{"value": 7}')
        self.assertEqual(restored.value, 7)

    def test_from_redis_bytes(self) -> None:
        restored = self.DummyDto.from_redis_value(b'{"value": 5}')
        self.assertEqual(restored.value, 5)

    def test_from_redis_invalid_type_raises(self) -> None:
        with self.assertRaises(TypeError):
            self.DummyDto.from_redis_value(123)  # type: ignore[arg-type]


# =============================================================================
#  /simple/price
# =============================================================================


class SimplePriceDtoTests(SimpleTestCase):
    def test_parse_list_simple_price(self) -> None:
        ts = 1_700_000_000
        raw: Dict[str, Dict[str, Any]] = {
            "bitcoin": {
                "usd": 123.45,
                "last_updated_at": ts,
            }
        }

        dto = parse_list_simple_price(raw)

        self.assertIsInstance(dto, ListSimplePricesEntry)
        self.assertEqual(len(dto.simple_prices), 1)

        btc = dto.simple_prices[0]
        self.assertIsInstance(btc, SimplePriceEntry)
        self.assertEqual(btc.coin_id, "bitcoin")
        self.assertEqual(btc.vs_currency, "usd")
        self.assertAlmostEqual(btc.price, 123.45)
        self.assertEqual(btc.last_updated_at, ts)

    def test_list_simple_prices_entry_redis_roundtrip(self) -> None:
        dto = ListSimplePricesEntry(
            simple_prices=[
                SimplePriceEntry(
                    coin_id="bitcoin",
                    vs_currency="usd",
                    price=123.45,
                    market_cap=1000.0,
                    vol_24h=50.0,
                    change_24h=-1.23,
                    last_updated_at=1_700_000_000,
                )
            ]
        )

        dumped = dto.to_redis_value()
        restored = ListSimplePricesEntry.from_redis_value(dumped)

        self.assertIsInstance(restored, ListSimplePricesEntry)
        self.assertEqual(asdict(dto), asdict(restored))


# =============================================================================
#  /simple/token_price
# =============================================================================


class SimpleTokenPriceDtoTests(SimpleTestCase):
    def test_parse_simple_token_prices(self) -> None:
        ts = 1_700_000_000
        raw: Dict[str, Dict[str, Any]] = {
            "0xToken": {
                "usd": 1.5,
                "last_updated_at": ts,
            }
        }

        dto = parse_simple_token_prices(raw)

        self.assertIsInstance(dto, SimpleTokenPricesList)
        self.assertEqual(len(dto.simple_token_prices), 1)

        entry = dto.simple_token_prices[0]
        self.assertIsInstance(entry, SimpleTokenPriceEntry)
        self.assertEqual(entry.contract_address, "0xToken")
        self.assertEqual(entry.vs_currency, "usd")
        self.assertAlmostEqual(entry.price, 1.5)
        self.assertEqual(entry.last_updated_at, ts)

    def test_simple_token_prices_redis_roundtrip(self) -> None:
        dto = SimpleTokenPricesList(
            simple_token_prices=[
                SimpleTokenPriceEntry(
                    contract_address="0xToken",
                    vs_currency="usd",
                    price=2.0,
                    market_cap=None,
                    vol_24h=None,
                    change_24h=None,
                    last_updated_at=1_700_000_000,
                )
            ]
        )

        dumped = dto.to_redis_value()
        restored = SimpleTokenPricesList.from_redis_value(dumped)

        self.assertIsInstance(restored, SimpleTokenPricesList)
        self.assertEqual(asdict(dto), asdict(restored))


# =============================================================================
#  /simple/supported_vs_currencies
# =============================================================================


class SupportedVsCurrenciesDtoTests(SimpleTestCase):
    def test_parse_supported_vs_currencies_normalizes(self) -> None:
        raw = ["USD", "btc", "Eth", 123, None]

        dto = parse_supported_vs_currencies(raw)

        self.assertIsInstance(dto, SupportedVSCurrencies)
        # порядок: как пришли, но нормализованные
        self.assertEqual(dto.currencies, ["usd", "btc", "eth"])

    def test_supported_vs_currencies_redis_roundtrip(self) -> None:
        dto = SupportedVSCurrencies(currencies=["usd", "eur"])

        dumped = dto.to_redis_value()
        restored = SupportedVSCurrencies.from_redis_value(dumped)

        self.assertIsInstance(restored, SupportedVSCurrencies)
        self.assertEqual(dto.currencies, restored.currencies)


# =============================================================================
#  /coins/list
# =============================================================================


class CoinsListDtoTests(SimpleTestCase):
    def test_parse_coins_list(self) -> None:
        raw = [
            {"id": "bitcoin", "symbol": "btc", "name": "Bitcoin"},
        ]

        dto = parse_coins_list(raw)

        self.assertIsInstance(dto, CoinsList)
        self.assertEqual(len(dto.coins_list), 1)

        coin = dto.coins_list[0]
        self.assertIsInstance(coin, CoinsListItem)
        self.assertEqual(coin.id, "bitcoin")
        self.assertEqual(coin.symbol, "btc")
        self.assertEqual(coin.name, "Bitcoin")

    def test_coins_list_redis_roundtrip(self) -> None:
        dto = CoinsList(
            coins_list=[
                CoinsListItem(id="bitcoin", symbol="btc", name="Bitcoin"),
                CoinsListItem(id="ethereum", symbol="eth", name="Ethereum"),
            ]
        )

        dumped = dto.to_redis_value()
        restored = CoinsList.from_redis_value(dumped)

        self.assertIsInstance(restored, CoinsList)
        self.assertEqual(asdict(dto), asdict(restored))


# =============================================================================
#  /exchange_rates
# =============================================================================


class ExchangeRatesDtoTests(SimpleTestCase):
    def test_parse_exchange_rates(self) -> None:
        raw = {
            "base": "btc",
            "rates": {
                "btc": {
                    "name": "Bitcoin",
                    "unit": "BTC",
                    "value": 1.0,
                    "type": "crypto",
                }
            },
        }

        dto = parse_exchange_rates(raw)

        self.assertIsInstance(dto, ExchangeRates)
        self.assertEqual(dto.base, "btc")

        # в разных версиях DTO поле может называться exchange_rates или rates
        rates_list = getattr(dto, "exchange_rates", None)
        if rates_list is None:
            rates_list = getattr(dto, "rates", None)
        self.assertIsNotNone(rates_list)

        rate = rates_list[0]
        self.assertIsInstance(rate, ExchangeRate)
        self.assertEqual(rate.code, "btc")
        self.assertEqual(rate.name, "Bitcoin")
        self.assertEqual(rate.unit, "BTC")
        self.assertAlmostEqual(rate.value, 1.0)

    def test_exchange_rates_redis_roundtrip(self) -> None:
        dto = ExchangeRates(
            base="btc",
            exchange_rates=[
                ExchangeRate(
                    code="btc",
                    name="Bitcoin",
                    unit="BTC",
                    value=1.0,
                    type=ExchangeRateType.CRYPTO,
                )
            ],
        )

        dumped = dto.to_redis_value()
        restored = ExchangeRates.from_redis_value(dumped)

        self.assertIsInstance(restored, ExchangeRates)
        self.assertEqual(asdict(dto), asdict(restored))


# =============================================================================
#  /coins/{id}/history
# =============================================================================


class CoinHistoryDtoTests(SimpleTestCase):
    def test_parse_coin_history(self) -> None:
        raw = {
            "id": "bitcoin",
            "symbol": "btc",
            "name": "Bitcoin",
            "market_data": {
                "current_price": {"usd": 100.0},
                "market_cap": {"usd": 1000.0},
                "total_volume": {"usd": 10.0},
            },
        }

        dto = parse_coin_history(raw)

        self.assertIsInstance(dto, CoinHistory)
        self.assertEqual(dto.id, "bitcoin")
        self.assertEqual(dto.symbol, "btc")

        self.assertIsInstance(dto.current_price, CoinHistoryMarketData)
        self.assertEqual(dto.current_price.usd, Decimal("100.0"))


# =============================================================================
#  /exchanges
# =============================================================================


class ExchangesDtoTests(SimpleTestCase):
    def test_parse_exchanges_basic(self) -> None:
        raw = [
            {
                "id": "binance",
                "name": "Binance",
                "year_established": 2017,
                "country": "Cayman Islands",
                "description": "",
                "url": "https://www.binance.com/",
                "image": "https://img",
                "has_trading_incentive": False,
                "trust_score": 10,
                "trust_score_rank": 1,
                "trade_volume_24h_btc": 1000.0,
            }
        ]

        dto = parse_exchanges(raw)

        self.assertIsInstance(dto, Exchanges)
        self.assertEqual(len(dto.exchanges), 1)

        ex = dto.exchanges[0]
        self.assertIsInstance(ex, Exchange)
        self.assertEqual(ex.id, "binance")
        self.assertEqual(ex.name, "Binance")

    def test_exchanges_redis_roundtrip(self) -> None:
        dto = Exchanges(
            exchanges=[
                Exchange(
                    id="binance",
                    name="Binance",
                    year_established=2017,
                    country="Cayman Islands",
                    description="",
                    url="https://www.binance.com/",
                    image="https://img",
                    has_trading_incentive=False,
                    trust_score=10,
                    trust_score_rank=1,
                    trade_volume_24h_btc=1000.0,
                )
            ]
        )

        dumped = dto.to_redis_value()
        restored = Exchanges.from_redis_value(dumped)

        self.assertIsInstance(restored, Exchanges)
        self.assertEqual(asdict(dto), asdict(restored))


# =============================================================================
#  /exchanges/list
# =============================================================================


class ExchangesListDtoTests(SimpleTestCase):
    def test_parse_exchanges_list_basic(self) -> None:
        raw = [
            {"id": "binance", "name": "Binance"},
        ]

        dto = parse_exchanges_list(raw)

        self.assertIsInstance(dto, ExchangesList)
        self.assertEqual(len(dto.exchanges_list), 1)

        ex = dto.exchanges_list[0]
        self.assertIsInstance(ex, ExchangeListItem)
        self.assertEqual(ex.id, "binance")
        self.assertEqual(ex.name, "Binance")

    def test_exchanges_list_redis_roundtrip(self) -> None:
        dto = ExchangesList(
            exchanges_list=[
                ExchangeListItem(id="binance", name="Binance"),
                ExchangeListItem(id="okx", name="OKX"),
            ]
        )

        dumped = dto.to_redis_value()
        restored = ExchangesList.from_redis_value(dumped)

        self.assertIsInstance(restored, ExchangesList)
        self.assertEqual(asdict(dto), asdict(restored))


# =============================================================================
#  /global
# =============================================================================


class GlobalDataDtoTests(SimpleTestCase):
    def test_parse_global_data(self) -> None:
        raw = {
            "active_cryptocurrencies": 100,
            "upcoming_icos": 10,
            "ongoing_icos": 5,
            "ended_icos": 1,
            "markets": 200,
            "total_market_cap": {"usd": 100.1},
            "total_volume": {"usd": 10.5},
            "market_cap_percentage": {"btc": 50.0},
            "market_cap_change_percentage_24h_usd": 1.23,
            "updated_at": 1_700_000_000,
        }

        dto = parse_global_data(raw)

        self.assertIsInstance(dto, GlobalData)
        self.assertEqual(dto.active_cryptocurrencies, 100)

        self.assertTrue(
            any(e.currency == "usd" and e.value == 100.1 for e in dto.total_market_cap)
        )
        self.assertTrue(
            any(e.currency == "usd" and e.value == 10.5 for e in dto.total_volume)
        )
        self.assertTrue(
            any(
                e.currency == "btc" and e.value == 50.0
                for e in dto.market_cap_percentage
            )
        )

    def test_global_data_redis_roundtrip(self) -> None:
        dto = GlobalData(
            active_cryptocurrencies=100,
            upcoming_icos=10,
            ongoing_icos=5,
            ended_icos=1,
            markets=200,
            total_market_cap=[
                GlobalMarketCapEntry(currency="usd", value=100.1),
            ],
            total_volume=[
                GlobalVolumeEntry(currency="usd", value=10.5),
            ],
            market_cap_percentage=[
                GlobalMarketCapPercentageEntry(currency="btc", value=50.0),
            ],
            market_cap_change_percentage_24h_usd=1.23,
            updated_at=1_700_000_000,
        )

        dumped = dto.to_redis_value()
        restored = GlobalData.from_redis_value(dumped)

        self.assertIsInstance(restored, GlobalData)
        self.assertEqual(asdict(dto), asdict(restored))


# =============================================================================
#  /search/trending
# =============================================================================


class SearchTrendingDtoTests(SimpleTestCase):
    def test_parse_search_trending(self) -> None:
        raw = {
            "coins": [
                {
                    "item": {
                        "id": "zcash",
                        "coin_id": 486,
                        "name": "Zcash",
                        "symbol": "ZEC",
                        "market_cap_rank": 17,
                        "thumb": "https://thumb",
                        "small": "https://small",
                        "large": "https://large",
                        "slug": "zcash",
                        "price_btc": 0.0069,
                        "score": 0,
                    }
                }
            ],
            "nfts": [],
            "categories": [],
        }

        dto = parse_search_trending(raw)

        self.assertIsInstance(dto, SearchTrendingResult)
        self.assertGreaterEqual(len(dto.coins), 1)

    def test_search_trending_redis_roundtrip(self) -> None:
        dto = SearchTrendingResult(coins=[], categories=[], nfts=[])

        dumped = dto.to_redis_value()
        restored = SearchTrendingResult.from_redis_value(dumped)

        self.assertIsInstance(restored, SearchTrendingResult)
        self.assertEqual(asdict(dto), asdict(restored))


# =============================================================================
#  Дополнительный smoke-тест roundtrip для сложных DTO
# =============================================================================


class RedisJsonRoundtripSmokeTests(SimpleTestCase):
    def _assert_roundtrip(self, dto: RedisJSON) -> None:
        dumped = dto.to_redis_value()
        restored = type(dto).from_redis_value(dumped)
        self.assertEqual(asdict(dto), asdict(restored))

    def test_roundtrip_list_simple_prices(self) -> None:
        dto = ListSimplePricesEntry(
            simple_prices=[
                SimplePriceEntry(
                    coin_id="bitcoin",
                    vs_currency="usd",
                    price=123.45,
                    market_cap=1000.0,
                    vol_24h=50.0,
                    change_24h=-1.23,
                    last_updated_at=1_700_000_000,
                )
            ]
        )
        self._assert_roundtrip(dto)

    def test_roundtrip_global_data(self) -> None:
        dto = GlobalData(
            active_cryptocurrencies=100,
            upcoming_icos=10,
            ongoing_icos=5,
            ended_icos=1,
            markets=200,
            total_market_cap=[
                GlobalMarketCapEntry(currency="usd", value=100.1),
            ],
            total_volume=[
                GlobalVolumeEntry(currency="usd", value=10.5),
            ],
            market_cap_percentage=[
                GlobalMarketCapPercentageEntry(currency="btc", value=50.0),
            ],
            market_cap_change_percentage_24h_usd=1.23,
            updated_at=1_700_000_000,
        )
        self._assert_roundtrip(dto)
