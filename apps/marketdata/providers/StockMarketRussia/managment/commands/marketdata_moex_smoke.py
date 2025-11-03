from datetime import date
from django.core.management.base import BaseCommand
from apps.marketdata.providers.StockMarketRussia.moex import MoexISSProvider

class Command(BaseCommand):
    help = "Быстрый smoke-тест MOEX ISS провайдера (без записи в БД)."

    def add_arguments(self, parser):
        parser.add_argument("--symbols", nargs="+", default=["SBER", "GAZP"])
        parser.add_argument("--interval", type=str, default="1d")
        parser.add_argument("--from", dest="since", type=str, default=None)
        parser.add_argument("--till", dest="till", type=str, default=None)
        parser.add_argument("--board", type=str, default="TQBR")

    def handle(self, *args, **opts):
        provider = MoexISSProvider(board=opts["board"])

        # Quotes
        quotes = provider.get_quotes(opts["symbols"])
        self.stdout.write(self.style.SUCCESS(f"Quotes [{opts['board']}]: {len(quotes)}"))
        for q in quotes[:5]:
            self.stdout.write(f"  {q.symbol}: last={q.last} bid={q.bid} ask={q.ask} ts={q.ts}")

        # Candles (по первому символу)
        since = date.fromisoformat(opts["since"]) if opts["since"] else date.today()
        till  = date.fromisoformat(opts["till"])  if opts["till"]  else since
        candles = provider.get_candles(opts["symbols"][0], opts["interval"], since, till)
        self.stdout.write(self.style.SUCCESS(
            f"Candles {opts['symbols'][0]} {opts['interval']} {since}..{till}: {len(candles)}"
        ))
        for c in candles[:3]:
            self.stdout.write(f"  {c.ts} O:{c.open} H:{c.high} L:{c.low} C:{c.close} V:{c.volume}")
