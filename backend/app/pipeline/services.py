from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import random
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone as dt_timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Optional

import redis
from django.db import transaction as db_transaction
from django.utils import timezone

from app.analytics.models import PortfolioPositionDaily, PortfolioValuationDaily
from app.assets.models import Asset, AssetType
from app.integrations.models import Integration, WalletAddress
from app.portfolio.models import Portfolio, PortfolioAsset
from app.transaction.models import Transaction

logger = logging.getLogger(__name__)


SOURCE_QUEUE_MAP = {
    "finam": "sync_ru_brokers",
    "t": "sync_ru_brokers",
    "tinkoff": "sync_ru_brokers",
    "t-bank": "sync_ru_brokers",
    "tbank": "sync_ru_brokers",
    "bcs": "sync_ru_brokers",
    "bks": "sync_ru_brokers",
    "binance": "sync_crypto",
    "bybit": "sync_crypto",
    "okx": "sync_crypto",
    "ton": "sync_ton",
}

CURRENCY_SYMBOLS = {
    "USD",
    "EUR",
    "RUB",
    "GBP",
    "CNY",
    "JPY",
    "HKD",
    "CHF",
    "AED",
    "TRY",
    "KZT",
    "BYN",
}


@dataclass(frozen=True)
class ConnectionSpec:
    user_id: int
    portfolio_id: int
    integration_id: int
    connection_id: int
    connection_kind: str
    source_type: str


class TransientSyncError(RuntimeError):
    """Retryable sync failure."""


def normalize_exchange_name(value: Optional[str]) -> str:
    return (value or "").strip().lower()


def resolve_source_type(exchange_name: str) -> Optional[str]:
    return SOURCE_QUEUE_MAP.get(normalize_exchange_name(exchange_name))


def list_active_connections() -> dict[int, list[ConnectionSpec]]:
    integrations = list(
        Integration.objects.select_related("portfolio_id", "exchange_id")
    )
    wallet_rows = list(
        WalletAddress.objects.select_related("integration_id", "portfolio_id")
        .filter(is_active=True)
    )
    wallets_by_integration: dict[int, list[WalletAddress]] = {}
    for wallet in wallet_rows:
        wallets_by_integration.setdefault(wallet.integration_id_id, []).append(wallet)

    by_user: dict[int, list[ConnectionSpec]] = {}
    for integration in integrations:
        exchange_name = normalize_exchange_name(integration.exchange_id.name)
        source_type = resolve_source_type(exchange_name)
        if not source_type:
            continue
        portfolio = integration.portfolio_id
        user_id = portfolio.user_id

        if exchange_name == "ton":
            wallets = wallets_by_integration.get(integration.id, [])
            for wallet in wallets:
                by_user.setdefault(user_id, []).append(
                    ConnectionSpec(
                        user_id=user_id,
                        portfolio_id=wallet.portfolio_id_id,
                        integration_id=integration.id,
                        connection_id=wallet.id,
                        connection_kind="ton_wallet",
                        source_type=source_type,
                    )
                )
            continue

        by_user.setdefault(user_id, []).append(
            ConnectionSpec(
                user_id=user_id,
                portfolio_id=portfolio.id,
                integration_id=integration.id,
                connection_id=integration.id,
                connection_kind="integration",
                source_type=source_type,
            )
        )

    return by_user


def acquire_daily_lock(redis_url: str, lock_key: str, ttl_seconds: int) -> bool:
    client = redis.from_url(redis_url)
    return bool(client.set(lock_key, "1", nx=True, ex=ttl_seconds))


def random_jitter_seconds(max_minutes: int) -> int:
    return random.randint(0, max_minutes * 60)


def parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt_timezone.utc)
    return parsed


def format_datetime(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt_timezone.utc)
    return value.isoformat()


