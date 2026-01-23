from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("transaction", "0003_add_transaction_types_executed_at"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    """
DO $$
BEGIN
    EXECUTE 'CREATE SCHEMA IF NOT EXISTS transaction';
    IF to_regclass('public.transaction_transaction') IS NOT NULL THEN
        EXECUTE 'ALTER TABLE public.transaction_transaction SET SCHEMA transaction';
    END IF;
    IF to_regclass('transaction.transaction_transaction') IS NOT NULL THEN
        EXECUTE 'ALTER TABLE transaction.transaction_transaction RENAME TO "transaction"';
    END IF;
END $$;
""",
                    reverse_sql="""
DO $$
BEGIN
    IF to_regclass('transaction."transaction"') IS NOT NULL THEN
        EXECUTE 'ALTER TABLE transaction."transaction" RENAME TO transaction_transaction';
        EXECUTE 'ALTER TABLE transaction.transaction_transaction SET SCHEMA public';
    END IF;
END $$;
""",
                )
            ],
            state_operations=[
                migrations.AlterModelTable(name="transaction", table='"transaction"."transaction"'),
            ],
        )
    ]
