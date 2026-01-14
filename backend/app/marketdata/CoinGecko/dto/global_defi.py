from decimal import Decimal
from typing import Any

import strawberry

from app.marketdata.services.redis_json import RedisJSON


@strawberry.type
class GlobalDefiData(RedisJSON):
    defi_market_cap: str | None
    eth_market_data: str | None
    defi_to_eth_ratio: str | None
    trading_volume_24h: str | None
    defi_dominance: str | None
    top_coin_name: str | None
    top_coin_defi_dominance: Decimal | None

def _to_dec(x) -> Decimal | None:
    if x is None:
        return None
    # через str(x) чтобы не ловить двоичную погрешность float
    return Decimal(str(x))

def parse_global_defi_data(raw: dict[str, dict[str, Any]]) -> GlobalDefiData:
    data = raw.get("data")
    return GlobalDefiData(
        defi_market_cap=data.get("defi_market_cap"),
        eth_market_data=data.get("eth_market_data"),
        defi_to_eth_ratio=data.get("defi_to_eth_ratio"),
        trading_volume_24h=data.get("trading_volume_24h"),
        defi_dominance=data.get("defi_dominance"),
        top_coin_name=data.get("top_coin_name"),
        top_coin_defi_dominance=_to_dec(data.get("top_coin_defi_dominance")),
    )