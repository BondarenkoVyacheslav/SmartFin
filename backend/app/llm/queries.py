from __future__ import annotations

from typing import List

import strawberry
from strawberry import auto

from app.llm.models import LLMChat, LLMMessage, ChatSettings
from app.llm.services.chat_service import ChatService
from app.llm.services.model_registry import list_models
from app.llm.services.token_accounting import calculate_token_limits, estimate_message_tokens
from app.llm.services.prompt_templates import build_system_prompt, build_context_prompt
from app.llm.services.context_builder import build_context_pack


@strawberry.django.type(ChatSettings)
class ChatSettingsType:
    id: auto
    model_id: auto
    provider: auto
    temperature: auto
    max_context_tokens_per_request: auto
    max_output_tokens: auto
    context_window_tokens: auto
    system_prompt: auto
    context_mode: auto
    created_at: auto
    updated_at: auto


@strawberry.django.type(LLMChat)
class LLMChatType:
    id: auto
    title: auto
    mode: auto
    is_archived: auto
    created_at: auto
    updated_at: auto
    last_message_at: auto
    settings: ChatSettingsType


@strawberry.django.type(LLMMessage)
class LLMMessageType:
    id: auto
    chat: LLMChatType
    role: auto
    content: auto
    status: auto
    provider: auto
    model_id: auto
    prompt_tokens: auto
    completion_tokens: auto
    total_tokens: auto
    created_at: auto
    error_code: auto
    error_message: auto


@strawberry.type
class LLMModelType:
    model_id: str
    provider: str
    context_window_tokens: int
    max_output_tokens: int
    max_context_tokens_per_request: int
    default_temperature: float
    title: str


@strawberry.type
class TokenLimitsType:
    context_tokens_remaining: int
    user_tokens_remaining_daily: int | None
    user_tokens_remaining_monthly: int | None


def _require_user(info):
    user = info.context.request.user
    if not user or not user.is_authenticated:
        raise PermissionError("Authentication required")
    return user


@strawberry.type
class LLMChatQueries:
    @strawberry.field
    def llm_chats(self, info) -> List[LLMChatType]:
        user = _require_user(info)
        return list(LLMChat.objects.filter(user=user, is_archived=False).select_related("settings"))

    @strawberry.field
    def llm_chat_messages(self, info, chat_id: int, limit: int = 50, offset: int = 0) -> List[LLMMessageType]:
        user = _require_user(info)
        chat = LLMChat.objects.get(id=chat_id, user=user)
        return list(
            LLMMessage.objects.filter(chat=chat)
            .order_by("-created_at")[offset:offset + limit]
        )

    @strawberry.field
    def llm_token_limits(self, info, chat_id: int) -> TokenLimitsType:
        user = _require_user(info)
        chat = LLMChat.objects.get(id=chat_id, user=user)
        settings = chat.settings
        system_prompt = build_system_prompt(chat.mode, settings.system_prompt)
        context_pack = build_context_pack(user, settings)
        messages = [
            {"role": "system", "content": system_prompt},
        ]
        if context_pack:
            messages.append({"role": "system", "content": build_context_prompt(context_pack.text)})
        history = ChatService._get_message_history(chat, limit=20)
        for msg in history:
            messages.append({"role": msg.role, "content": msg.content})
        context_used = estimate_message_tokens(messages)
        limits = calculate_token_limits(user, settings.context_window_tokens, context_used)
        return TokenLimitsType(
            context_tokens_remaining=limits.context_tokens_remaining,
            user_tokens_remaining_daily=limits.user_tokens_remaining_daily,
            user_tokens_remaining_monthly=limits.user_tokens_remaining_monthly,
        )

    @strawberry.field
    def llm_available_models(self, info) -> List[LLMModelType]:
        _require_user(info)
        return [
            LLMModelType(
                model_id=spec.model_id,
                provider=spec.provider,
                context_window_tokens=spec.context_window_tokens,
                max_output_tokens=spec.max_output_tokens,
                max_context_tokens_per_request=spec.max_context_tokens_per_request,
                default_temperature=spec.default_temperature,
                title=spec.title,
            )
            for spec in list_models()
        ]
