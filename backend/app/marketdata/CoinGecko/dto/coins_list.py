from typing import Optional, Sequence, Any
import strawberry
from strawberry.scalars import JSON
from app.marketdata.services.redis_json import RedisJSON


@strawberry.type(name="CoinsListCoin")
class Coin:
    id: str
    symbol: str
    name: str
    platforms: Optional[JSON]


@strawberry.type
class CoinsList(RedisJSON):
    coins_list: list[Coin]


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
