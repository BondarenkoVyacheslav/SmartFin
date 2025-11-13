import dataclasses
import decimal
import json
from typing import Sequence, Any

import strawberry


@strawberry.type
class Exchange:
    id: str
    name: str
    year_established: int
    country: str
    description: str
    url: str
    image: str
    has_trading_incentive: bool
    trust_score: int
    trust_score_rank: int
    trade_volume_24h_btc: decimal


@strawberry.type
class Exchanges:
    exchanges: list[Exchange]

    def to_redis_value(self) -> str:
        return json.dumps(
            dataclasses.asdict(self),
            ensure_ascii=False,
            separators=(",", ":")
        )

    @classmethod
    def from_redis_value(cls, value: str) -> "Exchanges":
        data = json.loads(value)

        raw: Exchanges = data.get("exchanges", [])
        return parse_exchanges(raw)


def parse_exchanges(raw: Sequence[dict[str, Any]]) -> Exchanges:
    exchanges: Exchanges = Exchanges(exchanges=list())

    for exchange in raw:
        exchanges.exchanges.append(
            Exchange(
                id=exchange.get("id"),
                name=exchange.get("name"),
                year_established=exchange.get("established"),
                country=exchange.get("country"),
                description=exchange.get("description"),
                url=exchange.get("url"),
                image=exchange.get("image"),
                has_trading_incentive=exchange.get("has_trading_incentive"),
                trust_score=exchange.get("trust_score"),
                trust_score_rank=exchange.get("trust_score_rank"),
                trade_volume_24h_btc=exchange.get("trade_volume_24h_btc"),
            )
        )

    return exchanges