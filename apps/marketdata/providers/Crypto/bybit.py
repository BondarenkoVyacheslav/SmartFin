import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import aiohttp
from pybit.unified_trading import HTTP, WebSocket
import threading
import time

logger = logging.getLogger(__name__)


class BybitProvider:
    """
    Класс для работы с API Bybit с кешированием данных в Redis
    """

    def __init__(
            self,
            redis_cache_service: RedisCacheService,
            api_key: Optional[str] = None,
            api_secret: Optional[str] = None,
            testnet: bool = False,
            update_interval: int = 300  # 5 минут по умолчанию
    ):
        """
        Args:
            redis_cache_service: Сервис для работы с Redis
            api_key: API ключ Bybit (опционально для публичных данных)
            api_secret: API секрет Bybit (опционально для публичных данных)
            testnet: Использовать тестовую сеть
            update_interval: Интервал обновления данных в секундах
        """
        self.redis = redis_cache_service
        self.testnet = testnet
        self.update_interval = update_interval
        self._running = False
        self._update_thread = None

        # Инициализация HTTP клиента
        self.http_client = HTTP(
            testnet=testnet,
            api_key=api_key,
            api_secret=api_secret
        )

        # WebSocket клиенты для разных категорий
        self.ws_clients = {}

        # Ключи для Redis
        self.redis_keys = {
            'tickers_spot': 'bybit:tickers:spot',
            'tickers_linear': 'bybit:tickers:linear',
            'tickers_inverse': 'bybit:tickers:inverse',
            'orderbook': 'bybit:orderbook:{}',  # {} заменится на символ
            'klines': 'bybit:klines:{}:{}',  # {} заменится на символ и интервал
            'funding_rate': 'bybit:funding:{}',
            'open_interest': 'bybit:oi:{}',
            'last_update': 'bybit:last_update'
        }

    def start_periodic_updates(self):
        """Запуск периодического обновления данных"""
        if self._running:
            logger.warning("Periodic updates already running")
            return

        self._running = True
        self._update_thread = threading.Thread(target=self._update_worker, daemon=True)
        self._update_thread.start()
        logger.info("Started periodic Bybit data updates")

    def stop_periodic_updates(self):
        """Остановка периодического обновления"""
        self._running = False
        if self._update_thread:
            self._update_thread.join(timeout=10)
        logger.info("Stopped periodic Bybit data updates")

    def _update_worker(self):
        """Рабочий процесс для периодического обновления"""
        while self._running:
            try:
                self.update_all_market_data()
                logger.info(f"Successfully updated Bybit market data at {datetime.now()}")
            except Exception as e:
                logger.error(f"Error updating Bybit data: {e}")

            # Ожидание до следующего обновления
            time.sleep(self.update_interval)

    def update_all_market_data(self):
        """Обновление всех рыночных данных"""
        try:
            # Получение тикеров для всех категорий
            categories = ['spot', 'linear', 'inverse']
            for category in categories:
                tickers = self.get_tickers(category)
                if tickers:
                    key = self.redis_keys[f'tickers_{category}']
                    self.redis.set(key, tickers, ttl=self.update_interval + 60)
                    logger.debug(f"Updated {category} tickers: {len(tickers)} symbols")

            # Сохранение времени последнего обновления
            self.redis.set(
                self.redis_keys['last_update'],
                datetime.now().isoformat(),
                ttl=self.update_interval + 60
            )

        except Exception as e:
            logger.error(f"Error updating all market data: {e}")
            raise

    def get_tickers(self, category: str = 'spot') -> Optional[Dict[str, Any]]:
        """
        Получение тикеров для указанной категории

        Args:
            category: spot, linear, inverse

        Returns:
            Словарь с данными тикеров или None в случае ошибки
        """
        try:
            response = self.http_client.get_tickers(
                category=category,
                limit=1000  # Максимальное количество
            )

            if response['retCode'] == 0:
                return {
                    'category': category,
                    'timestamp': datetime.now().isoformat(),
                    'tickers': response['result']['list'],
                    'total_count': len(response['result']['list'])
                }
            else:
                logger.error(f"Bybit API error: {response['retMsg']}")
                return None

        except Exception as e:
            logger.error(f"Error getting tickers for {category}: {e}")
            return None

    def get_cached_tickers(self, category: str = 'spot') -> Optional[Dict[str, Any]]:
        """
        Получение кешированных тикеров

        Args:
            category: spot, linear, inverse

        Returns:
            Кешированные данные тикеров или None если данных нет
        """
        key = self.redis_keys[f'tickers_{category}']
        return self.redis.get(key)

    def get_orderbook(self, symbol: str, category: str = 'spot') -> Optional[Dict[str, Any]]:
        """
        Получение стакана ордеров для символа

        Args:
            symbol: Торговый символ (например: BTCUSDT)
            category: spot, linear, inverse

        Returns:
            Данные стакана ордеров
        """
        try:
            response = self.http_client.get_orderbook(
                category=category,
                symbol=symbol,
                limit=50  # Глубина стакана
            )

            if response['retCode'] == 0:
                data = {
                    'symbol': symbol,
                    'category': category,
                    'timestamp': datetime.now().isoformat(),
                    'bids': response['result']['b'],
                    'asks': response['result']['a']
                }

                # Кеширование на 30 секунд (быстро меняющиеся данные)
                key = self.redis_keys['orderbook'].format(symbol)
                self.redis.set(key, data, ttl=30)

                return data
            else:
                logger.error(f"Bybit API error for orderbook {symbol}: {response['retMsg']}")
                return None

        except Exception as e:
            logger.error(f"Error getting orderbook for {symbol}: {e}")
            return None

    def get_cached_orderbook(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Получение кешированного стакана ордеров

        Args:
            symbol: Торговый символ

        Returns:
            Кешированные данные стакана или None
        """
        key = self.redis_keys['orderbook'].format(symbol)
        return self.redis.get(key)

    def get_klines(
            self,
            symbol: str,
            interval: str = '15',
            category: str = 'spot',
            limit: int = 200
    ) -> Optional[Dict[str, Any]]:
        """
        Получение свечных данных (K-line)

        Args:
            symbol: Торговый символ
            interval: Интервал (1, 3, 5, 15, 30, 60, 120, 240, 360, 720, D, W, M)
            category: spot, linear, inverse
            limit: Количество свечей

        Returns:
            Свечные данные
        """
        try:
            response = self.http_client.get_kline(
                category=category,
                symbol=symbol,
                interval=interval,
                limit=limit
            )

            if response['retCode'] == 0:
                data = {
                    'symbol': symbol,
                    'category': category,
                    'interval': interval,
                    'timestamp': datetime.now().isoformat(),
                    'klines': response['result']['list']
                }

                # Кеширование на 1 минуту
                key = self.redis_keys['klines'].format(symbol, interval)
                self.redis.set(key, data, ttl=60)

                return data
            else:
                logger.error(f"Bybit API error for klines {symbol}: {response['retMsg']}")
                return None

        except Exception as e:
            logger.error(f"Error getting klines for {symbol}: {e}")
            return None

    def get_cached_klines(self, symbol: str, interval: str) -> Optional[Dict[str, Any]]:
        """
        Получение кешированных свечных данных

        Args:
            symbol: Торговый символ
            interval: Интервал свечей

        Returns:
            Кешированные свечные данные или None
        """
        key = self.redis_keys['klines'].format(symbol, interval)
        return self.redis.get(key)

    def get_funding_rate(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Получение ставки финансирования для фьючерсов

        Args:
            symbol: Торговый символ

        Returns:
            Данные ставки финансирования
        """
        try:
            response = self.http_client.get_funding_rate_history(
                category='linear',
                symbol=symbol,
                limit=1
            )

            if response['retCode'] == 0 and response['result']['list']:
                data = {
                    'symbol': symbol,
                    'timestamp': datetime.now().isoformat(),
                    'funding_rate': response['result']['list'][0]
                }

                # Кеширование на 5 минут
                key = self.redis_keys['funding_rate'].format(symbol)
                self.redis.set(key, data, ttl=300)

                return data
            else:
                logger.error(f"Bybit API error for funding rate {symbol}: {response['retMsg']}")
                return None

        except Exception as e:
            logger.error(f"Error getting funding rate for {symbol}: {e}")
            return None

    def get_open_interest(self, symbol: str, period: str = '5min') -> Optional[Dict[str, Any]]:
        """
        Получение открытого интереса

        Args:
            symbol: Торговый символ
            period: Период (5min, 15min, 30min, 1h, 4h, 1d)

        Returns:
            Данные открытого интереса
        """
        try:
            response = self.http_client.get_open_interest(
                category='linear',
                symbol=symbol,
                interval=period,
                limit=1
            )

            if response['retCode'] == 0 and response['result']['list']:
                data = {
                    'symbol': symbol,
                    'period': period,
                    'timestamp': datetime.now().isoformat(),
                    'open_interest': response['result']['list'][0]
                }

                # Кеширование на 5 минут
                key = self.redis_keys['open_interest'].format(symbol)
                self.redis.set(key, data, ttl=300)

                return data
            else:
                logger.error(f"Bybit API error for OI {symbol}: {response['retMsg']}")
                return None

        except Exception as e:
            logger.error(f"Error getting open interest for {symbol}: {e}")
            return None

    def get_market_status(self) -> Dict[str, Any]:
        """
        Получение общего статуса рынка и статистики кеша

        Returns:
            Статистика и статус данных
        """
        try:
            categories = ['spot', 'linear', 'inverse']
            status = {
                'last_update': self.redis.get(self.redis_keys['last_update']),
                'cache_stats': self.redis.get_stats(),
                'categories': {}
            }

            for category in categories:
                key = self.redis_keys[f'tickers_{category}']
                data = self.redis.get(key)
                if data:
                    status['categories'][category] = {
                        'symbols_count': data.get('total_count', 0),
                        'last_update': data.get('timestamp'),
                        'ttl': self.redis.ttl(key)
                    }
                else:
                    status['categories'][category] = {
                        'symbols_count': 0,
                        'last_update': None,
                        'ttl': None
                    }

            return status

        except Exception as e:
            logger.error(f"Error getting market status: {e}")
            return {}

    def search_symbols(self, query: str, category: str = 'spot') -> List[Dict[str, Any]]:
        """
        Поиск символов по названию

        Args:
            query: Строка для поиска
            category: Категория для поиска

        Returns:
            Список найденных символов
        """
        try:
            tickers_data = self.get_cached_tickers(category)
            if not tickers_data or 'tickers' not in tickers_data:
                return []

            query = query.upper()
            results = []

            for ticker in tickers_data['tickers']:
                symbol = ticker.get('symbol', '')
                if query in symbol:
                    results.append(ticker)

            return results

        except Exception as e:
            logger.error(f"Error searching symbols: {e}")
            return []


# Пример использования
def main():
    # Инициализация Redis
    redis_service = RedisCacheService(
        redis_url='redis://localhost:6379/0',
        default_ttl=300
    )

    # Инициализация коллектора Bybit
    collector = BybitDataCollector(
        redis_cache_service=redis_service,
        testnet=True,  # Используем тестовую сеть для начала
        update_interval=300  # Обновление каждые 5 минут
    )

    try:
        # Запуск периодического обновления
        collector.start_periodic_updates()

        # Даем время для первого обновления
        time.sleep(10)

        # Получение кешированных данных
        spot_tickers = collector.get_cached_tickers('spot')
        if spot_tickers:
            print(f"Получено {spot_tickers['total_count']} спот-символов")

        # Получение стакана для BTCUSDT
        orderbook = collector.get_orderbook('BTCUSDT', 'spot')
        if orderbook:
            print(f"Стакан BTCUSDT: {len(orderbook['bids'])} bids, {len(orderbook['asks'])} asks")

        # Получение статуса рынка
        status = collector.get_market_status()
        print(f"Статус: {status}")

        # Ожидание для демонстрации периодического обновления
        time.sleep(600)

    except KeyboardInterrupt:
        print("Остановка...")
    finally:
        collector.stop_periodic_updates()


if __name__ == "__main__":
    main()