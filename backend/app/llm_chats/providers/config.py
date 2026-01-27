from __future__ import annotations

import os

from django.conf import settings


def get_provider_config(provider: str) -> dict:
    config = getattr(settings, "LLM_PROVIDER_CONFIG", {})
    provider_cfg = config.get(provider, {}) if isinstance(config, dict) else {}
    return provider_cfg


def get_env(name: str) -> str | None:
    value = os.environ.get(name)
    if value:
        return value
    return None
