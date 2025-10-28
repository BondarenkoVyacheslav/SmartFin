from typing import Dict, Type
from .base import Provider
from .moex import MoexISSProvider
from .tinkoff.provider import TinkoffProvider

PROVIDERS: Dict[str, Type[Provider]] = {
    "tinkoff": TinkoffProvider,
    "moex": MoexISSProvider,
}

def get_provider(code: str, **kwargs) -> Provider:
    cls = PROVIDERS.get(code)
    if not cls:
        raise ValueError(f"Unknown provider: {code}")
    return cls(**kwargs)


