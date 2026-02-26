import asyncio
from dataclasses import dataclass
from typing import Any


if hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

try:
    asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

from ib_insync import IB, Stock


@dataclass
class PriceResult:
    price: float | None
    currency: str | None
    warning: str | None = None


class IBService:
    def __init__(self, host: str, port: int, client_id: int):
        self.host = host
        self.port = port
        self.client_id = client_id
        self.ib = IB()

    def connect(self):
        if not self.ib.isConnected():
            self.ib.connect(self.host, self.port, clientId=self.client_id)

    def safe_connect(self):
        try:
            self.connect()
        except Exception:
            return False
        return self.ib.isConnected()

    def health(self) -> dict[str, Any]:
        connected = self.safe_connect()
        return {
            "connected": connected,
            "host": self.host,
            "port": self.port,
            "client_id": self.client_id,
        }

    def get_positions(self):
        if not self.safe_connect():
            return []
        return self.ib.positions()

    def get_last_price(self, ticker: str) -> PriceResult:
        if not self.safe_connect():
            return PriceResult(price=None, currency=None, warning="IB not connected")

        contract = Stock(ticker, "SMART", "USD")
        try:
            self.ib.qualifyContracts(contract)
            tick = self.ib.reqMktData(contract, "", False, False)
            self.ib.sleep(1.0)
            price = tick.marketPrice() or tick.last or tick.close
            currency = getattr(contract, "currency", "USD")
            if price is None or price != price:
                return PriceResult(price=None, currency=currency, warning="Market data unavailable")
            return PriceResult(price=float(price), currency=currency, warning=None)
        except Exception:
            return PriceResult(price=None, currency="USD", warning="Market data unavailable")
