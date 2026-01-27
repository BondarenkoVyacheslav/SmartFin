from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class LLMMessagePayload:
    role: str
    content: str


@dataclass
class LLMChatRequest:
    model: str
    messages: list[LLMMessagePayload]
    temperature: float
    max_output_tokens: int
    metadata: dict[str, Any] | None = None


@dataclass
class LLMChatResponse:
    text: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    raw: dict[str, Any] | None = None


class LLMProviderError(RuntimeError):
    def __init__(self, code: str, message: str, *, retriable: bool = False, status_code: int | None = None):
        super().__init__(message)
        self.code = code
        self.retriable = retriable
        self.status_code = status_code


class LLMProvider:
    name = "base"

    def send_chat(self, request: LLMChatRequest) -> LLMChatResponse:
        raise NotImplementedError
