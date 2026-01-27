from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.llm.providers import http_provider
from app.llm.providers.base import LLMProviderError, LLMChatRequest, LLMMessagePayload
from app.llm.providers.http_provider import HTTPProvider
from app.llm.providers.proxyapi_provider import ProxyAPIProvider
from app.llm.providers.registry import get_provider
from app.llm.services.model_registry import FIXED_MODEL_ID, list_models, get_default_model


class ModelRegistryTests(unittest.TestCase):
    def test_list_models_single_fixed(self):
        models = list(list_models())
        self.assertEqual(len(models), 1)
        self.assertEqual(models[0].model_id, FIXED_MODEL_ID)
        self.assertEqual(get_default_model().model_id, FIXED_MODEL_ID)


class ProviderRegistryTests(unittest.TestCase):
    def test_get_provider_proxyapi(self):
        with patch.dict(os.environ, {"PROXY_API_KEY": "test-key"}):
            provider = get_provider("proxyapi")
        self.assertEqual(provider.name, "proxyapi")


class ProxyAPIProviderTests(unittest.TestCase):
    def test_send_chat_payload_and_parse(self):
        with patch.dict(os.environ, {"PROXY_API_KEY": "test-key"}):
            provider = ProxyAPIProvider()
        request = LLMChatRequest(
            model=FIXED_MODEL_ID,
            messages=[LLMMessagePayload(role="user", content="Hello")],
            temperature=0.2,
            max_output_tokens=128,
            metadata={"chat_id": 1},
        )
        response_data = {
            "choices": [{"message": {"content": "Hi there"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        with patch.object(ProxyAPIProvider, "_post_json", return_value=response_data) as post_json:
            response = provider.send_chat(request)
        self.assertEqual(response.text, "Hi there")
        self.assertEqual(response.prompt_tokens, 10)
        self.assertEqual(response.completion_tokens, 5)
        self.assertEqual(response.total_tokens, 15)
        args, kwargs = post_json.call_args
        self.assertEqual(args[0], "/chat/completions")
        payload = args[1]
        self.assertEqual(payload["model"], FIXED_MODEL_ID)
        self.assertEqual(payload["messages"], [{"role": "user", "content": "Hello"}])
        self.assertEqual(payload["temperature"], 0.2)
        self.assertEqual(payload["max_tokens"], 128)
        headers = args[2] if len(args) > 2 else kwargs.get("headers", {})
        self.assertIn("Authorization", headers)


@unittest.skipIf(http_provider.httpx is None, "httpx not installed")
class HTTPProviderErrorHandlingTests(unittest.TestCase):
    def test_http_provider_429_and_5xx_retriable(self):
        class DummyResponse:
            def __init__(self, status_code: int):
                self.status_code = status_code
                self.text = "error"

            def json(self):
                return {}

        class DummyClient:
            def __init__(self, response):
                self.response = response

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def post(self, url, json, headers):
                return self.response

        provider = HTTPProvider(base_url="https://example.com", api_key="x", max_retries=0)
        for status_code in (429, 500):
            with self.subTest(status_code=status_code):
                response = DummyResponse(status_code)
                with patch.object(http_provider.httpx, "Client", return_value=DummyClient(response)):
                    with self.assertRaises(LLMProviderError) as ctx:
                        provider._post_json("/chat", payload={}, headers={})
                self.assertTrue(ctx.exception.retriable)
