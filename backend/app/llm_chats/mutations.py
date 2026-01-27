from __future__ import annotations

from typing import Optional

import strawberry

from app.llm_chats.models import LLMChat, LLMMessage
from app.llm_chats.enums import ChatModeEnum, ContextModeEnum, AnalysisTypeEnum
from app.llm_chats.queries import LLMChatType, LLMMessageType
from app.llm_chats.services.chat_service import ChatService, BudgetExceededError
from app.llm_chats.tasks import run_analysis_task


@strawberry.type
class TokenUsageType:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@strawberry.type
class SendMessagePayload:
    message: LLMMessageType
    usage: TokenUsageType
    context_tokens_remaining: int
    user_tokens_remaining_daily: int | None
    user_tokens_remaining_monthly: int | None


@strawberry.type
class AnalysisTaskPayload:
    task_id: str
    queued: bool


def _require_user(info):
    user = info.context.request.user
    if not user or not user.is_authenticated:
        raise PermissionError("Authentication required")
    return user


@strawberry.type
class LLMChatMutations:
    @strawberry.mutation
    def create_llm_chat(
        self,
        info,
        title: Optional[str] = None,
        mode: Optional[ChatModeEnum] = None,
        model_id: Optional[str] = None,
    ) -> LLMChatType:
        user = _require_user(info)
        chat = ChatService.create_chat(
            user=user,
            title=title,
            mode=mode.value if mode else None,
            model_id=model_id,
        )
        return chat

    @strawberry.mutation
    def send_llm_message(
        self,
        info,
        chat_id: int,
        content: str,
        model_id: Optional[str] = None,
    ) -> SendMessagePayload:
        user = _require_user(info)
        chat = LLMChat.objects.get(id=chat_id, user=user)
        try:
            result = ChatService.send_message(user=user, chat=chat, content=content, model_id=model_id)
        except BudgetExceededError as exc:
            raise ValueError(str(exc))
        msg = result.assistant_message
        usage = TokenUsageType(
            prompt_tokens=msg.prompt_tokens or 0,
            completion_tokens=msg.completion_tokens or 0,
            total_tokens=msg.total_tokens or 0,
        )
        return SendMessagePayload(
            message=msg,
            usage=usage,
            context_tokens_remaining=result.token_limits.context_tokens_remaining,
            user_tokens_remaining_daily=result.token_limits.user_tokens_remaining_daily,
            user_tokens_remaining_monthly=result.token_limits.user_tokens_remaining_monthly,
        )

    @strawberry.mutation
    def update_llm_chat_settings(
        self,
        info,
        chat_id: int,
        model_id: Optional[str] = None,
        temperature: Optional[float] = None,
        system_prompt: Optional[str] = None,
        context_mode: Optional[ContextModeEnum] = None,
    ) -> LLMChatType:
        user = _require_user(info)
        chat = LLMChat.objects.get(id=chat_id, user=user)
        settings = chat.settings
        if model_id is not None:
            settings.model_id = model_id
        if temperature is not None:
            settings.temperature = temperature
        if system_prompt is not None:
            settings.system_prompt = system_prompt
        if context_mode is not None:
            settings.context_mode = context_mode.value
        settings.save()
        return chat

    @strawberry.mutation
    def clear_llm_chat_context(self, info, chat_id: int) -> bool:
        user = _require_user(info)
        chat = LLMChat.objects.get(id=chat_id, user=user)
        LLMMessage.objects.filter(chat=chat).delete()
        return True

    @strawberry.mutation
    def compress_llm_chat_context(self, info, chat_id: int, keep_last: int = 6) -> bool:
        user = _require_user(info)
        chat = LLMChat.objects.get(id=chat_id, user=user)
        ChatService.compress_context(chat, keep_last=keep_last)
        return True

    @strawberry.mutation
    def start_llm_analysis(
        self,
        info,
        chat_id: int,
        analysis_type: AnalysisTypeEnum,
    ) -> AnalysisTaskPayload:
        user = _require_user(info)
        chat = LLMChat.objects.get(id=chat_id, user=user)
        task = run_analysis_task.delay(chat.id, user.id, analysis_type.value)
        return AnalysisTaskPayload(task_id=task.id, queued=True)
