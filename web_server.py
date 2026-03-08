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
ANALYSIS_PROMPT_SETTING_KEY_BUSINESS_MODEL = "analysis_prompt_business_model"
ANALYSIS_PROMPT_SETTING_KEY_KEY_VARIABLES = "analysis_prompt_key_variables"
ANALYSIS_PROMPT_SETTING_KEY_SCENARIOS = "analysis_prompt_scenarios"

DEFAULT_PROMPT_BUSINESS_MODEL = """You are an equity analyst.

Based on the company context below, identify what the company most likely does, how it makes money, and what economic engine drives its revenue and margins over a 5-year horizon.

Company context:
- Symbol: $Symbol
- Current price: $Price USD

Return ONLY valid JSON in this exact structure:
{
  "symbol": "$Symbol",
  "business_model": "concise description of what the company does, how it makes money, and the core economic engine",
  "business_summary": "short summary of the main revenue drivers, cost drivers, and major risks"
}

Rules:
- Be specific and practical.
- Focus on the business model, not stock valuation commentary.
- business_model should be concise but concrete.
- business_summary should be short and useful for later analysis.
- JSON only.
- No markdown.
- No commentary outside JSON."""

DEFAULT_PROMPT_KEY_VARIABLES = """You are an equity analyst.

Using the business model below, identify the few most important company-specific variables that could materially push the stock price up or down over the next 5 years.

Company context:
- Symbol: $Symbol
- Current price: $Price USD
- Business model: $BusinessModel

Definitions:
- A key variable is one of the most important company-specific factors that could materially move the stock price over 5 years.
- Confidence means how strong the current evidence is that this variable is acting in that direction now.
- Importance means how much this variable could influence the stock price over the 5-year horizon.

Guidance:
- Prefer company-specific drivers such as demand growth, product adoption, pricing power, margins, utilization, capacity expansion, customer concentration, contract pipeline, technology leadership, competitive position, execution risk, capital intensity, or dilution risk when relevant.
- Avoid generic macro variables such as GDP growth, interest rates, regulation, legal risk, or valuation multiples unless they are truly dominant drivers for this specific company.
- Focus on the few variables that matter most.

Return ONLY valid JSON in this exact structure:
{
  "symbol": "$Symbol",
  "key_variables": [
    {
      "variable": "text",
      "type": "Bullish",
      "confidence": 0,
      "importance": 0
    }
  ]
}

Rules:
- Return 6 to 8 key variables.
- Most variables should be company-specific business drivers.
- type must be exactly Bullish or Bearish.
- confidence must be an integer from 0 to 10.
- importance must be an integer from 0 to 10.
- JSON only.
- No markdown.
- No commentary outside JSON."""

DEFAULT_PROMPT_SCENARIOS = """You are an equity analyst building a 5-year stock scenario analysis.

Company context:
- Symbol: $Symbol
- Current price: $Price USD
- Business model: $BusinessModel
- Key variables: $KeyVariables

Task:
Build Bear, Base, and Bull stock price scenarios over a 5-year horizon using the business model and key variables above.

Definitions:
- Bear = pessimistic but plausible outcome
- Base = most likely central outcome
- Bull = optimistic but plausible outcome

Return ONLY valid JSON in this exact structure:
{
  "symbol": "$Symbol",
  "assumptions": "short explanation of the thesis behind the scenarios",
  "scenarios": [
    {"name": "Bear", "price_low": 0, "price_high": 0, "cagr_low": 0, "cagr_high": 0, "probability": 0},
    {"name": "Base", "price_low": 0, "price_high": 0, "cagr_low": 0, "cagr_high": 0, "probability": 0},
    {"name": "Bull", "price_low": 0, "price_high": 0, "cagr_low": 0, "cagr_high": 0, "probability": 0}
  ]
}

Rules:
- Exactly 3 scenarios in this order: Bear, Base, Bull.
- Probabilities must sum to 100.
- Use realistic price ranges and CAGR ranges.
- If current price is known, use it as an anchor, but do not force the Base case too close to the current price if the business profile justifies otherwise.
- assumptions should be concise and reflect the business model and key variables.
- JSON only.
- No markdown.
- No commentary outside JSON."""

PROMPT_TEMPLATE_CONFIG = {
    ANALYSIS_PROMPT_SETTING_KEY_BUSINESS_MODEL: {
        "default": DEFAULT_PROMPT_BUSINESS_MODEL,
        "required_vars": ["$Symbol", "$Price"],
    },
    ANALYSIS_PROMPT_SETTING_KEY_KEY_VARIABLES: {
        "default": DEFAULT_PROMPT_KEY_VARIABLES,
        "required_vars": ["$Symbol", "$Price", "$BusinessModel"],
    },
    ANALYSIS_PROMPT_SETTING_KEY_SCENARIOS: {
        "default": DEFAULT_PROMPT_SCENARIOS,
        "required_vars": ["$Symbol", "$Price", "$BusinessModel", "$KeyVariables"],
    },
}


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


