from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("analytics", "0002_add_daily_valuation_models"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    """
DO $$
BEGIN
    EXECUTE 'CREATE SCHEMA IF NOT EXISTS analytics';
    IF to_regclass('public.analytics_portfoliodailysnapshot') IS NOT NULL THEN
        EXECUTE 'ALTER TABLE public.analytics_portfoliodailysnapshot SET SCHEMA analytics';
    END IF;
    IF to_regclass('analytics.analytics_portfoliodailysnapshot') IS NOT NULL THEN
        EXECUTE 'ALTER TABLE analytics.analytics_portfoliodailysnapshot RENAME TO "portfoliodailysnapshot"';
    END IF;
    IF to_regclass('public.analytics_portfolioassetdailysnapshot') IS NOT NULL THEN
        EXECUTE 'ALTER TABLE public.analytics_portfolioassetdailysnapshot SET SCHEMA analytics';
    END IF;
    IF to_regclass('analytics.analytics_portfolioassetdailysnapshot') IS NOT NULL THEN
        EXECUTE 'ALTER TABLE analytics.analytics_portfolioassetdailysnapshot RENAME TO "portfolioassetdailysnapshot"';
    END IF;
    IF to_regclass('public.analytics_portfoliovaluationdaily') IS NOT NULL THEN
        EXECUTE 'ALTER TABLE public.analytics_portfoliovaluationdaily SET SCHEMA analytics';
    END IF;
    IF to_regclass('analytics.analytics_portfoliovaluationdaily') IS NOT NULL THEN
        EXECUTE 'ALTER TABLE analytics.analytics_portfoliovaluationdaily RENAME TO "portfoliovaluationdaily"';
    END IF;
    IF to_regclass('public.analytics_portfoliopositiondaily') IS NOT NULL THEN
        EXECUTE 'ALTER TABLE public.analytics_portfoliopositiondaily SET SCHEMA analytics';
    END IF;
    IF to_regclass('analytics.analytics_portfoliopositiondaily') IS NOT NULL THEN
        EXECUTE 'ALTER TABLE analytics.analytics_portfoliopositiondaily RENAME TO "portfoliopositiondaily"';
    END IF;
END $$;
""",
                    reverse_sql="""
DO $$
BEGIN
    IF to_regclass('analytics."portfoliodailysnapshot"') IS NOT NULL THEN
        EXECUTE 'ALTER TABLE analytics."portfoliodailysnapshot" RENAME TO analytics_portfoliodailysnapshot';
        EXECUTE 'ALTER TABLE analytics.analytics_portfoliodailysnapshot SET SCHEMA public';
    END IF;
    IF to_regclass('analytics."portfolioassetdailysnapshot"') IS NOT NULL THEN
        EXECUTE 'ALTER TABLE analytics."portfolioassetdailysnapshot" RENAME TO analytics_portfolioassetdailysnapshot';
        EXECUTE 'ALTER TABLE analytics.analytics_portfolioassetdailysnapshot SET SCHEMA public';
    END IF;
    IF to_regclass('analytics."portfoliovaluationdaily"') IS NOT NULL THEN
        EXECUTE 'ALTER TABLE analytics."portfoliovaluationdaily" RENAME TO analytics_portfoliovaluationdaily';
        EXECUTE 'ALTER TABLE analytics.analytics_portfoliovaluationdaily SET SCHEMA public';
    END IF;
    IF to_regclass('analytics."portfoliopositiondaily"') IS NOT NULL THEN
        EXECUTE 'ALTER TABLE analytics."portfoliopositiondaily" RENAME TO analytics_portfoliopositiondaily';
        EXECUTE 'ALTER TABLE analytics.analytics_portfoliopositiondaily SET SCHEMA public';
    END IF;
END $$;
""",
                )
            ],
            state_operations=[
                migrations.AlterModelTable(name="portfoliodailysnapshot", table='"analytics"."portfoliodailysnapshot"'),
                migrations.AlterModelTable(name="portfolioassetdailysnapshot", table='"analytics"."portfolioassetdailysnapshot"'),
                migrations.AlterModelTable(name="portfoliovaluationdaily", table='"analytics"."portfoliovaluationdaily"'),
                migrations.AlterModelTable(name="portfoliopositiondaily", table='"analytics"."portfoliopositiondaily"'),
            ],
        )
    ]
