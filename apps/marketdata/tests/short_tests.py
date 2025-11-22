from __future__ import annotations

import json
import enum
from dataclasses import dataclass
from datetime import datetime, date
from decimal import Decimal

from django.test import SimpleTestCase

from apps.marketdata.providers.Crypto.CoinGecko.redis_json import RedisJSON
from apps.marketdata.providers.Crypto.CoinGecko.dto.simple_price import (
    SimplePriceEntry,
    ListSimplePricesEntry,
)
from apps.marketdata.providers.Crypto.CoinGecko.dto.exchanges import (
    Exchange as ExchangeDTO,
    Exchanges,
)
from apps.marketdata.providers.Crypto.CoinGecko.dto.search_trending import (
    SearchTrendingResult,
    TrendingCoin,
    TrendingCoinItem,
    TrendingCoinData,
    TrendingNft,
    TrendingNftData,
    TrendingCategory,
    TrendingCategoryData,
    TrendingContent,
)


# =====================================================================
#  Вспомогательный DTO для проверки Decimal / datetime / Enum / list / dict
# =====================================================================

class Status(enum.Enum):
    ACTIVE = "active"
    DISABLED = "disabled"


@dataclass
class ComplexDTO(RedisJSON):
    amount: Decimal
    at: datetime
    day: date
    status: Status
    decimals_list: list[Decimal]
    decimals_map: dict[str, Decimal]


# =====================================================================
#  Core-тесты RedisJSON.from_redis_value / to_redis_value
# =====================================================================

class RedisJSONCoreTests(SimpleTestCase):
    """
    Тестируем базовое поведение миксина RedisJSON:
    - None -> None
    - dict / str / bytes -> dataclass
    - неправильный тип -> TypeError
    - сериализация Decimal / datetime / date / Enum / list / dict
    """

    def _sample_raw_dict(self) -> dict:
        # Это JSON, который мы ожидаем получить из Redis
        return {
            "amount": "123.45",
            "at": "2025-01-01T12:00:00",
            "day": "2025-01-02",
            "status": Status.ACTIVE.value,
            "decimals_list": ["1.0", "2.5"],
            "decimals_map": {"x": "0.1"},
        }

    def _assert_complex_dto(self, obj: ComplexDTO) -> None:
        self.assertIsInstance(obj, ComplexDTO)
        self.assertEqual(obj.amount, Decimal("123.45"))
        self.assertEqual(obj.at, datetime(2025, 1, 1, 12, 0, 0))
        self.assertEqual(obj.day, date(2025, 1, 2))
        self.assertEqual(obj.status, Status.ACTIVE)
        self.assertEqual(obj.decimals_list, [Decimal("1.0"), Decimal("2.5")])
        self.assertEqual(obj.decimals_map, {"x": Decimal("0.1")})

    def test_from_redis_value_none_returns_none(self):
        self.assertIsNone(ComplexDTO.from_redis_value(None))

    def test_from_redis_value_dict_builds_dataclass(self):
        raw = self._sample_raw_dict()
        obj = ComplexDTO.from_redis_value(raw)
        self._assert_complex_dto(obj)

    def test_from_redis_value_json_string_builds_dataclass(self):
        raw = self._sample_raw_dict()
        json_str = json.dumps(raw)
        obj = ComplexDTO.from_redis_value(json_str)
        self._assert_complex_dto(obj)

    def test_from_redis_value_bytes_builds_dataclass(self):
        raw = self._sample_raw_dict()
        json_bytes = json.dumps(raw).encode("utf-8")
        obj = ComplexDTO.from_redis_value(json_bytes)
        self._assert_complex_dto(obj)

    def test_from_redis_value_wrong_type_raises_type_error(self):
        # не dict / не JSON-строка с dict → TypeError
        with self.assertRaises(TypeError):
            ComplexDTO.from_redis_value([1, 2, 3])

    def test_to_redis_value_and_back_with_complex_types(self):
        obj = ComplexDTO(
            amount=Decimal("123.45"),
            at=datetime(2025, 1, 1, 12, 0, 0),
            day=date(2025, 1, 2),
            status=Status.ACTIVE,
            decimals_list=[Decimal("1.0"), Decimal("2.5")],
            decimals_map={"x": Decimal("0.1")},
        )

        json_str = obj.to_redis_value()
        self.assertIsInstance(json_str, str)

        data = json.loads(json_str)
        # Проверяем, как именно сериализуются специальные типы
        self.assertEqual(data["amount"], "123.45")                # Decimal → str
        self.assertEqual(data["at"], "2025-01-01T12:00:00")       # datetime → ISO
        self.assertEqual(data["day"], "2025-01-02")               # date → ISO
        self.assertEqual(data["status"], Status.ACTIVE.value)     # Enum → value
        self.assertEqual(data["decimals_list"], ["1.0", "2.5"])   # list[Decimal] → list[str]
        self.assertEqual(data["decimals_map"], {"x": "0.1"})      # dict[str, Decimal] → dict[str, str]

        restored = ComplexDTO.from_redis_value(json_str)
        # dataclass сравнивается по полям
        self.assertEqual(restored, obj)


