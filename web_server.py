import asyncio
import json
import math
import os
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse


HOST = "127.0.0.1"
PORT = 8080
BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"

IB_HOST = os.getenv("IB_HOST", "127.0.0.1")
IB_PORT = int(os.getenv("IB_PORT", "7496"))
IB_CLIENT_ID = int(os.getenv("IB_CLIENT_ID", "7"))


def ensure_event_loop():
    """Ensure a current event loop exists (needed by ib_insync on newer Python)."""
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())


def safe_number(value):
    if isinstance(value, (int, float)) and math.isfinite(value):
        return float(value)
    return None


class BakingMoneyHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(BASE_DIR), **kwargs)

    def _send_json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/api/positions":
            return self.handle_positions_api()

        if path == "/":
            self.path = "/static/index.html"
        elif path.startswith("/static/"):
            pass
        else:
            self.send_error(404, "Not Found")
            return

        return super().do_GET()

    def handle_positions_api(self):
        try:
            ensure_event_loop()
            from ib_insync import IB

            ib = IB()
            ib.connect(IB_HOST, IB_PORT, clientId=IB_CLIENT_ID, timeout=5)
            positions = ib.positions()
            contracts = [p.contract for p in positions]
            tickers_by_conid = {}

            if contracts:
                tickers = ib.reqTickers(*contracts)
                tickers_by_conid = {
                    t.contract.conId: t for t in tickers if getattr(t, "contract", None)
                }

            data = []
            for p in positions:
                contract = p.contract
                ticker = tickers_by_conid.get(contract.conId)

                qty = safe_number(p.position)
                avg_cost = safe_number(p.avgCost)
                price = safe_number(ticker.marketPrice()) if ticker else None
                close = safe_number(getattr(ticker, "close", None)) if ticker else None

                market_value = qty * price if qty is not None and price is not None else None
                unrealized_pnl = (
                    (price - avg_cost) * qty
                    if qty is not None and price is not None and avg_cost is not None
                    else None
                )
                daily_pnl = (
                    (price - close) * qty
                    if qty is not None and price is not None and close is not None
                    else None
                )
                change_percent = (
                    ((price - close) / close) * 100
                    if price is not None and close not in (None, 0)
                    else None
                )

                data.append(
                    {
                        "symbol": contract.symbol,
                        "position": qty,
                        "avgCost": avg_cost,
                        "price": price,
                        "changePercent": change_percent,
                        "marketValue": market_value,
                        "unrealizedPnL": unrealized_pnl,
                        "dailyPnL": daily_pnl,
                        "currency": getattr(contract, "currency", None),
                    }
                )

            self._send_json({"positions": data})
        except Exception as exc:
            self._send_json(
                {
                    "error": "Unable to fetch positions from IBKR. Check that TWS is running and API access is enabled.",
                    "details": str(exc),
                },
                status=500,
            )
        finally:
            if "ib" in locals() and ib.isConnected():
                ib.disconnect()


if __name__ == "__main__":
    if not STATIC_DIR.exists():
        raise FileNotFoundError("Missing static directory. Expected: ./static")

    server = HTTPServer((HOST, PORT), BakingMoneyHandler)
    print(f"Server running at http://{HOST}:{PORT}")
    server.serve_forever()
