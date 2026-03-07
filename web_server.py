import asyncio
import json
import logging
import math
import os
import sqlite3
from datetime import datetime, timezone
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlparse
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
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")
OPENAI_REASONING_EFFORT = os.getenv("OPENAI_REASONING_EFFORT", "medium").strip().lower() or "medium"
OPENAI_TEMPERATURE_RAW = os.getenv("OPENAI_TEMPERATURE", "0.1")
NO_PRICE_WARNING = "No live API market data (delayed/unavailable)"

_ib = None
logger = logging.getLogger(__name__)


def ensure_event_loop():
    """Ensure a current event loop exists for libraries that call get_event_loop()."""
    try:
        asyncio.get_running_loop()
        return
    except RuntimeError:
        pass

    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())


def get_ib_connection():
    global _ib
    ensure_event_loop()
    from ib_insync import IB

    if _ib and _ib.isConnected():
        return _ib

    _ib = IB()
    _ib.connect(IB_HOST, IB_PORT, clientId=IB_CLIENT_ID, timeout=5)
    _ib.reqMarketDataType(3)
    return _ib


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


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
    return first_valid_number(market_price, getattr(ticker, "last", None), getattr(ticker, "close", None))


def extract_close(ticker):
    if not ticker:
        return None
    return first_valid_number(getattr(ticker, "close", None), getattr(ticker, "prevClose", None))


def normalize_symbol(value):
    if not isinstance(value, str):
        return None
    symbol = value.strip().upper()
    return symbol if symbol else None


def parse_temperature(raw_value):
    try:
        value = float(raw_value)
    except (TypeError, ValueError):
        return 0.1
    if not math.isfinite(value):
        return 0.1
    return max(0.0, min(2.0, value))


def normalize_reasoning_effort(raw_value):
    allowed = {"low", "medium", "high"}
    return raw_value if raw_value in allowed else "medium"


def model_supports_temperature(model_name):
    if not isinstance(model_name, str):
        return True
    normalized = model_name.strip().lower()
    return not normalized.startswith("gpt-5")


def get_latest_price_for_symbol(symbol):
    prices, warnings = fetch_ib_prices([symbol])
    price = prices.get(symbol)
    warning = warnings.get(symbol)
    if price is None:
        logger.info("Price anchor unavailable for %s (%s)", symbol, warning or "unknown reason")
    return price


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

    ensure_event_loop()
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


def get_company_context(symbol):
    """Best-effort company metadata from IBKR contract details."""
    ensure_event_loop()
    from ib_insync import Stock

    context = {
        "long_name": None,
        "industry": None,
        "category": None,
        "subcategory": None,
    }

    try:
        ib = get_ib_connection()
        contract = Stock(symbol, "SMART", "USD")
        qualified = ib.qualifyContracts(contract)
        if not qualified:
            return context

        details = ib.reqContractDetails(qualified[0])
        if not details:
            return context

        detail = details[0]
        context["long_name"] = getattr(detail, "longName", None)
        context["industry"] = getattr(detail, "industry", None)
        context["category"] = getattr(detail, "category", None)
        context["subcategory"] = getattr(detail, "subcategory", None)
    except Exception as exc:
        logger.info("Company context unavailable for %s (%s)", symbol, exc)

    return context


