from decimal import Decimal
from typing import Any

import strawberry

from apps.marketdata.providers.Crypto.CoinGecko.redis_json import RedisJSON


@strawberry.type
class GlobalDefiData(RedisJSON):
    defi_market_cap: str
    eth_market_data: str
    defi_to_eth_ratio: str
    trading_volume_24h: str
    defi_dominance: str
    top_coin_name: str
    top_coin_defi_dominance: Decimal


def parse_global_defi_data(raw: dict[str, dict[str, Any]]) -> GlobalDefiData:
    data = raw.get("data")
    return GlobalDefiData(
        defi_market_cap=data.get("defi_market_cap"),
        eth_market_data=data.get("eth_market_data"),
        defi_to_eth_ratio=data.get("defi_to_eth_ratio"),
        trading_volume_24h=data.get("trading_volume_24h"),
        defi_dominance=data.get("defi_dominance"),
        top_coin_name=data.get("top_coin_name"),
        top_coin_defi_dominance=data.get("top_coin_defi_dominance"),
    )