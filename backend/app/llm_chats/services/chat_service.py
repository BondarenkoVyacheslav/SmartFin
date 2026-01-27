from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from django.db import transaction
from django.utils import timezone

from app.llm_chats.models import LLMChat, LLMMessage, ChatSettings, ContextSnapshot
from app.llm_chats.providers.base import LLMChatRequest, LLMMessagePayload, LLMProviderError
from app.llm_chats.providers.registry import get_provider
from app.llm_chats.services.context_builder import (
    build_context_pack,
    build_snapshot_from_messages,
)
from app.llm_chats.services.model_registry import get_default_model, get_model_spec
from app.llm_chats.services.prompt_templates import build_context_prompt, build_system_prompt
from app.llm_chats.services.token_accounting import (
    TokenLimits,
    estimate_message_tokens,
    record_token_usage,
    calculate_token_limits,
    estimate_tokens,
)


class BudgetExceededError(RuntimeError):
    pass


@dataclass
class SendMessageResult:
    assistant_message: LLMMessage
    token_limits: TokenLimits


class ChatService:
    @staticmethod
    def create_chat(
        *,
        user,
        title: str | None = None,
        mode: str | None = None,
        model_id: str | None = None,
        temperature: float | None = None,
        system_prompt: str | None = None,
    ) -> LLMChat:
        spec = get_model_spec(model_id) if model_id else get_default_model()
        with transaction.atomic():
            chat = LLMChat.objects.create(
                user=user,
                title=title or "",
                mode=mode or LLMChat.Mode.GENERAL,
            )
            ChatSettings.objects.create(
                chat=chat,
                model_id=spec.model_id,
                provider=spec.provider,
                temperature=temperature if temperature is not None else spec.default_temperature,
                max_context_tokens_per_request=spec.max_context_tokens_per_request,
                max_output_tokens=spec.max_output_tokens,
                context_window_tokens=spec.context_window_tokens,
                system_prompt=system_prompt or "",
            )
        return chat

    @staticmethod
    def send_message(
        *,
        user,
        chat: LLMChat,
        content: str,
        model_id: str | None = None,
    ) -> SendMessageResult:
        if chat.user_id != user.id:
            raise PermissionError("Chat does not belong to user")
        settings = chat.settings
        spec = get_model_spec(model_id or settings.model_id)
        provider = get_provider(spec.provider)

        system_prompt = build_system_prompt(chat.mode, settings.system_prompt)
        context_pack = build_context_pack(user, settings)

        message_history = ChatService._get_message_history(chat, limit=50)
        base_messages = ChatService._build_base_messages(
            system_prompt=system_prompt,
            context_pack=context_pack,
            user_content=content,
        )
        history = ChatService._trim_history_to_budget(
            history=message_history,
            base_messages=base_messages,
            max_tokens=settings.max_context_tokens_per_request,
        )
        messages = ChatService._build_prompt_messages(
            base_messages=base_messages,
            history=history,
            user_content=content,
        )

        context_tokens_used = estimate_message_tokens([msg.__dict__ for msg in messages])
        token_limits_pre = calculate_token_limits(
            user,
            context_window=spec.context_window_tokens,
            context_used=context_tokens_used,
        )
        ChatService._enforce_budget(token_limits_pre)

        try:
            response = provider.send_chat(
                LLMChatRequest(
                    model=spec.model_id,
                    messages=messages,
                    temperature=float(settings.temperature),
                    max_output_tokens=settings.max_output_tokens,
                    metadata={"chat_id": chat.id, "user_id": user.id},
                )
            )
        except LLMProviderError as exc:
            with transaction.atomic():
                user_msg = LLMMessage.objects.create(
                    chat=chat,
                    role=LLMMessage.Role.USER,
                    content=content,
                )
                assistant_msg = LLMMessage.objects.create(
                    chat=chat,
                    role=LLMMessage.Role.ASSISTANT,
                    content="",
                    status=LLMMessage.Status.ERROR,
                    provider=spec.provider,
                    model_id=spec.model_id,
                    error_code=exc.code,
                    error_message=str(exc),
                )
                chat.last_message_at = timezone.now()
                chat.save(update_fields=["last_message_at", "updated_at"])
            raise

        with transaction.atomic():
            user_msg = LLMMessage.objects.create(
                chat=chat,
                role=LLMMessage.Role.USER,
                content=content,
            )
            assistant_msg = LLMMessage.objects.create(
                chat=chat,
                role=LLMMessage.Role.ASSISTANT,
                content=response.text,
                provider=spec.provider,
                model_id=spec.model_id,
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                total_tokens=response.total_tokens,
            )
            record_token_usage(
                user=user,
                chat=chat,
                message=assistant_msg,
                provider=spec.provider,
                model_id=spec.model_id,
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                context_tokens=context_tokens_used,
            )
            chat.last_message_at = timezone.now()
            chat.save(update_fields=["last_message_at", "updated_at"])
        token_limits = calculate_token_limits(
            user,
            context_window=spec.context_window_tokens,
            context_used=context_tokens_used,
        )
        return SendMessageResult(assistant_message=assistant_msg, token_limits=token_limits)

    @staticmethod
    def compress_context(chat: LLMChat, keep_last: int = 6) -> ContextSnapshot:
        messages = (
            LLMMessage.objects.filter(chat=chat)
            .order_by("-created_at")
            .values_list("content", flat=True)[:keep_last]
        )
        summary = build_snapshot_from_messages(list(messages))
        snapshot = ContextSnapshot.objects.create(
            chat=chat,
            summary_text=summary,
            data={"kept": keep_last},
            token_count=estimate_tokens(summary),
        )
        return snapshot

    @staticmethod
    def _build_base_messages(
        *,
        system_prompt: str,
        context_pack,
        user_content: str,
    ) -> list[LLMMessagePayload]:
        messages: list[LLMMessagePayload] = [
            LLMMessagePayload(role="system", content=system_prompt)
        ]
        if context_pack:
            messages.append(
                LLMMessagePayload(role="system", content=build_context_prompt(context_pack.text))
            )
        messages.append(LLMMessagePayload(role="user", content=user_content))
        return messages

    @staticmethod
    def _build_prompt_messages(
        *,
        base_messages: list[LLMMessagePayload],
        history: Iterable[LLMMessage],
        user_content: str,
    ) -> list[LLMMessagePayload]:
        messages: list[LLMMessagePayload] = []
        # base_messages already include system/context + current user message placeholder
        if base_messages:
            messages.extend(base_messages[:-1])
        for msg in history:
            messages.append(LLMMessagePayload(role=msg.role, content=msg.content))
        messages.append(LLMMessagePayload(role="user", content=user_content))
        return messages

    @staticmethod
    def _get_message_history(chat: LLMChat, limit: int) -> list[LLMMessage]:
        return list(
            LLMMessage.objects.filter(chat=chat, status=LLMMessage.Status.COMPLETED)
            .order_by("-created_at")
            .select_related("chat")[:limit]
        )[::-1]

    @staticmethod
    def _trim_history_to_budget(
        *, history: list[LLMMessage], base_messages: list[LLMMessagePayload], max_tokens: int
    ) -> list[LLMMessage]:
        if max_tokens <= 0:
            return []
        base_tokens = estimate_message_tokens([msg.__dict__ for msg in base_messages])
        if base_tokens >= max_tokens:
            return []
        selected: list[LLMMessage] = []
        current = base_tokens
        for msg in reversed(history):
            msg_tokens = estimate_message_tokens([{"role": msg.role, "content": msg.content}])
            if current + msg_tokens > max_tokens:
                break
            selected.append(msg)
            current += msg_tokens
        return list(reversed(selected))

    @staticmethod
    def _enforce_budget(token_limits: TokenLimits) -> None:
        if token_limits.user_tokens_remaining_daily is not None and token_limits.user_tokens_remaining_daily <= 0:
            raise BudgetExceededError("Daily token budget exceeded")
        if token_limits.user_tokens_remaining_monthly is not None and token_limits.user_tokens_remaining_monthly <= 0:
            raise BudgetExceededError("Monthly token budget exceeded")
