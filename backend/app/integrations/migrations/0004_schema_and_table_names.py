from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("integrations", "0003_exchange_kind_integration_access_token_and_more"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    """
DO $$
BEGIN
    EXECUTE 'CREATE SCHEMA IF NOT EXISTS integrations';
    IF to_regclass('public.integrations_exchange') IS NOT NULL THEN
        EXECUTE 'ALTER TABLE public.integrations_exchange SET SCHEMA integrations';
    END IF;
    IF to_regclass('integrations.integrations_exchange') IS NOT NULL THEN
        EXECUTE 'ALTER TABLE integrations.integrations_exchange RENAME TO "exchange"';
    END IF;
    IF to_regclass('public.integrations_integration') IS NOT NULL THEN
        EXECUTE 'ALTER TABLE public.integrations_integration SET SCHEMA integrations';
    END IF;
    IF to_regclass('integrations.integrations_integration') IS NOT NULL THEN
        EXECUTE 'ALTER TABLE integrations.integrations_integration RENAME TO "integration"';
    END IF;
    IF to_regclass('public.integrations_walletaddress') IS NOT NULL THEN
        EXECUTE 'ALTER TABLE public.integrations_walletaddress SET SCHEMA integrations';
    END IF;
    IF to_regclass('integrations.integrations_walletaddress') IS NOT NULL THEN
        EXECUTE 'ALTER TABLE integrations.integrations_walletaddress RENAME TO "walletaddress"';
    END IF;
END $$;
""",
                    reverse_sql="""
DO $$
BEGIN
    IF to_regclass('integrations."exchange"') IS NOT NULL THEN
        EXECUTE 'ALTER TABLE integrations."exchange" RENAME TO integrations_exchange';
        EXECUTE 'ALTER TABLE integrations.integrations_exchange SET SCHEMA public';
    END IF;
    IF to_regclass('integrations."integration"') IS NOT NULL THEN
        EXECUTE 'ALTER TABLE integrations."integration" RENAME TO integrations_integration';
        EXECUTE 'ALTER TABLE integrations.integrations_integration SET SCHEMA public';
    END IF;
    IF to_regclass('integrations."walletaddress"') IS NOT NULL THEN
        EXECUTE 'ALTER TABLE integrations."walletaddress" RENAME TO integrations_walletaddress';
        EXECUTE 'ALTER TABLE integrations.integrations_walletaddress SET SCHEMA public';
    END IF;
END $$;
""",
                )
            ],
            state_operations=[
                migrations.AlterModelTable(name="exchange", table='"integrations"."exchange"'),
                migrations.AlterModelTable(name="integration", table='"integrations"."integration"'),
                migrations.AlterModelTable(name="walletaddress", table='"integrations"."walletaddress"'),
            ],
        )
    ]
