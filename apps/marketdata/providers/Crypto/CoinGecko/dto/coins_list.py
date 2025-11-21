import dataclasses
import json
from typing import Optional, Sequence, Any
import strawberry

from apps.marketdata.providers.Crypto.CoinGecko.redis_json import RedisJSON


@strawberry.type
class Coin:
    id: str
    symbol: str
    name: str
    platforms: Optional[dict[str, str]]

    def to_redis_value(self) -> str:
        return json.dumps(dataclasses.asdict(self), ensure_ascii=False, separators=(",", ":"))



@strawberry.type
class CoinsList(RedisJSON):
    coins_list: list[Coin]

    @classmethod
    def from_redis_value(cls, value: str) -> "CoinsList":
        data = json.loads(value)

        raw: CoinsList = data.get("coins_list", [])
        return parse_coins_list(raw)



def parse_coins_list(raw: Sequence[dict[str, Any]]) -> CoinsList:
    coins_list: CoinsList = CoinsList(coins_list=list())
    for coin in raw:
        coins_list.coins_list.append(Coin(
            id=coin.get("id"),
            symbol=coin.get("symbol"),
            name=coin.get("name"),
            platforms=coin.get("platforms")
        ))

    return coins_list
