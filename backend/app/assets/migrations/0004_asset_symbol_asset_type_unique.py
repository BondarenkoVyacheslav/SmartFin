from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("assets", "0003_add_asset_type_code"),
    ]

    operations = [
        migrations.AlterField(
            model_name="asset",
            name="symbol",
            field=models.CharField(max_length=50),
        ),
        migrations.AddConstraint(
            model_name="asset",
            constraint=models.UniqueConstraint(
                fields=("symbol", "asset_type"),
                name="asset_symbol_asset_type_unique",
            ),
        ),
    ]
