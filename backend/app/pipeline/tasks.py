from __future__ import annotations

import time
from datetime import date, datetime
from zoneinfo import ZoneInfo

from celery import Task, chord, group, shared_task
from celery.utils.log import get_task_logger
from django.conf import settings

from .services import (
    TransientSyncError,
    acquire_daily_lock,
    build_daily_snapshots_for_user,
    compute_user_metrics,
    list_active_connections,
    random_jitter_seconds,
    sync_connection,
)

logger = get_task_logger(__name__)


class BaseTask(Task):
    autoretry_for = (TransientSyncError,)
    retry_backoff = True
    retry_backoff_max = 300
    retry_jitter = True
    retry_kwargs = {"max_retries": 5}
    soft_time_limit = 9 * 60
    time_limit = 10 * 60


class PipelineTask(Task):
    soft_time_limit = 5 * 60
    time_limit = 10 * 60


class AnalyticsTask(Task):
    soft_time_limit = 10 * 60
    time_limit = 15 * 60


def _parse_date(value: str | None) -> date:
    if not value:
        return datetime.now(ZoneInfo(settings.CELERY_TIMEZONE)).date()
    return datetime.strptime(value, "%Y-%m-%d").date()


@shared_task(bind=True, base=PipelineTask)
def nightly_pipeline(self, as_of_date: str | None = None) -> dict[str, int]:
    snapshot_date = _parse_date(as_of_date)
    lock_key = f"nightly_pipeline:{snapshot_date.isoformat()}"
    redis_url = settings.REDIS_URL
    if not acquire_daily_lock(redis_url, lock_key, ttl_seconds=6 * 60 * 60):
        logger.info("nightly_pipeline skipped lock_key=%s", lock_key)
        return {"scheduled_users": 0, "scheduled_connections": 0}

    connections_by_user = list_active_connections()
    scheduled_users = 0
    scheduled_connections = 0

    for user_id, connections in connections_by_user.items():
        if not connections:
            continue
        scheduled_users += 1
        scheduled_connections += len(connections)
        header = [
            sync_connector.s(
                user_id=user_id,
                connection_id=spec.connection_id,
                connection_kind=spec.connection_kind,
                source_type=spec.source_type,
            ).set(queue=spec.source_type)
            for spec in connections
        ]
        body = run_user_analytics.s(
            user_id=user_id,
            as_of_date=snapshot_date.isoformat(),
        )
        jitter = random_jitter_seconds(max_minutes=30)
        chord(group(header), body).apply_async(countdown=jitter)

    logger.info(
        "nightly_pipeline scheduled users=%s connections=%s date=%s",
        scheduled_users,
        scheduled_connections,
        snapshot_date,
    )
    return {
        "scheduled_users": scheduled_users,
        "scheduled_connections": scheduled_connections,
    }


@shared_task(bind=True, base=BaseTask)
def sync_connector(
    self,
    *,
    user_id: int,
    connection_id: int,
    connection_kind: str,
    source_type: str,
) -> dict[str, int]:
    started_at = time.monotonic()
    result = sync_connection(
        connection_id=connection_id,
        connection_kind=connection_kind,
        source_type=source_type,
    )
    duration_ms = int((time.monotonic() - started_at) * 1000)
    logger.info(
        "sync_connector done source_type=%s user_id=%s connection_id=%s duration_ms=%s result=%s",
        source_type,
        user_id,
        connection_id,
        duration_ms,
        result,
    )
    return result


@shared_task(bind=True, base=AnalyticsTask)
def run_user_analytics(self, *, user_id: int, as_of_date: str) -> dict[str, object]:
    snapshot_date = _parse_date(as_of_date)
    valuations = build_daily_snapshots_for_user(user_id, snapshot_date)
    metrics = compute_user_metrics(user_id, snapshot_date)
    logger.info(
        "run_user_analytics done user_id=%s date=%s portfolios=%s total_value=%s",
        user_id,
        snapshot_date,
        len(valuations),
        metrics.get("total_value_base"),
    )
    total_value = metrics.get("total_value_base")
    return {
        "portfolios": len(valuations),
        "total_value_base": str(total_value) if total_value is not None else "0",
    }
