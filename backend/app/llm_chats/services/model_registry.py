from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from django.conf import settings


@dataclass(frozen=True)
class LLMModelSpec:
    model_id: str
    provider: str
    context_window_tokens: int
    max_output_tokens: int
    max_context_tokens_per_request: int
    default_temperature: float
    title: str


DEFAULT_MODEL_SPECS: dict[str, LLMModelSpec] = {
    "openai:gpt-4o-mini": LLMModelSpec(
        model_id="openai:gpt-4o-mini",
        provider="openai",
        context_window_tokens=128000,
        max_output_tokens=4096,
        max_context_tokens_per_request=20000,
        default_temperature=0.2,
        title="OpenAI GPT-4o mini",
    ),
}


def _load_from_settings() -> dict[str, LLMModelSpec]:
    models_cfg = getattr(settings, "LLM_MODELS", None)
    if not models_cfg:
        return {}
    registry: dict[str, LLMModelSpec] = {}
    for item in models_cfg:
        spec = LLMModelSpec(
            model_id=item["model_id"],
            provider=item["provider"],
            context_window_tokens=int(item["context_window_tokens"]),
            max_output_tokens=int(item.get("max_output_tokens", 2048)),
            max_context_tokens_per_request=int(item.get("max_context_tokens_per_request", 12000)),
            default_temperature=float(item.get("default_temperature", 0.2)),
            title=str(item.get("title", item["model_id"])),
        )
        registry[spec.model_id] = spec
    return registry


def get_model_registry() -> dict[str, LLMModelSpec]:
    registry = DEFAULT_MODEL_SPECS.copy()
    registry.update(_load_from_settings())
    return registry


def get_model_spec(model_id: str) -> LLMModelSpec:
    registry = get_model_registry()
    if model_id not in registry:
        raise ValueError(f"Unknown model_id: {model_id}")
    return registry[model_id]


def list_models() -> Iterable[LLMModelSpec]:
    return get_model_registry().values()


def get_default_model() -> LLMModelSpec:
    registry = get_model_registry()
    default_id = getattr(settings, "LLM_DEFAULT_MODEL", None)
    if default_id and default_id in registry:
        return registry[default_id]
    if registry:
        return next(iter(registry.values()))
    raise ValueError("No LLM models configured")
