import redis
import json
import pickle
from typing import Any, Optional, Dict, List, Union
from datetime import datetime, timedelta
import logging
from functools import wraps
import time

logger = logging.getLogger(__name__)


class RedisCacheService:
    """
    Универсальный сервис для работы с Redis кешем.
    Поддерживает различные стратегии сериализации, экспирации и обработки ошибок.
    """

    def __init__(self, redis_url: str, default_ttl: int = 300, max_retries: int = 3):
        """
        Args:
            redis_url: URL для подключения к Redis
            default_ttl: TTL по умолчанию в секундах (5 минут)
            max_retries: Максимальное количество попыток переподключения
        """
        self.redis_url = redis_url
        self.default_ttl = default_ttl
        self.max_retries = max_retries
        self._client = None
        self._connect()

    def _connect(self):
        """Установка подключения к Redis с retry логикой"""
        for attempt in range(self.max_retries):
            try:
                self._client = redis.from_url(
                    self.redis_url,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                    retry_on_timeout=True,
                    health_check_interval=30
                )
                # Тестовый ping для проверки подключения
                self._client.ping()
                logger.info(f"Successfully connected to Redis (attempt {attempt + 1})")
                return
            except Exception as e:
                logger.warning(f"Redis connection attempt {attempt + 1} failed: {e}")
                if attempt == self.max_retries - 1:
                    logger.error(f"All Redis connection attempts failed: {e}")
                    raise
                time.sleep(1)  # Задержка перед повторной попыткой

    def _ensure_connection(self):
        """Проверка и восстановление подключения при необходимости"""
        try:
            self._client.ping()
        except (redis.ConnectionError, redis.TimeoutError):
            logger.warning("Redis connection lost, attempting to reconnect...")
            self._connect()

    def get(self, key: str, default: Any = None) -> Optional[Any]:
        """
        Получить значение по ключу

        Args:
            key: Ключ
            default: Значение по умолчанию, если ключ не найден

        Returns:
            Десериализованное значение или default
        """
        try:
            self._ensure_connection()
            data = self._client.get(key)
            if data is None:
                return default
            return json.loads(data)
        except json.JSONDecodeError:
            # Пробуем десериализовать как pickle
            try:
                return pickle.loads(data)
            except:
                logger.error(f"Failed to deserialize data for key {key}")
                return default
        except Exception as e:
            logger.error(f"Redis get error for key {key}: {e}")
            return default

    def set(self, key: str, value: Any, ttl: Optional[int] = None,
            serialize_method: str = 'json') -> bool:
        """
        Установить значение по ключу

        Args:
            key: Ключ
            value: Значение для сохранения
            ttl: Время жизни в секундах
            serialize_method: Метод сериализации ('json' или 'pickle')

        Returns:
            True если успешно, False в случае ошибки
        """
        try:
            self._ensure_connection()
            ttl = ttl or self.default_ttl

            if serialize_method == 'json':
                serialized = json.dumps(value, default=self._json_serializer)
            elif serialize_method == 'pickle':
                serialized = pickle.dumps(value)
            else:
                raise ValueError(f"Unsupported serialize method: {serialize_method}")

            return bool(self._client.setex(key, ttl, serialized))
        except Exception as e:
            logger.error(f"Redis set error for key {key}: {e}")
            return False

    def _json_serializer(self, obj):
        """Кастомный сериализатор для JSON"""
        if isinstance(obj, (datetime, timedelta)):
            return obj.isoformat()
        elif hasattr(obj, '__dict__'):
            return obj.__dict__
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    def delete(self, key: str) -> bool:
        """Удалить ключ"""
        try:
            self._ensure_connection()
            return bool(self._client.delete(key))
        except Exception as e:
            logger.error(f"Redis delete error for key {key}: {e}")
            return False

    def get_many(self, keys: List[str]) -> Dict[str, Optional[Any]]:
        """
        Получить несколько значений за один запрос

        Args:
            keys: Список ключей

        Returns:
            Словарь {ключ: значение}
        """
        try:
            self._ensure_connection()
            values = self._client.mget(keys)
            results = {}

            for key, value in zip(keys, values):
                if value is not None:
                    try:
                        results[key] = json.loads(value)
                    except json.JSONDecodeError:
                        try:
                            results[key] = pickle.loads(value)
                        except:
                            logger.error(f"Failed to deserialize data for key {key}")
                            results[key] = None
                else:
                    results[key] = None

            return results
        except Exception as e:
            logger.error(f"Redis get_many error for keys {keys}: {e}")
            return {key: None for key in keys}

    def set_many(self, data: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """
        Установить несколько значений

        Args:
            data: Словарь {ключ: значение}
            ttl: Время жизни в секундах

        Returns:
            True если все операции успешны
        """
        success = True
        pipeline = self._client.pipeline()

        try:
            self._ensure_connection()
            ttl = ttl or self.default_ttl

            for key, value in data.items():
                serialized = json.dumps(value, default=self._json_serializer)
                pipeline.setex(key, ttl, serialized)

            pipeline.execute()
        except Exception as e:
            logger.error(f"Redis set_many error: {e}")
            success = False

        return success

    def exists(self, key: str) -> bool:
        """Проверить существование ключа"""
        try:
            self._ensure_connection()
            return bool(self._client.exists(key))
        except Exception as e:
            logger.error(f"Redis exists error for key {key}: {e}")
            return False

    def ttl(self, key: str) -> Optional[int]:
        """Получить оставшееся время жизни ключа"""
        try:
            self._ensure_connection()
            ttl = self._client.ttl(key)
            return ttl if ttl >= 0 else None
        except Exception as e:
            logger.error(f"Redis ttl error for key {key}: {e}")
            return None

    def expire(self, key: str, ttl: int) -> bool:
        """Установить TTL для ключа"""
        try:
            self._ensure_connection()
            return bool(self._client.expire(key, ttl))
        except Exception as e:
            logger.error(f"Redis expire error for key {key}: {e}")
            return False

    def keys(self, pattern: str = "*") -> List[str]:
        """Найти ключи по паттерну"""
        try:
            self._ensure_connection()
            return self._client.keys(pattern)
        except Exception as e:
            logger.error(f"Redis keys error for pattern {pattern}: {e}")
            return []

    def delete_many(self, keys: List[str]) -> int:
        """Удалить несколько ключей"""
        try:
            self._ensure_connection()
            if not keys:
                return 0
            return self._client.delete(*keys)
        except Exception as e:
            logger.error(f"Redis delete_many error for {len(keys)} keys: {e}")
            return 0

    def delete_pattern(self, pattern: str) -> int:
        """Удалить все ключи по паттерну"""
        try:
            self._ensure_connection()
            keys = self.keys(pattern)
            if keys:
                return self.delete_many(keys)
            return 0
        except Exception as e:
            logger.error(f"Redis delete_pattern error for pattern {pattern}: {e}")
            return 0

    def increment(self, key: str, amount: int = 1, ttl: Optional[int] = None) -> Optional[int]:
        """Инкремент числового значения"""
        try:
            self._ensure_connection()
            pipeline = self._client.pipeline()
            result = pipeline.incrby(key, amount)
            if ttl:
                pipeline.expire(key, ttl)
            pipeline.execute()
            return result
        except Exception as e:
            logger.error(f"Redis increment error for key {key}: {e}")
            return None

    def decrement(self, key: str, amount: int = 1, ttl: Optional[int] = None) -> Optional[int]:
        """Декремент числового значения"""
        try:
            self._ensure_connection()
            pipeline = self._client.pipeline()
            result = pipeline.decrby(key, amount)
            if ttl:
                pipeline.expire(key, ttl)
            pipeline.execute()
            return result
        except Exception as e:
            logger.error(f"Redis decrement error for key {key}: {e}")
            return None

    def hash_set(self, key: str, field: str, value: Any) -> bool:
        """Установить значение в hash"""
        try:
            self._ensure_connection()
            serialized = json.dumps(value, default=self._json_serializer)
            return bool(self._client.hset(key, field, serialized))
        except Exception as e:
            logger.error(f"Redis hash_set error for key {key}.{field}: {e}")
            return False

    def hash_get(self, key: str, field: str, default: Any = None) -> Any:
        """Получить значение из hash"""
        try:
            self._ensure_connection()
            data = self._client.hget(key, field)
            if data is None:
                return default
            return json.loads(data)
        except Exception as e:
            logger.error(f"Redis hash_get error for key {key}.{field}: {e}")
            return default

    def hash_get_all(self, key: str) -> Dict[str, Any]:
        """Получить все поля hash"""
        try:
            self._ensure_connection()
            data = self._client.hgetall(key)
            result = {}
            for field, value in data.items():
                result[field.decode() if isinstance(field, bytes) else field] = json.loads(value)
            return result
        except Exception as e:
            logger.error(f"Redis hash_get_all error for key {key}: {e}")
            return {}

    def list_push(self, key: str, value: Any, side: str = 'right', ttl: Optional[int] = None) -> bool:
        """Добавить элемент в список"""
        try:
            self._ensure_connection()
            serialized = json.dumps(value, default=self._json_serializer)

            pipeline = self._client.pipeline()
            if side == 'right':
                pipeline.rpush(key, serialized)
            else:
                pipeline.lpush(key, serialized)

            if ttl:
                pipeline.expire(key, ttl)

            pipeline.execute()
            return True
        except Exception as e:
            logger.error(f"Redis list_push error for key {key}: {e}")
            return False

    def list_range(self, key: str, start: int = 0, end: int = -1) -> List[Any]:
        """Получить диапазон элементов списка"""
        try:
            self._ensure_connection()
            data = self._client.lrange(key, start, end)
            return [json.loads(item) for item in data]
        except Exception as e:
            logger.error(f"Redis list_range error for key {key}: {e}")
            return []

    def health_check(self) -> Dict[str, Any]:
        """Проверка здоровья Redis подключения"""
        try:
            self._ensure_connection()
            info = self._client.info()
            return {
                'status': 'healthy',
                'connected_clients': info.get('connected_clients', 0),
                'used_memory': info.get('used_memory', 0),
                'keyspace_hits': info.get('keyspace_hits', 0),
                'keyspace_misses': info.get('keyspace_misses', 0),
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }

    def clear_all(self) -> bool:
        """Очистить всю базу (осторожно!)"""
        try:
            self._ensure_connection()
            return bool(self._client.flushdb())
        except Exception as e:
            logger.error(f"Redis clear_all error: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику использования кеша"""
        try:
            self._ensure_connection()
            info = self._client.info()
            db_stats = info.get('db0', {})

            return {
                'total_keys': db_stats.get('keys', 0),
                'expires': db_stats.get('expires', 0),
                'avg_ttl': db_stats.get('avg_ttl', 0),
                'hit_rate': self._calculate_hit_rate(info),
                'memory_usage': info.get('used_memory_human', '0'),
                'connected_clients': info.get('connected_clients', 0),
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Redis get_stats error: {e}")
            return {}

    def _calculate_hit_rate(self, info: Dict) -> float:
        """Рассчитать hit rate"""
        hits = info.get('keyspace_hits', 0)
        misses = info.get('keyspace_misses', 0)
        total = hits + misses
        return (hits / total * 100) if total > 0 else 0.0


# Декоратор для кеширования результатов функций
def cached(ttl: int = 300, key_prefix: str = "func_cache"):
    """
    Декоратор для кеширования результатов функций в Redis

    Args:
        ttl: Время жизни кеша в секундах
        key_prefix: Префикс для ключей кеша
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Создаем уникальный ключ на основе функции и аргументов
            cache_key = f"{key_prefix}:{func.__name__}:{str(args)}:{str(kwargs)}"

            # Пробуем получить из кеша
            cache_service = wrapper.cache_service
            cached_result = cache_service.get(cache_key)

            if cached_result is not None:
                return cached_result

            # Выполняем функцию и кешируем результат
            result = func(*args, **kwargs)
            cache_service.set(cache_key, result, ttl=ttl)

            return result

        return wrapper

    return decorator


# Глобальный экземпляр (опционально)
_global_cache_instance = None


def get_redis_cache(redis_url: str = None, **kwargs) -> RedisCacheService:
    """Фабричная функция для получения экземпляра RedisCacheService"""
    global _global_cache_instance

    if _global_cache_instance is None:
        redis_url = redis_url or os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        _global_cache_instance = RedisCacheService(redis_url, **kwargs)

    return _global_cache_instance