import requests
import hashlib
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class TradingViewProvider:
    """
    Провайдер для взаимодействия с API TradingView с кешированием в Redis.
    """

    def __init__(self, cache_service: RedisCacheService, api_key: str = None,
                 base_url: str = "https://api.tradingview.com"):
        """
        Args:
            cache_service: Экземпляр RedisCacheService для кеширования
            api_key: API ключ для TradingView (опционально)
            base_url: Базовый URL API TradingView
        """
        self.cache = cache_service
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()

        # Настройка сессии
        if self.api_key:
            self.session.headers.update({
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            })

    def _generate_cache_key(self, endpoint: str, params: Dict[str, Any]) -> str:
        """
        Генерация уникального ключа кеша на основе эндпоинта и параметров.

        Args:
            endpoint: API эндпоинт
            params: Параметры запроса

        Returns:
            Уникальный ключ для кеша
        """
        param_str = json.dumps(params, sort_keys=True)
        key_string = f"tradingview:{endpoint}:{param_str}"
        return hashlib.md5(key_string.encode()).hexdigest()

    def _make_request(self, endpoint: str, params: Dict[str, Any], cache_ttl: int = 60) -> Optional[Dict[str, Any]]:
        """
        Выполнение запроса к API с кешированием.

        Args:
            endpoint: API эндпоинт
            params: Параметры запроса
            cache_ttl: TTL кеша в секундах

        Returns:
            Ответ API или None в случае ошибки
        """
        cache_key = self._generate_cache_key(endpoint, params)

        # Пробуем получить данные из кеша
        cached_data = self.cache.get(cache_key)
        if cached_data is not None:
            logger.debug(f"Cache hit for {endpoint}")
            cached_data['_cached'] = True
            cached_data['_cache_timestamp'] = self.cache._client.ttl(cache_key)
            return cached_data

        try:
            url = f"{self.base_url}/{endpoint.lstrip('/')}"
            logger.info(f"Making request to {url} with params {params}")

            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()

            # Сохраняем в кеш
            cache_data = data.copy()
            self.cache.set(cache_key, cache_data, ttl=cache_ttl)

            data['_cached'] = False
            data['_cache_timestamp'] = datetime.now().isoformat()

            return data

        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed for {endpoint}: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response from {endpoint}: {e}")
            return None

    def get_symbol_info(self, symbol: str, exchange: str = None) -> Optional[Dict[str, Any]]:
        """
        Получить информацию о символе.

        Args:
            symbol: Тикер символа (например: 'AAPL')
            exchange: Биржа (например: 'NASDAQ')

        Returns:
            Информация о символе
        """
        endpoint = "/v1/symbols/info"
        params = {"symbol": symbol}
        if exchange:
            params["exchange"] = exchange

        return self._make_request(endpoint, params, cache_ttl=3600)  # Кешируем на 1 час

    def get_quotes(self, symbols: List[str], fields: List[str] = None) -> Optional[Dict[str, Any]]:
        """
        Получить котировки для списка символов.

        Args:
            symbols: Список символов (например: ['AAPL', 'MSFT'])
            fields: Список полей для получения (по умолчанию основные поля)

        Returns:
            Котировки символов
        """
        endpoint = "/v1/quote"
        params = {"symbols": ",".join(symbols)}

        if fields:
            params["fields"] = ",".join(fields)
        else:
            # Основные поля по умолчанию
            default_fields = [
                "lp", "ch", "chp", "ask", "bid", "open", "high", "low",
                "volume", "previous_close", "currency", "description"
            ]
            params["fields"] = ",".join(default_fields)

        return self._make_request(endpoint, params, cache_ttl=30)  # Кешируем на 30 секунд

    def get_technical_indicators(self, symbol: str, indicators: List[str],
                                 interval: str = "1h", range: str = "1m") -> Optional[Dict[str, Any]]:
        """
        Получить технические индикаторы для символа.

        Args:
            symbol: Символ
            indicators: Список индикаторов (например: ['RSI', 'MACD.macd', 'SMA20'])
            interval: Таймфрейм (1m, 5m, 15m, 1h, 4h, 1d и т.д.)
            range: Период (1d, 1w, 1m, 3m, 1y и т.д.)

        Returns:
            Данные технических индикаторов
        """
        endpoint = "/v1/indicators"
        params = {
            "symbol": symbol,
            "indicators": ",".join(indicators),
            "interval": interval,
            "range": range
        }

        return self._make_request(endpoint, params, cache_ttl=300)  # Кешируем на 5 минут

    def get_screener_data(self, screener: str = "america", filters: List[Dict] = None,
                          columns: List[str] = None, limit: int = 50) -> Optional[Dict[str, Any]]:
        """
        Получить данные из скринера.

        Args:
            screener: Регион скринера
            filters: Список фильтров
            columns: Список колонок для отображения
            limit: Лимит результатов

        Returns:
            Данные скринера
        """
        endpoint = "/v1/screener/scan"
        params = {
            "screener": screener,
            "limit": limit
        }

        if filters:
            params["filters"] = json.dumps(filters)
        if columns:
            params["columns"] = ",".join(columns)

        return self._make_request(endpoint, params, cache_ttl=600)  # Кешируем на 10 минут

    def get_market_overview(self, market: str = "stocks") -> Optional[Dict[str, Any]]:
        """
        Получить обзор рынка.

        Args:
            market: Тип рынка (stocks, crypto, forex, etc.)

        Returns:
            Обзор рынка
        """
        endpoint = f"/v1/markets/{market}/overview"
        return self._make_request(endpoint, {}, cache_ttl=300)  # Кешируем на 5 минут

    def get_news(self, symbol: str = None, category: str = "general",
                 limit: int = 20) -> Optional[Dict[str, Any]]:
        """
        Получить новости.

        Args:
            symbol: Символ для фильтрации новостей
            category: Категория новостей
            limit: Лимит новостей

        Returns:
            Список новостей
        """
        endpoint = "/v1/news"
        params = {
            "category": category,
            "limit": limit
        }

        if symbol:
            params["symbol"] = symbol

        return self._make_request(endpoint, params, cache_ttl=180)  # Кешируем на 3 минуты

    def clear_tradingview_cache(self, pattern: str = "tradingview:*") -> int:
        """
        Очистить кеш TradingView.

        Args:
            pattern: Паттерн для удаления ключей

        Returns:
            Количество удаленных ключей
        """
        return self.cache.delete_pattern(pattern)

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Получить статистику кеша TradingView.

        Returns:
            Статистика кеша
        """
        stats = self.cache.get_stats()
        tradingview_keys = self.cache.keys("tradingview:*")

        stats['tradingview_keys_count'] = len(tradingview_keys)
        stats['tradingview_keys'] = tradingview_keys[:10]  # Первые 10 ключей для примера

        return stats

    def health_check(self) -> Dict[str, Any]:
        """
        Проверка здоровья провайдера.

        Returns:
            Статус здоровья
        """
        cache_health = self.cache.health_check()

        # Проверяем доступность API
        api_health = "unknown"
        try:
            test_response = self.get_symbol_info("AAPL")
            api_health = "healthy" if test_response else "unhealthy"
        except Exception as e:
            api_health = f"unhealthy: {e}"

        return {
            "cache": cache_health,
            "api": api_health,
            "timestamp": datetime.now().isoformat()
        }


# Пример использования
if __name__ == "__main__":
    # Инициализация кеша
    cache_service = RedisCacheService("redis://localhost:6379/0")

    # Инициализация провайдера
    provider = TradingViewProvider(
        cache_service=cache_service,
        api_key="your_tradingview_api_key"  # Опционально
    )

    # Пример получения котировок
    quotes = provider.get_quotes(["AAPL", "MSFT", "GOOGL"])
    if quotes:
        print("Quotes:", quotes)

    # Пример получения технических индикаторов
    indicators = provider.get_technical_indicators(
        symbol="AAPL",
        indicators=["RSI", "MACD.macd", "SMA20", "SMA50"],
        interval="1d",
        range="6m"
    )
    if indicators:
        print("Indicators:", indicators)

    # Статистика кеша
    stats = provider.get_cache_stats()
    print("Cache stats:", stats)

    # Проверка здоровья
    health = provider.health_check()
    print("Health check:", health)