import asyncio
import json
import math
import os
import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlencode, urlparse
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from dotenv import load_dotenv

from analysis_service import (
    AnalysisValidationError,
    calculate_expected_price,
    calculate_overall_confidence,
    calculate_upside,
    extract_json_payload,
    parse_analysis_payload,
)

load_dotenv()


HOST = "127.0.0.1"
PORT = 8080
BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
DB_PATH = BASE_DIR / "bakingmoney.db"

IB_HOST = os.getenv("IB_HOST", "127.0.0.1")
IB_PORT = int(os.getenv("IB_PORT", "7496"))
IB_CLIENT_ID = int(os.getenv("IB_CLIENT_ID", "7"))
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5")
CACHE_TTL_HOURS = 24
NO_PRICE_WARNING = "No live API market data (delayed/unavailable)"

_ib = None

logger = logging.getLogger(__name__)


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




def extract_close(ticker):
    if not ticker:
        return None
    return first_valid_number(
        getattr(ticker, "close", None),
        getattr(ticker, "prevClose", None),
    )

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS analysis_symbols (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              symbol TEXT NOT NULL UNIQUE,
              current_price REAL,
              expected_price REAL NOT NULL,
              upside REAL,
              overall_confidence REAL,
              assumptions_text TEXT,
              raw_ai_response TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS analysis_scenarios (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              analysis_symbol_id INTEGER NOT NULL,
              scenario_name TEXT NOT NULL,
              price_low REAL NOT NULL,
              price_high REAL NOT NULL,
              cagr_low REAL NOT NULL,
              cagr_high REAL NOT NULL,
              probability REAL NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY (analysis_symbol_id) REFERENCES analysis_symbols(id) ON DELETE CASCADE,
              UNIQUE(analysis_symbol_id, scenario_name)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS analysis_key_variables (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              analysis_symbol_id INTEGER NOT NULL,
              variable_text TEXT NOT NULL,
              variable_type TEXT NOT NULL,
              confidence REAL NOT NULL,
              importance REAL NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY (analysis_symbol_id) REFERENCES analysis_symbols(id) ON DELETE CASCADE
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
        position_contracts_by_symbol = {}
        try:
            for position in ib.positions():
                contract = getattr(position, "contract", None)
                contract_symbol = normalize_symbol(getattr(contract, "symbol", None))
                if contract and contract_symbol and contract_symbol not in position_contracts_by_symbol:
                    position_contracts_by_symbol[contract_symbol] = contract
        except Exception:
            position_contracts_by_symbol = {}

        contracts = [
            position_contracts_by_symbol.get(symbol, Stock(symbol, "SMART", "USD"))
            for symbol in symbols
        ]
        qualified = ib.qualifyContracts(*contracts) if contracts else []
        symbol_by_conid = {
            getattr(contract, "conId", None): symbol
            for symbol, contract in zip(symbols, contracts)
            if getattr(contract, "conId", None)
        }

        if qualified:
            tickers = ib.reqTickers(*qualified)
            ib.sleep(1.0)
            for ticker in tickers:
                contract = getattr(ticker, "contract", None)
                conid = getattr(contract, "conId", None)
                symbol = symbol_by_conid.get(conid)
                if not symbol:
                    symbol = normalize_symbol(getattr(contract, "symbol", None))
                if not symbol:
                    continue

                price = extract_price(ticker)
                prices[symbol] = price
                if price is None:
                    warnings[symbol] = NO_PRICE_WARNING

        for symbol in symbols:
            if prices[symbol] is None and warnings[symbol] is None:
                warnings[symbol] = NO_PRICE_WARNING
    except Exception:
        for symbol in symbols:
            warnings[symbol] = NO_PRICE_WARNING

    return prices, warnings


def extract_finnhub_pe_values(data):
    metric = data.get("metric", {}) if isinstance(data, dict) else {}
    if not isinstance(metric, dict):
        metric = {}

    pe_candidate_keys = [
        key
        for key in metric.keys()
        if isinstance(key, str) and "pe" in key.lower()
    ][:50]

    pe = safe_number(metric.get("peBasicExclExtraTTM"))
    pe_key_used = "peBasicExclExtraTTM" if pe is not None else None

    if pe is None:
        for key in metric.keys():
            if not isinstance(key, str):
                continue
            key_lower = key.lower()
            if "pe" not in key_lower or "peg" in key_lower:
                continue
            value = safe_number(metric.get(key))
            if value is not None:
                pe = value
                pe_key_used = key
                break

    forward_pe = None
    forward_pe_key_used = None
    for key in metric.keys():
        if not isinstance(key, str):
            continue
        key_lower = key.lower()
        if "peg" in key_lower:
            continue
        has_pe = "pe" in key_lower
        forward_match = "forward" in key_lower and has_pe
        normalized_annual_match = has_pe and (
            "normalized" in key_lower or "annual" in key_lower
        )
        if not (forward_match or normalized_annual_match):
            continue

        value = safe_number(metric.get(key))
        if value is not None:
            forward_pe = value
            forward_pe_key_used = key
            break

    return {
        "hasMetric": bool(metric),
        "pe": pe,
        "forwardPe": forward_pe,
        "peKeyUsed": pe_key_used,
        "forwardPeKeyUsed": forward_pe_key_used,
        "peCandidateKeys": pe_candidate_keys,
    }


def fetch_finnhub_metric_snapshot(symbol):
    if not FINNHUB_API_KEY:
        return {
            "httpStatus": None,
            "hasMetric": False,
            "pe": None,
            "forwardPe": None,
            "peKeyUsed": None,
            "forwardPeKeyUsed": None,
            "peCandidateKeys": [],
            "apiKeyPresent": bool(FINNHUB_API_KEY),
            "apiKeyLast4": FINNHUB_API_KEY[-4:] if FINNHUB_API_KEY else None,
        }

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
        extracted = extract_finnhub_pe_values(payload)
        extracted["httpStatus"] = getattr(response, "status", None)
        return extracted


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

    try:
        snapshot = fetch_finnhub_metric_snapshot(symbol)
        pe = snapshot["pe"]
        forward_pe = snapshot["forwardPe"]
    except Exception:
        return {
            "pe": cache_row["pe"] if cache_row else None,
            "forwardPe": cache_row["forward_pe"] if cache_row else None,
        }

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


def build_analysis_prompt(symbol):
    return f"""You are analyzing a stock over a 5-year horizon.
Return ONLY valid JSON with this schema:
{{
  "symbol": "{symbol}",
  "assumptions": "short text",
  "scenarios": [
    {{
      "name": "Bear",
      "price_low": 40,
      "price_high": 80,
      "cagr_low": -15,
      "cagr_high": -2,
      "probability": 25
    }},
    {{
      "name": "Base",
      "price_low": 200,
      "price_high": 350,
      "cagr_low": 17,
      "cagr_high": 31,
      "probability": 50
    }},
    {{
      "name": "Bull",
      "price_low": 500,
      "price_high": 900,
      "cagr_low": 41,
      "cagr_high": 59,
      "probability": 25
    }}
  ],
  "key_variables": [
    {{
      "variable": "Growth of global demand for AI training and inference compute",
      "type": "Bullish",
      "confidence": 9,
      "importance": 10
    }}
  ]
}}

Rules for the model:
- Always include exactly 3 scenarios: Bear, Base, Bull
- Probabilities should total 100
- Confidence must be from 0 to 10
- Importance must be from 0 to 10
- Type must be either Bullish or Bearish
- Keep assumptions concise
- Return JSON only, no markdown, no commentary"""


def request_ai_analysis(symbol):
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is required for analysis generation")

    body = {
        "model": OPENAI_MODEL,
        "input": [
            {"role": "user", "content": [{"type": "input_text", "text": build_analysis_prompt(symbol)}]}
        ],
        "reasoning": {"effort": "high"},
        "text": {"format": {"type": "json_object"}},
    }
    request = Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=60) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        response_text = ""
        try:
            response_text = exc.read().decode("utf-8")
        except Exception:
            response_text = ""
        raise RuntimeError(
            f"OpenAI request failed with status {getattr(exc, 'code', 'unknown')}: {response_text[:400]}"
        ) from exc

    output_text = raw.get("output_text")
    if not output_text:
        for item in raw.get("output", []):
            for content in item.get("content", []):
                if content.get("type") in ("output_text", "text") and content.get("text"):
                    output_text = content["text"]
                    break
            if output_text:
                break

    if not output_text:
        raise RuntimeError("AI response did not contain output text")

    return output_text


def list_analysis_symbols(conn):
    rows = conn.execute(
        """
        SELECT symbol, current_price, expected_price, upside, overall_confidence, updated_at
        FROM analysis_symbols
        ORDER BY symbol ASC
        """
    ).fetchall()
    return [dict(row) for row in rows]


def get_analysis_detail(conn, symbol):
    row = conn.execute(
        """
        SELECT id, symbol, current_price, expected_price, upside, overall_confidence, assumptions_text,
               created_at, updated_at
        FROM analysis_symbols
        WHERE symbol = ?
        """,
        (symbol,),
    ).fetchone()
    if not row:
        return None

    scenarios = conn.execute(
        """
        SELECT scenario_name, price_low, price_high, cagr_low, cagr_high, probability
        FROM analysis_scenarios
        WHERE analysis_symbol_id = ?
        ORDER BY CASE scenario_name WHEN 'Bear' THEN 1 WHEN 'Base' THEN 2 WHEN 'Bull' THEN 3 ELSE 99 END
        """,
        (row["id"],),
    ).fetchall()

    key_variables = conn.execute(
        """
        SELECT variable_text, variable_type, confidence, importance
        FROM analysis_key_variables
        WHERE analysis_symbol_id = ?
        ORDER BY id ASC
        """,
        (row["id"],),
    ).fetchall()

    return {
        "symbol": row["symbol"],
        "current_price": row["current_price"],
        "expected_price": row["expected_price"],
        "upside": row["upside"],
        "overall_confidence": row["overall_confidence"],
        "assumptions": row["assumptions_text"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "scenarios": [dict(s) for s in scenarios],
        "key_variables": [dict(v) for v in key_variables],
    }


def upsert_analysis(conn, symbol, current_price=None):
    ai_raw_text = request_ai_analysis(symbol)
    payload = extract_json_payload(ai_raw_text)
    parsed = parse_analysis_payload(payload)

    if parsed["symbol"] != symbol:
        parsed["symbol"] = symbol

    expected_price = calculate_expected_price(parsed["scenarios"])
    upside = calculate_upside(expected_price, current_price)
    overall_confidence = calculate_overall_confidence(parsed["key_variables"])
    now = utc_now_iso()

    conn.execute("BEGIN")
    try:
        conn.execute(
            """
            INSERT INTO analysis_symbols (
                symbol, current_price, expected_price, upside, overall_confidence,
                assumptions_text, raw_ai_response, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol) DO UPDATE SET
                current_price = excluded.current_price,
                expected_price = excluded.expected_price,
                upside = excluded.upside,
                overall_confidence = excluded.overall_confidence,
                assumptions_text = excluded.assumptions_text,
                raw_ai_response = excluded.raw_ai_response,
                updated_at = excluded.updated_at
            """,
            (
                symbol,
                current_price,
                expected_price,
                upside,
                overall_confidence,
                parsed["assumptions"],
                json.dumps(payload),
                now,
                now,
            ),
        )

        analysis_row = conn.execute(
            "SELECT id FROM analysis_symbols WHERE symbol = ?",
            (symbol,),
        ).fetchone()
        analysis_symbol_id = analysis_row["id"]

        conn.execute("DELETE FROM analysis_scenarios WHERE analysis_symbol_id = ?", (analysis_symbol_id,))
        conn.execute("DELETE FROM analysis_key_variables WHERE analysis_symbol_id = ?", (analysis_symbol_id,))

        for scenario in parsed["scenarios"]:
            conn.execute(
                """
                INSERT INTO analysis_scenarios (
                    analysis_symbol_id, scenario_name, price_low, price_high,
                    cagr_low, cagr_high, probability, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    analysis_symbol_id,
                    scenario["scenario_name"],
                    scenario["price_low"],
                    scenario["price_high"],
                    scenario["cagr_low"],
                    scenario["cagr_high"],
                    scenario["probability"],
                    now,
                    now,
                ),
            )

        for variable in parsed["key_variables"]:
            conn.execute(
                """
                INSERT INTO analysis_key_variables (
                    analysis_symbol_id, variable_text, variable_type,
                    confidence, importance, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    analysis_symbol_id,
                    variable["variable_text"],
                    variable["variable_type"],
                    variable["confidence"],
                    variable["importance"],
                    now,
                    now,
                ),
            )

        conn.commit()
    except Exception:
        conn.rollback()
        raise

    return get_analysis_detail(conn, symbol)


def get_positions_with_prices():
    ib = get_ib_connection()
    positions = ib.positions()
    symbols = sorted({normalize_symbol(p.contract.symbol) for p in positions if p.contract})
    symbols = [s for s in symbols if s]
    prices, _warnings = fetch_ib_prices(symbols)
    return symbols, prices


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
        parsed_url = urlparse(self.path)
        path = parsed_url.path

        if path == "/api/positions":
            return self.handle_positions_api()
        if path == "/api/watchlist":
            return self.handle_watchlist_get()
        if path == "/api/analysis":
            return self.handle_analysis_get()
        if path.startswith("/api/analysis/"):
            symbol = normalize_symbol(path[len("/api/analysis/") :])
            if not symbol:
                return self._send_json({"error": "Invalid symbol"}, status=400)
            return self.handle_analysis_detail_get(symbol)
        if path == "/api/debug/finnhub":
            return self.handle_debug_finnhub(parsed_url.query)

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
        if path == "/api/analysis":
            return self.handle_analysis_post()
        if path == "/api/analysis/import-from-positions":
            return self.handle_analysis_import_positions()

        self.send_error(404, "Not Found")

    def handle_debug_finnhub(self, query_string):
        from urllib.parse import parse_qs

        params = parse_qs(query_string or "")
        symbol = normalize_symbol((params.get("symbol") or [""])[0])
        if not symbol:
            return self._send_json({"error": "symbol query parameter is required"}, status=400)

        try:
            snapshot = fetch_finnhub_metric_snapshot(symbol)
            snapshot["apiKeyPresent"] = bool(FINNHUB_API_KEY)
            snapshot["apiKeyLast4"] = FINNHUB_API_KEY[-4:] if FINNHUB_API_KEY else None
            self._send_json(snapshot)
        except Exception as exc:
            self._send_json(
                {
                    "httpStatus": None,
                    "hasMetric": False,
                    "pe": None,
                    "forwardPe": None,
                    "peKeyUsed": None,
                    "forwardPeKeyUsed": None,
                    "peCandidateKeys": [],
                    "apiKeyPresent": bool(FINNHUB_API_KEY),
                    "apiKeyLast4": FINNHUB_API_KEY[-4:] if FINNHUB_API_KEY else None,
                    "error": str(exc),
                },
                status=500,
            )

    def do_DELETE(self):
        path = urlparse(self.path).path
        prefix = "/api/watchlist/"
        analysis_prefix = "/api/analysis/"
        if path.startswith(prefix):
            symbol = normalize_symbol(path[len(prefix) :])
            if not symbol:
                return self._send_json({"error": "Invalid symbol"}, status=400)
            return self.handle_watchlist_delete(symbol)
        if path.startswith(analysis_prefix):
            symbol = normalize_symbol(path[len(analysis_prefix) :])
            if not symbol:
                return self._send_json({"error": "Invalid symbol"}, status=400)
            return self.handle_analysis_delete(symbol)

        self.send_error(404, "Not Found")

    def handle_positions_api(self):
        try:
            ib = get_ib_connection()
            positions = ib.positions()
            contracts = [p.contract for p in positions if p.contract]
            tickers_by_conid = {}

            if contracts:
                qualified = ib.qualifyContracts(*contracts)
                if qualified:
                    tickers = ib.reqTickers(*qualified)
                    ib.sleep(1.0)
                    tickers_by_conid = {
                        t.contract.conId: t for t in tickers if getattr(t, "contract", None)
                    }

            data = []
            for p in positions:
                contract = p.contract
                ticker = tickers_by_conid.get(getattr(contract, "conId", None))

                qty = safe_number(p.position)
                avg_cost = safe_number(p.avgCost)
                price = extract_price(ticker)
                close = extract_close(ticker)

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
                        "price": price,
                        "avgCost": avg_cost,
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

    def handle_analysis_get(self):
        conn = get_db_connection()
        try:
            self._send_json({"analysis": list_analysis_symbols(conn)})
        except Exception as exc:
            self._send_json(
                {"error": "Unable to fetch analysis list.", "details": str(exc)},
                status=500,
            )
        finally:
            conn.close()

    def handle_analysis_detail_get(self, symbol):
        conn = get_db_connection()
        try:
            detail = get_analysis_detail(conn, symbol)
            if not detail:
                return self._send_json({"error": "Analysis symbol not found"}, status=404)
            self._send_json({"analysis": detail})
        except Exception as exc:
            self._send_json(
                {"error": "Unable to fetch analysis details.", "details": str(exc)},
                status=500,
            )
        finally:
            conn.close()

    def handle_analysis_post(self):
        payload = self._read_json_body() or {}
        symbol = normalize_symbol(payload.get("symbol"))
        if not symbol:
            return self._send_json({"error": "Symbol is required."}, status=400)

        explicit_current_price = safe_number(payload.get("currentPrice"))
        current_price = explicit_current_price
        if current_price is None:
            prices, _warnings = fetch_ib_prices([symbol])
            current_price = prices.get(symbol)

        conn = get_db_connection()
        try:
            detail = upsert_analysis(conn, symbol, current_price=current_price)
            self._send_json({"ok": True, "analysis": detail}, status=201)
        except AnalysisValidationError as exc:
            logger.warning("Analysis validation failed for symbol %s: %s", symbol, exc)
            self._send_json(
                {"error": "AI response validation failed.", "details": str(exc)},
                status=422,
            )
        except Exception as exc:
            logger.exception("Unable to create analysis for symbol %s", symbol)
            self._send_json(
                {
                    "error": "Unable to create analysis.",
                    "details": str(exc),
                    "debugHint": "Check server logs for traceback details.",
                },
                status=500,
            )
        finally:
            conn.close()

    def handle_analysis_import_positions(self):
        conn = get_db_connection()
        try:
            symbols, prices = get_positions_with_prices()
            imported = []
            failures = []

            for symbol in symbols:
                try:
                    upsert_analysis(conn, symbol, current_price=prices.get(symbol))
                    imported.append(symbol)
                except Exception as exc:
                    logger.exception("Failed analysis import for symbol %s", symbol)
                    failures.append({"symbol": symbol, "error": str(exc)})

            self._send_json(
                {
                    "ok": len(failures) == 0,
                    "importedSymbols": imported,
                    "failures": failures,
                },
                status=207 if failures else 200,
            )
        except Exception as exc:
            logger.exception("Unable to import analysis from positions")
            self._send_json(
                {"error": "Unable to import analysis from positions.", "details": str(exc)},
                status=500,
            )
        finally:
            conn.close()

    def handle_analysis_delete(self, symbol):
        conn = get_db_connection()
        try:
            conn.execute("DELETE FROM analysis_symbols WHERE symbol = ?", (symbol,))
            conn.commit()
            self._send_json({"ok": True, "symbol": symbol})
        except Exception as exc:
            self._send_json(
                {"error": "Unable to remove analysis symbol.", "details": str(exc)},
                status=500,
            )
        finally:
            conn.close()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )

    if not STATIC_DIR.exists():
        raise FileNotFoundError("Missing static directory. Expected: ./static")

    init_db()
    server = HTTPServer((HOST, PORT), BakingMoneyHandler)
    print(f"Server running at http://{HOST}:{PORT}")
    server.serve_forever()
