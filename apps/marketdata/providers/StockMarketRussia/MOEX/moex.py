from apps.marketdata.providers.provider import Provider
from apps.marketdata.services.redis_cache import RedisCacheService


class MOEXProvider(Provider):

    def __init__(self, cache: RedisCacheService):
        self.cache = cache
