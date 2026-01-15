import strawberry
from .queries import IntegrationType


@strawberry.type
class IntegrationMutations:
    @strawberry.mutation
    def create_integration(
        self,
        portfolio_id: int,
        exchange_id: int,
        key: str,
        api_key: str,
        api_secret: str,
        passphrase: str | None = None,
        extra_params: dict | None = None,
    ) -> IntegrationType:
        return IntegrationType.objects.create(
            portfolio_id=portfolio_id,
            exchange_id=exchange_id,
            key=key,
            api_key=api_key,
            api_secret=api_secret,
            passphrase=passphrase,
            extra_params=extra_params or {},
        )
