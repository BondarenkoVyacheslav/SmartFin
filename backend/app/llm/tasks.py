from __future__ import annotations

from celery import shared_task

from app.llm.models import LLMChat
from app.llm.services.chat_service import ChatService


@shared_task(name="app.llm.tasks.run_analysis")
def run_analysis_task(chat_id: int, user_id: int, analysis_type: str) -> dict:
    """Run heavier analysis flows asynchronously."""
    chat = LLMChat.objects.get(id=chat_id, user_id=user_id)
    prompt = f"Run analysis: {analysis_type}. Provide insights and caveats."
    result = ChatService.send_message(user=chat.user, chat=chat, content=prompt)
    return {
        "chat_id": chat_id,
        "analysis_type": analysis_type,
        "message_id": result.assistant_message.id,
    }
