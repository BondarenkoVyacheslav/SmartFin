from redis import asyncio as redis
import json
import pickle
from typing import Any, Optional, Dict, List
from datetime import datetime, timedelta
import logging
import asyncio

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
        self._client = None  # подключение делаем лениво через _ensure_connection

    async def _connect(self):
        """Установка подключения к Redis с retry логикой"""
        for attempt in range(self.max_retries):
            try:
                self._client = redis.from_url(
                    self.redis_url,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                    retry_on_timeout=True,
                    health_check_interval=30,
                )
                # Тестовый ping для проверки подключения
                await self._client.ping()
                logger.info(f"Successfully connected to Redis (attempt {attempt + 1})")
                return
            except Exception as e:
                logger.warning(f"Redis connection attempt {attempt + 1} failed: {e}")
                if attempt == self.max_retries - 1:
                    logger.error(f"All Redis connection attempts failed: {e}")
                    raise
                await asyncio.sleep(1)  # Задержка перед повторной попыткой

    async def _ensure_connection(self):
        """Проверка и восстановление подключения при необходимости"""
        if self._client is None:
            await self._connect()
            return

        try:
            await self._client.ping()
        except (redis.ConnectionError, redis.TimeoutError):
            logger.warning("Redis connection lost, attempting to reconnect...")
            await self._connect()

    async def get(self, key: str, default: Any = None) -> Optional[Any]:
        """
        Получить значение по ключу

        Args:
            key: Ключ
            default: Значение по умолчанию, если ключ не найден

        Returns:
            Десериализованное значение или default
        """
        data = None
        try:
            await self._ensure_connection()
            data = await self._client.get(key)
            if data is None:
                return default
            return json.loads(data)
        except json.JSONDecodeError:
            # Пробуем десериализовать как pickle
            try:
                return pickle.loads(data)
            except Exception:
                logger.error(f"Failed to deserialize data for key {key}")
                return default
        except Exception as e:
            logger.error(f"Redis get error for key {key}: {e}")
            return default

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        serialize_method: str = "json",
    ) -> bool:
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
            await self._ensure_connection()
            ttl = ttl or self.default_ttl

            if serialize_method == "json":
                serialized = json.dumps(value, default=self._json_serializer)
            elif serialize_method == "pickle":
                serialized = pickle.dumps(value)
            else:
                raise ValueError(f"Unsupported serialize method: {serialize_method}")

            return bool(await self._client.setex(key, ttl, serialized))
        except Exception as e:
            logger.error(f"Redis set error for key {key}: {e}")
            return False

    def _json_serializer(self, obj):
        """Кастомный сериализатор для JSON"""
        if isinstance(obj, (datetime, timedelta)):
            return obj.isoformat()
        elif hasattr(obj, "__dict__"):
            return obj.__dict__
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    async def delete(self, key: str) -> bool:
        """Удалить ключ"""
        try:
            await self._ensure_connection()
            return bool(await self._client.delete(key))
        except Exception as e:
            logger.error(f"Redis delete error for key {key}: {e}")
            return False

    async def get_many(self, keys: List[str]) -> Dict[str, Optional[Any]]:
        """
        Получить несколько значений за один запрос

        Args:
            keys: Список ключей

        Returns:
            Словарь {ключ: значение}
        """
        try:
            await self._ensure_connection()
            values = await self._client.mget(keys)
            results: Dict[str, Optional[Any]] = {}

            for key, value in zip(keys, values):
                if value is not None:
                    try:
                        results[key] = json.loads(value)
                    except json.JSONDecodeError:
                        try:
                            results[key] = pickle.loads(value)
                        except Exception:
                            logger.error(f"Failed to deserialize data for key {key}")
                            results[key] = None
                else:
                    results[key] = None

            return results
        except Exception as e:
            logger.error(f"Redis get_many error for keys {keys}: {e}")
            return {key: None for key in keys}

    async def set_many(self, data: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """
        Установить несколько значений

        Args:
            data: Словарь {ключ: значение}
            ttl: Время жизни в секундах

        Returns:
            True если все операции успешны
        """
        success = True

        try:
            await self._ensure_connection()
            ttl = ttl or self.default_ttl

            pipeline = self._client.pipeline()
            for key, value in data.items():
                serialized = json.dumps(value, default=self._json_serializer)
                pipeline.setex(key, ttl, serialized)

            await pipeline.execute()
        except Exception as e:
            logger.error(f"Redis set_many error: {e}")
            success = False

        return success

    async def exists(self, key: str) -> bool:
        """Проверить существование ключа"""
        try:
            await self._ensure_connection()
            return bool(await self._client.exists(key))
        except Exception as e:
            logger.error(f"Redis exists error for key {key}: {e}")
            return False

    async def ttl(self, key: str) -> Optional[int]:
        """Получить оставшееся время жизни ключа"""
        try:
            await self._ensure_connection()
            ttl_val = await self._client.ttl(key)
            return ttl_val if ttl_val >= 0 else None
        except Exception as e:
            logger.error(f"Redis ttl error for key {key}: {e}")
            return None

    async def expire(self, key: str, ttl: int) -> bool:
        """Установить TTL для ключа"""
        try:
            await self._ensure_connection()
            return bool(await self._client.expire(key, ttl))
        except Exception as e:
            logger.error(f"Redis expire error for key {key}: {e}")
            return False

    async def keys(self, pattern: str = "*") -> List[str]:
        """Найти ключи по паттерну"""
        try:
            await self._ensure_connection()
            return await self._client.keys(pattern)
        except Exception as e:
            logger.error(f"Redis keys error for pattern {pattern}: {e}")
            return []

    async def delete_many(self, keys: List[str]) -> int:
        """Удалить несколько ключей"""
        try:
            await self._ensure_connection()
            if not keys:
                return 0
            return await self._client.delete(*keys)
        except Exception as e:
            logger.error(f"Redis delete_many error for {len(keys)} keys: {e}")
            return 0

    async def delete_pattern(self, pattern: str) -> int:
        """Удалить все ключи по паттерну"""
        try:
            await self._ensure_connection()
            keys = await self.keys(pattern)
            if keys:
                return await self.delete_many(keys)
            return 0
        except Exception as e:
            logger.error(f"Redis delete_pattern error for pattern {pattern}: {e}")
            return 0

    async def increment(
        self, key: str, amount: int = 1, ttl: Optional[int] = None
    ) -> Optional[int]:
        """Инкремент числового значения"""
        try:
            await self._ensure_connection()
            pipeline = self._client.pipeline()
            pipeline.incrby(key, amount)
            if ttl:
                pipeline.expire(key, ttl)
            results = await pipeline.execute()
            return results[0] if results else None
        except Exception as e:
            logger.error(f"Redis increment error for key {key}: {e}")
            return None

    async def decrement(
        self, key: str, amount: int = 1, ttl: Optional[int] = None
    ) -> Optional[int]:
        """Декремент числового значения"""
        try:
            await self._ensure_connection()
            pipeline = self._client.pipeline()
            pipeline.decrby(key, amount)
            if ttl:
                pipeline.expire(key, ttl)
            results = await pipeline.execute()
            return results[0] if results else None
        except Exception as e:
            logger.error(f"Redis decrement error for key {key}: {e}")
            return None

    async def hash_set(self, key: str, field: str, value: Any) -> bool:
        """Установить значение в hash"""
        try:
            await self._ensure_connection()
            serialized = json.dumps(value, default=self._json_serializer)
            return bool(await self._client.hset(key, field, serialized))
        except Exception as e:
            logger.error(f"Redis hash_set error for key {key}.{field}: {e}")
            return False

    async def hash_get(self, key: str, field: str, default: Any = None) -> Any:
        """Получить значение из hash"""
        try:
            await self._ensure_connection()
            data = await self._client.hget(key, field)
            if data is None:
                return default
            return json.loads(data)
        except Exception as e:
            logger.error(f"Redis hash_get error for key {key}.{field}: {e}")
            return default

    async def hash_get_all(self, key: str) -> Dict[str, Any]:
        """Получить все поля hash"""
        try:
            await self._ensure_connection()
            data = await self._client.hgetall(key)
            result: Dict[str, Any] = {}
            for field, value in data.items():
                field_key = field.decode() if isinstance(field, bytes) else field
                result[field_key] = json.loads(value)
            return result
        except Exception as e:
            logger.error(f"Redis hash_get_all error for key {key}: {e}")
            return {}

    async def list_push(
        self, key: str, value: Any, side: str = "right", ttl: Optional[int] = None
    ) -> bool:
        """Добавить элемент в список"""
        try:
            await self._ensure_connection()
            serialized = json.dumps(value, default=self._json_serializer)

            pipeline = self._client.pipeline()
            if side == "right":
                pipeline.rpush(key, serialized)
            else:
                pipeline.lpush(key, serialized)

            if ttl:
                pipeline.expire(key, ttl)

            await pipeline.execute()
            return True
        except Exception as e:
            logger.error(f"Redis list_push error for key {key}: {e}")
            return False

    async def list_range(self, key: str, start: int = 0, end: int = -1) -> List[Any]:
        """Получить диапазон элементов списка"""
        try:
            await self._ensure_connection()
            data = await self._client.lrange(key, start, end)
            return [json.loads(item) for item in data]
        except Exception as e:
            logger.error(f"Redis list_range error for key {key}: {e}")
            return []

    async def health_check(self) -> Dict[str, Any]:
        """Проверка здоровья Redis подключения"""
        try:
            await self._ensure_connection()
            info = await self._client.info()
            return {
                "status": "healthy",
                "connected_clients": info.get("connected_clients", 0),
                "used_memory": info.get("used_memory", 0),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    async def clear_all(self) -> bool:
        """Очистить всю базу (осторожно!)"""
        try:
            await self._ensure_connection()
            return bool(await self._client.flushdb())
        except Exception as e:
            logger.error(f"Redis clear_all error: {e}")
            return False

    async def get_stats(self) -> Dict[str, Any]:
        """Получить статистику использования кеша"""
        try:
            await self._ensure_connection()
            info = await self._client.info()
            db_stats = info.get("db0", {})

            return {
                "total_keys": db_stats.get("keys", 0),
                "expires": db_stats.get("expires", 0),
                "avg_ttl": db_stats.get("avg_ttl", 0),
                "hit_rate": self._calculate_hit_rate(info),
                "memory_usage": info.get("used_memory_human", "0"),
                "connected_clients": info.get("connected_clients", 0),
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.error(f"Redis get_stats error: {e}")
            return {}

    def _calculate_hit_rate(self, info: Dict) -> float:
        """Рассчитать hit rate"""
        hits = info.get("keyspace_hits", 0)
        misses = info.get("keyspace_misses", 0)
        total = hits + misses
        return (hits / total * 100) if total > 0 else 0.0
