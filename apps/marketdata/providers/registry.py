from typing import Dict, Type
from .Provider import Provider
from apps.marketdata.providers.StockMarketRussia.moex import MoexISSProvider
from apps.marketdata.providers.StockMarketRussia.tinkoff.provider import TinkoffProvider

PROVIDERS: Dict[str, Type[Provider]] = {
    "tinkoff": TinkoffProvider,
    "moex": MoexISSProvider,
}

def get_provider(code: str, **kwargs) -> Provider:
    cls = PROVIDERS.get(code)
    if not cls:
        raise ValueError(f"Unknown provider: {code}")
    return cls(**kwargs)


