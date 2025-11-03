from .api import MarketDataAPI
import os

# Создаем глобальный экземпляр API
market_data_api = MarketDataAPI()

# Экспортируем основной API класс и экземпляр
__all__ = ['MarketDataAPI', 'market_data_api']