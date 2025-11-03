from django.core.management.base import BaseCommand
from apps.marketdata.providers.StockMarketRussia.tinkoff.provider import TinkoffProvider
from apps.marketdata.providers.transports import TinkoffCreds, TransportPrefs, Transport

class Command(BaseCommand):
    help = "Smoke-тест TinkoffProvider (без реальной сети, проверка конфигурации и импортов)."

    def add_arguments(self, parser):
        parser.add_argument("--token", type=str, required=False)
        parser.add_argument("--symbols", nargs="+", default=["SBER","GAZP"])

    def handle(self, *args, **opts):
        token = opts.get("token")
        provider = TinkoffProvider(
            creds=TinkoffCreds(token=token or "DUMMY"),
            prefs=TransportPrefs(
                quotes_order=(Transport.WS, Transport.GRPC, Transport.REST),
                candles_order=(Transport.GRPC, Transport.REST),
            ),
        )
        self.stdout.write(self.style.SUCCESS(
            f"TinkoffProvider initialized. code={provider.code}, name={provider.name}"
        ))
        try:
            provider.get_quotes(opts["symbols"])
        except NotImplementedError:
            self.stdout.write("NotImplementedError: transports are skeletons — ок для первого шага.")