# =====================================================================
#  Интеграционные тесты: реальные DTO + RedisJSON
# =====================================================================

class RedisJSONDtoIntegrationTests(SimpleTestCase):
    """
    Проверяем, что реальные DTO на базе RedisJSON:
    - корректно сериализуются в JSON,
    - корректно собираются из dict / JSON-строки,
    - сохраняют вложенные структуры.
    """

    def test_list_simple_prices_entry_roundtrip_and_from_dict(self):
        entry = SimplePriceEntry(
            coin_id="bitcoin",
            vs_currency="usd",
            price=42000.5,
            market_cap=1_000_000.0,
            vol_24h=500_000.0,
            change_24h=-1.5,
            last_updated_at=1700000000,
        )
        dto = ListSimplePricesEntry(simple_prices=[entry])

        # to_redis_value -> JSON-строка
        json_str = dto.to_redis_value()

        # восстановление из JSON-строки
        restored_from_str = ListSimplePricesEntry.from_redis_value(json_str)

        # восстановление из dict (как если бы RedisCacheService уже сделал json.loads)
        decoded = json.loads(json_str)
        restored_from_dict = ListSimplePricesEntry.from_redis_value(decoded)

        for restored in (restored_from_str, restored_from_dict):
            self.assertIsInstance(restored, ListSimplePricesEntry)
            self.assertEqual(len(restored.simple_prices), 1)

            item = restored.simple_prices[0]
            self.assertEqual(item.coin_id, "bitcoin")
            self.assertEqual(item.vs_currency, "usd")
            self.assertEqual(item.price, 42000.5)
            self.assertEqual(item.market_cap, 1_000_000.0)
            self.assertEqual(item.vol_24h, 500_000.0)
            self.assertEqual(item.change_24h, -1.5)
            self.assertEqual(item.last_updated_at, 1700000000)

    def test_exchanges_roundtrip(self):
        ex = ExchangeDTO(
            id="binance",
            name="Binance",
            year_established=2017,
            country="Cayman Islands",
            description="Major exchange",
            url="https://binance.com",
            image="https://example.com/logo.png",
            has_trading_incentive=True,
            trust_score=10,
            trust_score_rank=1,
            trade_volume_24h_btc=123456.789,
        )
        dto = Exchanges(exchanges=[ex])

        json_str = dto.to_redis_value()
        restored = Exchanges.from_redis_value(json_str)

        self.assertIsInstance(restored, Exchanges)
        self.assertEqual(len(restored.exchanges), 1)

        restored_ex = restored.exchanges[0]
        self.assertEqual(restored_ex.id, ex.id)
        self.assertEqual(restored_ex.name, ex.name)
        self.assertEqual(restored_ex.year_established, ex.year_established)
        self.assertEqual(restored_ex.country, ex.country)
        self.assertEqual(restored_ex.description, ex.description)
        self.assertEqual(restored_ex.url, ex.url)
        self.assertEqual(restored_ex.image, ex.image)
        self.assertEqual(restored_ex.has_trading_incentive, ex.has_trading_incentive)
        self.assertEqual(restored_ex.trust_score, ex.trust_score)
        self.assertEqual(restored_ex.trust_score_rank, ex.trust_score_rank)
        # тип trade_volume_24h_btc может быть float/Decimal — сравниваем по значению
        self.assertAlmostEqual(
            float(restored_ex.trade_volume_24h_btc),
            float(ex.trade_volume_24h_btc),
        )

    def test_search_trending_result_roundtrip(self):
        # --- coins ---
        content = TrendingContent(
            title="Hot coin",
            description="Very hot coin",
        )

        coin_data = TrendingCoinData(
            price=1.23,
            price_btc="0.0001",
            price_change_percentage_24h={"usd": 2.5},
            market_cap="1000000",
            market_cap_btc="10",
            total_volume="500000",
            total_volume_btc="5",
            sparkline="sparkline",
            content=content,
        )

        coin_item = TrendingCoinItem(
            id="bitcoin",
            coin_id=1,
            name="Bitcoin",
            symbol="BTC",
            market_cap_rank=1,
            thumb="thumb",
            small="small",
            large="large",
            slug="bitcoin",
            price_btc=0.0001,
            score=0,
            data=coin_data,
        )

        coin = TrendingCoin(item=coin_item)

        # --- nfts ---
        nft_data = TrendingNftData(
            floor_price="1.0",
            floor_price_in_usd_24h_percentage_change="3.14",
            h24_volume="1000",
            h24_average_sale_price="2.0",
            sparkline="sparkline",
            content=content,
        )

        nft = TrendingNft(
            id="nft1",
            name="Cool NFT",
            symbol="NFT",
            thumb="thumb",
            nft_contract_id=42,
            native_currency_symbol="ETH",
            floor_price_in_native_currency=1.0,
            floor_price_24h_percentage_change=5.0,
            data=nft_data,
        )

        # --- categories ---
        category_data = TrendingCategoryData(
            market_cap=123.0,
            market_cap_btc=1.23,
            total_volume=456.0,
            total_volume_btc=4.56,
            market_cap_change_percentage_24h={"usd": -1.0},
            sparkline="sparkline",
        )

        category = TrendingCategory(
            id=10,
            name="Layer1",
            market_cap_1h_change=0.5,
            slug="layer1",
            coins_count="100",
            data=category_data,
        )

        dto = SearchTrendingResult(
            coins=[coin],
            nfts=[nft],
            categories=[category],
        )

        json_str = dto.to_redis_value()
        restored = SearchTrendingResult.from_redis_value(json_str)

        self.assertIsInstance(restored, SearchTrendingResult)
        self.assertEqual(len(restored.coins), 1)
        self.assertEqual(len(restored.nfts), 1)
        self.assertEqual(len(restored.categories), 1)

        # coins
        coin_restored_item = restored.coins[0].item
        self.assertEqual(coin_restored_item.id, "bitcoin")
        self.assertEqual(coin_restored_item.name, "Bitcoin")
        self.assertIsNotNone(coin_restored_item.data)
        self.assertEqual(coin_restored_item.data.price, 1.23)
        self.assertIsInstance(
            coin_restored_item.data.price_change_percentage_24h["usd"],
            float,
        )

        # nfts
        nft_restored = restored.nfts[0]
        self.assertEqual(nft_restored.id, "nft1")
        self.assertIsNotNone(nft_restored.data)
        self.assertEqual(nft_restored.data.floor_price, "1.0")

        # categories
        category_restored = restored.categories[0]
        self.assertEqual(category_restored.id, 10)
        self.assertIsNotNone(category_restored.data)
        self.assertEqual(
            category_restored.data.market_cap_change_percentage_24h["usd"],
            -1.0,
        )
