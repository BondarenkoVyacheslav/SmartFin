from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model

from config.shcema import schema
from app.llm.models import LLMChat, TokenUsage
from app.llm.providers.base import LLMChatResponse, LLMProvider
from app.llm.services.chat_service import ChatService


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


@override_settings(
    LLM_MODELS=[
        {
            "model_id": "stub:local",
            "provider": "stub",
            "context_window_tokens": 8000,
            "max_output_tokens": 512,
            "max_context_tokens_per_request": 4000,
            "default_temperature": 0.1,
            "title": "Stub Model",
        }
    ],
    LLM_DEFAULT_MODEL="stub:local",
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
        self.assertEqual(chat.settings.model_id, "stub:local")

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
