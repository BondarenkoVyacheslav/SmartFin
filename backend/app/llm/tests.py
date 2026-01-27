from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model

from config.shcema import schema
from app.llm.models import LLMChat, TokenUsage
from app.llm.providers.base import LLMChatResponse, LLMProvider, LLMProviderError, LLMChatRequest, LLMMessagePayload
from app.llm.providers.http_provider import HTTPProvider
from app.llm.providers.proxyapi_provider import ProxyAPIProvider
from app.llm.providers.registry import get_provider
from app.llm.services.chat_service import ChatService
from app.llm.services.model_registry import FIXED_MODEL_ID, list_models, get_default_model


class StubProvider(LLMProvider):
    name = "stub"

    def send_chat(self, request):
        return LLMChatResponse(
            text="stub reply",
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            raw={"stub": True},
        )


class LLMChatServiceTests(TestCase):
    def setUp(self):
        self.User = get_user_model()
        self.user = self.User.objects.create_user(
            email="user@example.com",
            username="user",
            password="pass1234",
        )

    def test_create_chat(self):
        chat = ChatService.create_chat(user=self.user, title="Test")
        self.assertIsInstance(chat, LLMChat)
        self.assertEqual(chat.settings.model_id, FIXED_MODEL_ID)

    def test_send_message_records_usage(self):
        chat = ChatService.create_chat(user=self.user, title="Test")
        with patch("app.llm.services.chat_service.get_provider", return_value=StubProvider()):
            result = ChatService.send_message(user=self.user, chat=chat, content="Hello")
        self.assertEqual(result.assistant_message.content, "stub reply")
        usage_rows = TokenUsage.objects.filter(user=self.user, usage_type=TokenUsage.UsageType.MESSAGE)
        self.assertEqual(usage_rows.count(), 1)
        aggregate_rows = TokenUsage.objects.filter(user=self.user, usage_type=TokenUsage.UsageType.DAILY)
        self.assertEqual(aggregate_rows.count(), 1)

    def test_graphql_send_message(self):
        chat = ChatService.create_chat(user=self.user, title="GraphQL")
        mutation = """
            mutation SendMsg($chatId: Int!, $content: String!) {
                sendLlmMessage(chatId: $chatId, content: $content) {
                    message { id content }
                    usage { totalTokens }
                }
            }
        """
        ctx = SimpleNamespace(request=SimpleNamespace(user=self.user))
        with patch("app.llm.services.chat_service.get_provider", return_value=StubProvider()):
            result = schema.execute_sync(
                mutation,
                variable_values={"chatId": chat.id, "content": "Hi"},
                context_value=ctx,
            )
        self.assertIsNone(result.errors)
        payload = result.data["sendLlmMessage"]
        self.assertEqual(payload["message"]["content"], "stub reply")


class ModelRegistryTests(TestCase):
    def test_list_models_single_fixed(self):
        models = list(list_models())
        self.assertEqual(len(models), 1)
        self.assertEqual(models[0].model_id, FIXED_MODEL_ID)
        self.assertEqual(get_default_model().model_id, FIXED_MODEL_ID)


class ProviderRegistryTests(TestCase):
    @override_settings(LLM_PROXYAPI_KEY="test-key")
    def test_get_provider_proxyapi(self):
        provider = get_provider("proxyapi")
        self.assertIsInstance(provider, ProxyAPIProvider)


class ProxyAPIProviderTests(TestCase):
    @override_settings(LLM_PROXYAPI_KEY="test-key")
    def test_send_chat_payload_and_parse(self):
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


class HTTPProviderErrorHandlingTests(TestCase):
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
                with patch("app.llm.providers.http_provider.httpx.Client", return_value=DummyClient(response)):
                    with self.assertRaises(LLMProviderError) as ctx:
                        provider._post_json("/chat", payload={}, headers={})
                self.assertTrue(ctx.exception.retriable)
