from typing import List, Dict, Any, Optional
import redis
import json
import os
import logging
from datetime import datetime, timedelta
from .providers.base import BaseMarketDataProvider
from apps.marketdata.providers.StockMarketRussia.moex import MoexProvider
from apps.marketdata.providers.StockMarketRussia.tinkoff.provider import TinkoffProvider
from .providers.transports import RequestsTransport

logger = logging.getLogger(__name__)


class MarketDataAPI:
    """
    Основной класс API, инкапсулирующий всю бизнес-логику модуля marketdata.
    Отвечает за инициализацию компонентов, кеширование, работу с провайдерами.
    """

    def __init__(self, redis_url: str = None, providers_config: Dict = None):
        self.redis_url = redis_url or os.getenv('REDIS_URL', 'redis://localhost:6379/0')

        # Инициализация компонентов
        self.redis = RedisCacheService(
            redis_url=self.redis_url,
            default_ttl=300,
            max_retries=3
        )
        self._init_providers(providers_config or {})
        self._init_settings()

        logger.info("MarketDataAPI initialized successfully")

    def _init_redis(self):
        """Инициализация Redis клиента"""
        try:
            self.redis_client = redis.from_url(self.redis_url)
            # Тестовое подключение
            self.redis_client.ping()
            logger.info("Redis connection established")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    def _init_providers(self, config: Dict):
        """Инициализация и регистрация провайдеров"""
        self.providers = {}

        # MOEX провайдер
        moex_transport = RequestsTransport()
        self.providers['moex'] = MoexProvider(moex_transport)

        # Tinkoff провайдер (если есть токен)
        tinkoff_token = config.get('tinkoff_token') or os.getenv('TINKOFF_TOKEN')
        if tinkoff_token:
            self.providers['tinkoff'] = TinkoffProvider(tinkoff_token)

        # Провайдер по умолчанию
        self.default_provider = 'moex'

        logger.info(f"Initialized providers: {list(self.providers.keys())}")

    def _init_settings(self):
        """Инициализация настроек TTL для разных типов данных"""
        self.ttl_settings = {
            'quotes': 240,  # 4 минуты для котировок
            'currency_rates': 300,  # 5 минут для валют
            'bonds': 600,  # 10 минут для облигаций
            'crypto': 120,  # 2 минуты для крипты
            'indices': 300  # 5 минут для индексов
        }

    # ===== БИЗНЕС-ЛОГИКА КЕШИРОВАНИЯ =====

    def _get_cache_key(self, data_type: str, identifier: str, provider: str = None) -> str:
        """Генерация ключа для кеша"""
        provider = provider or self.default_provider
        return f"marketdata:{data_type}:{provider}:{identifier}"

    def _get_from_cache(self, key: str) -> Optional[Any]:
        """Получение данных из кеша"""
        try:
            data = self.redis_client.get(key)
            if data:
                return json.loads(data)
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
        return None

    def _set_to_cache(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Сохранение данных в кеш"""
        try:
            serialized = json.dumps(value, default=str)
            ttl = ttl or self.default_ttl
            return bool(self.redis_client.setex(key, ttl, serialized))
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False

    # ===== ОСНОВНАЯ БИЗНЕС-ЛОГИКА =====

    def get_quotes(self, symbols: List[str], provider: Optional[str] = None) -> Dict[str, Any]:
        """
        Получить котировки для списка символов с кешированием
        """
        provider_name = provider or self.default_provider
        provider_instance = self.providers.get(provider_name)

        if not provider_instance:
            raise ValueError(f"Provider {provider_name} not found")

        # Бизнес-логика: проверка кеша и запрос недостающих данных
        cached_results = {}
        symbols_to_fetch = []

        for symbol in symbols:
            cache_key = self._get_cache_key('quotes', symbol, provider_name)
            cached = self._get_from_cache(cache_key)

            if cached:
                cached_results[symbol] = cached
            else:
                symbols_to_fetch.append(symbol)

        # Запрашиваем отсутствующие данные у провайдера
        if symbols_to_fetch:
            fresh_data = provider_instance.get_quotes(symbols_to_fetch)

            # Кешируем новые данные
            for symbol, quote in fresh_data.items():
                if quote:
                    cache_key = self._get_cache_key('quotes', symbol, provider_name)
                    self._set_to_cache(cache_key, quote, self.ttl_settings['quotes'])

            # Объединяем результаты
            cached_results.update(fresh_data)

        return cached_results

    def get_currency_rates(self, currencies: List[str] = None, provider: Optional[str] = None) -> Dict[str, float]:
        """
        Получить курсы валют с кешированием
        """
        if currencies is None:
            currencies = ['USD', 'EUR', 'CNY', 'GBP', 'CHF', 'JPY']

        provider_name = provider or self.default_provider
        cache_key = self._get_cache_key('currency_rates', '_'.join(sorted(currencies)), provider_name)

        # Пробуем получить из кеша
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached

        # Запрашиваем у провайдера
        provider_instance = self.providers.get(provider_name)
        if not provider_instance:
            raise ValueError(f"Provider {provider_name} not found")

        rates = provider_instance.get_currency_rates(currencies)

        # Бизнес-логика: нормализация курсов
        normalized_rates = self._normalize_currency_rates(rates, currencies)

        # Кешируем
        self._set_to_cache(cache_key, normalized_rates, self.ttl_settings['currency_rates'])

        return normalized_rates

    def get_portfolio_value(self, assets: List[Dict]) -> Dict[str, Any]:
        """
        Рассчитать стоимость портфеля - основная бизнес-логика для модуля Assets
        """
        if not assets:
            return {
                'total_value': 0.0,
                'assets': [],
                'calculation_time': datetime.now().isoformat()
            }

        # Группируем символы по типам для оптимизации запросов
        stock_symbols = [asset['symbol'] for asset in assets if asset.get('type') == 'stock']
        crypto_symbols = [asset['symbol'] for asset in assets if asset.get('type') == 'crypto']

        # Получаем котировки
        stock_quotes = self.get_quotes(stock_symbols, 'moex') if stock_symbols else {}
        crypto_prices = self.get_crypto_prices(crypto_symbols) if crypto_symbols else {}

        # Бизнес-логика: расчет стоимости
        total_value = 0.0
        asset_details = []

        for asset in assets:
            symbol = asset.get('symbol')
            quantity = asset.get('quantity', 0)
            asset_type = asset.get('type', 'stock')

            current_price = 0
            if asset_type == 'stock' and symbol in stock_quotes:
                current_price = stock_quotes[symbol].get('price', 0)
            elif asset_type == 'crypto' and symbol in crypto_prices:
                current_price = crypto_prices[symbol]

            asset_value = current_price * quantity
            total_value += asset_value

            asset_details.append({
                'symbol': symbol,
                'type': asset_type,
                'quantity': quantity,
                'current_price': current_price,
                'current_value': asset_value,
                'purchase_price': asset.get('purchase_price', 0),
                'purchase_value': asset.get('purchase_price', 0) * quantity
            })

        # Дополнительная бизнес-логика: расчет прибыли
        total_purchase_value = sum(asset['purchase_value'] for asset in asset_details)
        total_profit = total_value - total_purchase_value
        profit_percentage = (total_profit / total_purchase_value * 100) if total_purchase_value else 0

        return {
            'total_value': total_value,
            'total_purchase_value': total_purchase_value,
            'total_profit': total_profit,
            'profit_percentage': profit_percentage,
            'assets': asset_details,
            'calculation_time': datetime.now().isoformat(),
            'base_currency': 'RUB'  # Можно сделать настраиваемым
        }

    def get_asset_current_prices(self, assets: List[Dict]) -> List[Dict]:
        """
        Получить текущие цены для списка активов с детализацией
        """
        # Бизнес-логика: группировка и оптимизация запросов
        symbols_by_type = {}
        for asset in assets:
            asset_type = asset.get('type', 'stock')
            if asset_type not in symbols_by_type:
                symbols_by_type[asset_type] = []
            symbols_by_type[asset_type].append(asset['symbol'])

        # Получаем цены по типам активов
        prices_by_type = {}
        for asset_type, symbols in symbols_by_type.items():
            if asset_type == 'stock':
                prices_by_type[asset_type] = self.get_quotes(symbols)
            elif asset_type == 'crypto':
                prices_by_type[asset_type] = self.get_crypto_prices(symbols)
            elif asset_type == 'currency':
                prices_by_type[asset_type] = self.get_currency_rates(symbols)

        # Формируем результат
        result = []
        for asset in assets:
            asset_type = asset.get('type', 'stock')
            symbol = asset['symbol']
            quantity = asset.get('quantity', 0)

            current_price = 0
            if asset_type in prices_by_type and symbol in prices_by_type[asset_type]:
                price_data = prices_by_type[asset_type][symbol]
                current_price = price_data.get('price', 0) if isinstance(price_data, dict) else price_data

            asset_data = asset.copy()
            asset_data.update({
                'current_price': current_price,
                'current_value': current_price * quantity,
                'last_updated': datetime.now().isoformat()
            })

            result.append(asset_data)

        return result

    # ===== ВСПОМОГАТЕЛЬНАЯ БИЗНЕС-ЛОГИКА =====

    def _normalize_currency_rates(self, rates: Dict[str, float], currencies: List[str]) -> Dict[str, float]:
        """
        Нормализация курсов валют - бизнес-логика форматов
        """
        normalized = {}
        base_currency = 'RUB'

        for currency in currencies:
            # Пробуем разные форматы ключей
            possible_keys = [
                f"{currency}{base_currency}",
                f"{currency}/{base_currency}",
                f"{currency}_{base_currency}",
                currency  # Прямое значение
            ]

            for key in possible_keys:
                if key in rates:
                    normalized[f"{currency}{base_currency}"] = rates[key]
                    break
            else:
                # Если курс не найден, используем значение по умолчанию или логируем ошибку
                logger.warning(f"Currency rate for {currency} not found")
                normalized[f"{currency}{base_currency}"] = 0.0

        return normalized

    def refresh_data(self, symbols: List[str], data_type: str = 'quotes', provider: Optional[str] = None) -> bool:
        """
        Принудительное обновление данных в кеше - бизнес-логика обновления
        """
        provider_name = provider or self.default_provider
        provider_instance = self.providers.get(provider_name)

        if not provider_instance:
            logger.error(f"Provider {provider_name} not found for refresh")
            return False

        try:
            if data_type == 'quotes':
                new_data = provider_instance.get_quotes(symbols)
            elif data_type == 'currency_rates':
                new_data = provider_instance.get_currency_rates(symbols)
            else:
                logger.error(f"Unsupported data type for refresh: {data_type}")
                return False

            # Обновляем кеш
            cache_updates = {}
            for symbol, data in new_data.items():
                if data:
                    cache_key = self._get_cache_key(data_type, symbol, provider_name)
                    cache_updates[cache_key] = data

            # Бизнес-логика: батчевое обновление кеша
            for key, value in cache_updates.items():
                self._set_to_cache(key, value, self.ttl_settings.get(data_type, self.default_ttl))

            logger.info(f"Refreshed {len(cache_updates)} {data_type} records")
            return True

        except Exception as e:
            logger.error(f"Error refreshing {data_type}: {e}")
            return False

    # ===== ДЕЛЕГИРОВАНИЕ К ПРОВАЙДЕРАМ =====

    def get_bond_data(self, isins: List[str], provider: Optional[str] = None) -> Dict[str, Any]:
        """Делегирование метода провайдеру с кешированием"""
        provider_name = provider or self.default_provider
        provider_instance = self.providers.get(provider_name)

        if not provider_instance:
            raise ValueError(f"Provider {provider_name} not found")

        cache_key = self._get_cache_key('bonds', '_'.join(sorted(isins)), provider_name)
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached

        data = provider_instance.get_bond_data(isins)
        self._set_to_cache(cache_key, data, self.ttl_settings['bonds'])
        return data

    def get_crypto_prices(self, cryptos: List[str], provider: Optional[str] = None) -> Dict[str, float]:
        """Делегирование метода провайдеру с кешированием"""
        provider_name = provider or self.default_provider
        provider_instance = self.providers.get(provider_name)

        if not provider_instance:
            raise ValueError(f"Provider {provider_name} not found")

        cache_key = self._get_cache_key('crypto', '_'.join(sorted(cryptos)), provider_name)
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached

        data = provider_instance.get_crypto_prices(cryptos)
        self._set_to_cache(cache_key, data, self.ttl_settings['crypto'])
        return data

    def get_index_values(self, indices: List[str], provider: Optional[str] = None) -> Dict[str, float]:
        """Делегирование метода провайдеру с кешированием"""
        provider_name = provider or self.default_provider
        provider_instance = self.providers.get(provider_name)

        if not provider_instance:
            raise ValueError(f"Provider {provider_name} not found")

        cache_key = self._get_cache_key('indices', '_'.join(sorted(indices)), provider_name)
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached

        data = provider_instance.get_index_values(indices)
        self._set_to_cache(cache_key, data, self.ttl_settings['indices'])
        return data

    # ===== СИСТЕМНЫЕ МЕТОДЫ =====

    def health_check(self) -> Dict[str, Any]:
        """Проверка здоровья всех компонентов"""
        redis_health = self.cache.health_check()
        providers_health = self._check_providers_health()

        return {
            'redis': redis_health,
            'providers': providers_health,
            'overall': redis_health and any(providers_health.values()),
            'timestamp': datetime.now().isoformat()
        }

    def _check_redis_health(self) -> bool:
        """Проверка Redis"""
        try:
            self.redis_client.ping()
            return True
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False

    def _check_providers_health(self) -> Dict[str, bool]:
        """Проверка провайдеров"""
        health_status = {}
        for name, provider in self.providers.items():
            try:
                health_status[name] = provider.health_check()
            except Exception as e:
                logger.error(f"Health check failed for provider {name}: {e}")
                health_status[name] = False
        return health_status

    def get_available_providers(self) -> List[str]:
        """Список доступных провайдеров"""
        return list(self.providers.keys())

    def clear_cache(self, pattern: str = "marketdata:*") -> int:
        """
        Очистка кеша по паттерну
        Возвращает количество удаленных ключей
        """
        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                return self.redis_client.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Error clearing cache with pattern {pattern}: {e}")
            return 0