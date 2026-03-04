import asyncio
import json
import math
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlencode, urlparse
from urllib.request import urlopen


HOST = "127.0.0.1"
PORT = 8080
BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
DB_PATH = BASE_DIR / "bakingmoney.db"

IB_HOST = os.getenv("IB_HOST", "127.0.0.1")
IB_PORT = int(os.getenv("IB_PORT", "7496"))
IB_CLIENT_ID = int(os.getenv("IB_CLIENT_ID", "7"))
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "").strip()
CACHE_TTL_HOURS = 24
NO_PRICE_WARNING = "No live API market data (delayed/unavailable)"

_ib = None


def ensure_event_loop():
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())


def get_ib_connection():
    """Create/reuse one IB connection; set delayed market data once per connection."""
    global _ib
    ensure_event_loop()
    from ib_insync import IB

    if _ib and _ib.isConnected():
        return _ib

    _ib = IB()
    _ib.connect(IB_HOST, IB_PORT, clientId=IB_CLIENT_ID, timeout=5)
    _ib.reqMarketDataType(3)  # delayed
    return _ib


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


def parse_iso(dt_str):
    try:
        return datetime.fromisoformat(dt_str)
    except Exception:
        return None


def safe_number(value):
    if isinstance(value, (int, float)) and math.isfinite(value):
        return float(value)
    return None


def first_valid_number(*values):
    for value in values:
        numeric = safe_number(value)
        if numeric is not None:
            return numeric
    return None


