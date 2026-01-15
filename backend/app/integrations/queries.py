import strawberry
from strawberry import auto
from app.integrations.models import Exchange, Integration
from typing import List


@strawberry.django.type(Exchange)
class ExchangeType:
    id: auto
    name: auto
    description: auto

@strawberry.django.type(Integration)
class IntegrationType:
    id: auto
    key: auto
    api_key: auto
    api_secret: auto
    passphrase: auto
    extra_params: auto
    portfolio_id = auto
    exchange_id = auto


@strawberry.type
class IntegrationQueries:
    exchanges: List[ExchangeType] = strawberry.django.field()
    integrations: List[IntegrationType] = strawberry.django.field()
