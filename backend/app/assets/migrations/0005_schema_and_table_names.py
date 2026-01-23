from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("assets", "0004_asset_symbol_asset_type_unique"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    """
DO $$
BEGIN
    EXECUTE 'CREATE SCHEMA IF NOT EXISTS assets';
    IF to_regclass('public.assets_assettype') IS NOT NULL THEN
        EXECUTE 'ALTER TABLE public.assets_assettype SET SCHEMA assets';
    END IF;
    IF to_regclass('assets.assets_assettype') IS NOT NULL THEN
        EXECUTE 'ALTER TABLE assets.assets_assettype RENAME TO "assettype"';
    END IF;
    IF to_regclass('public.assets_asset') IS NOT NULL THEN
        EXECUTE 'ALTER TABLE public.assets_asset SET SCHEMA assets';
    END IF;
    IF to_regclass('assets.assets_asset') IS NOT NULL THEN
        EXECUTE 'ALTER TABLE assets.assets_asset RENAME TO "asset"';
    END IF;
END $$;
""",
                    reverse_sql="""
DO $$
BEGIN
    IF to_regclass('assets."assettype"') IS NOT NULL THEN
        EXECUTE 'ALTER TABLE assets."assettype" RENAME TO assets_assettype';
        EXECUTE 'ALTER TABLE assets.assets_assettype SET SCHEMA public';
    END IF;
    IF to_regclass('assets."asset"') IS NOT NULL THEN
        EXECUTE 'ALTER TABLE assets."asset" RENAME TO assets_asset';
        EXECUTE 'ALTER TABLE assets.assets_asset SET SCHEMA public';
    END IF;
END $$;
""",
                )
            ],
            state_operations=[
                migrations.AlterModelTable(name="assettype", table='"assets"."assettype"'),
                migrations.AlterModelTable(name="asset", table='"assets"."asset"'),
            ],
        )
    ]
