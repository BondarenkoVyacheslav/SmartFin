from datetime import datetime, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from app.analytics.services import build_portfolio_daily_snapshot
from app.portfolio.models import Portfolio


class Command(BaseCommand):
    help = "Build EOD daily snapshot for portfolios"

    def add_arguments(self, parser):
        parser.add_argument("--date", type=str, help="Snapshot date YYYY-MM-DD (defaults to yesterday)")
        parser.add_argument("--portfolio-id", type=int, help="Build snapshot for a single portfolio")

    def handle(self, *args, **options):
        date_str = options.get("date")
        if date_str:
            snapshot_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        else:
            snapshot_date = timezone.localdate() - timedelta(days=1)

        portfolio_id = options.get("portfolio_id")
        if portfolio_id:
            portfolio_ids = [portfolio_id]
        else:
            portfolio_ids = list(Portfolio.objects.values_list("id", flat=True))

        for pid in portfolio_ids:
            valuation = build_portfolio_daily_snapshot(pid, snapshot_date)
            self.stdout.write(
                f"portfolio={pid} date={snapshot_date} value={valuation.value_base} pnl={valuation.pnl_base}"
            )
