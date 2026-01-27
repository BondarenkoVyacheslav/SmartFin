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


def _pick_name(sec_name: Optional[str], short_name: Optional[str], fallback: str) -> str:
    if sec_name and len(sec_name) <= 255:
        return sec_name
    if short_name and len(short_name) <= 255:
        return short_name
    if sec_name:
        return sec_name[:255]
    return (short_name or fallback)[:255]


def _fetch_moex_securities_table(
    base_url: str,
    *,
    columns_query: Optional[str] = None,
    paginate: bool = False,
) -> dict:
    if not paginate:
        query = {"iss.meta": "off", "iss.only": "securities"}
        if columns_query:
            query["securities.columns"] = columns_query
        url = f"{base_url}?{urlencode(query)}"
        try:
            with urlopen(url, timeout=30) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # pragma: no cover - network dependent
            raise RuntimeError(f"Failed to fetch MOEX securities snapshot: {exc}") from exc

        table = payload.get("securities")
        if not isinstance(table, dict):
            return {}
        return table

    limit = 100
    start = 0
    columns: list[str] = []
    rows: list[list[object]] = []

    while True:
        query = {
            "iss.meta": "off",
            "iss.only": "securities",
            "start": start,
            "limit": limit,
        }
        if columns_query:
            query["securities.columns"] = columns_query

        url = f"{base_url}?{urlencode(query)}"
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


def _load_moex_securities(config: dict[str, object]) -> Iterable[dict[str, Optional[str]]]:
    local_json_paths = config.get("local_json_paths") or []
    snapshot_path = config.get("snapshot_path")

    table: dict = {}
    used_local = False
    used_snapshot = False

    for path in local_json_paths:
        if path and path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            table = payload.get("securities") if isinstance(payload, dict) else payload
            if not isinstance(table, dict):
                table = {}
            used_local = True
            break

    if not used_local and isinstance(snapshot_path, Path) and snapshot_path.exists():
        payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
        table = payload.get("securities") if isinstance(payload, dict) else payload
        if not isinstance(table, dict):
            table = {}
        used_snapshot = True

    if not used_local and not used_snapshot:
        table = _fetch_moex_securities_table(
            config["url"],
            columns_query=config.get("columns_query"),
            paginate=bool(config.get("paginate")),
        )

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


def _get_asset_type(AssetType, filters: list[tuple[str, str]], create_data: dict) -> object:
    for field, value in filters:
        asset_type = AssetType.objects.filter(**{field: value}).first()
        if asset_type is not None:
            return asset_type
    return AssetType.objects.create(**create_data)


def _find_asset_type(AssetType, filters: list[tuple[str, str]]) -> Optional[object]:
    for field, value in filters:
        asset_type = AssetType.objects.filter(**{field: value}).first()
        if asset_type is not None:
            return asset_type
    return None


def _pick_currency(item: dict[str, Optional[str]], fields: list[str]) -> str:
    for field in fields:
        value = item.get(field)
        if value:
            return _normalize_currency(value)
    return _normalize_currency(None)