def get_default_prompt_template(key):
    if key not in PROMPT_TEMPLATE_CONFIG:
        raise ValueError(f"Unknown prompt template key: {key}")
    return PROMPT_TEMPLATE_CONFIG[key]["default"]


def validate_prompt_template(key, template):
    if key not in PROMPT_TEMPLATE_CONFIG:
        raise ValueError(f"Unknown prompt template key: {key}")
    if not isinstance(template, str) or not template.strip():
        raise ValueError("Prompt template cannot be empty")

    required_vars = PROMPT_TEMPLATE_CONFIG[key]["required_vars"]
    missing = [var for var in required_vars if var not in template]
    if missing:
        raise ValueError(f"Prompt template is missing required variable(s): {', '.join(missing)}")


def get_prompt_template(conn, key):
    row = conn.execute(
        "SELECT value FROM app_settings WHERE key = ?",
        (key,),
    ).fetchone()

    if row and row["value"]:
        logger.info("Using custom prompt template key=%s", key)
        return row["value"], "custom"

    logger.info("Using default prompt template key=%s", key)
    return get_default_prompt_template(key), "default"


def get_all_prompt_templates(conn):
    templates = {}
    sources = {}
    for key in PROMPT_TEMPLATE_CONFIG.keys():
        template, source = get_prompt_template(conn, key)
        templates[key] = template
        sources[key] = source
    return templates, sources


def save_prompt_template(conn, key, template):
    validate_prompt_template(key, template)
    conn.execute(
        """
        INSERT INTO app_settings (key, value, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
          value = excluded.value,
          updated_at = excluded.updated_at
        """,
        (key, template, utc_now_iso()),
    )
    conn.commit()


def reset_prompt_template(conn, key):
    if key not in PROMPT_TEMPLATE_CONFIG:
        raise ValueError(f"Unknown prompt template key: {key}")
    conn.execute("DELETE FROM app_settings WHERE key = ?", (key,))
    conn.commit()


def render_prompt_template(template, context):
    rendered = template
    for placeholder, value in context.items():
        rendered = rendered.replace(placeholder, value)

    logger.info(
        "Rendered prompt for symbol=%s with price=%s",
        context.get("$Symbol", "unknown"),
        context.get("$Price", "unknown"),
    )
    logger.debug("Rendered prompt body: %s", rendered)
    return rendered


def format_key_variables_for_prompt(key_variables):
    return json.dumps(key_variables, separators=(",", ":"), ensure_ascii=False)


def build_prompt_context(symbol, price=None, business_model="", key_variables=None):
    symbol_value = symbol or "unknown"
    price_value = f"{price:.2f}" if isinstance(price, (int, float)) and math.isfinite(price) else "unknown"
    business_value = business_model or ""
    key_vars_value = format_key_variables_for_prompt(key_variables or [])
    return {
        "$Symbol": symbol_value,
        "$Price": price_value,
        "$BusinessModel": business_value,
        "$KeyVariables": key_vars_value,
    }


