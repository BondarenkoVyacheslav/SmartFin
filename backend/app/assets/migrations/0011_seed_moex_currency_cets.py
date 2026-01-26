from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import urlencode
from urllib.request import urlopen

from django.db import migrations


def _to_str(value: object) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


def _normalize_currency(value: Optional[str]) -> str:
    if not value:
        return "RUB"
    code = value.strip().upper()
    if code == "SUR":
        return "RUB"
    return code or "RUB"


def _pick_name(sec_name: Optional[str], short_name: Optional[str]) -> str:
    if sec_name and len(sec_name) <= 255:
        return sec_name
    if short_name and len(short_name) <= 255:
        return short_name
    if sec_name:
        return sec_name[:255]
    return (short_name or "MOEX Currency")[:255]


def _fetch_moex_securities_table() -> dict:
    base_url = "https://iss.moex.com/iss/engines/currency/markets/selt/boards/CETS/securities.json"
    limit = 100
    start = 0
    columns: list[str] = []
    rows: list[list[object]] = []
    columns_query = "SECID,SECNAME,SHORTNAME,CURRENCYID,FACEUNIT,STATUS"

    while True:
        query = urlencode(
            {
                "iss.meta": "off",
                "iss.only": "securities",
                "securities.columns": columns_query,
                "start": start,
                "limit": limit,
            }
        )
        url = f"{base_url}?{query}"
        try:
            with urlopen(url, timeout=30) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # pragma: no cover - network dependent
            raise RuntimeError(f"Failed to fetch MOEX securities snapshot: {exc}") from exc

        table = payload.get("securities")
        if not isinstance(table, dict):
            break

        page_columns = table.get("columns") or []
        page_data = table.get("data") or []
        if columns == [] and isinstance(page_columns, list):
            columns = page_columns

        if not isinstance(page_data, list) or not page_data:
            break

        rows.extend(page_data)
        if len(page_data) < limit:
            break

        start += limit

    return {"columns": columns, "data": rows}


def _load_moex_securities() -> Iterable[dict[str, Optional[str]]]:
    migration_dir = Path(__file__).resolve().parent
    local_json_path = migration_dir / "cets.json"
    legacy_local_json_path = migration_dir / "cets_data.json"
    base_dir = Path(__file__).resolve().parents[2]
    json_path = base_dir / "marketdata" / "MOEX" / "cets_securities_snapshot.json"
    if local_json_path.exists():
        payload = json.loads(local_json_path.read_text(encoding="utf-8"))
        table = payload.get("securities") if isinstance(payload, dict) else payload
        if not isinstance(table, dict):
            table = {}
    elif legacy_local_json_path.exists():
        payload = json.loads(legacy_local_json_path.read_text(encoding="utf-8"))
        table = payload.get("securities") if isinstance(payload, dict) else payload
        if not isinstance(table, dict):
            table = {}
    elif json_path.exists():
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        table = payload.get("securities") if isinstance(payload, dict) else payload
        if not isinstance(table, dict):
            table = {}
    else:
        table = _fetch_moex_securities_table()

    columns = table.get("columns") or []
    data = table.get("data") or []
    if not isinstance(columns, list) or not isinstance(data, list):
        return []

    idx = {col: i for i, col in enumerate(columns)}
    seen: set[str] = set()

    for row in data:
        if not isinstance(row, list):
            continue

        def get(col: str) -> Optional[object]:
            pos = idx.get(col)
            if pos is None or pos >= len(row):
                return None
            return row[pos]

        secid = _to_str(get("SECID"))
        if not secid or secid in seen:
            continue
        seen.add(secid)

        yield {
            "secid": secid,
            "secname": _to_str(get("SECNAME")),
            "shortname": _to_str(get("SHORTNAME")),
            "currency": _to_str(get("CURRENCYID")),
            "faceunit": _to_str(get("FACEUNIT")),
            "status": _to_str(get("STATUS")),
        }


def seed_moex_currency_cets(apps, schema_editor):
    AssetType = apps.get_model("assets", "AssetType")
    Asset = apps.get_model("assets", "Asset")

    asset_type = (
        AssetType.objects.filter(code="currency").first()
        or AssetType.objects.filter(name="Валюты").first()
    )
    if asset_type is None:
        asset_type = AssetType.objects.create(
            name="Валюты",
            code="currency",
            description="Валютные инструменты MOEX CETS",
        )

    for item in _load_moex_securities():
        status = (item.get("status") or "").strip().upper()
        if status and status != "A":
            continue

        symbol = item["secid"]
        name = _pick_name(item.get("secname"), item.get("shortname"))
        currency = _normalize_currency(item.get("currency") or item.get("faceunit"))
        market_url = f"moex-currency:{symbol}"

        Asset.objects.update_or_create(
            symbol=symbol,
            asset_type=asset_type,
            defaults={
                "name": name,
                "market_url": market_url,
                "currency": currency,
            },
        )


def unseed_moex_currency_cets(apps, schema_editor):
    AssetType = apps.get_model("assets", "AssetType")
    Asset = apps.get_model("assets", "Asset")

    asset_type = (
        AssetType.objects.filter(code="currency").first()
        or AssetType.objects.filter(name="Валюты").first()
    )
    if asset_type is None:
        return

    symbols: list[str] = []
    for item in _load_moex_securities():
        status = (item.get("status") or "").strip().upper()
        if status and status != "A":
            continue
        symbols.append(item["secid"])

    if symbols:
        Asset.objects.filter(asset_type=asset_type, symbol__in=symbols).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("assets", "0010_seed_moex_bonds_tqcb"),
    ]

    operations = [
        migrations.RunPython(seed_moex_currency_cets, reverse_code=unseed_moex_currency_cets),
    ]
