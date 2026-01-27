from __future__ import annotations

from typing import Type

from app.llm.providers.base import LLMProvider
from app.llm.providers.proxyapi_provider import ProxyAPIProvider


_PROVIDER_MAP: dict[str, Type[LLMProvider]] = {
    ProxyAPIProvider.name: ProxyAPIProvider,
}


def get_provider(provider_name: str) -> LLMProvider:
    if provider_name not in _PROVIDER_MAP:
        raise ValueError(f"Unknown provider: {provider_name}")
    return _PROVIDER_MAP[provider_name]()
