import asyncio
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


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
        self.ib = None
        self.Stock = None
        self.last_error: str | None = None

    async def connect_async(self):
        loop = asyncio.get_running_loop()
        asyncio.set_event_loop(loop)
        if hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

        from ib_insync import IB, Stock

        if self.ib is None:
            self.ib = IB()
            self.Stock = Stock

        if self.ib.isConnected():
            self.last_error = None
            return True

        try:
            await self.ib.connectAsync(self.host, self.port, clientId=self.client_id)
            self.last_error = None
            return self.ib.isConnected()
        except Exception as exc:
            self.last_error = f"IB connection failed: {exc}"
            logger.warning(self.last_error)
            return False

    def is_connected(self):
        return self.ib is not None and self.ib.isConnected()

    def health(self) -> dict[str, Any]:
        return {
            "connected": self.is_connected(),
            "host": self.host,
            "port": self.port,
            "client_id": self.client_id,
            "warning": self.last_error,
        }

    def get_positions(self):
        if not self.is_connected():
            return []
        return self.ib.positions()

    def get_last_price(self, ticker: str) -> PriceResult:
        if not self.is_connected() or self.Stock is None:
            return PriceResult(price=None, currency=None, warning=self.last_error or "IB not connected")

        contract = self.Stock(ticker, "SMART", "USD")
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
