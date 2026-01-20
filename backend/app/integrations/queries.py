from __future__ import annotations

from typing import List, Optional

import strawberry
from asgiref.sync import sync_to_async
from strawberry import auto

from app.integrations.models import Exchange, Integration, WalletAddress


@strawberry.django.type(Exchange)
class ExchangeType:
    id: auto
    name: auto
    description: auto
    kind: auto

@strawberry.django.type(Integration)
class IntegrationType:
    id: auto
    key: auto
    api_key: auto
    api_secret: auto
    passphrase: auto
    token: auto
    access_token: auto
    refresh_token: auto
    secret: auto
    client_id: auto
    account_id: auto
    token_expires_at: auto
    refresh_expires_at: auto
    extra_params: auto
    portfolio_id = auto
    exchange_id = auto


@strawberry.django.type(WalletAddress)
class WalletAddressType:
    id: auto
    portfolio_id: auto
    integration_id: auto
    network: auto
    address: auto
    tag: auto
    label: auto
    asset_symbol: auto
    is_active: auto
    extra_params: auto


@strawberry.type
class IntegrationPingResult:
    ok: bool
    message: Optional[str] = None
    error_type: Optional[str] = None
    error_code: Optional[str] = None
    status_code: Optional[int] = None
    raw_error: Optional[str] = None
    account_ids: Optional[List[str]] = None
    ok_addresses: Optional[List[str]] = None
    failed_addresses: Optional[List[str]] = None