def build_analysis_prompt(symbol, current_price=None, company_context=None):
    company_context = company_context or {}
    price_anchor = (
        f"Current price from TWS/IBKR: {current_price:.4f}."
        if current_price is not None
        else "Current price from TWS/IBKR is unavailable; proceed without a price anchor."
    )

    long_name = company_context.get("long_name") or "unknown"
    industry = company_context.get("industry") or "unknown"
    category = company_context.get("category") or "unknown"
    subcategory = company_context.get("subcategory") or "unknown"

    return f"""Goal: Analyze the company and stock price for symbol {symbol} over a 5-year horizon.

Context:
- Symbol: {symbol}
- Company name hint: {long_name}
- Industry hint: {industry}
- Category hint: {category}
- Subcategory hint: {subcategory}
- {price_anchor}

Method requirements:
1) First infer what this company likely does and its business model using the symbol + company metadata hints + market analysis and commentary.
2) Then build Bear/Base/Bull scenarios grounded in company-specific drivers of that business model.
3) Prioritize company-specific operating drivers (adoption, pricing power, unit economics, margins, utilization, contract pipeline, product mix, competition, moat/technology leadership, capex/capacity, execution risk, dilution/balance-sheet constraints).
4) Avoid generic macro/finance boilerplate (rates, GDP, regulation, valuation multiples, broad market mood) unless it is truly a top driver for this company; keep macro variables to at most 1-2 items.

Return ONLY valid JSON matching this contract:
{{
  "symbol": "{symbol}",
  "assumptions": "concise company-specific text",
  "scenarios": [
    {{"name": "Bear", "price_low": number, "price_high": number, "cagr_low": number, "cagr_high": number, "probability": number}},
    {{"name": "Base", "price_low": number, "price_high": number, "cagr_low": number, "cagr_high": number, "probability": number}},
    {{"name": "Bull", "price_low": number, "price_high": number, "cagr_low": number, "cagr_high": number, "probability": number}}
  ],
  "key_variables": [
    {{"variable": "text", "type": "Bullish|Bearish", "confidence": integer_0_to_10, "importance": integer_0_to_10}}
  ]
}}

Rules:
- Scenarios must be exactly 3 entries in this exact order: Bear, Base, Bull.
- Probabilities must sum to 100.
- key_variables must include 6 to 10 items and be mostly company-specific.
- type must be exactly Bullish or Bearish.
- confidence must be an integer from 0 to 10.
- importance must be an integer from 0 to 10.
- assumptions must be concise and company-specific.
- confidence = strength of current evidence that the variable is acting in that direction now.
- importance = how much the variable can influence stock price over 5 years.
- If current price is known: Bear range should generally be below current price, Base should be realistic vs current price, Bull should be above current price.
- Do not include markdown or commentary. JSON only."""


def request_ai_analysis(symbol, current_price=None):
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is required for analysis generation")

    effective_price = current_price
    if effective_price is None:
        effective_price = get_latest_price_for_symbol(symbol)

    temperature = parse_temperature(OPENAI_TEMPERATURE_RAW)
    reasoning_effort = normalize_reasoning_effort(OPENAI_REASONING_EFFORT)
    supports_temperature = model_supports_temperature(OPENAI_MODEL)

    logger.info(
        "Requesting analysis symbol=%s model=%s temp=%s reasoning=%s current_price=%s",
        symbol,
        OPENAI_MODEL,
        f"{temperature:.2f}" if supports_temperature else "omitted",
        reasoning_effort,
        f"{effective_price:.4f}" if isinstance(effective_price, (int, float)) else "None",
    )

    json_schema = {
        "name": "analysis_response",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "symbol": {"type": "string"},
                "assumptions": {"type": "string"},
                "scenarios": {
                    "type": "array",
                    "minItems": 3,
                    "maxItems": 3,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "name": {"type": "string", "enum": ["Bear", "Base", "Bull"]},
                            "price_low": {"type": "number"},
                            "price_high": {"type": "number"},
                            "cagr_low": {"type": "number"},
                            "cagr_high": {"type": "number"},
                            "probability": {"type": "number"},
                        },
                        "required": ["name", "price_low", "price_high", "cagr_low", "cagr_high", "probability"],
                    },
                },
                "key_variables": {
                    "type": "array",
                    "minItems": 6,
                    "maxItems": 10,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "variable": {"type": "string"},
                            "type": {"type": "string", "enum": ["Bullish", "Bearish"]},
                            "confidence": {"type": "integer", "minimum": 0, "maximum": 10},
                            "importance": {"type": "integer", "minimum": 0, "maximum": 10},
                        },
                        "required": ["variable", "type", "confidence", "importance"],
                    },
                },
            },
            "required": ["symbol", "assumptions", "scenarios", "key_variables"],
        },
    }

    company_context = get_company_context(symbol)
    logger.info(
        "Company context for %s: name=%s industry=%s category=%s subcategory=%s",
        symbol,
        company_context.get("long_name") or "unknown",
        company_context.get("industry") or "unknown",
        company_context.get("category") or "unknown",
        company_context.get("subcategory") or "unknown",
    )

    prompt_text = build_analysis_prompt(symbol, effective_price, company_context=company_context)
    logger.info("OpenAI analysis prompt for %s: %s", symbol, prompt_text)

    body = {
        "model": OPENAI_MODEL,
        "input": [
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": "You are a disciplined financial scenario analysis engine. Be consistent, conservative, and structured.",
                    }
                ],
            },
            {
                "role": "user",
                "content": [{"type": "input_text", "text": prompt_text}],
            },
        ],
        "reasoning": {"effort": reasoning_effort},
        "text": {"format": {"type": "json_schema", "name": json_schema["name"], "schema": json_schema["schema"], "strict": True}},
    }
    if supports_temperature:
        body["temperature"] = temperature

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

    return output_text, effective_price


