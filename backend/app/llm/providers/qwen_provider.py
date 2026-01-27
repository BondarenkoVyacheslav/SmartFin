from __future__ import annotations

from typing import Any

from app.llm.providers.base import LLMChatRequest, LLMChatResponse, LLMProviderError
from app.llm.providers.config import get_env, get_provider_config
from app.llm.providers.http_provider import HTTPProvider


class QwenProvider(HTTPProvider):
    name = "qwen"

    def __init__(self):
        cfg = get_provider_config(self.name)
        api_key = cfg.get("api_key") or get_env("QWEN_API_KEY")
        base_url = cfg.get("base_url") or get_env("QWEN_BASE_URL")
        path = cfg.get("chat_path") or get_env("QWEN_CHAT_PATH")
        if not api_key or not base_url or not path:
            raise LLMProviderError(
                code="missing_config",
                message="Qwen provider configuration is missing",
                retriable=False,
            )
        self.chat_path = path
        super().__init__(base_url=base_url, api_key=api_key,
                         timeout_s=float(cfg.get("timeout_s", 30)),
                         max_retries=int(cfg.get("max_retries", 2)))

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
        return _parse_chat_response(data)


def _parse_chat_response(data: dict[str, Any]) -> LLMChatResponse:
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
