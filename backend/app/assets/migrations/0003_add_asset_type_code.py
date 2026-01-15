from django.db import migrations, models


def populate_asset_type_codes(apps, schema_editor):
    AssetType = apps.get_model("assets", "AssetType")

    mapping = {
        "Криптовалюты": "crypto",
        "Акции РФ": "stock_ru",
        "Акции США": "stock_us",
        "Фиат": "fiat",
        "Банковский вклад": "deposit",
        "Облигации": "bond",
        "Валюты": "currency",
        "Драгоценные металлы": "metal",
        "Индексы": "index",
        "Фьючерсы": "futures",
    }

    for name, code in mapping.items():
        AssetType.objects.filter(name=name, code__isnull=True).update(code=code)
        AssetType.objects.filter(name=name, code="").update(code=code)

    remaining = AssetType.objects.filter(code__isnull=True) | AssetType.objects.filter(code="")
    for asset_type in remaining:
        asset_type.code = f"type_{asset_type.id}"
        asset_type.save(update_fields=["code"])


class Migration(migrations.Migration):
    dependencies = [
        ("assets", "0002_seed_asset_types"),
    ]

    operations = [
        migrations.AddField(
            model_name="assettype",
            name="code",
            field=models.CharField(max_length=50, null=True, unique=True),
        ),
        migrations.RunPython(
            populate_asset_type_codes,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="assettype",
            name="code",
            field=models.CharField(max_length=50, unique=True),
        ),
    ]
