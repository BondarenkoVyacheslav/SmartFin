from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Optional

from django.db import migrations


def _to_str(value: object) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


def _load_binance_symbols() -> Iterable[dict[str, object]]:
    migration_dir = Path(__file__).resolve().parent
    json_path = migration_dir / "binance.json"
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return []
    symbols = payload.get("symbols") or []
    if not isinstance(symbols, list):
        return []
    return symbols


def _iter_binance_coins() -> Iterable[str]:
    seen: set[str] = set()
    for item in _load_binance_symbols():
        if not isinstance(item, dict):
            continue
        status = (_to_str(item.get("status")) or "").strip().upper()
        if status != "TRADING":
            continue
        if item.get("isSpotTradingAllowed") is False:
            continue

        for key in ("baseAsset", "quoteAsset"):
            symbol = _to_str(item.get(key))
            if not symbol:
                continue
            symbol = symbol.strip().upper()
            if not symbol or symbol in seen:
                continue
            seen.add(symbol)
            yield symbol


def seed_binance_crypto_assets(apps, schema_editor):
    AssetType = apps.get_model("assets", "AssetType")
    Asset = apps.get_model("assets", "Asset")

    asset_type = (
        AssetType.objects.filter(code="crypto").first()
        or AssetType.objects.filter(name="Криптовалюты").first()
    )
    if asset_type is None:
        asset_type = AssetType.objects.create(
            name="Криптовалюты",
            code="crypto",
            description="Крипта и стейблкоины",
        )

    for symbol in _iter_binance_coins():
        market_url = f"binance:{symbol}"
        Asset.objects.update_or_create(
            symbol=symbol,
            asset_type=asset_type,
            defaults={
                "name": symbol[:255],
                "market_url": market_url,
                "currency": symbol,
            },
        )


def unseed_binance_crypto_assets(apps, schema_editor):
    AssetType = apps.get_model("assets", "AssetType")
    Asset = apps.get_model("assets", "Asset")

    asset_type = (
        AssetType.objects.filter(code="crypto").first()
        or AssetType.objects.filter(name="Криптовалюты").first()
    )
    if asset_type is None:
        return

    symbols = list(_iter_binance_coins())
    if symbols:
        Asset.objects.filter(asset_type=asset_type, symbol__in=symbols).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("assets", "0008_seed_alpaca_us_equity"),
    ]

    operations = [
        migrations.RunPython(seed_binance_crypto_assets, reverse_code=unseed_binance_crypto_assets),
    ]
