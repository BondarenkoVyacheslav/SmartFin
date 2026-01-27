from __future__ import annotations

from typing import Any

from app.llm_chats.providers.base import LLMChatRequest, LLMChatResponse, LLMProviderError
from app.llm_chats.providers.config import get_env, get_provider_config
from app.llm_chats.providers.http_provider import HTTPProvider


class GeminiProvider(HTTPProvider):
    name = "gemini"

    def __init__(self):
        cfg = get_provider_config(self.name)
        api_key = cfg.get("api_key") or get_env("GEMINI_API_KEY")
        base_url = cfg.get("base_url") or get_env("GEMINI_BASE_URL")
        path = cfg.get("chat_path") or get_env("GEMINI_CHAT_PATH")
        if not api_key or not base_url or not path:
            raise LLMProviderError(
                code="missing_config",
                message="Gemini provider configuration is missing",
                retriable=False,
            )
        self.chat_path = path
        super().__init__(base_url=base_url, api_key=api_key,
                         timeout_s=float(cfg.get("timeout_s", 30)),
                         max_retries=int(cfg.get("max_retries", 2)))

    def send_chat(self, request: LLMChatRequest) -> LLMChatResponse:
        payload = {
            "model": request.model,
            "contents": [
                {"role": msg.role, "parts": [{"text": msg.content}]}
                for msg in request.messages
            ],
            "generationConfig": {
                "temperature": request.temperature,
                "maxOutputTokens": request.max_output_tokens,
            },
        }
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
        }
        data = self._post_json(self.chat_path, payload, headers=headers)
        return _parse_gemini_response(data)


def _parse_gemini_response(data: dict[str, Any]) -> LLMChatResponse:
    candidates = data.get("candidates", [])
    text = ""
    if candidates:
        content = candidates[0].get("content", {})
        parts = content.get("parts", [])
        if parts:
            text = parts[0].get("text", "")
    usage = data.get("usageMetadata", {})
    prompt_tokens = int(usage.get("promptTokenCount", 0))
    completion_tokens = int(usage.get("candidatesTokenCount", 0))
    total_tokens = int(usage.get("totalTokenCount", prompt_tokens + completion_tokens))
    return LLMChatResponse(
        text=text,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        raw=data,
    )