def run_async(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    finally:
        asyncio.set_event_loop(None)
        loop.close()


def _to_decimal(value: Any) -> Optional[Decimal]:
    if value is None:
        return None
    try:
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _normalize_symbol(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return value.strip().upper() or None


def _is_currency_symbol(symbol: Optional[str]) -> bool:
    if not symbol:
        return False
    return symbol.upper() in CURRENCY_SYMBOLS


def _resolve_asset_type_code(source_type: str, symbol: Optional[str], *, is_balance: bool) -> str:
    if source_type in {"sync_crypto", "sync_ton"}:
        return "crypto"
    if source_type == "sync_ru_brokers":
        if is_balance and _is_currency_symbol(symbol):
            return "currency"
        return "stock_ru"
    return "crypto"


def _get_or_create_asset(
    *,
    symbol: str,
    asset_type_code: str,
    market_url_prefix: str,
    currency: Optional[str],
) -> Asset:
    asset_type = AssetType.objects.filter(code=asset_type_code).first()
    if asset_type is None:
        asset_type = AssetType.objects.create(
            name=asset_type_code,
            code=asset_type_code,
            description=asset_type_code,
        )

    asset = Asset.objects.filter(symbol=symbol, asset_type=asset_type).first()
    if asset is not None:
        return asset

    market_url = f"{market_url_prefix}:{symbol}"
    return Asset.objects.create(
        name=symbol,
        symbol=symbol,
        asset_type=asset_type,
        market_url=market_url,
        currency=currency or symbol,
    )


def _map_activity_to_transaction_type(activity_type: str, side: Optional[str]) -> Optional[str]:
    atype = (activity_type or "").strip().lower()
    side_norm = (side or "").strip().lower()

    if atype in {"spot_trade", "trade", "order", "buy", "sell"}:
        if side_norm == "buy":
            return "buy"
        if side_norm == "sell":
            return "sell"

    if atype == "futures_trade":
        if side_norm == "buy":
            return "futures_buy"
        if side_norm == "sell":
            return "futures_sell"

    if atype in {"deposit", "input", "transfer_in"}:
        return "deposit"
    if atype in {"withdraw", "withdrawal", "output", "transfer_out"}:
        return "withdrawal"

    if "transfer_in" in atype:
        return "deposit"
    if "transfer_out" in atype:
        return "withdrawal"

    if atype in {"conversion", "exchange", "currency_exchange"}:
        return "conversion"

    return None


def _extract_external_id(raw: Any) -> Optional[str]:
    if not isinstance(raw, dict):
        return None
    for key in (
        "id",
        "tradeId",
        "trade_id",
        "orderId",
        "order_id",
        "txId",
        "txid",
        "transaction_id",
        "hash",
        "uuid",
        "uid",
    ):
        value = raw.get(key)
        if value:
            return str(value)
    return None


def _build_dedupe_key(
    integration_id: int,
    activity_type: str,
    raw: Any,
    payload: dict[str, Any],
    *,
    suffix: Optional[str] = None,
) -> str:
    external_id = _extract_external_id(raw)
    if external_id:
        key = f"{integration_id}:{activity_type}:{external_id}"
    else:
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
        key = f"{integration_id}:{activity_type}:{digest}"

    if suffix:
        key = f"{key}:{suffix}"

    if len(key) > 240:
        key = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return key


def _build_transactions_from_activity(
    *,
    integration: Integration,
    portfolio: Portfolio,
    activity: Any,
    source_type: str,
    market_url_prefix: str,
) -> list[Transaction]:
    tx_type = _map_activity_to_transaction_type(activity.activity_type, activity.side)
    if tx_type is None:
        return []

    base_symbol = _normalize_symbol(activity.base_asset) or _normalize_symbol(activity.symbol)
    quote_symbol = _normalize_symbol(activity.quote_asset)
    amount = _to_decimal(activity.amount)
    price = _to_decimal(activity.price)
    executed_at = activity.timestamp

    payload = {
        "activity_type": activity.activity_type,
        "symbol": activity.symbol,
        "base_asset": activity.base_asset,
        "quote_asset": activity.quote_asset,
        "side": activity.side,
        "amount": activity.amount,
        "price": activity.price,
        "timestamp": format_datetime(activity.timestamp),
        "raw": activity.raw if isinstance(activity.raw, dict) else None,
    }

    if tx_type == "conversion":
        results: list[Transaction] = []
        if base_symbol and amount is not None:
            asset = _get_or_create_asset(
                symbol=base_symbol,
                asset_type_code=_resolve_asset_type_code(source_type, base_symbol, is_balance=False),
                market_url_prefix=market_url_prefix,
                currency=base_symbol,
            )
            key = _build_dedupe_key(
                integration.id,
                activity.activity_type,
                activity.raw,
                payload,
                suffix="from",
            )
            results.append(
                Transaction(
                    portfolio=portfolio,
                    asset=asset,
                    transaction_type="conversion",
                    amount=amount,
                    price=price,
                    price_currency=quote_symbol,
                    executed_at=executed_at,
                    source="INTEGRATION",
                    integration_dedupe_key=key,
                )
            )
        if quote_symbol and price is not None:
            asset = _get_or_create_asset(
                symbol=quote_symbol,
                asset_type_code=_resolve_asset_type_code(source_type, quote_symbol, is_balance=False),
                market_url_prefix=market_url_prefix,
                currency=quote_symbol,
            )
            key = _build_dedupe_key(
                integration.id,
                activity.activity_type,
                activity.raw,
                payload,
                suffix="to",
            )
            results.append(
                Transaction(
                    portfolio=portfolio,
                    asset=asset,
                    transaction_type="conversion",
                    amount=price,
                    price=amount,
                    price_currency=base_symbol,
                    executed_at=executed_at,
                    source="INTEGRATION",
                    integration_dedupe_key=key,
                )
            )
        return results

    if base_symbol is None or amount is None:
        return []

    asset = _get_or_create_asset(
        symbol=base_symbol,
        asset_type_code=_resolve_asset_type_code(source_type, base_symbol, is_balance=False),
        market_url_prefix=market_url_prefix,
        currency=base_symbol,
    )
    key = _build_dedupe_key(
        integration.id,
        activity.activity_type,
        activity.raw,
        payload,
    )
    return [
        Transaction(
            portfolio=portfolio,
            asset=asset,
            transaction_type=tx_type,
            amount=amount,
            price=price,
            price_currency=quote_symbol,
            executed_at=executed_at,
            source="INTEGRATION",
            integration_dedupe_key=key,
        )
    ]


def _persist_transactions(
    *,
    integration: Integration,
    portfolio: Portfolio,
    activities: Iterable[Any],
    source_type: str,
    market_url_prefix: str,
) -> int:
    to_create: list[Transaction] = []
    for activity in activities:
        to_create.extend(
            _build_transactions_from_activity(
                integration=integration,
                portfolio=portfolio,
                activity=activity,
                source_type=source_type,
                market_url_prefix=market_url_prefix,
            )
        )

    if not to_create:
        return 0

    with db_transaction.atomic():
        Transaction.objects.bulk_create(to_create, ignore_conflicts=True)
    return len(to_create)


def _persist_balances(
    *,
    portfolio: Portfolio,
    balances: Iterable[Any],
    source_type: str,
    market_url_prefix: str,
) -> int:
    updated = 0
    for balance in balances:
        symbol = _normalize_symbol(getattr(balance, "asset", None))
        total = _to_decimal(getattr(balance, "total", None) or getattr(balance, "free", None))
        if symbol is None or total is None:
            continue
        asset = _get_or_create_asset(
            symbol=symbol,
            asset_type_code=_resolve_asset_type_code(source_type, symbol, is_balance=True),
            market_url_prefix=market_url_prefix,
            currency=symbol,
        )
        PortfolioAsset.objects.update_or_create(
            portfolio=portfolio,
            asset=asset,
            defaults={"quantity": total},
        )
        updated += 1
    return updated


def _persist_positions(
    *,
    portfolio: Portfolio,
    positions: Iterable[Any],
    source_type: str,
    market_url_prefix: str,
) -> int:
    updated = 0
    for position in positions:
        symbol = _normalize_symbol(getattr(position, "symbol", None))
        qty = _to_decimal(getattr(position, "qty", None) or getattr(position, "size", None))
        if symbol is None or qty is None:
            continue
        avg_price = _to_decimal(getattr(position, "avg_price", None) or getattr(position, "entry_price", None))
        currency = _normalize_symbol(getattr(position, "currency", None))
        asset = _get_or_create_asset(
            symbol=symbol,
            asset_type_code=_resolve_asset_type_code(source_type, symbol, is_balance=False),
            market_url_prefix=market_url_prefix,
            currency=currency or symbol,
        )
        defaults: dict[str, Any] = {"quantity": qty}
        if avg_price is not None:
            defaults["avg_buy_price"] = avg_price
        if currency:
            defaults["buy_currency"] = currency
        PortfolioAsset.objects.update_or_create(
            portfolio=portfolio,
            asset=asset,
            defaults=defaults,
        )
        updated += 1
    return updated


def _build_adapter(integration: Integration, *, address: Optional[str] = None):
    exchange_name = normalize_exchange_name(integration.exchange_id.name)
    raw = integration.extra_params or {}

    if exchange_name == "binance":
        from app.integrations.Binance.adapter import BinanceAdapter

        return BinanceAdapter(
            api_key=integration.api_key or "",
            api_secret=integration.api_secret or "",
            testnet=bool(raw.get("testnet", False)),
            recv_window=int(raw.get("recv_window", 5000)),
            extra_params=dict(raw.get("client_params") or raw),
        )

    if exchange_name == "bybit":
        from app.integrations.Bybit.adapter import BybitAdapter

        return BybitAdapter(
            api_key=integration.api_key or "",
            api_secret=integration.api_secret or "",
            testnet=bool(raw.get("testnet", False)),
            recv_window=int(raw.get("recv_window", 5000)),
            extra_params=dict(raw.get("client_params") or {}),
        )

    if exchange_name == "okx":
        from app.integrations.OKX.adapter import OKXAdapter

        return OKXAdapter(
            api_key=integration.api_key or "",
            api_secret=integration.api_secret or "",
            passphrase=integration.passphrase or "",
            testnet=bool(raw.get("testnet", False)),
            flag=raw.get("flag"),
            use_server_time=bool(raw.get("use_server_time", False)),
            extra_params=dict(raw.get("client_params") or {}),
        )

    if exchange_name in {"t", "tinkoff", "t-bank", "tbank"}:
        from app.integrations.T.adapter import TAdapter

        token = integration.token or integration.access_token or integration.api_key or ""
        return TAdapter(
            token=token,
            account_id=integration.account_id,
            app_name=raw.get("app_name"),
            extra_params=dict(raw.get("client_params") or raw),
        )

    if exchange_name == "bcs":
        from app.integrations.BCS.adapter import BcsAdapter

        def token_updater(access_token, refresh_token, access_expires_at, refresh_expires_at):
            Integration.objects.filter(id=integration.id).update(
                access_token=access_token,
                refresh_token=refresh_token,
                token_expires_at=access_expires_at,
                refresh_expires_at=refresh_expires_at,
            )

        return BcsAdapter(
            access_token=integration.access_token,
            refresh_token=integration.refresh_token or integration.token,
            client_id=integration.client_id or "trade-api-read",
            access_expires_at=integration.token_expires_at,
            refresh_expires_at=integration.refresh_expires_at,
            token_margin_s=int(raw.get("token_margin_s", 300)),
            base_url=raw.get("base_url") or BcsAdapter.DEFAULT_BASE_URL,
            timeout_s=float(raw.get("timeout_s", 20.0)),
            extra_headers=raw.get("extra_headers") or None,
            verify_tls=bool(raw.get("verify_tls", True)),
            token_updater=token_updater,
        )

    if exchange_name == "finam":
        from app.integrations.Finam.adapter import FinamAdapter

        secret = integration.secret or integration.api_secret or integration.token or ""
        return FinamAdapter(
            secret=secret,
            account_id=integration.account_id,
            extra_params=dict(raw.get("client_params") or raw),
        )

    if exchange_name == "ton":
        from app.integrations.TON.adapter import TONAdapter

        return TONAdapter(
            toncenter_api_key=raw.get("toncenter_api_key"),
            tonapi_api_key=raw.get("tonapi_api_key"),
            toncenter_base_url=raw.get("toncenter_base_url") or TONAdapter.DEFAULT_TONCENTER_URL,
            tonapi_base_url=raw.get("tonapi_base_url") or TONAdapter.DEFAULT_TONAPI_URL,
            timeout_s=float(raw.get("timeout_s", TONAdapter.DEFAULT_TIMEOUT_S)),
            verify_tls=bool(raw.get("verify_tls", True)),
            extra_headers=raw.get("extra_headers") or None,
        )

    raise ValueError(f"Unsupported integration: {integration.exchange_id.name}")


def _close_adapter(adapter: Any) -> None:
    aclose = getattr(adapter, "aclose", None)
    if not callable(aclose):
        return
    try:
        run_async(aclose())
    except Exception:
        logger.exception("Failed to close adapter")


def sync_connection(
    *,
    connection_id: int,
    connection_kind: str,
    source_type: str,
) -> dict[str, Any]:
    if connection_kind == "ton_wallet":
        wallet = WalletAddress.objects.select_related("integration_id", "portfolio_id", "integration_id__exchange_id").get(
            id=connection_id
        )
        integration = wallet.integration_id
        portfolio = wallet.portfolio_id
        address = wallet.address
    else:
        integration = Integration.objects.select_related("portfolio_id", "exchange_id").get(id=connection_id)
        portfolio = integration.portfolio_id
        address = None

    extra = integration.extra_params or {}
    since = parse_datetime(extra.get("last_sync_at"))
    limit = int(extra.get("sync_limit") or os.environ.get("SYNC_ACTIVITY_LIMIT", 200))

    adapter = _build_adapter(integration, address=address)
    started_at = time.monotonic()
    exchange_name = normalize_exchange_name(integration.exchange_id.name)
    last_cursor_value = None
    try:
        if exchange_name == "ton":
            snapshot = run_async(
                adapter.fetch_snapshot(
                    address=address,
                    since=since,
                    limit=limit,
                    include_jettons=bool(extra.get("include_jettons", True)),
                    include_staking=bool(extra.get("include_staking", True)),
                )
            )
        elif exchange_name in {"t", "tinkoff", "t-bank", "tbank"}:
            snapshot = run_async(
                adapter.fetch_snapshot(
                    account_id=integration.account_id,
                    since=since,
                    limit=limit,
                )
            )
        elif exchange_name == "finam":
            snapshot = run_async(
                adapter.fetch_snapshot(
                    account_id=integration.account_id,
                    since=since,
                    limit=limit,
                )
            )
        else:
            snapshot = run_async(
                adapter.fetch_snapshot(
                    since=since,
                    limit=limit,
                )
            )
        last_cursor = getattr(adapter, "last_cursor", None)
        if callable(last_cursor):
            try:
                last_cursor_value = last_cursor()
            except Exception:
                last_cursor_value = None
    except Exception as exc:
        duration_ms = int((time.monotonic() - started_at) * 1000)
        logger.warning(
            "sync_connector failed source_type=%s integration_id=%s duration_ms=%s error=%s",
            source_type,
            integration.id,
            duration_ms,
            exc,
        )
        if _is_transient_error(exc):
            raise TransientSyncError(str(exc)) from exc
        raise
    finally:
        _close_adapter(adapter)

    market_prefix = exchange_name

    created_txs = _persist_transactions(
        integration=integration,
        portfolio=portfolio,
        activities=getattr(snapshot, "activities", []) or [],
        source_type=source_type,
        market_url_prefix=market_prefix,
    )
    balances_count = _persist_balances(
        portfolio=portfolio,
        balances=getattr(snapshot, "balances", []) or [],
        source_type=source_type,
        market_url_prefix=market_prefix,
    )
    positions_count = _persist_positions(
        portfolio=portfolio,
        positions=getattr(snapshot, "positions", []) or [],
        source_type=source_type,
        market_url_prefix=market_prefix,
    )

    extra = dict(extra)
    extra["last_sync_at"] = format_datetime(timezone.now())
    if last_cursor_value:
        extra["last_cursor"] = last_cursor_value
    Integration.objects.filter(id=integration.id).update(extra_params=extra)

    duration_ms = int((time.monotonic() - started_at) * 1000)
    return {
        "integration_id": integration.id,
        "portfolio_id": portfolio.id,
        "new_tx_count": created_txs,
        "positions_count": positions_count,
        "balances_count": balances_count,
        "duration_ms": duration_ms,
    }


def _is_transient_error(exc: Exception) -> bool:
    if isinstance(exc, TransientSyncError):
        return True
    try:
        import httpx

        if isinstance(exc, httpx.TimeoutException):
            return True
        if isinstance(exc, httpx.HTTPStatusError):
            status = exc.response.status_code if exc.response is not None else None
            if status and (status == 429 or status >= 500):
                return True
    except Exception:
        pass

    if isinstance(exc, (TimeoutError, ConnectionError)):
        return True
    return False


def _latest_price_base(portfolio_id: int, asset_id: int, base_currency: str) -> Optional[Decimal]:
    tx = (
        Transaction.objects.filter(
            portfolio_id=portfolio_id,
            asset_id=asset_id,
            price_currency=base_currency,
        )
        .order_by("-executed_at", "-created_at")
        .first()
    )
    if tx is None:
        return None
    return _to_decimal(tx.price)


def build_portfolio_snapshot_db_only(portfolio: Portfolio, snapshot_date: date) -> Optional[PortfolioValuationDaily]:
    base_currency = (portfolio.base_currency or "USD").strip().upper()
    positions = list(
        PortfolioAsset.objects.select_related("asset")
        .filter(portfolio_id=portfolio.id)
    )

    total_value = Decimal("0")
    with db_transaction.atomic():
        for position in positions:
            quantity = _to_decimal(position.quantity) or Decimal("0")
            price_base = None
            if position.avg_buy_price and position.buy_currency:
                if position.buy_currency.strip().upper() == base_currency:
                    price_base = _to_decimal(position.avg_buy_price)
            if price_base is None:
                asset_currency = (position.asset.currency or "").strip().upper()
                if asset_currency == base_currency:
                    price_base = _latest_price_base(portfolio.id, position.asset_id, base_currency)

            value_base = None
            if price_base is not None:
                value_base = quantity * price_base
                total_value += value_base

            PortfolioPositionDaily.objects.update_or_create(
                portfolio_id=portfolio.id,
                asset_id=position.asset_id,
                snapshot_date=snapshot_date,
                defaults={
                    "quantity": quantity,
                    "price_base": price_base,
                    "value_base": value_base,
                },
            )

        flow_qs = Transaction.objects.filter(
            portfolio_id=portfolio.id,
            transaction_type__in=("deposit", "withdrawal"),
        )
        flow_executed = list(flow_qs.filter(executed_at__date=snapshot_date))
        flow_created = list(flow_qs.filter(executed_at__isnull=True, created_at__date=snapshot_date))
        flows = flow_executed + flow_created

        net_flow = Decimal("0")
        for tx in flows:
            amount = _to_decimal(tx.amount) or Decimal("0")
            price = _to_decimal(tx.price)
            if price is not None and (tx.price_currency or "").strip().upper() == base_currency:
                value = amount * price
            else:
                asset_currency = (tx.asset.currency or "").strip().upper()
                if asset_currency != base_currency:
                    continue
                value = amount
            if tx.transaction_type == "withdrawal":
                value = -value
            net_flow += value

        prev_snapshot = PortfolioValuationDaily.objects.filter(
            portfolio_id=portfolio.id,
            snapshot_date=snapshot_date - timedelta(days=1),
        ).first()
        prev_value = prev_snapshot.value_base if prev_snapshot else Decimal("0")
        pnl_base = total_value - prev_value - net_flow

        valuation, _ = PortfolioValuationDaily.objects.update_or_create(
            portfolio_id=portfolio.id,
            snapshot_date=snapshot_date,
            defaults={
                "base_currency": base_currency,
                "value_base": total_value,
                "net_flow_base": net_flow,
                "pnl_base": pnl_base,
            },
        )

    return valuation


def build_daily_snapshots_for_user(user_id: int, snapshot_date: date) -> list[PortfolioValuationDaily]:
    results: list[PortfolioValuationDaily] = []
    for portfolio in Portfolio.objects.filter(user_id=user_id):
        valuation = build_portfolio_snapshot_db_only(portfolio, snapshot_date)
        if valuation is not None:
            results.append(valuation)
    return results


def compute_user_metrics(user_id: int, snapshot_date: date) -> dict[str, Any]:
    valuations = PortfolioValuationDaily.objects.filter(
        portfolio__user_id=user_id,
        snapshot_date=snapshot_date,
    )
    total_value = Decimal("0")
    for item in valuations:
        total_value += item.value_base
    return {
        "portfolio_count": valuations.count(),
        "total_value_base": total_value,
    }
