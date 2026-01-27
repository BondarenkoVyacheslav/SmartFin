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


def _pick_name(name: Optional[str], symbol: str) -> str:
    if name:
        return name[:255]
    return symbol[:255]


def _load_us_equity() -> Iterable[dict[str, object]]:
    migration_dir = Path(__file__).resolve().parent
    json_path = migration_dir / "us_equity.json"
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        return []
    return payload


def seed_alpaca_us_equity(apps, schema_editor):
    AssetType = apps.get_model("assets", "AssetType")
    Asset = apps.get_model("assets", "Asset")

    asset_type = (
        AssetType.objects.filter(code="stock_us").first()
        or AssetType.objects.filter(name="Акции США").first()
    )
    if asset_type is None:
        asset_type = AssetType.objects.create(
            name="Акции США",
            code="stock_us",
            description="Публичные компании, торгующиеся на американских площадках",
        )

    for item in _load_us_equity():
        if not isinstance(item, dict):
            continue
        if item.get("tradable") is not True:
            continue

        symbol = _to_str(item.get("symbol"))
        if not symbol:
            continue
        symbol = symbol.strip().upper()
        if not symbol:
            continue

        name = _pick_name(_to_str(item.get("name")), symbol)
        market_url = f"alpaca:{symbol}"

        Asset.objects.update_or_create(
            symbol=symbol,
            asset_type=asset_type,
            defaults={
                "name": name,
                "market_url": market_url,
                "currency": "USD",
            },
        )


def unseed_alpaca_us_equity(apps, schema_editor):
    AssetType = apps.get_model("assets", "AssetType")
    Asset = apps.get_model("assets", "Asset")

    asset_type = (
        AssetType.objects.filter(code="stock_us").first()
        or AssetType.objects.filter(name="Акции США").first()
    )
    if asset_type is None:
        return

    symbols: list[str] = []
    for item in _load_us_equity():
        if not isinstance(item, dict):
            continue
        if item.get("tradable") is not True:
            continue
        symbol = _to_str(item.get("symbol"))
        if not symbol:
            continue
        symbol = symbol.strip().upper()
        if not symbol:
            continue
        symbols.append(symbol)

    if symbols:
        Asset.objects.filter(asset_type=asset_type, symbol__in=symbols).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("assets", "0007_seed_moex_shares"),
    ]

    operations = [
        migrations.RunPython(seed_alpaca_us_equity, reverse_code=unseed_alpaca_us_equity),
    ]
