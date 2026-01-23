from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("portfolio", "0003_add_portfolio_asset_price_fields"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    """
DO $$
BEGIN
    EXECUTE 'CREATE SCHEMA IF NOT EXISTS portfolio';
    IF to_regclass('public.portfolio_portfolio') IS NOT NULL THEN
        EXECUTE 'ALTER TABLE public.portfolio_portfolio SET SCHEMA portfolio';
    END IF;
    IF to_regclass('portfolio.portfolio_portfolio') IS NOT NULL THEN
        EXECUTE 'ALTER TABLE portfolio.portfolio_portfolio RENAME TO "portfolio"';
    END IF;
    IF to_regclass('public.portfolio_portfolioasset') IS NOT NULL THEN
        EXECUTE 'ALTER TABLE public.portfolio_portfolioasset SET SCHEMA portfolio';
    END IF;
    IF to_regclass('portfolio.portfolio_portfolioasset') IS NOT NULL THEN
        EXECUTE 'ALTER TABLE portfolio.portfolio_portfolioasset RENAME TO "portfolioasset"';
    END IF;
END $$;
""",
                    reverse_sql="""
DO $$
BEGIN
    IF to_regclass('portfolio."portfolio"') IS NOT NULL THEN
        EXECUTE 'ALTER TABLE portfolio."portfolio" RENAME TO portfolio_portfolio';
        EXECUTE 'ALTER TABLE portfolio.portfolio_portfolio SET SCHEMA public';
    END IF;
    IF to_regclass('portfolio."portfolioasset"') IS NOT NULL THEN
        EXECUTE 'ALTER TABLE portfolio."portfolioasset" RENAME TO portfolio_portfolioasset';
        EXECUTE 'ALTER TABLE portfolio.portfolio_portfolioasset SET SCHEMA public';
    END IF;
END $$;
""",
                )
            ],
            state_operations=[
                migrations.AlterModelTable(name="portfolio", table='"portfolio"."portfolio"'),
                migrations.AlterModelTable(name="portfolioasset", table='"portfolio"."portfolioasset"'),
            ],
        )
    ]
