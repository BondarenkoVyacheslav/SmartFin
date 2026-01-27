from __future__ import annotations

import enum
import strawberry

from app.llm_chats.models import LLMChat, ChatSettings


@strawberry.enum
class ChatModeEnum(enum.Enum):
    GENERAL = LLMChat.Mode.GENERAL
    PORTFOLIO_ANALYSIS = LLMChat.Mode.PORTFOLIO_ANALYSIS
    RISK_REVIEW = LLMChat.Mode.RISK_REVIEW
    PERFORMANCE_REVIEW = LLMChat.Mode.PERFORMANCE_REVIEW
    MARKET_TRENDS = LLMChat.Mode.MARKET_TRENDS


@strawberry.enum
class ContextModeEnum(enum.Enum):
    FULL = ChatSettings.ContextMode.FULL
    COMPACT = ChatSettings.ContextMode.COMPACT
    OFF = ChatSettings.ContextMode.OFF


@strawberry.enum
class AnalysisTypeEnum(enum.Enum):
    STRATEGY = "STRATEGY"
    RISK = "RISK"
    RETURNS = "RETURNS"
    MISTAKES = "MISTAKES"
    TRENDS = "TRENDS"
