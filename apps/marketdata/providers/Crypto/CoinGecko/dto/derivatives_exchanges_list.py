from typing import Sequence
import strawberry

from apps.marketdata.services.redis_json import RedisJSON


@strawberry.type(name="DerivativesExchangesListDerivative")
class Derivative:
    id: str
    name: str

@strawberry.type
class DerivativesExchangesList(RedisJSON):
    derivatives_exchanges_list: list[Derivative] = strawberry.field(default_factory=list)


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