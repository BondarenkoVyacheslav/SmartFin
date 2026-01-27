from __future__ import annotations

from typing import Type

from app.llm.providers.base import LLMProvider
from app.llm.providers.deepseek_provider import DeepSeekProvider
from app.llm.providers.gemini_provider import GeminiProvider
from app.llm.providers.openai_provider import OpenAIProvider
from app.llm.providers.qwen_provider import QwenProvider


_PROVIDER_MAP: dict[str, Type[LLMProvider]] = {
    OpenAIProvider.name: OpenAIProvider,
    GeminiProvider.name: GeminiProvider,
    QwenProvider.name: QwenProvider,
    DeepSeekProvider.name: DeepSeekProvider,
}


def get_provider(provider_name: str) -> LLMProvider:
    if provider_name not in _PROVIDER_MAP:
        raise ValueError(f"Unknown provider: {provider_name}")
    return _PROVIDER_MAP[provider_name]()
