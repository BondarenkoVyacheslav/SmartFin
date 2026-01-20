from datetime import datetime

import strawberry
from .queries import IntegrationType, WalletAddressType


@strawberry.type
class IntegrationMutations:
    @strawberry.mutation
    def create_integration(
        self,
        portfolio_id: int,
        exchange_id: int,
        key: str,
        api_key: str | None = None,
        api_secret: str | None = None,
        passphrase: str | None = None,
        token: str | None = None,
        access_token: str | None = None,
        refresh_token: str | None = None,
        secret: str | None = None,
        client_id: str | None = None,
        account_id: str | None = None,
        token_expires_at: datetime | None = None,
        refresh_expires_at: datetime | None = None,
        extra_params: dict | None = None,
    ) -> IntegrationType:
        return IntegrationType.objects.create(
            portfolio_id=portfolio_id,
            exchange_id=exchange_id,
            key=key,
            api_key=api_key,
            api_secret=api_secret,
            passphrase=passphrase,
            token=token,
            access_token=access_token,
            refresh_token=refresh_token,
            secret=secret,
            client_id=client_id,
            account_id=account_id,
            token_expires_at=token_expires_at,
            refresh_expires_at=refresh_expires_at,
            extra_params=extra_params or {},
        )

    @strawberry.mutation
    def create_wallet_address(
        self,
        portfolio_id: int,
        network: str,
        address: str,
        integration_id: int | None = None,
        tag: str | None = None,
        label: str | None = None,
        asset_symbol: str | None = None,
        is_active: bool = True,
        extra_params: dict | None = None,
    ) -> WalletAddressType:
        return WalletAddressType.objects.create(
            portfolio_id=portfolio_id,
            integration_id=integration_id,
            network=network,
            address=address,
            tag=tag,
            label=label,
            asset_symbol=asset_symbol,
            is_active=is_active,
            extra_params=extra_params or {},
        )
