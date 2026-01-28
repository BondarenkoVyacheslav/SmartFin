try:
    from django.utils.functional import LazyObject
except ModuleNotFoundError:  # pragma: no cover - used in non-Django test runs
    class LazyObject:
        _wrapped = None

        def _setup(self):
            raise NotImplementedError

        def __getattr__(self, name):
            if self._wrapped is None:
                self._setup()
            return getattr(self._wrapped, name)

        def __setattr__(self, name, value):
            if name == "_wrapped":
                object.__setattr__(self, name, value)
                return
            if self._wrapped is None:
                self._setup()
            setattr(self._wrapped, name, value)

from .router import AssetPriceRequest, AssetPriceResult, MarketDataRouter

__all__ = [
    "AssetPriceRequest",
    "AssetPriceResult",
    "MarketDataRouter",
]
