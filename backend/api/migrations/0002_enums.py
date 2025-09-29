from django.db import migrations


class Migration(migrations.Migration):
    
    dependencies = [
        ('api', '0001_extensions'),
    ]

    operations = [
        # Create ENUM types with IF NOT EXISTS
        migrations.RunSQL(
            "DO $$ BEGIN CREATE TYPE asset_class_enum AS ENUM ('stock','bond','fund','crypto','fiat','metal','cash','deposit','other'); EXCEPTION WHEN duplicate_object THEN null; END $$;",
            reverse_sql="DROP TYPE IF EXISTS asset_class_enum;"
        ),
        migrations.RunSQL(
            "DO $$ BEGIN CREATE TYPE transaction_type_enum AS ENUM ('buy','sell','deposit','withdraw','transfer_in','transfer_out','dividend','coupon','interest','fee','split','merge','adjustment'); EXCEPTION WHEN duplicate_object THEN null; END $$;",
            reverse_sql="DROP TYPE IF EXISTS transaction_type_enum;"
        ),
        migrations.RunSQL(
            "DO $$ BEGIN CREATE TYPE price_interval_enum AS ENUM ('tick','min','hour','day'); EXCEPTION WHEN duplicate_object THEN null; END $$;",
            reverse_sql="DROP TYPE IF EXISTS price_interval_enum;"
        ),
    ]