def refresh_analysis_market_prices(conn):
    rows = conn.execute(
        """
        SELECT id, symbol, current_price, expected_price
        FROM analysis_symbols
        ORDER BY symbol ASC
        """
    ).fetchall()

    symbols = [row["symbol"] for row in rows]
    if not symbols:
        return

    prices, _warnings = fetch_ib_prices(symbols)
    now = utc_now_iso()

    for row in rows:
        symbol = row["symbol"]
        latest_price = prices.get(symbol)
        if latest_price is None:
            continue

        new_upside = calculate_upside(row["expected_price"], latest_price)
        conn.execute(
            """
            UPDATE analysis_symbols
            SET current_price = ?, upside = ?, updated_at = ?
            WHERE id = ?
            """,
            (latest_price, new_upside, now, row["id"]),
        )

    conn.commit()


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
    ai_raw_text, effective_current_price = request_ai_analysis(symbol, current_price=current_price)
    payload = extract_json_payload(ai_raw_text)
    parsed = parse_analysis_payload(payload)

    if parsed["symbol"] != symbol:
        parsed["symbol"] = symbol

    expected_price = calculate_expected_price(parsed["scenarios"])
    upside = calculate_upside(expected_price, effective_current_price)
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
                effective_current_price,
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
    ensure_event_loop()
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
        if path == "/api/analysis":
            return self.handle_analysis_get()
        if path.startswith("/api/analysis/"):
            symbol = normalize_symbol(path[len("/api/analysis/") :])
            if not symbol:
                return self._send_json({"error": "Invalid symbol"}, status=400)
            return self.handle_analysis_detail_get(symbol)

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
        if path == "/api/analysis":
            return self.handle_analysis_post()
        if path == "/api/analysis/import-from-positions":
            return self.handle_analysis_import_positions()

        self.send_error(404, "Not Found")

    def do_DELETE(self):
        path = urlparse(self.path).path
        analysis_prefix = "/api/analysis/"
        if path.startswith(analysis_prefix):
            symbol = normalize_symbol(path[len(analysis_prefix) :])
            if not symbol:
                return self._send_json({"error": "Invalid symbol"}, status=400)
            return self.handle_analysis_delete(symbol)

        self.send_error(404, "Not Found")

    def handle_positions_api(self):
        try:
            ensure_event_loop()
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

    def handle_analysis_get(self):
        conn = get_db_connection()
        try:
            refresh_analysis_market_prices(conn)
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
        current_price = explicit_current_price if explicit_current_price is not None else get_latest_price_for_symbol(symbol)

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
