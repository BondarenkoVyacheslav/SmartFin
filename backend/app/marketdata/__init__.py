from django.utils.functional import LazyObject


def _load_market_data_api():
    from .api import MarketDataAPI

    return MarketDataAPI()


class _LazyMarketDataApi(LazyObject):
    def _setup(self):
        self._wrapped = _load_market_data_api()


market_data_api = _LazyMarketDataApi()

__all__ = ["market_data_api"]
