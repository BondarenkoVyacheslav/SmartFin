from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

@dataclass(frozen=True)
class LLMModelSpec:
    model_id: str
    provider: str
    context_window_tokens: int
    max_output_tokens: int
    max_context_tokens_per_request: int
    default_temperature: float
    title: str


PROXYAPI_PROVIDER = "proxyapi"
FIXED_MODEL_ID = "gpt-5.2-chat"
FIXED_MODEL_TITLE = "ChatGPT 5.2"
# Token limits based on existing project defaults.
FIXED_CONTEXT_WINDOW_TOKENS = 128000
FIXED_MAX_OUTPUT_TOKENS = 4096
FIXED_MAX_CONTEXT_TOKENS_PER_REQUEST = 20000
FIXED_DEFAULT_TEMPERATURE = 0.2

FIXED_MODEL_SPEC = LLMModelSpec(
    model_id=FIXED_MODEL_ID,
    provider=PROXYAPI_PROVIDER,
    context_window_tokens=FIXED_CONTEXT_WINDOW_TOKENS,
    max_output_tokens=FIXED_MAX_OUTPUT_TOKENS,
    max_context_tokens_per_request=FIXED_MAX_CONTEXT_TOKENS_PER_REQUEST,
    default_temperature=FIXED_DEFAULT_TEMPERATURE,
    title=FIXED_MODEL_TITLE,
)


def get_model_registry() -> dict[str, LLMModelSpec]:
    return {FIXED_MODEL_SPEC.model_id: FIXED_MODEL_SPEC}


def get_model_spec(model_id: str) -> LLMModelSpec:
    registry = get_model_registry()
    if model_id not in registry:
        raise ValueError(f"Unknown model_id: {model_id}")
    return registry[model_id]


def list_models() -> Iterable[LLMModelSpec]:
    return get_model_registry().values()


def get_default_model() -> LLMModelSpec:
    return FIXED_MODEL_SPEC
