from __future__ import annotations

from typing import Any, Optional


def route_task(
    name: str,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    options: dict[str, Any],
    task: Any = None,
    **_extra: Any,
) -> Optional[dict[str, Any]]:
    if name == "app.pipeline.tasks.sync_connector":
        source_type = None
        if kwargs:
            source_type = kwargs.get("source_type")
        if source_type is None and args:
            # args order: user_id, connection_id, connection_kind, source_type
            if len(args) >= 4:
                source_type = args[3]
        if source_type == "sync_ru_brokers":
            return {"queue": "sync_ru_brokers"}
        if source_type == "sync_crypto":
            return {"queue": "sync_crypto"}
        if source_type == "sync_ton":
            return {"queue": "sync_ton"}

    if name == "app.pipeline.tasks.run_user_analytics":
        return {"queue": "analytics"}

    if name == "app.llm_chats.tasks.run_analysis":
        return {"queue": "llm_analytics"}

    return None
