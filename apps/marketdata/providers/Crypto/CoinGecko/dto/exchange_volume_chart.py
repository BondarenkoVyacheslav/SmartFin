import dataclasses
import json
from typing import List, Sequence, Any

import strawberry


@strawberry.type
class ExchangeVolumePoint:
    """
    Одна точка на графике объёма биржи.

    timestamp_ms — Unix-время в миллисекундах (как в ответе CoinGecko).
    volume       — объём (по доке CoinGecko — volume в BTC).
    """
    timestamp_ms: int
    volume: float


@strawberry.type
class ExchangeVolumeChart:
    """
    Нормализованный ответ /exchanges/{id}/volume_chart.
    """
    exchange_id: str
    days: int
    points: List[ExchangeVolumePoint]

    def to_redis_value(self) -> str:
        """
        Сериализует DTO в компактный JSON для хранения в Redis.
        dataclasses.asdict работает, т.к. strawberry.type — это dataclass.
        """
        return json.dumps(
            dataclasses.asdict(self),
            ensure_ascii=False,
            separators=(",", ":"),
        )


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
            timestamp_ms = int(ts_raw)
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