@strawberry.type
class IntegrationQueries:
    exchanges: List[ExchangeType] = strawberry.django.field()
    integrations: List[IntegrationType] = strawberry.django.field()
    wallet_addresses: List[WalletAddressType] = strawberry.django.field()

    @strawberry.field
    async def ping_integration(
        self,
        integration_id: int,
        addresses: Optional[List[str]] = None,
    ) -> IntegrationPingResult:
        integration = await sync_to_async(
            Integration.objects.select_related("exchange_id").get
        )(id=integration_id)
        exchange_name = _normalize_exchange_name(integration.exchange_id.name)
        raw = integration.extra_params or {}

        try:
            if exchange_name in {"binance"}:
                from app.integrations.Binance.adapter import BinanceAdapter

                adapter = BinanceAdapter(
                    api_key=integration.api_key or "",
                    api_secret=integration.api_secret or "",
                    testnet=bool(raw.get("testnet", False)),
                    recv_window=int(raw.get("recv_window", 5000)),
                    extra_params=_pick_client_params(raw),
                )
                res = await adapter.ping()
                return _pack_ping_result(res)

            if exchange_name in {"bybit"}:
                from app.integrations.Bybit.adapter import BybitAdapter

                adapter = BybitAdapter(
                    api_key=integration.api_key or "",
                    api_secret=integration.api_secret or "",
                    testnet=bool(raw.get("testnet", False)),
                    recv_window=int(raw.get("recv_window", 5000)),
                    extra_params=dict(raw.get("client_params") or {}),
                )
                account_type = _normalize_str(raw.get("account_type")) or "UNIFIED"
                res = await adapter.ping(account_type=account_type)
                return _pack_ping_result(res)

            if exchange_name in {"okx"}:
                from app.integrations.OKX.adapter import OKXAdapter

                adapter = OKXAdapter(
                    api_key=integration.api_key or "",
                    api_secret=integration.api_secret or "",
                    passphrase=integration.passphrase or "",
                    testnet=bool(raw.get("testnet", False)),
                    flag=_normalize_str(raw.get("flag")),
                    use_server_time=bool(raw.get("use_server_time", False)),
                    extra_params=dict(raw.get("client_params") or {}),
                )
                res = await adapter.ping()
                return _pack_ping_result(res)

            if exchange_name in {"t", "tinkoff", "t-bank", "tbank"}:
                from app.integrations.T.adapter import TAdapter

                token = integration.token or integration.access_token or integration.api_key or ""
                adapter = TAdapter(
                    token=token,
                    account_id=integration.account_id,
                    app_name=_normalize_str(raw.get("app_name")),
                    extra_params=_pick_client_params(raw),
                )
                res = await adapter.ping()
                return _pack_ping_result(res)

            if exchange_name in {"bcs"}:
                from app.integrations.BCS.adapter import BcsAdapter

                adapter = BcsAdapter(
                    access_token=integration.access_token,
                    refresh_token=integration.refresh_token or integration.token,
                    client_id=integration.client_id or "trade-api-read",
                    access_expires_at=integration.token_expires_at,
                    refresh_expires_at=integration.refresh_expires_at,
                    token_margin_s=int(raw.get("token_margin_s", 300)),
                    base_url=raw.get("base_url") or BcsAdapter.DEFAULT_BASE_URL,
                    timeout_s=float(raw.get("timeout_s", 20.0)),
                    extra_headers=_normalize_dict(raw.get("extra_headers")),
                    verify_tls=bool(raw.get("verify_tls", True)),
                )
                try:
                    res = await adapter.ping()
                finally:
                    await adapter.aclose()
                return _pack_ping_result(res)

            if exchange_name in {"finam"}:
                from app.integrations.Finam.adapter import FinamAdapter

                secret = integration.secret or integration.api_secret or integration.token or ""
                adapter = FinamAdapter(
                    secret=secret,
                    account_id=integration.account_id,
                    extra_params=_pick_client_params(raw),
                )
                try:
                    res = await adapter.ping()
                finally:
                    await adapter.aclose()
                return _pack_ping_result(res)

            if exchange_name in {"ton"}:
                from app.integrations.TON.adapter import TONAdapter

                address_list = _normalize_address_list(addresses)
                if not address_list:
                    address_list = await sync_to_async(list)(
                        WalletAddress.objects.filter(integration_id=integration.id)
                        .values_list("address", flat=True)
                    )
                    address_list = _normalize_address_list(address_list)

                adapter = TONAdapter(
                    toncenter_api_key=_normalize_str(raw.get("toncenter_api_key")),
                    tonapi_api_key=_normalize_str(raw.get("tonapi_api_key")),
                    toncenter_base_url=raw.get("toncenter_base_url")
                    or TONAdapter.DEFAULT_TONCENTER_URL,
                    tonapi_base_url=raw.get("tonapi_base_url", TONAdapter.DEFAULT_TONAPI_URL),
                    timeout_s=float(raw.get("timeout_s", TONAdapter.DEFAULT_TIMEOUT_S)),
                    verify_tls=bool(raw.get("verify_tls", True)),
                    extra_headers=_normalize_dict(raw.get("extra_headers")),
                )
                try:
                    res = await adapter.ping(addresses=address_list)
                finally:
                    await adapter.aclose()
                return _pack_ping_result(res)
        except Exception as exc:
            return IntegrationPingResult(
                ok=False,
                message="Ping failed",
                error_type=type(exc).__name__,
                error_code="PING_FAILED",
                raw_error=str(exc),
            )

        return IntegrationPingResult(
            ok=False,
            message=f"Unsupported integration: {integration.exchange_id.name}",
            error_type="ValueError",
            error_code="UNSUPPORTED_INTEGRATION",
        )


def _normalize_exchange_name(value: Optional[str]) -> str:
    return (value or "").strip().lower()


def _normalize_str(value: Optional[object]) -> Optional[str]:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _normalize_dict(value: Optional[object]) -> Optional[dict]:
    if isinstance(value, dict):
        return dict(value)
    return None


def _normalize_address_list(values: Optional[List[str]]) -> List[str]:
    if not values:
        return []
    return [item.strip() for item in values if item and str(item).strip()]


def _pick_client_params(raw: dict) -> dict:
    client_params = raw.get("client_params")
    if isinstance(client_params, dict):
        return dict(client_params)
    filtered = {k: v for k, v in raw.items() if k not in {"testnet", "recv_window", "account_type"}}
    return filtered


def _pack_ping_result(payload) -> IntegrationPingResult:
    return IntegrationPingResult(
        ok=bool(getattr(payload, "ok", False)),
        message=getattr(payload, "message", None),
        error_type=getattr(payload, "error_type", None),
        error_code=getattr(payload, "error_code", None),
        status_code=getattr(payload, "status_code", None),
        raw_error=getattr(payload, "raw_error", None),
        account_ids=getattr(payload, "account_ids", None),
        ok_addresses=getattr(payload, "ok_addresses", None),
        failed_addresses=getattr(payload, "failed_addresses", None),
    )
