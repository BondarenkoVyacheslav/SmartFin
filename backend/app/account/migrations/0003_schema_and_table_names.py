from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("account", "0002_user_has_subscription"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    """
DO $$
BEGIN
    EXECUTE 'CREATE SCHEMA IF NOT EXISTS account';
    IF to_regclass('public.account_user') IS NOT NULL THEN
        EXECUTE 'ALTER TABLE public.account_user SET SCHEMA account';
    END IF;
    IF to_regclass('account.account_user') IS NOT NULL THEN
        EXECUTE 'ALTER TABLE account.account_user RENAME TO "user"';
    END IF;
END $$;
""",
                    reverse_sql="""
DO $$
BEGIN
    IF to_regclass('account."user"') IS NOT NULL THEN
        EXECUTE 'ALTER TABLE account."user" RENAME TO account_user';
        EXECUTE 'ALTER TABLE account.account_user SET SCHEMA public';
    END IF;
END $$;
""",
                )
            ],
            state_operations=[
                migrations.AlterModelTable(name="user", table='"account"."user"'),
            ],
        )
    ]
