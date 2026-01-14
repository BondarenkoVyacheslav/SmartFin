from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("portfolio", "0001_initial"),
        ("transaction", "0001_initial"),
        ("assets", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="portfolio",
            name="transactions",
            field=models.ManyToManyField(
                related_name="portfolio_transactions",
                through="transaction.Transaction",
                to="assets.asset",
            ),
        ),
    ]