def _get_moex_configs() -> list[dict[str, object]]:
    migration_dir = Path(__file__).resolve().parent
    base_dir = Path(__file__).resolve().parents[2]

    return [
        {
            "name": "shares",
            "url": "https://iss.moex.com/iss/engines/stock/markets/shares/boards/TQBR/securities.json",
            "snapshot_path": base_dir / "marketdata" / "MOEX" / "tqbr_securities_snapshot.json",
            "local_json_paths": [],
            "paginate": False,
            "columns_query": None,
            "asset_type_filters": [
                ("code", "stock_ru"),
                ("name", "Акции РФ"),
            ],
            "asset_type_create": {
                "name": "Акции РФ",
                "code": "stock_ru",
                "description": "Публичные компании, торгующиеся на российских площадках",
            },
            "market_url_prefix": "moex-stock:",
            "currency_fields": ["currency"],
            "name_fallback": "MOEX Share",
        },
        {
            "name": "etf",
            "url": "https://iss.moex.com/iss/engines/stock/markets/shares/boards/TQTF/securities.json",
            "snapshot_path": base_dir / "marketdata" / "MOEX" / "tqtf_securities_snapshot.json",
            "local_json_paths": [],
            "paginate": False,
            "columns_query": None,
            "asset_type_filters": [
                ("code", "etf_ru"),
                ("name", "ETF РФ"),
                ("name", "ETF"),
            ],
            "asset_type_create": {
                "name": "ETF РФ",
                "code": "etf_ru",
                "description": "Биржевые фонды (ETF/БПИФ), торгующиеся на российских площадках",
            },
            "market_url_prefix": "moex-etf:",
            "currency_fields": ["currency"],
            "name_fallback": "MOEX ETF",
        },
        {
            "name": "bonds_tqob",
            "url": "https://iss.moex.com/iss/engines/stock/markets/bonds/boards/TQOB/securities.json",
            "snapshot_path": base_dir / "marketdata" / "MOEX" / "tqob_securities_snapshot.json",
            "local_json_paths": [],
            "paginate": True,
            "columns_query": None,
            "asset_type_filters": [
                ("code", "bond_ru"),
                ("code", "bond"),
                ("name", "Облигации"),
                ("name", "Гособлигации"),
            ],
            "asset_type_create": {
                "name": "Облигации РФ",
                "code": "bond_ru",
                "description": "Государственные облигации РФ (TQOB)",
            },
            "market_url_prefix": "moex-bond:",
            "currency_fields": ["faceunit", "currency"],
            "name_fallback": "MOEX Bond",
        },
        {
            "name": "bonds_tqcb",
            "url": "https://iss.moex.com/iss/engines/stock/markets/bonds/boards/TQCB/securities.json",
            "snapshot_path": base_dir / "marketdata" / "MOEX" / "tqcb_securities_snapshot.json",
            "local_json_paths": [
                migration_dir / "tqcb.json",
                migration_dir / "tqcb_data.json",
            ],
            "paginate": True,
            "columns_query": "SECID,SECNAME,SHORTNAME,CURRENCYID,FACEUNIT,STATUS",
            "asset_type_filters": [
                ("code", "bond"),
                ("name", "Облигации"),
            ],
            "asset_type_create": {
                "name": "Облигации",
                "code": "bond",
                "description": "Корпоративные облигации (TQCB)",
            },
            "market_url_prefix": "moex-bond:",
            "currency_fields": ["faceunit", "currency"],
            "name_fallback": "MOEX Bond",
        },
        {
            "name": "currency_cets",
            "url": "https://iss.moex.com/iss/engines/currency/markets/selt/boards/CETS/securities.json",
            "snapshot_path": base_dir / "marketdata" / "MOEX" / "cets_securities_snapshot.json",
            "local_json_paths": [
                migration_dir / "cets.json",
                migration_dir / "cets_data.json",
            ],
            "paginate": True,
            "columns_query": "SECID,SECNAME,SHORTNAME,CURRENCYID,FACEUNIT,STATUS",
            "asset_type_filters": [
                ("code", "currency"),
                ("name", "Валюты"),
            ],
            "asset_type_create": {
                "name": "Валюты",
                "code": "currency",
                "description": "Валютные инструменты MOEX CETS",
            },
            "market_url_prefix": "moex-currency:",
            "currency_fields": ["currency", "faceunit"],
            "name_fallback": "MOEX Currency",
        },
    ]


def seed_moex_assets(apps, schema_editor):
    AssetType = apps.get_model("assets", "AssetType")
    Asset = apps.get_model("assets", "Asset")

    for config in _get_moex_configs():
        asset_type = _get_asset_type(
            AssetType,
            config["asset_type_filters"],
            config["asset_type_create"],
        )

        for item in _load_moex_securities(config):
            status = (item.get("status") or "").strip().upper()
            if status and status != "A":
                continue

            symbol = item["secid"]
            name = _pick_name(item.get("secname"), item.get("shortname"), config["name_fallback"])
            currency = _pick_currency(item, config["currency_fields"])
            market_url = f"{config['market_url_prefix']}{symbol}"

            Asset.objects.update_or_create(
                symbol=symbol,
                asset_type=asset_type,
                defaults={
                    "name": name,
                    "market_url": market_url,
                    "currency": currency,
                },
            )


def unseed_moex_assets(apps, schema_editor):
    AssetType = apps.get_model("assets", "AssetType")
    Asset = apps.get_model("assets", "Asset")

    for config in _get_moex_configs():
        asset_type = _find_asset_type(AssetType, config["asset_type_filters"])
        if asset_type is None:
            continue

        symbols: list[str] = []
        for item in _load_moex_securities(config):
            status = (item.get("status") or "").strip().upper()
            if status and status != "A":
                continue
            symbols.append(item["secid"])

        if symbols:
            Asset.objects.filter(asset_type=asset_type, symbol__in=symbols).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("assets", "0006_seed_moex_indices"),
    ]

    operations = [
        migrations.RunPython(seed_moex_assets, reverse_code=unseed_moex_assets),
    ]
