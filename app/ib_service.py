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
        if hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

        loop = asyncio.get_running_loop()
        asyncio.set_event_loop(loop)

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

    @staticmethod
    def _extract_price(tick) -> float | None:
        for value in (tick.marketPrice(), tick.last, tick.close, tick.midpoint(), tick.bid, tick.ask):
            if value is not None and value == value and value > 0:
                return float(value)
        return None

    def get_last_price(self, ticker: str) -> PriceResult:
        if not self.is_connected() or self.Stock is None:
            return PriceResult(price=None, currency=None, warning=self.last_error or "IB not connected")

        contract = self.Stock(ticker, "SMART", "USD")
        try:
            self.ib.qualifyContracts(contract)
            currency = getattr(contract, "currency", "USD")

            # Try live market data first.
            self.ib.reqMarketDataType(1)
            live_tick = self.ib.reqTickers(contract)[0]
            live_price = self._extract_price(live_tick)
            if live_price is not None:
                return PriceResult(price=live_price, currency=currency, warning=None)

            # Fallback to delayed market data where live subscriptions are unavailable.
            self.ib.reqMarketDataType(3)
            delayed_tick = self.ib.reqTickers(contract)[0]
            delayed_price = self._extract_price(delayed_tick)
            if delayed_price is not None:
                return PriceResult(price=delayed_price, currency=currency, warning="Using delayed market data")

            return PriceResult(price=None, currency=currency, warning="Market data unavailable (no live/delayed entitlement)")
        except Exception as exc:
            logger.warning("Price fetch failed for %s: %s", ticker, exc)
            return PriceResult(price=None, currency="USD", warning="Market data unavailable")
