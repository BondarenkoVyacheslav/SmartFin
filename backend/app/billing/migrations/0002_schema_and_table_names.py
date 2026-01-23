from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0001_initial"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    """
DO $$
BEGIN
    EXECUTE 'CREATE SCHEMA IF NOT EXISTS billing';
    IF to_regclass('public.billing_plan') IS NOT NULL THEN
        EXECUTE 'ALTER TABLE public.billing_plan SET SCHEMA billing';
    END IF;
    IF to_regclass('billing.billing_plan') IS NOT NULL THEN
        EXECUTE 'ALTER TABLE billing.billing_plan RENAME TO "plan"';
    END IF;
    IF to_regclass('public.billing_subscription') IS NOT NULL THEN
        EXECUTE 'ALTER TABLE public.billing_subscription SET SCHEMA billing';
    END IF;
    IF to_regclass('billing.billing_subscription') IS NOT NULL THEN
        EXECUTE 'ALTER TABLE billing.billing_subscription RENAME TO "subscription"';
    END IF;
END $$;
""",
                    reverse_sql="""
DO $$
BEGIN
    IF to_regclass('billing."plan"') IS NOT NULL THEN
        EXECUTE 'ALTER TABLE billing."plan" RENAME TO billing_plan';
        EXECUTE 'ALTER TABLE billing.billing_plan SET SCHEMA public';
    END IF;
    IF to_regclass('billing."subscription"') IS NOT NULL THEN
        EXECUTE 'ALTER TABLE billing."subscription" RENAME TO billing_subscription';
        EXECUTE 'ALTER TABLE billing.billing_subscription SET SCHEMA public';
    END IF;
END $$;
""",
                )
            ],
            state_operations=[
                migrations.AlterModelTable(name="plan", table='"billing"."plan"'),
                migrations.AlterModelTable(name="subscription", table='"billing"."subscription"'),
            ],
        )
    ]
