from django.db import migrations


def seed_asset_types(apps, schema_editor):
    AssetType = apps.get_model("assets", "AssetType")

    asset_types = [
        ("Криптовалюты", "Крипта и стейблкоины"),
        ("Акции РФ", "Публичные компании, торгующиеся на российских площадках"),
        ("Акции США", "Публичные компании, торгующиеся на американских площадках"),
        ("Фиат", "Наличные и безналичные средства"),
        ("Банковский вклад", "Депозиты в банках"),
        ("Облигации", "Гособлигации и корпоративные облигации"),
        ("Валюты", "Позиции в иностранных валютах"),
        ("Драгоценные металлы", "Слитки, обезличенные металлические счета"),
    ]

    for name, description in asset_types:
        AssetType.objects.get_or_create(
            name=name,
            defaults={"description": description},
        )


def unseed_asset_types(apps, schema_editor):
    AssetType = apps.get_model("assets", "AssetType")
    names = [
        "Криптовалюты",
        "Акции РФ",
        "Акции США",
        "Фиат",
        "Банковский вклад",
        "Облигации",
        "Валюты",
        "Драгоценные металлы",
    ]
    AssetType.objects.filter(name__in=names).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("assets", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_asset_types, reverse_code=unseed_asset_types),
    ]
