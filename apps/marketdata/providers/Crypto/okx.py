import logging
import threading
import time
from typing import Dict, List, Optional, Any
from datetime import datetime

# Установите библиотеку: pip install python-okx
from okx import MarketData, Account, Trade
from redis_service import RedisCacheService  # Ваш существующий сервис

logger = logging.getLogger(__name__)


class OKXProvider:
    """
    Класс для работы с API OKX с кешированием данных в Redis
    """

    def __init__(
            self,
            redis_cache_service: RedisCacheService,
            api_key: Optional[str] = None,
            api_secret: Optional[str] = None,
            passphrase: Optional[str] = None,
            flag: str = "0",  # "0" - реальный режим, "1" - демо-режим
            testnet: bool = False,
            update_interval: int = 300  # 5 минут по умолчанию
    ):
        """
        Args:
            redis_cache_service: Сервис для работы с Redis
            api_key: API ключ OKX
            api_secret: API секрет OKX
            passphrase: Парольная фраза API
            flag: Режим торговли ("0" - реальный, "1" - демо)
            testnet: Использовать тестовую сеть
            update_interval: Интервал обновления данных в секундах
        """
        self.redis = redis_cache_service
        self.flag = flag
        self.testnet = testnet
        self.update_interval = update_interval
        self._running = False
        self._update_thread = None

        # Инициализация клиентов OKX API
        try:
            self.market_api = MarketData.MarketAPI(
                api_key=api_key,
                api_secret_key=api_secret,
                passphrase=passphrase,
                flag=flag,
                testnet=testnet
            )

            # Для публичных данных аутентификация не обязательна
            self.public_market_api = MarketData.MarketAPI(flag=flag, testnet=testnet)

            # Для приватных данных (если нужны)
            if api_key and api_secret and passphrase:
                self.account_api = Account.AccountAPI(
                    api_key=api_key,
                    api_secret_key=api_secret,
                    passphrase=passphrase,
                    flag=flag,
                    testnet=testnet
                )

            logger.info("OKX API clients initialized successfully")

        except Exception as e:
            logger.error(f"Error initializing OKX API clients: {e}")
            raise

        # Ключи для Redis
        self.redis_keys = {
            'tickers_spot': 'okx:tickers:spot',
            'tickers_swap': 'okx:tickers:swap',
            'tickers_futures': 'okx:tickers:futures',
            'tickers_option': 'okx:tickers:option',
            'orderbook': 'okx:orderbook:{}',  # {} заменится на символ
            'klines': 'okx:klines:{}:{}',  # {} заменится на символ и интервал
            'instruments': 'okx:instruments:{}',  # {} заменится на тип инструмента
            'last_update': 'okx:last_update'
        }

    def start_periodic_updates(self):
        """Запуск периодического обновления данных"""
        if self._running:
            logger.warning("Periodic updates already running")
            return

        self._running = True
        self._update_thread = threading.Thread(target=self._update_worker, daemon=True)
        self._update_thread.start()
        logger.info("Started periodic OKX data updates")

    def stop_periodic_updates(self):
        """Остановка периодического обновления"""
        self._running = False
        if self._update_thread:
            self._update_thread.join(timeout=10)
        logger.info("Stopped periodic OKX data updates")

    def _update_worker(self):
        """Рабочий процесс для периодического обновления"""
        while self._running:
            try:
                self.update_all_market_data()
                logger.info(f"Successfully updated OKX market data at {datetime.now()}")
            except Exception as e:
                logger.error(f"Error updating OKX data: {e}")

            time.sleep(self.update_interval)

    def update_all_market_data(self):
        """Обновление всех рыночных данных"""
        try:
            # Получение тикеров для всех типов инструментов
            inst_types = ['SPOT', 'SWAP', 'FUTURES', 'OPTION']

            for inst_type in inst_types:
                tickers = self.get_tickers(inst_type)
                if tickers and tickers.get('code') == '0':
                    key = self.redis_keys[f'tickers_{inst_type.lower()}']
                    # Сохраняем только данные, без кода ответа
                    data_to_cache = {
                        'data': tickers.get('data', []),
                        'timestamp': datetime.now().isoformat(),
                        'total_count': len(tickers.get('data', []))
                    }
                    self.redis.set(key, data_to_cache, ttl=self.update_interval + 60)
                    logger.debug(f"Updated {inst_type} tickers: {len(tickers.get('data', []))} symbols")
                else:
                    logger.warning(
                        f"No data received for {inst_type} or API error: {tickers.get('msg', 'Unknown error')}")

            # Сохранение времени последнего обновления
            self.redis.set(
                self.redis_keys['last_update'],
                datetime.now().isoformat(),
                ttl=self.update_interval + 60
            )

        except Exception as e:
            logger.error(f"Error updating all market data: {e}")
            raise

    def get_tickers(self, inst_type: str = 'SPOT') -> Optional[Dict[str, Any]]:
        """
        Получение тикеров для указанного типа инструмента

        Args:
            inst_type: SPOT, SWAP, FUTURES, OPTION

        Returns:
            Ответ API с данными тикеров или None в случае ошибки
        """
        try:
            # Используем публичный API для рыночных данных
            response = self.public_market_api.get_tickers(instType=inst_type)
            return response
        except Exception as e:
            logger.error(f"Error getting tickers for {inst_type}: {e}")
            return None

    def get_cached_tickers(self, inst_type: str = 'SPOT') -> Optional[Dict[str, Any]]:
        """
        Получение кешированных тикеров

        Args:
            inst_type: SPOT, SWAP, FUTURES, OPTION

        Returns:
            Кешированные данные тикеров или None если данных нет
        """
        key = self.redis_keys[f'tickers_{inst_type.lower()}']
        return self.redis.get(key)

    def get_orderbook(self, inst_id: str, sz: int = 20) -> Optional[Dict[str, Any]]:
        """
        Получение стакана ордеров для инструмента

        Args:
            inst_id: ID инструмента (например: BTC-USDT)
            sz: Глубина стакана (по умолчанию 20)

        Returns:
            Данные стакана ордеров
        """
        try:
            response = self.public_market_api.get_orderbook(instId=inst_id, sz=sz)

            if response.get('code') == '0':
                data = {
                    'inst_id': inst_id,
                    'timestamp': datetime.now().isoformat(),
                    'bids': response['data'][0]['bids'],
                    'asks': response['data'][0]['asks'],
                    'ts': response['data'][0]['ts']
                }

                # Кеширование на 30 секунд (быстро меняющиеся данные)
                key = self.redis_keys['orderbook'].format(inst_id)
                self.redis.set(key, data, ttl=30)

                return data
            else:
                logger.error(f"OKX API error for orderbook {inst_id}: {response.get('msg')}")
                return None

        except Exception as e:
            logger.error(f"Error getting orderbook for {inst_id}: {e}")
            return None

    def get_cached_orderbook(self, inst_id: str) -> Optional[Dict[str, Any]]:
        """
        Получение кешированного стакана ордеров

        Args:
            inst_id: ID инструмента

        Returns:
            Кешированные данные стакана или None
        """
        key = self.redis_keys['orderbook'].format(inst_id)
        return self.redis.get(key)

    def get_klines(
            self,
            inst_id: str,
            bar: str = '15m',
            limit: int = 100
    ) -> Optional[Dict[str, Any]]:
        """
        Получение свечных данных (K-line)

        Args:
            inst_id: ID инструмента
            bar: Гранулярность свечей (1m, 5m, 15m, 1H, 4H, 1D и т.д.)
            limit: Количество свечей (по умолчанию 100)

        Returns:
            Свечные данные
        """
        try:
            response = self.public_market_api.get_candlesticks(
                instId=inst_id,
                bar=bar,
                limit=limit
            )

            if response.get('code') == '0':
                data = {
                    'inst_id': inst_id,
                    'bar': bar,
                    'timestamp': datetime.now().isoformat(),
                    'klines': response['data']
                }

                # Кеширование на 1 минуту
                key = self.redis_keys['klines'].format(inst_id, bar)
                self.redis.set(key, data, ttl=60)

                return data
            else:
                logger.error(f"OKX API error for klines {inst_id}: {response.get('msg')}")
                return None

        except Exception as e:
            logger.error(f"Error getting klines for {inst_id}: {e}")
            return None

    def get_cached_klines(self, inst_id: str, bar: str) -> Optional[Dict[str, Any]]:
        """
        Получение кешированных свечных данных

        Args:
            inst_id: ID инструмента
            bar: Гранулярность свечей

        Returns:
            Кешированные свечные данные или None
        """
        key = self.redis_keys['klines'].format(inst_id, bar)
        return self.redis.get(key)

    def get_instruments(self, inst_type: str = 'SPOT') -> Optional[Dict[str, Any]]:
        """
        Получение информации о доступных инструментах

        Args:
            inst_type: Тип инструмента (SPOT, SWAP, FUTURES, OPTION)

        Returns:
            Информация об инструментах
        """
        try:
            response = self.public_market_api.get_instruments(instType=inst_type)

            if response.get('code') == '0':
                data = {
                    'inst_type': inst_type,
                    'timestamp': datetime.now().isoformat(),
                    'instruments': response['data']
                }

                # Кеширование на 1 час (редко меняющиеся данные)
                key = self.redis_keys['instruments'].format(inst_type)
                self.redis.set(key, data, ttl=3600)

                return data
            else:
                logger.error(f"OKX API error for instruments {inst_type}: {response.get('msg')}")
                return None

        except Exception as e:
            logger.error(f"Error getting instruments for {inst_type}: {e}")
            return None

    def get_cached_instruments(self, inst_type: str = 'SPOT') -> Optional[Dict[str, Any]]:
        """
        Получение кешированной информации об инструментах

        Args:
            inst_type: Тип инструмента

        Returns:
            Кешированная информация об инструментах или None
        """
        key = self.redis_keys['instruments'].format(inst_type)
        return self.redis.get(key)

    def get_market_status(self) -> Dict[str, Any]:
        """
        Получение общего статуса рынка и статистики кеша

        Returns:
            Статистика и статус данных
        """
        try:
            inst_types = ['spot', 'swap', 'futures', 'option']
            status = {
                'last_update': self.redis.get(self.redis_keys['last_update']),
                'cache_stats': self.redis.get_stats(),
                'instrument_types': {}
            }

            for inst_type in inst_types:
                key = self.redis_keys[f'tickers_{inst_type}']
                data = self.redis.get(key)
                if data:
                    status['instrument_types'][inst_type] = {
                        'symbols_count': data.get('total_count', 0),
                        'last_update': data.get('timestamp'),
                        'ttl': self.redis.ttl(key)
                    }
                else:
                    status['instrument_types'][inst_type] = {
                        'symbols_count': 0,
                        'last_update': None,
                        'ttl': None
                    }

            return status

        except Exception as e:
            logger.error(f"Error getting market status: {e}")
            return {}

    def search_instruments(self, query: str, inst_type: str = 'SPOT') -> List[Dict[str, Any]]:
        """
        Поиск инструментов по названию

        Args:
            query: Строка для поиска
            inst_type: Тип инструмента для поиска

        Returns:
            Список найденных инструментов
        """
        try:
            instruments_data = self.get_cached_instruments(inst_type)
            if not instruments_data or 'instruments' not in instruments_data:
                # Пробуем получить свежие данные
                fresh_data = self.get_instruments(inst_type)
                if not fresh_data:
                    return []
                instruments_data = fresh_data

            query = query.upper()
            results = []

            for instrument in instruments_data['instruments']:
                inst_id = instrument.get('instId', '')
                if query in inst_id:
                    results.append(instrument)

            return results

        except Exception as e:
            logger.error(f"Error searching instruments: {e}")
            return []

    def health_check(self) -> Dict[str, Any]:
        """
        Проверка здоровья подключения к OKX API

        Returns:
            Статус здоровья
        """
        try:
            # Пробуем получить спот тикеры как тестовый запрос
            response = self.get_tickers('SPOT')

            return {
                'status': 'healthy' if response and response.get('code') == '0' else 'unhealthy',
                'last_api_response': response.get('msg', 'Unknown') if response else 'No response',
                'timestamp': datetime.now().isoformat(),
                'cache_status': self.redis.health_check()
            }
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }