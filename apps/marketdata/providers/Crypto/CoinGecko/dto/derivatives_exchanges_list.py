import dataclasses
import json
from typing import Sequence
import strawberry



@strawberry.type
class Derivative:
    id: str
    name: str

@strawberry.type
class DerivativesExchangesList:
    derivatives_exchanges_list: list[Derivative] = strawberry.field(default_factory=list)

    def to_redis_value(self):
        return json.dumps(
            dataclasses.asdict(self),
            ensure_ascii=False,
            separators=(",", ":"),
        )


def parse_derivatives_exchanges_list(raw: Sequence[dict[str, str]]) -> DerivativesExchangesList:
    derivatives_exchanges_list: DerivativesExchangesList = DerivativesExchangesList()

    for derivative in raw:
        derivatives_exchanges_list.derivatives_exchanges_list.append(
            Derivative(
                id=derivative.get("id"),
                name=derivative.get("name"),
            )
        )

    return derivatives_exchanges_list