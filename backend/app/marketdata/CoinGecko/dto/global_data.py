from typing import Any, Dict, List

import strawberry

from app.marketdata.services.redis_json import RedisJSON


@strawberry.type
class GlobalMarketCapEntry:
    """
    Элемент из total_market_cap:
    currency -> value (рыночная капитализация в этой валюте)
    """
    currency: str
    value: float


@strawberry.type
class GlobalVolumeEntry:
    """
    Элемент из total_volume:
    currency -> value (объём торгов в этой валюте)
    """
    currency: str
    value: float


@strawberry.type
class GlobalMarketCapPercentageEntry:
    """
    Элемент из market_cap_percentage:
    asset -> percentage (доля в общей капе в %)
    пример ключа: "btc", "eth", "usdt" и т.д.
    """
    asset: str
    percentage: float


@strawberry.type
class GlobalData(RedisJSON):
    """
    Нормализованный ответ CoinGecko /global (внутреннее поле "data").
    Все map'ы (total_market_cap, total_volume, market_cap_percentage)
    превращены в списки записей для удобной работы в GraphQL.
    """

    active_cryptocurrencies: int
    upcoming_icos: int
    ongoing_icos: int
    ended_icos: int
    markets: int

    total_market_cap: List[GlobalMarketCapEntry]
    total_volume: List[GlobalVolumeEntry]
    market_cap_percentage: List[GlobalMarketCapPercentageEntry]

    market_cap_change_percentage_24h_usd: float
    updated_at: int  # unix timestamp (секунды)


def _parse_market_cap_map(raw_map: Any) -> List[GlobalMarketCapEntry]:
    entries: List[GlobalMarketCapEntry] = []
    if not isinstance(raw_map, dict):
        return entries

    for currency, value in raw_map.items():
        if not isinstance(currency, str):
            continue
        if not isinstance(value, (int, float)):
            continue
        entries.append(
            GlobalMarketCapEntry(
                currency=currency,
                value=float(value),
            )
        )
    return entries


def _parse_volume_map(raw_map: Any) -> List[GlobalVolumeEntry]:
    entries: List[GlobalVolumeEntry] = []
    if not isinstance(raw_map, dict):
        return entries

    for currency, value in raw_map.items():
        if not isinstance(currency, str):
            continue
        if not isinstance(value, (int, float)):
            continue
        entries.append(
            GlobalVolumeEntry(
                currency=currency,
                value=float(value),
            )
        )
    return entries


def _parse_market_cap_percentage_map(raw_map: Any) -> List[GlobalMarketCapPercentageEntry]:
    entries: List[GlobalMarketCapPercentageEntry] = []
    if not isinstance(raw_map, dict):
        return entries

    for asset, percentage in raw_map.items():
        if not isinstance(asset, str):
            continue
        if not isinstance(percentage, (int, float)):
            continue
        entries.append(
            GlobalMarketCapPercentageEntry(
                asset=asset,
                percentage=float(percentage),
            )
        )
    return entries


def parse_global(raw: Dict[str, Any]) -> GlobalData:
    """
    Превращает сырой ответ CoinGecko /global в DTO GlobalData.

    Ожидаемый сырой ответ:
    {
      "data": {
        "active_cryptocurrencies": ...,
        "upcoming_icos": ...,
        "ongoing_icos": ...,
        "ended_icos": ...,
        "markets": ...,
        "total_market_cap": { "usd": ..., "btc": ..., ... },
        "total_volume": { "usd": ..., "btc": ..., ... },
        "market_cap_percentage": { "btc": ..., "eth": ..., ... },
        "market_cap_change_percentage_24h_usd": ...,
        "updated_at": 1763208398
      }
    }
    """
    data = raw.get("data") or {}

    active_cryptocurrencies = data.get("active_cryptocurrencies") or 0
    upcoming_icos = data.get("upcoming_icos") or 0
    ongoing_icos = data.get("ongoing_icos") or 0
    ended_icos = data.get("ended_icos") or 0
    markets = data.get("markets") or 0

    total_market_cap_raw = data.get("total_market_cap") or {}
    total_volume_raw = data.get("total_volume") or {}
    market_cap_percentage_raw = data.get("market_cap_percentage") or {}

    market_cap_change_percentage_24h_usd = data.get(
        "market_cap_change_percentage_24h_usd"
    ) or 0.0
    updated_at = data.get("updated_at") or 0

    return GlobalData(
        active_cryptocurrencies=int(active_cryptocurrencies),
        upcoming_icos=int(upcoming_icos),
        ongoing_icos=int(ongoing_icos),
        ended_icos=int(ended_icos),
        markets=int(markets),
        total_market_cap=_parse_market_cap_map(total_market_cap_raw),
        total_volume=_parse_volume_map(total_volume_raw),
        market_cap_percentage=_parse_market_cap_percentage_map(
            market_cap_percentage_raw
        ),
        market_cap_change_percentage_24h_usd=float(
            market_cap_change_percentage_24h_usd
        ),
        updated_at=int(updated_at),
    )