def ensure_column_exists(conn, table_name, column_name, column_definition):
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    existing = {row["name"] for row in rows}
    if column_name in existing:
        return
    conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}")


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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS app_settings (
              key TEXT PRIMARY KEY,
              value TEXT NOT NULL,
              updated_at TEXT NOT NULL
            )
            """
        )
        ensure_column_exists(conn, "analysis_symbols", "business_model_text", "TEXT")
        ensure_column_exists(conn, "analysis_symbols", "business_summary_text", "TEXT")
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


def build_analysis_prompt(symbol, current_price=None, template=None, business_model="", key_variables=None):
    base_template = template if template is not None else DEFAULT_PROMPT_SCENARIOS
    context = build_prompt_context(
        symbol=symbol,
        price=current_price,
        business_model=business_model,
        key_variables=key_variables,
    )
    return render_prompt_template(base_template, context)


def _extract_output_text(raw):
    output_text = raw.get("output_text")
    if output_text:
        return output_text

    for item in raw.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in ("output_text", "text") and content.get("text"):
                return content["text"]
    return None


def request_ai_step(step_name, prompt_text, json_schema):
    temperature = parse_temperature(OPENAI_TEMPERATURE_RAW)
    reasoning_effort = normalize_reasoning_effort(OPENAI_REASONING_EFFORT)
    supports_temperature = model_supports_temperature(OPENAI_MODEL)

    logger.info(
        "Starting AI step=%s model=%s temp=%s reasoning=%s",
        step_name,
        OPENAI_MODEL,
        f"{temperature:.2f}" if supports_temperature else "omitted",
        reasoning_effort,
    )

    body = {
        "model": OPENAI_MODEL,
        "input": [
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": "You are a disciplined equity analyst. Produce company-specific, realistic, and concise analysis. Avoid generic filler and focus on the few business drivers that matter most.",
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
            f"OpenAI request failed on step {step_name} with status {getattr(exc, 'code', 'unknown')}: {response_text[:400]}"
        ) from exc

    output_text = _extract_output_text(raw)
    if not output_text:
        raise RuntimeError(f"AI step {step_name} response did not contain output text")

    payload = extract_json_payload(output_text)
    logger.info("AI step=%s completed", step_name)
    return payload


def validate_step1_business_model(payload):
    symbol = payload.get("symbol")
    business_model = payload.get("business_model")
    business_summary = payload.get("business_summary")

    if not isinstance(symbol, str) or not symbol.strip():
        raise AnalysisValidationError("step1.symbol is required")
    if not isinstance(business_model, str) or not business_model.strip():
        raise AnalysisValidationError("step1.business_model is required")
    if not isinstance(business_summary, str) or not business_summary.strip():
        raise AnalysisValidationError("step1.business_summary is required")

    return {
        "symbol": symbol.strip().upper(),
        "business_model": business_model.strip(),
        "business_summary": business_summary.strip(),
    }


def validate_step2_key_variables(payload):
    symbol = payload.get("symbol")
    key_variables = payload.get("key_variables")

    combined = {
        "symbol": symbol,
        "assumptions": "temp",
        "scenarios": [
            {"name": "Bear", "price_low": 1, "price_high": 2, "cagr_low": -1, "cagr_high": 0, "probability": 34},
            {"name": "Base", "price_low": 2, "price_high": 3, "cagr_low": 0, "cagr_high": 1, "probability": 33},
            {"name": "Bull", "price_low": 3, "price_high": 4, "cagr_low": 1, "cagr_high": 2, "probability": 33},
        ],
        "key_variables": key_variables,
    }

    parsed = parse_analysis_payload(combined)
    return {
        "symbol": parsed["symbol"],
        "key_variables": parsed["key_variables"],
    }


def validate_step3_scenarios(payload, symbol, key_variables):
    combined = {
        "symbol": payload.get("symbol", symbol),
        "assumptions": payload.get("assumptions"),
        "scenarios": payload.get("scenarios"),
        "key_variables": [
            {
                "variable": item["variable_text"],
                "type": item["variable_type"],
                "confidence": item["confidence"],
                "importance": item["importance"],
            }
            for item in key_variables
        ],
    }
    return parse_analysis_payload(combined)


def request_ai_analysis(symbol, current_price=None):
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is required for analysis generation")

    effective_price = current_price if current_price is not None else get_latest_price_for_symbol(symbol)

    conn = get_db_connection()
    try:
        templates, sources = get_all_prompt_templates(conn)
    finally:
        conn.close()

    logger.info(
        "Prompt sources business_model=%s key_variables=%s scenarios=%s",
        sources[ANALYSIS_PROMPT_SETTING_KEY_BUSINESS_MODEL],
        sources[ANALYSIS_PROMPT_SETTING_KEY_KEY_VARIABLES],
        sources[ANALYSIS_PROMPT_SETTING_KEY_SCENARIOS],
    )

    schema_step1 = {
        "name": "analysis_business_model",
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "symbol": {"type": "string"},
                "business_model": {"type": "string"},
                "business_summary": {"type": "string"},
            },
            "required": ["symbol", "business_model", "business_summary"],
        },
    }
    schema_step2 = {
        "name": "analysis_key_variables",
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "symbol": {"type": "string"},
                "key_variables": {
                    "type": "array",
                    "minItems": 6,
                    "maxItems": 8,
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
            "required": ["symbol", "key_variables"],
        },
    }
    schema_step3 = {
        "name": "analysis_scenarios",
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
            },
            "required": ["symbol", "assumptions", "scenarios"],
        },
    }

    prompt1 = build_analysis_prompt(symbol, effective_price, template=templates[ANALYSIS_PROMPT_SETTING_KEY_BUSINESS_MODEL])
    step1_raw = request_ai_step("business_model", prompt1, schema_step1)
    step1 = validate_step1_business_model(step1_raw)

    business_for_prompt = f"{step1['business_model']}\nSummary: {step1['business_summary']}"
    prompt2 = build_analysis_prompt(
        symbol,
        effective_price,
        template=templates[ANALYSIS_PROMPT_SETTING_KEY_KEY_VARIABLES],
        business_model=business_for_prompt,
    )
    step2_raw = request_ai_step("key_variables", prompt2, schema_step2)
    step2 = validate_step2_key_variables(step2_raw)

    prompt3 = build_analysis_prompt(
        symbol,
        effective_price,
        template=templates[ANALYSIS_PROMPT_SETTING_KEY_SCENARIOS],
        business_model=business_for_prompt,
        key_variables=step2["key_variables"],
    )
    step3_raw = request_ai_step("scenarios", prompt3, schema_step3)
    parsed = validate_step3_scenarios(step3_raw, symbol, step2["key_variables"])

    return {
        "effective_price": effective_price,
        "business_model": step1,
        "key_variables": step2["key_variables"],
        "parsed": parsed,
        "raw": {
            "step1": step1_raw,
            "step2": step2_raw,
            "step3": step3_raw,
        },
    }


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
               business_model_text, business_summary_text, created_at, updated_at
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
        "business_model": row["business_model_text"],
        "business_summary": row["business_summary_text"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "scenarios": [dict(s) for s in scenarios],
        "key_variables": [dict(v) for v in key_variables],
    }


def upsert_analysis(conn, symbol, current_price=None):
    ai_result = request_ai_analysis(symbol, current_price=current_price)
    parsed = ai_result["parsed"]

    if parsed["symbol"] != symbol:
        parsed["symbol"] = symbol

    expected_price = calculate_expected_price(parsed["scenarios"])
    upside = calculate_upside(expected_price, ai_result["effective_price"])
    overall_confidence = calculate_overall_confidence(parsed["key_variables"])
    now = utc_now_iso()

    conn.execute("BEGIN")
    try:
        conn.execute(
            """
            INSERT INTO analysis_symbols (
                symbol, current_price, expected_price, upside, overall_confidence,
                assumptions_text, business_model_text, business_summary_text,
                raw_ai_response, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol) DO UPDATE SET
                current_price = excluded.current_price,
                expected_price = excluded.expected_price,
                upside = excluded.upside,
                overall_confidence = excluded.overall_confidence,
                assumptions_text = excluded.assumptions_text,
                business_model_text = excluded.business_model_text,
                business_summary_text = excluded.business_summary_text,
                raw_ai_response = excluded.raw_ai_response,
                updated_at = excluded.updated_at
            """,
            (
                symbol,
                ai_result["effective_price"],
                expected_price,
                upside,
                overall_confidence,
                parsed["assumptions"],
                ai_result["business_model"]["business_model"],
                ai_result["business_model"]["business_summary"],
                json.dumps(ai_result["raw"]),
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
        if path == "/api/configuration/prompts":
            return self.handle_configuration_prompts_get()

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
        if path == "/api/configuration/prompts/preview":
            return self.handle_configuration_prompts_preview()
        if path == "/api/configuration/prompts/reset":
            return self.handle_configuration_prompts_reset()

        self.send_error(404, "Not Found")

    def do_PUT(self):
        path = urlparse(self.path).path
        if path == "/api/configuration/prompts":
            return self.handle_configuration_prompts_put()

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

    def handle_configuration_prompts_get(self):
        conn = get_db_connection()
        try:
            templates, sources = get_all_prompt_templates(conn)
            self._send_json({"templates": templates, "sources": sources})
        except Exception as exc:
            self._send_json(
                {"error": "Unable to load prompt configuration.", "details": str(exc)},
                status=500,
            )
        finally:
            conn.close()

    def handle_configuration_prompts_put(self):
        payload = self._read_json_body() or {}
        templates = payload.get("templates")
        if not isinstance(templates, dict):
            return self._send_json({"error": "templates object is required"}, status=400)

        conn = get_db_connection()
        try:
            for key, value in templates.items():
                save_prompt_template(conn, key, value)
            self._send_json({"ok": True})
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=400)
        except Exception as exc:
            self._send_json(
                {"error": "Unable to save prompt configuration.", "details": str(exc)},
                status=500,
            )
        finally:
            conn.close()

    def handle_configuration_prompts_reset(self):
        conn = get_db_connection()
        try:
            for key in PROMPT_TEMPLATE_CONFIG.keys():
                reset_prompt_template(conn, key)
            templates, sources = get_all_prompt_templates(conn)
            self._send_json({"ok": True, "templates": templates, "sources": sources})
        except Exception as exc:
            self._send_json(
                {"error": "Unable to reset prompt configuration.", "details": str(exc)},
                status=500,
            )
        finally:
            conn.close()

    def handle_configuration_prompts_preview(self):
        payload = self._read_json_body() or {}
        symbol = normalize_symbol(payload.get("symbol"))
        if not symbol:
            return self._send_json({"error": "Symbol is required."}, status=400)

        price = get_latest_price_for_symbol(symbol)

        conn = get_db_connection()
        try:
            templates, _sources = get_all_prompt_templates(conn)
        finally:
            conn.close()

        context = build_prompt_context(symbol=symbol, price=price)
        preview = {
            key: render_prompt_template(template, context)
            for key, template in templates.items()
        }

        self._send_json(
            {
                "symbol": symbol,
                "price": context["$Price"],
                "rendered_prompts": preview,
            }
        )


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
