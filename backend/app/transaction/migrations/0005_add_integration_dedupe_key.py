from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("integrations", "0004_schema_and_table_names"),
        ("transaction", "0004_schema_and_table_names"),
    ]

    operations = [
        migrations.AddField(
            model_name="transaction",
            name="integration",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="transactions",
                to="integrations.integration",
            ),
        ),
        migrations.AddField(
            model_name="transaction",
            name="dedupe_key",
            field=models.CharField(blank=True, db_index=True, max_length=64, null=True),
        ),
        migrations.AddConstraint(
            model_name="transaction",
            constraint=models.UniqueConstraint(
                fields=("integration", "dedupe_key"),
                name="transaction_unique_integration_dedupe",
            ),
        ),
    ]
