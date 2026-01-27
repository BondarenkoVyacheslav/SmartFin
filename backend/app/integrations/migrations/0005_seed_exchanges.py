from django.db import migrations

EXCHANGES = [
    ("Binance", "Криптобиржа Binance", "exchange"),
    ("Bybit", "Криптобиржа Bybit", "exchange"),
    ("OKX", "Криптобиржа OKX", "exchange"),
    ("T-Bank", "Брокер Т-Банк", "broker"),
    ("BCS", "Брокер БКС", "broker"),
    ("Finam", "Брокер Финам", "broker"),
    ("TON", "Кошелек TON", "wallet"),
]


def seed_exchanges(apps, schema_editor):
    Exchange = apps.get_model("integrations", "Exchange")
    for name, description, kind in EXCHANGES:
        Exchange.objects.update_or_create(
            name=name,
            defaults={"description": description, "kind": kind},
        )


def unseed_exchanges(apps, schema_editor):
    Exchange = apps.get_model("integrations", "Exchange")
    names = [name for name, _, _ in EXCHANGES]
    Exchange.objects.filter(name__in=names).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("integrations", "0004_schema_and_table_names"),
    ]

    operations = [
        migrations.RunPython(seed_exchanges, reverse_code=unseed_exchanges),
    ]
