import importlib
import json
import os
from unittest import SkipTest
from unittest.mock import patch

from django.apps import apps as django_apps
from django.test import TestCase


_migration = importlib.import_module("assets.migrations.0010_seed_moex_bonds_tqcb")


class SeedMoexBondsTqcbTests(TestCase):
    def setUp(self) -> None:
        AssetType = django_apps.get_model("assets", "AssetType")
        self.Asset = django_apps.get_model("assets", "Asset")
        self.asset_type, _ = AssetType.objects.get_or_create(
            code="bond",
            defaults={"name": "Облигации"},
        )

    def test_seed_filters_status_and_uses_faceunit_currency(self) -> None:
        sample = [
            {
                "secid": "AAA",
                "secname": "Sec A",
                "shortname": "A",
                "currency": "RUB",
                "faceunit": "USD",
                "status": "A",
            },
            {
                "secid": "BBB",
                "secname": "Sec B",
                "shortname": "B",
                "currency": "SUR",
                "faceunit": None,
                "status": "N",
            },
        ]

        with patch.object(_migration, "_load_moex_securities", return_value=sample):
            _migration.seed_moex_bonds_tqcb(django_apps, None)

        self.assertEqual(self.Asset.objects.filter(asset_type=self.asset_type).count(), 1)
        asset = self.Asset.objects.get(symbol="AAA", asset_type=self.asset_type)
        self.assertEqual(asset.name, "Sec A")
        self.assertEqual(asset.currency, "USD")
        self.assertEqual(asset.market_url, "moex-bond:AAA")

    def test_seed_updates_existing_asset(self) -> None:
        self.Asset.objects.create(
            name="Old Name",
            symbol="AAA",
            asset_type=self.asset_type,
            market_url="moex-bond:AAA",
            currency="RUB",
        )
        sample = [
            {
                "secid": "AAA",
                "secname": "New Name",
                "shortname": "New",
                "currency": "EUR",
                "faceunit": None,
                "status": "A",
            },
        ]

        with patch.object(_migration, "_load_moex_securities", return_value=sample):
            _migration.seed_moex_bonds_tqcb(django_apps, None)

        asset = self.Asset.objects.get(symbol="AAA", asset_type=self.asset_type)
        self.assertEqual(asset.name, "New Name")
        self.assertEqual(asset.currency, "EUR")

    def test_unseed_removes_only_active(self) -> None:
        self.Asset.objects.create(
            name="Sec A",
            symbol="AAA",
            asset_type=self.asset_type,
            market_url="moex-bond:AAA",
            currency="USD",
        )
        self.Asset.objects.create(
            name="Sec B",
            symbol="BBB",
            asset_type=self.asset_type,
            market_url="moex-bond:BBB",
            currency="RUB",
        )
        sample = [
            {
                "secid": "AAA",
                "secname": "Sec A",
                "shortname": "A",
                "currency": "USD",
                "faceunit": None,
                "status": "A",
            },
            {
                "secid": "BBB",
                "secname": "Sec B",
                "shortname": "B",
                "currency": "RUB",
                "faceunit": None,
                "status": "N",
            },
        ]

        with patch.object(_migration, "_load_moex_securities", return_value=sample):
            _migration.unseed_moex_bonds_tqcb(django_apps, None)

        self.assertFalse(
            self.Asset.objects.filter(symbol="AAA", asset_type=self.asset_type).exists()
        )
        self.assertTrue(
            self.Asset.objects.filter(symbol="BBB", asset_type=self.asset_type).exists()
        )


class SeedMoexBondsTqcbLiveTests(TestCase):
    def test_live_fetch_and_parse_snapshot(self) -> None:
        if os.getenv("MOEX_LIVE") != "1":
            raise SkipTest("Set MOEX_LIVE=1 to run live MOEX request test")

        try:
            table = _migration._fetch_moex_securities_table()
        except RuntimeError as exc:
            raise SkipTest(str(exc)) from exc

        columns = table.get("columns") or []
        data = table.get("data") or []
        self.assertTrue(columns, "MOEX returned empty columns")
        self.assertTrue(data, "MOEX returned empty data")

        sample_row = data[0]
        sample_map = dict(zip(columns, sample_row))
        print("MOEX_TQCB_SAMPLE", json.dumps(sample_map, ensure_ascii=False))

        idx = {col: i for i, col in enumerate(columns)}

        def get(col: str):
            pos = idx.get(col)
            if pos is None or pos >= len(sample_row):
                return None
            return sample_row[pos]

        parsed = {
            "secid": _migration._to_str(get("SECID")),
            "secname": _migration._to_str(get("SECNAME")),
            "shortname": _migration._to_str(get("SHORTNAME")),
            "currency": _migration._to_str(get("CURRENCYID")),
            "faceunit": _migration._to_str(get("FACEUNIT")),
            "status": _migration._to_str(get("STATUS")),
        }
        print("MOEX_TQCB_PARSED", parsed)
