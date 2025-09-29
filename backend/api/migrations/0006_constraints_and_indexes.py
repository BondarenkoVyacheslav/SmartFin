# Constraints and indexes migration

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0005_business_models'),
    ]

    operations = [
        # Add constraints
        migrations.AlterUniqueTogether(
            name='asset',
            unique_together={('symbol', 'exchange')},
        ),
        migrations.AlterUniqueTogether(
            name='assetidentifier',
            unique_together={('id_type', 'id_value'), ('asset', 'id_type')},
        ),
        migrations.AlterUniqueTogether(
            name='portfolio',
            unique_together={('user', 'name')},
        ),
        migrations.AlterUniqueTogether(
            name='price',
            unique_together={('asset', 'ts', 'source', 'interval')},
        ),
        migrations.AlterUniqueTogether(
            name='fxrate',
            unique_together={('base_currency', 'quote_currency', 'ts', 'source')},
        ),
        migrations.AlterUniqueTogether(
            name='integration',
            unique_together={('user', 'provider', 'display_name')},
        ),
        
        # Add indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS ix_tx_portfolio_time ON transaction (portfolio_id, tx_time DESC);",
            reverse_sql="DROP INDEX IF EXISTS ix_tx_portfolio_time;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS ix_tx_asset_time ON transaction (asset_id, tx_time DESC);",
            reverse_sql="DROP INDEX IF EXISTS ix_tx_asset_time;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS ix_price_asset_ts ON price (asset_id, ts DESC);",
            reverse_sql="DROP INDEX IF EXISTS ix_price_asset_ts;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS ix_fx_pair_ts ON fx_rate (base_currency_id, quote_currency_id, ts DESC);",
            reverse_sql="DROP INDEX IF EXISTS ix_fx_pair_ts;"
        ),
    ]
