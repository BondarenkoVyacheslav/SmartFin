from __future__ import annotations

import os
from typing import Any

try:
    from django.conf import settings as django_settings
except Exception:  # pragma: no cover - fallback for non-Django environments
    django_settings = None

from app.llm.providers.base import LLMChatRequest, LLMChatResponse, LLMProviderError
from app.llm.providers.http_provider import HTTPProvider


class ProxyAPIProvider(HTTPProvider):
    name = "proxyapi"
    chat_path = "/chat/completions"

    def __init__(self) -> None:
        use_django_settings = django_settings is not None and getattr(django_settings, "configured", False)
        base_url = getattr(django_settings, "LLM_PROXYAPI_BASE_URL", None) if use_django_settings else None
        if not base_url:
            base_url = "https://api.proxyapi.ru/openai/v1"
        api_key = getattr(django_settings, "LLM_PROXYAPI_KEY", None) if use_django_settings else None
        if not api_key:
            api_key = os.environ.get("PROXY_API_KEY") or os.environ.get("PROXYAPI_KEY")
        if not api_key:
            raise LLMProviderError(
                code="missing_config",
                message="ProxyAPI key is missing (LLM_PROXYAPI_KEY)",
                retriable=False,
            )
        timeout_s = float(getattr(django_settings, "LLM_PROXYAPI_TIMEOUT_S", 30)) if use_django_settings else 30
        max_retries = int(getattr(django_settings, "LLM_PROXYAPI_MAX_RETRIES", 2)) if use_django_settings else 2
        super().__init__(base_url=base_url, api_key=api_key, timeout_s=timeout_s, max_retries=max_retries)

    def send_chat(self, request: LLMChatRequest) -> LLMChatResponse:
        payload = {
            "model": request.model,
            "messages": [msg.__dict__ for msg in request.messages],
            "temperature": request.temperature,
            "max_tokens": request.max_output_tokens,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        data = self._post_json(self.chat_path, payload, headers=headers)
        return _parse_openai_response(data)


def _parse_openai_response(data: dict[str, Any]) -> LLMChatResponse:
    choices = data.get("choices", [])
    message = choices[0].get("message", {}) if choices else {}
    text = message.get("content", "")
    usage = data.get("usage", {})
    prompt_tokens = int(usage.get("prompt_tokens", 0))
    completion_tokens = int(usage.get("completion_tokens", 0))
    total_tokens = int(usage.get("total_tokens", prompt_tokens + completion_tokens))
    return LLMChatResponse(
        text=text,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        raw=data,
    )
