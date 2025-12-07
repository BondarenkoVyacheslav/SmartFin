from typing import List, Sequence, Any

import strawberry

from apps.marketdata.services.redis_json import RedisJSON


@strawberry.type
class ExchangeVolumePoint:
    """
    Одна точка на графике объёма биржи.

    timestamp_ms — Unix-время в миллисекундах (как в ответе CoinGecko).
    volume       — объём (по доке CoinGecko — volume в BTC).
    """
    timestamp_ms: float
    volume: float


@strawberry.type
class ExchangeVolumeChart(RedisJSON):
    """
    Нормализованный ответ /exchanges/{id}/volume_chart.
    """
    exchange_id: str
    days: int
    points: List[ExchangeVolumePoint]


def parse_exchange_volume_chart(
        exchange_id: str,
        days: int,
        raw: Sequence[Sequence[Any]],
) -> ExchangeVolumeChart:
    """
    Нормализует ответ CoinGecko /exchanges/{id}/volume_chart
    (формата [[timestamp_ms, "volume_str"], ...]) в DTO ExchangeVolumeChart.
    """
    points: List[ExchangeVolumePoint] = []

    for item in raw:
        # Ожидаем [timestamp_ms, volume_str]
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue

        ts_raw, vol_raw = item[0], item[1]

        # timestamp в миллисекундах
        if not isinstance(ts_raw, (int, float)):
            continue

        # volume может прийти как строка или число — приводим к строке, потом к float
        vol_str = vol_raw if isinstance(vol_raw, str) else str(vol_raw)

        try:
            timestamp_ms = float(ts_raw)
            volume = float(vol_str)
        except (TypeError, ValueError):
            # Если что-то не парсится — просто пропускаем точку
            continue

        points.append(
            ExchangeVolumePoint(
                timestamp_ms=timestamp_ms,
                volume=volume,
            )
        )

    return ExchangeVolumeChart(
        exchange_id=exchange_id,
        days=days,
        points=points,
    )
