import dataclasses
import json
from typing import Sequence
import strawberry

@strawberry.type
class Exchange:
    id: str
    name: str

@strawberry.type
class ExchangesList:
    exchanges_list: list[Exchange] = strawberry.field(default_factory=list)

    def to_redis_value(self) -> str:
        return json.dumps(dataclasses.asdict(self), ensure_ascii=False, separators=(",", ":"))

    @classmethod
    def from_redis_value(cls, value: str) -> "ExchangesList":
        data = json.loads(value)

        raw: ExchangesList = data.get("exchanges_list")
        return parse_exchanges_list(raw)


def parse_exchanges_list(raw: Sequence[dict[str, str]]) -> ExchangesList:
    exchanges_list: ExchangesList = ExchangesList(exchanges_list=list())
    for exchange in raw:
        exchanges_list.exchanges_list.append(
            Exchange(
                id = exchange.get("id"),
                name = exchange.get("name")
            )
        )

    return exchanges_list