def extract_price(ticker):
    if not ticker:
        return None

    market_price = None
    if hasattr(ticker, "marketPrice"):
        market_price = safe_number(ticker.marketPrice())

    return first_valid_number(
        market_price,
        getattr(ticker, "last", None),
        getattr(ticker, "close", None),
    )


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS watchlist (
              symbol TEXT PRIMARY KEY,
              created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS fundamentals_cache (
              symbol TEXT PRIMARY KEY,
              pe REAL,
              forward_pe REAL,
              updated_at TEXT NOT NULL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def fetch_ib_prices(symbols):
    prices = {symbol: None for symbol in symbols}
    warnings = {symbol: None for symbol in symbols}
    if not symbols:
        return prices, warnings

    from ib_insync import Stock

    try:
        ib = get_ib_connection()
        contracts = [Stock(symbol, "SMART", "USD") for symbol in symbols]
        qualified = ib.qualifyContracts(*contracts) if contracts else []

        if qualified:
            tickers = ib.reqTickers(*qualified)
            ib.sleep(1.0)
            for ticker in tickers:
                contract = getattr(ticker, "contract", None)
                symbol = getattr(contract, "symbol", None)
                if not symbol:
                    continue

                symbol = symbol.upper()
                price = extract_price(ticker)
                prices[symbol] = price
                if price is None:
                    warnings[symbol] = NO_PRICE_WARNING
    except Exception:
        for symbol in symbols:
            warnings[symbol] = NO_PRICE_WARNING

    return prices, warnings


def get_fundamentals_for_symbol(conn, symbol):
    cache_row = conn.execute(
        "SELECT symbol, pe, forward_pe, updated_at FROM fundamentals_cache WHERE symbol = ?",
        (symbol,),
    ).fetchone()

    now = datetime.now(timezone.utc)
    if cache_row:
        updated_at = parse_iso(cache_row["updated_at"])
        if updated_at and now - updated_at <= timedelta(hours=CACHE_TTL_HOURS):
            return {"pe": cache_row["pe"], "forwardPe": cache_row["forward_pe"]}

    if not FINNHUB_API_KEY:
        return {
            "pe": cache_row["pe"] if cache_row else None,
            "forwardPe": cache_row["forward_pe"] if cache_row else None,
        }

    pe = None
    forward_pe = None
    try:
        query = urlencode(
            {
                "symbol": symbol,
                "metric": "all",
                "token": FINNHUB_API_KEY,
            }
        )
        url = f"https://finnhub.io/api/v1/stock/metric?{query}"
        with urlopen(url, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
            metrics = payload.get("metric", {})
            pe = safe_number(metrics.get("peBasicExclExtraTTM"))
            forward_pe = safe_number(metrics.get("peNormalizedAnnual"))
    except Exception:
        pe = None
        forward_pe = None

    conn.execute(
        """
        INSERT INTO fundamentals_cache (symbol, pe, forward_pe, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(symbol) DO UPDATE SET
          pe = excluded.pe,
          forward_pe = excluded.forward_pe,
          updated_at = excluded.updated_at
        """,
        (symbol, pe, forward_pe, utc_now_iso()),
    )
    conn.commit()

    return {"pe": pe, "forwardPe": forward_pe}


def normalize_symbol(value):
    if not isinstance(value, str):
        return None
    symbol = value.strip().upper()
    return symbol if symbol else None


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

    def _read_json_body(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return None

        if length <= 0:
            return None

        body = self.rfile.read(length)
        try:
            return json.loads(body.decode("utf-8"))
        except Exception:
            return None

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/api/positions":
            return self.handle_positions_api()
        if path == "/api/watchlist":
            return self.handle_watchlist_get()

        if path == "/":
            self.path = "/static/index.html"
        elif path.startswith("/static/"):
            pass
        else:
            self.send_error(404, "Not Found")
            return

        return super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/watchlist":
            return self.handle_watchlist_post()
        if path == "/api/watchlist/import-positions":
            return self.handle_watchlist_import_positions()

        self.send_error(404, "Not Found")

    def do_DELETE(self):
        path = urlparse(self.path).path
        prefix = "/api/watchlist/"
        if path.startswith(prefix):
            symbol = normalize_symbol(path[len(prefix) :])
            if not symbol:
                return self._send_json({"error": "Invalid symbol"}, status=400)
            return self.handle_watchlist_delete(symbol)

        self.send_error(404, "Not Found")

    def handle_positions_api(self):
        try:
            ib = get_ib_connection()
            positions = ib.positions()

            data = []
            for p in positions:
                contract = p.contract
                data.append(
                    {
                        "symbol": contract.symbol,
                        "position": safe_number(p.position),
                        "avgCost": safe_number(p.avgCost),
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

    def handle_watchlist_get(self):
        conn = get_db_connection()
        try:
            rows = conn.execute(
                "SELECT symbol FROM watchlist ORDER BY symbol ASC"
            ).fetchall()
            symbols = [row["symbol"] for row in rows]

            prices, quote_warnings = fetch_ib_prices(symbols)
            items = []
            for symbol in symbols:
                fundamentals = get_fundamentals_for_symbol(conn, symbol)
                items.append(
                    {
                        "symbol": symbol,
                        "price": prices.get(symbol),
                        "pe": fundamentals["pe"],
                        "forwardPe": fundamentals["forwardPe"],
                        "warning": quote_warnings.get(symbol),
                    }
                )

            self._send_json({"watchlist": items})
        except Exception as exc:
            self._send_json(
                {"error": "Unable to fetch watchlist.", "details": str(exc)},
                status=500,
            )
        finally:
            conn.close()

    def handle_watchlist_post(self):
        payload = self._read_json_body() or {}
        symbol = normalize_symbol(payload.get("symbol"))
        if not symbol:
            return self._send_json({"error": "Symbol is required."}, status=400)

        conn = get_db_connection()
        try:
            conn.execute(
                """
                INSERT INTO watchlist (symbol, created_at)
                VALUES (?, ?)
                ON CONFLICT(symbol) DO NOTHING
                """,
                (symbol, utc_now_iso()),
            )
            conn.commit()
            self._send_json({"ok": True, "symbol": symbol}, status=201)
        except Exception as exc:
            self._send_json(
                {"error": "Unable to add symbol.", "details": str(exc)},
                status=500,
            )
        finally:
            conn.close()

    def handle_watchlist_delete(self, symbol):
        conn = get_db_connection()
        try:
            conn.execute("DELETE FROM watchlist WHERE symbol = ?", (symbol,))
            conn.commit()
            self._send_json({"ok": True, "symbol": symbol})
        except Exception as exc:
            self._send_json(
                {"error": "Unable to remove symbol.", "details": str(exc)},
                status=500,
            )
        finally:
            conn.close()

    def handle_watchlist_import_positions(self):
        try:
            ib = get_ib_connection()
            positions = ib.positions()
            symbols = sorted(
                {normalize_symbol(p.contract.symbol) for p in positions if p.contract}
            )
            symbols = [s for s in symbols if s]

            conn = get_db_connection()
            try:
                for symbol in symbols:
                    conn.execute(
                        """
                        INSERT INTO watchlist (symbol, created_at)
                        VALUES (?, ?)
                        ON CONFLICT(symbol) DO NOTHING
                        """,
                        (symbol, utc_now_iso()),
                    )
                conn.commit()
            finally:
                conn.close()

            self._send_json({"ok": True, "addedSymbols": symbols})
        except Exception as exc:
            self._send_json(
                {
                    "error": "Unable to import symbols from positions.",
                    "details": str(exc),
                },
                status=500,
            )


if __name__ == "__main__":
    if not STATIC_DIR.exists():
        raise FileNotFoundError("Missing static directory. Expected: ./static")

    init_db()
    server = HTTPServer((HOST, PORT), BakingMoneyHandler)
    print(f"Server running at http://{HOST}:{PORT}")
    server.serve_forever()
