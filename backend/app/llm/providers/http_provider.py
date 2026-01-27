from __future__ import annotations

import time
import logging
from typing import Any

try:
    import httpx
except Exception:  # pragma: no cover - optional dependency for lightweight tests
    httpx = None

from app.llm.providers.base import LLMProvider, LLMProviderError


class HTTPProvider(LLMProvider):
    name = "http"

    def __init__(self, base_url: str, api_key: str, *, timeout_s: float = 30.0, max_retries: int = 2):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_s = timeout_s
        self.max_retries = max_retries

    def _post_json(self, path: str, payload: dict[str, Any], headers: dict[str, str] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        headers = headers or {}
        last_error: Exception | None = None
        logger = logging.getLogger(__name__)

        if httpx is None:
            raise LLMProviderError(
                code="missing_dependency",
                message="httpx is required to perform HTTP requests",
                retriable=False,
            )

        for attempt in range(self.max_retries + 1):
            try:
                with httpx.Client(timeout=self.timeout_s) as client:
                    response = client.post(url, json=payload, headers=headers)
                if response.status_code >= 500:
                    logger.warning("LLM provider 5xx response", extra={"status": response.status_code})
                    raise LLMProviderError(
                        code="upstream_5xx",
                        message=f"Upstream error {response.status_code}",
                        retriable=True,
                        status_code=response.status_code,
                    )
                if response.status_code in (429, 408):
                    logger.warning("LLM provider rate limit or timeout", extra={"status": response.status_code})
                    raise LLMProviderError(
                        code="rate_limited",
                        message=f"Rate limited {response.status_code}",
                        retriable=True,
                        status_code=response.status_code,
                    )
                if response.status_code >= 400:
                    logger.error("LLM provider bad request", extra={"status": response.status_code})
                    raise LLMProviderError(
                        code="bad_request",
                        message=response.text,
                        retriable=False,
                        status_code=response.status_code,
                    )
                return response.json()
            except LLMProviderError as exc:
                last_error = exc
                if not exc.retriable or attempt >= self.max_retries:
                    raise
            except httpx.RequestError as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    raise LLMProviderError(code="network_error", message=str(exc), retriable=True) from exc
            logger.info("Retrying LLM provider request", extra={"attempt": attempt + 1, "url": url})
            time.sleep(0.5 * (attempt + 1))

        raise LLMProviderError(code="unknown_error", message=str(last_error) if last_error else "unknown")
