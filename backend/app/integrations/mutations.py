import strawberry
from .queries import IntegrationType


@strawberry.type
class IntegrationMutations:
    @strawberry.mutation
    def create_integration(self, portfolio_id: int, exchange_id: int, key: str) -> IntegrationType:
        return IntegrationType.objects.create(portfolio_id= portfolio_id, exchange_id=exchange_id, key=key)

