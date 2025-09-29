# Business models migration

import django.db.models.deletion
import django.utils.timezone
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0004_core_models'),
    ]

    operations = [
        migrations.CreateModel(
            name='Asset',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('symbol', models.TextField()),
                ('name', models.TextField()),
                ('isin', models.TextField(blank=True, null=True)),
                ('metadata', models.JSONField(default=dict)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('exchange', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='api.exchange')),
                ('trading_currency', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='api.currency')),
            ],
            options={
                'db_table': 'asset',
            },
        ),
        # Add the class field with custom SQL since Django doesn't support ENUM directly
        migrations.RunSQL(
            "ALTER TABLE asset ADD COLUMN class asset_class_enum NOT NULL DEFAULT 'other';",
            reverse_sql="ALTER TABLE asset DROP COLUMN class;"
        ),
        migrations.CreateModel(
            name='AssetIdentifier',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('id_type', models.TextField()),
                ('id_value', models.TextField()),
                ('asset', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='api.asset')),
            ],
            options={
                'db_table': 'asset_identifier',
            },
        ),
        migrations.CreateModel(
            name='Portfolio',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('name', models.TextField()),
                ('settings', models.JSONField(default=dict)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('base_currency', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='api.currency')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'portfolio',
            },
        ),
        migrations.CreateModel(
            name='Transaction',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('tx_time', models.DateTimeField()),
                ('quantity', models.DecimalField(decimal_places=18, default=0, max_digits=38)),
                ('price', models.DecimalField(blank=True, decimal_places=10, max_digits=38, null=True)),
                ('fee', models.DecimalField(decimal_places=10, default=0, max_digits=38)),
                ('notes', models.TextField(blank=True, null=True)),
                ('metadata', models.JSONField(default=dict)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('asset', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='api.asset')),
                ('linked_tx', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='api.transaction')),
                ('portfolio', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='api.portfolio')),
                ('price_currency', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='api.currency')),
            ],
            options={
                'db_table': 'transaction',
            },
        ),
        # Add tx_type field with ENUM
        migrations.RunSQL(
            "ALTER TABLE transaction ADD COLUMN tx_type transaction_type_enum NOT NULL DEFAULT 'buy';",
            reverse_sql="ALTER TABLE transaction DROP COLUMN tx_type;"
        ),
        migrations.CreateModel(
            name='Price',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('ts', models.DateTimeField()),
                ('price', models.DecimalField(decimal_places=10, max_digits=38)),
                ('source', models.TextField()),
                ('metadata', models.JSONField(default=dict)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('asset', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='api.asset')),
                ('currency', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='api.currency')),
            ],
            options={
                'db_table': 'price',
            },
        ),
        # Add interval field with ENUM
        migrations.RunSQL(
            "ALTER TABLE price ADD COLUMN interval price_interval_enum NOT NULL DEFAULT 'day';",
            reverse_sql="ALTER TABLE price DROP COLUMN interval;"
        ),
        migrations.CreateModel(
            name='FxRate',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('ts', models.DateTimeField()),
                ('rate', models.DecimalField(decimal_places=10, max_digits=38)),
                ('source', models.TextField()),
                ('base_currency', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='base_fx_rates', to='api.currency')),
                ('quote_currency', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='quote_fx_rates', to='api.currency')),
            ],
            options={
                'db_table': 'fx_rate',
            },
        ),
        migrations.CreateModel(
            name='Integration',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('provider', models.TextField()),
                ('display_name', models.TextField()),
                ('status', models.TextField(default='active')),
                ('credentials_encrypted', models.TextField()),
                ('last_sync_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'integration',
            },
        ),
        migrations.CreateModel(
            name='Advice',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('kind', models.TextField()),
                ('message', models.TextField()),
                ('score', models.DecimalField(blank=True, decimal_places=4, max_digits=8, null=True)),
                ('payload', models.JSONField(default=dict)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('portfolio', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='api.portfolio')),
            ],
            options={
                'db_table': 'advice',
            },
        ),
        migrations.CreateModel(
            name='AuditLog',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('ts', models.DateTimeField(default=django.utils.timezone.now)),
                ('action', models.TextField()),
                ('target_type', models.TextField(blank=True, null=True)),
                ('target_id', models.UUIDField(blank=True, null=True)),
                ('ip', models.GenericIPAddressField(blank=True, null=True)),
                ('user_agent', models.TextField(blank=True, null=True)),
                ('details', models.JSONField(default=dict)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'audit_log',
            },
        ),
    ]
