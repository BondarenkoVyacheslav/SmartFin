import asyncio
from app.integrations.services.exchange_portfolio import (
    CcxtAdapter,
    ExchangePortfolioCollector,
    ExchangeCredentials,
)


async def main():
    adapter = CcxtAdapter()  # Можно подставить свой ExchangeAdapter
    collector = ExchangePortfolioCollector(adapter=adapter)

    creds_bybit = ExchangeCredentials(
        exchange="bybit",
        api_key="EWQCsR51W4qu45raOh",
        api_secret="cwt9gMEsAUWJVZUKXGJD7LkTYtrfEbZRitA7",
    )

    creds_list = [creds_bybit]
    result = await collector.fetch_all(creds_list)

    print("states:", result.states)
    print("errors:", result.errors)


if __name__ == "__main__":
    asyncio.run(main())
