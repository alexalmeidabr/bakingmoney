import asyncio
import json
import logging
import math
import os
import sqlite3
import statistics
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
OPENAI_WEB_SEARCH_TOOL_CANDIDATES = ("web_search", "web_search_preview")
OPENAI_REQUEST_TIMEOUT_SECONDS = float(os.getenv("OPENAI_REQUEST_TIMEOUT_SECONDS", "60"))
OPENAI_RECENT_EVENT_REQUEST_TIMEOUT_SECONDS = float(os.getenv("OPENAI_RECENT_EVENT_REQUEST_TIMEOUT_SECONDS", "120"))
NO_PRICE_WARNING = "No live API market data (delayed/unavailable)"
ANALYSIS_PROMPT_SETTING_KEY_BUSINESS_MODEL = "analysis_prompt_business_model"
ANALYSIS_PROMPT_SETTING_KEY_KEY_VARIABLES = "analysis_prompt_key_variables"
ANALYSIS_PROMPT_SETTING_KEY_SCENARIOS = "analysis_prompt_scenarios"
ANALYSIS_PROMPT_SETTING_KEY_RECENT_EVENT_CHECK = "analysis_prompt_recent_event_check"
ANALYSIS_SETTING_SCENARIO_MULTI_PASS_ENABLED = "scenario_multi_pass_enabled"
ANALYSIS_SETTING_SCENARIO_PASS_COUNT = "scenario_pass_count"
ANALYSIS_SETTING_SCENARIO_OUTLIER_FILTER_ENABLED = "scenario_outlier_filter_enabled"
ANALYSIS_SETTING_IB_PRICE_WAIT_SECONDS = "ib_price_wait_seconds"

DEFAULT_SCENARIO_MULTI_PASS_ENABLED = False
DEFAULT_SCENARIO_PASS_COUNT = 1
DEFAULT_SCENARIO_OUTLIER_FILTER_ENABLED = True
DEFAULT_IB_PRICE_WAIT_SECONDS = 5

RATING_SETTING_MIN_CONVICTION_HOLD_THRESHOLD = "min_conviction_hold_threshold"
RATING_SETTING_STRONG_BUY_MIN_UPSIDE = "strong_buy_min_upside"
RATING_SETTING_STRONG_BUY_MIN_DIFF = "strong_buy_min_diff"
RATING_SETTING_STRONG_BUY_MIN_BULLISH_CONFIDENCE = "strong_buy_min_bullish_confidence"
RATING_SETTING_BUY_MIN_UPSIDE = "buy_min_upside"
RATING_SETTING_BUY_MIN_DIFF = "buy_min_diff"
RATING_SETTING_BUY_MIN_BULLISH_CONFIDENCE = "buy_min_bullish_confidence"
RATING_SETTING_STRONG_SELL_MAX_UPSIDE = "strong_sell_max_upside"
RATING_SETTING_STRONG_SELL_MAX_DIFF = "strong_sell_max_diff"
RATING_SETTING_STRONG_SELL_MIN_BEARISH_CONFIDENCE = "strong_sell_min_bearish_confidence"
RATING_SETTING_SELL_MAX_UPSIDE = "sell_max_upside"
RATING_SETTING_SELL_MAX_DIFF = "sell_max_diff"
RATING_SETTING_SELL_MIN_BEARISH_CONFIDENCE = "sell_min_bearish_confidence"

SCENARIO_PROBABILITY_SETTING_SOURCE_MODE = "scenario_probability_source_mode"
SCENARIO_PROBABILITY_SETTING_HYBRID_AI_WEIGHT = "scenario_probability_hybrid_ai_weight"
SCENARIO_PROBABILITY_SETTING_HYBRID_BACKEND_WEIGHT = "scenario_probability_hybrid_backend_weight"
SCENARIO_PROBABILITY_SETTING_BACKEND_BASE_MAX = "scenario_probability_backend_base_max_probability"
SCENARIO_PROBABILITY_SETTING_BACKEND_BASE_MIN = "scenario_probability_backend_base_min_probability"

DEFAULT_SCENARIO_PROBABILITY_SETTINGS = {
    SCENARIO_PROBABILITY_SETTING_SOURCE_MODE: "hybrid",
    SCENARIO_PROBABILITY_SETTING_HYBRID_AI_WEIGHT: 0.70,
    SCENARIO_PROBABILITY_SETTING_HYBRID_BACKEND_WEIGHT: 0.30,
    SCENARIO_PROBABILITY_SETTING_BACKEND_BASE_MAX: 60.0,
    SCENARIO_PROBABILITY_SETTING_BACKEND_BASE_MIN: 35.0,
}

DEFAULT_RATING_SETTINGS = {
    RATING_SETTING_MIN_CONVICTION_HOLD_THRESHOLD: 5.0,
    RATING_SETTING_STRONG_BUY_MIN_UPSIDE: 50.0,
    RATING_SETTING_STRONG_BUY_MIN_DIFF: 1.5,
    RATING_SETTING_STRONG_BUY_MIN_BULLISH_CONFIDENCE: 7.0,
    RATING_SETTING_BUY_MIN_UPSIDE: 25.0,
    RATING_SETTING_BUY_MIN_DIFF: 0.5,
    RATING_SETTING_BUY_MIN_BULLISH_CONFIDENCE: 5.5,
    RATING_SETTING_STRONG_SELL_MAX_UPSIDE: 0.0,
    RATING_SETTING_STRONG_SELL_MAX_DIFF: -1.5,
    RATING_SETTING_STRONG_SELL_MIN_BEARISH_CONFIDENCE: 7.0,
    RATING_SETTING_SELL_MAX_UPSIDE: 10.0,
    RATING_SETTING_SELL_MAX_DIFF: -0.5,
    RATING_SETTING_SELL_MIN_BEARISH_CONFIDENCE: 5.5,
}

SCENARIO_MAX_BASE_DEVIATION = 0.40
SCENARIO_MAX_AVG_DEVIATION = 0.30

DEFAULT_PROMPT_BUSINESS_MODEL = """You are an equity analyst.

Describe the business model of the publicly traded company below.

Company context:
- Symbol: $Symbol
- Company name: $CompanyName
- Current price: $Price USD

Instructions:
- Explain what the company does in the real world.
- Explain how it makes money.
- Explain the core economic engine that drives revenue and margins.
- Keep the description practical, concise, and business-focused.
- Focus on the operating business, not stock valuation.

Return ONLY valid JSON in this exact structure:
{
  "symbol": "$Symbol",
  "company_name": "$CompanyName",
  "business_model": "concise description of what the company does, how it makes money, and the core economic engine",
  "business_summary": "short summary of the main revenue drivers, cost drivers, and major risks"
}

Rules:
- Be specific and practical.
- business_model should be concise but concrete.
- business_summary should be short and useful for later analysis.
- JSON only.
- No markdown.
- No commentary outside JSON."""

DEFAULT_PROMPT_KEY_VARIABLES = """You are an equity analyst.

Using the business model below, identify the few most important company-specific variables that could materially push the stock price up or down over the next 5 years.

Company context:
- Symbol: $Symbol
- Company name: $CompanyName
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
- Return at least 6 key variables.
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
- Company name: $CompanyName
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

DEFAULT_PROMPT_RECENT_EVENT_CHECK = """You are an equity analyst reviewing whether recent company-specific developments may materially affect an existing 5-year stock thesis.

Company context:
- Symbol: $Symbol
- Company name: $CompanyName
- Current price: $Price USD
- Business model: $BusinessModel
- Key variables: $KeyVariables

Task:
Review recent company-specific developments and determine whether any event should trigger a manual thesis-review alert.

Definitions:
- A thesis-review alert should be created only if a recent event may materially strengthen, weaken, challenge, or add to the current 5-year key-variable framework.
- Material means the event could plausibly affect revenue growth, margins, cash flow, valuation, capital needs, competitive position, or scenario probabilities over a multi-year horizon.
- Do not create alerts for short-term noise that does not change the long-term thesis.

Guidance:
- Check whether the event:
  - strengthens an existing key variable
  - weakens an existing key variable
  - suggests a missing key variable
  - suggests that a current key variable has become less relevant
- Focus on company-specific developments such as:
  - earnings/guidance changes
  - major customer wins or losses
  - large contracts or backlog changes
  - acquisitions or divestitures
  - financing, dilution, or capital raising
  - product launches or technical milestones
  - regulatory decisions that are central to the business model
  - major competitive developments
- Avoid generic market commentary unless it clearly affects this company’s core business model.
- Do not automatically change any key variable. This task is only to create review alerts.

Return ONLY valid JSON in this exact structure:
{
  "symbol": "$Symbol",
  "alerts": [
    {
      "alert_type": "text",
      "event_summary": "text",
      "impact_summary": "text",
      "affected_variables": ["text"],
      "suggested_action": "text"
    }
  ]
}

Rules:
- Return only alerts for material thesis-impacting events.
- If no material event is found, return an empty alerts array.
- alert_type must be exactly one of:
  - Strengthens existing variable
  - Weakens existing variable
  - Potential new variable
  - Potentially obsolete variable
- affected_variables should list the current variable text(s) impacted when applicable.
- Keep event_summary and impact_summary concise.
- For existing variables, add in the suggested_action a recommendation for the update on importance and confidence
- Do not modify the variables directly.
- JSON only.
- No markdown.
- No commentary outside JSON."""

ALLOWED_ALERT_TYPES = {
    "Strengthens existing variable",
    "Weakens existing variable",
    "Potential new variable",
    "Potentially obsolete variable",
}

PROMPT_TEMPLATE_CONFIG = {
    ANALYSIS_PROMPT_SETTING_KEY_BUSINESS_MODEL: {
        "default": DEFAULT_PROMPT_BUSINESS_MODEL,
        "required_vars": ["$Symbol", "$CompanyName"],
    },
    ANALYSIS_PROMPT_SETTING_KEY_KEY_VARIABLES: {
        "default": DEFAULT_PROMPT_KEY_VARIABLES,
        "required_vars": ["$Symbol", "$CompanyName", "$BusinessModel"],
    },
    ANALYSIS_PROMPT_SETTING_KEY_SCENARIOS: {
        "default": DEFAULT_PROMPT_SCENARIOS,
        "required_vars": ["$Symbol", "$CompanyName", "$BusinessModel", "$KeyVariables"],
    },
    ANALYSIS_PROMPT_SETTING_KEY_RECENT_EVENT_CHECK: {
        "default": DEFAULT_PROMPT_RECENT_EVENT_CHECK,
        "required_vars": ["$Symbol", "$CompanyName", "$KeyVariables"],
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


def compute_unrealized_pnl_percent(position_row):
    if not isinstance(position_row, dict):
        return None

    direct_value = safe_number(position_row.get("unrealizedPnLPercent"))
    if direct_value is not None:
        return direct_value

    unrealized_pnl = safe_number(position_row.get("unrealizedPnL"))
    qty = safe_number(position_row.get("position"))
    avg_cost = safe_number(position_row.get("avgCost"))
    if unrealized_pnl is None or qty is None or avg_cost is None:
        return None

    cost_basis = abs(avg_cost * qty)
    if cost_basis == 0:
        return None

    return (unrealized_pnl / cost_basis) * 100


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
        try:
            validate_prompt_template(key, row["value"])
            logger.info("Using custom prompt template key=%s", key)
            return row["value"], "custom"
        except ValueError as exc:
            logger.warning("Invalid custom prompt template key=%s, falling back to default (%s)", key, exc)

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


def _get_setting_value(conn, key):
    row = conn.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def get_bool_setting(conn, key, default):
    raw = _get_setting_value(conn, key)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def get_int_setting(conn, key, default, minimum=1, maximum=10):
    raw = _get_setting_value(conn, key)
    if raw is None:
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, value))


def get_float_setting(conn, key, default, minimum=1.0, maximum=30.0):
    raw = _get_setting_value(conn, key)
    if raw is None:
        return default
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(value):
        return default
    return max(minimum, min(maximum, value))


def get_scenario_generation_config(conn):
    return {
        "scenario_multi_pass_enabled": get_bool_setting(
            conn,
            ANALYSIS_SETTING_SCENARIO_MULTI_PASS_ENABLED,
            DEFAULT_SCENARIO_MULTI_PASS_ENABLED,
        ),
        "scenario_pass_count": get_int_setting(
            conn,
            ANALYSIS_SETTING_SCENARIO_PASS_COUNT,
            DEFAULT_SCENARIO_PASS_COUNT,
            minimum=1,
            maximum=8,
        ),
        "scenario_outlier_filter_enabled": get_bool_setting(
            conn,
            ANALYSIS_SETTING_SCENARIO_OUTLIER_FILTER_ENABLED,
            DEFAULT_SCENARIO_OUTLIER_FILTER_ENABLED,
        ),
    }


def save_scenario_generation_config(conn, settings):
    known = {
        ANALYSIS_SETTING_SCENARIO_MULTI_PASS_ENABLED,
        ANALYSIS_SETTING_SCENARIO_PASS_COUNT,
        ANALYSIS_SETTING_SCENARIO_OUTLIER_FILTER_ENABLED,
    }
    normalized = {}
    for key, value in settings.items():
        if key not in known:
            raise ValueError(f"Unknown scenario setting: {key}")
        if key == ANALYSIS_SETTING_SCENARIO_PASS_COUNT:
            try:
                value = int(value)
            except (TypeError, ValueError):
                raise ValueError("scenario_pass_count must be an integer")
            if value < 1 or value > 10:
                raise ValueError("scenario_pass_count must be between 1 and 10")
        elif key in {ANALYSIS_SETTING_SCENARIO_MULTI_PASS_ENABLED, ANALYSIS_SETTING_SCENARIO_OUTLIER_FILTER_ENABLED}:
            value = bool(value)
        normalized[key] = value

    for key, value in normalized.items():
        conn.execute(
            """
            INSERT INTO app_settings (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
              value = excluded.value,
              updated_at = excluded.updated_at
            """,
            (key, str(value), utc_now_iso()),
        )
    conn.commit()


def reset_scenario_generation_config(conn):
    for key in (
        ANALYSIS_SETTING_SCENARIO_MULTI_PASS_ENABLED,
        ANALYSIS_SETTING_SCENARIO_PASS_COUNT,
        ANALYSIS_SETTING_SCENARIO_OUTLIER_FILTER_ENABLED,
    ):
        conn.execute("DELETE FROM app_settings WHERE key = ?", (key,))
    conn.commit()


def _coerce_score(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(number):
        return 0.0
    return number


def calculate_rating(upside, bullish_confidence, bearish_confidence, rating_settings):
    upside_value = _coerce_score(upside)
    bullish_value = _coerce_score(bullish_confidence)
    bearish_value = _coerce_score(bearish_confidence)
    confidence_diff = bullish_value - bearish_value
    max_confidence = max(bullish_value, bearish_value)

    if max_confidence < rating_settings[RATING_SETTING_MIN_CONVICTION_HOLD_THRESHOLD]:
        return "Hold", confidence_diff

    if (
        upside_value >= rating_settings[RATING_SETTING_STRONG_BUY_MIN_UPSIDE]
        and confidence_diff >= rating_settings[RATING_SETTING_STRONG_BUY_MIN_DIFF]
        and bullish_value >= rating_settings[RATING_SETTING_STRONG_BUY_MIN_BULLISH_CONFIDENCE]
    ):
        return "Strong Buy", confidence_diff

    if (
        upside_value >= rating_settings[RATING_SETTING_BUY_MIN_UPSIDE]
        and confidence_diff >= rating_settings[RATING_SETTING_BUY_MIN_DIFF]
        and bullish_value >= rating_settings[RATING_SETTING_BUY_MIN_BULLISH_CONFIDENCE]
    ):
        return "Buy", confidence_diff

    if (
        upside_value <= rating_settings[RATING_SETTING_STRONG_SELL_MAX_UPSIDE]
        and confidence_diff <= rating_settings[RATING_SETTING_STRONG_SELL_MAX_DIFF]
        and bearish_value >= rating_settings[RATING_SETTING_STRONG_SELL_MIN_BEARISH_CONFIDENCE]
    ):
        return "Strong Sell", confidence_diff

    if (
        upside_value <= rating_settings[RATING_SETTING_SELL_MAX_UPSIDE]
        and confidence_diff <= rating_settings[RATING_SETTING_SELL_MAX_DIFF]
        and bearish_value >= rating_settings[RATING_SETTING_SELL_MIN_BEARISH_CONFIDENCE]
    ):
        return "Sell", confidence_diff

    return "Hold", confidence_diff


def get_rating_settings(conn):
    settings = {}
    for key, default in DEFAULT_RATING_SETTINGS.items():
        settings[key] = get_float_setting(conn, key, default, minimum=-10000.0, maximum=10000.0)

    for confidence_key in (
        RATING_SETTING_MIN_CONVICTION_HOLD_THRESHOLD,
        RATING_SETTING_STRONG_BUY_MIN_BULLISH_CONFIDENCE,
        RATING_SETTING_BUY_MIN_BULLISH_CONFIDENCE,
        RATING_SETTING_STRONG_SELL_MIN_BEARISH_CONFIDENCE,
        RATING_SETTING_SELL_MIN_BEARISH_CONFIDENCE,
    ):
        settings[confidence_key] = max(0.0, min(10.0, settings[confidence_key]))

    return settings


def normalize_probabilities(probabilities_by_name):
    required = ["Bear", "Base", "Bull"]
    values = {name: max(0.0, float(probabilities_by_name.get(name, 0.0))) for name in required}
    total = sum(values.values())
    if total <= 0:
        return {"Bear": 20.0, "Base": 60.0, "Bull": 20.0}

    normalized = {name: (values[name] / total) * 100.0 for name in required}
    rounded = {name: round(value, 2) for name, value in normalized.items()}
    delta = round(100.0 - sum(rounded.values()), 2)
    if abs(delta) > 1e-9:
        target = max(rounded.keys(), key=lambda k: rounded[k])
        rounded[target] = round(rounded[target] + delta, 2)
    return rounded


def scenario_probabilities_from_scenarios(scenarios):
    mapping = {}
    for item in scenarios or []:
        name = item.get("scenario_name") or item.get("name")
        if name in {"Bear", "Base", "Bull"}:
            mapping[name] = float(item.get("probability", 0.0)) * 100.0
    return normalize_probabilities(mapping)


def compute_backend_probabilities(key_variables, base_max, base_min):
    bull_score = 0.0
    bear_score = 0.0
    for item in key_variables or []:
        try:
            confidence = float(item.get("confidence", 0.0))
            importance = float(item.get("importance", 0.0))
        except (TypeError, ValueError):
            continue
        score = confidence * importance
        if item.get("variable_type") == "Bullish":
            bull_score += score
        elif item.get("variable_type") == "Bearish":
            bear_score += score

    total = bull_score + bear_score
    if total <= 0:
        return {"Bear": 20.0, "Base": 60.0, "Bull": 20.0}

    bull_share = bull_score / total
    bear_share = bear_score / total
    imbalance = abs(bull_share - bear_share)
    base = float(base_max) - imbalance * (float(base_max) - float(base_min))
    base = max(0.0, min(100.0, base))
    remaining = max(0.0, 100.0 - base)
    bull = remaining * bull_share
    bear = remaining * bear_share
    return normalize_probabilities({"Bear": bear, "Base": base, "Bull": bull})


def blend_probabilities(ai_probs, backend_probs, ai_weight, backend_weight):
    ai_w = max(0.0, float(ai_weight))
    backend_w = max(0.0, float(backend_weight))
    total_w = ai_w + backend_w
    if total_w <= 0:
        ai_w = 0.70
        backend_w = 0.30
        total_w = 1.0
    ai_w /= total_w
    backend_w /= total_w

    blended = {}
    for name in ["Bear", "Base", "Bull"]:
        blended[name] = ai_w * float(ai_probs.get(name, 0.0)) + backend_w * float(backend_probs.get(name, 0.0))
    return normalize_probabilities(blended)


def get_scenario_probability_settings(conn):
    mode = str(_get_setting_value(conn, SCENARIO_PROBABILITY_SETTING_SOURCE_MODE) or DEFAULT_SCENARIO_PROBABILITY_SETTINGS[SCENARIO_PROBABILITY_SETTING_SOURCE_MODE]).strip().lower()
    if mode not in {"ai", "backend", "hybrid"}:
        mode = "hybrid"

    return {
        "probability_source_mode": mode,
        "hybrid_ai_weight": get_float_setting(conn, SCENARIO_PROBABILITY_SETTING_HYBRID_AI_WEIGHT, DEFAULT_SCENARIO_PROBABILITY_SETTINGS[SCENARIO_PROBABILITY_SETTING_HYBRID_AI_WEIGHT], minimum=0.0, maximum=100.0),
        "hybrid_backend_weight": get_float_setting(conn, SCENARIO_PROBABILITY_SETTING_HYBRID_BACKEND_WEIGHT, DEFAULT_SCENARIO_PROBABILITY_SETTINGS[SCENARIO_PROBABILITY_SETTING_HYBRID_BACKEND_WEIGHT], minimum=0.0, maximum=100.0),
        "backend_base_max_probability": get_float_setting(conn, SCENARIO_PROBABILITY_SETTING_BACKEND_BASE_MAX, DEFAULT_SCENARIO_PROBABILITY_SETTINGS[SCENARIO_PROBABILITY_SETTING_BACKEND_BASE_MAX], minimum=0.0, maximum=100.0),
        "backend_base_min_probability": get_float_setting(conn, SCENARIO_PROBABILITY_SETTING_BACKEND_BASE_MIN, DEFAULT_SCENARIO_PROBABILITY_SETTINGS[SCENARIO_PROBABILITY_SETTING_BACKEND_BASE_MIN], minimum=0.0, maximum=100.0),
    }


def choose_final_probabilities(ai_probs, backend_probs, settings):
    mode = settings.get("probability_source_mode", "hybrid")
    mode_used = mode

    if mode == "ai":
        if ai_probs:
            final_probs = normalize_probabilities(ai_probs)
        elif backend_probs:
            final_probs = normalize_probabilities(backend_probs)
            mode_used = "backend_fallback_from_ai"
        else:
            final_probs = {"Bear": 20.0, "Base": 60.0, "Bull": 20.0}
            mode_used = "default_fallback_from_ai"
    elif mode == "backend":
        final_probs = normalize_probabilities(backend_probs)
    else:
        final_probs = blend_probabilities(
            ai_probs or {"Bear": 20.0, "Base": 60.0, "Bull": 20.0},
            backend_probs or {"Bear": 20.0, "Base": 60.0, "Bull": 20.0},
            settings.get("hybrid_ai_weight", 0.70),
            settings.get("hybrid_backend_weight", 0.30),
        )

    return {
        "ai_scenario_probabilities": normalize_probabilities(ai_probs) if ai_probs else None,
        "backend_scenario_probabilities": normalize_probabilities(backend_probs) if backend_probs else None,
        "final_scenario_probabilities": final_probs,
        "probability_source_mode_used": mode_used,
    }


def apply_final_probabilities_to_scenarios(scenarios, final_probabilities):
    normalized = []
    for item in scenarios:
        name = item.get("scenario_name")
        updated = dict(item)
        if name in final_probabilities:
            updated["probability"] = float(final_probabilities[name]) / 100.0
        normalized.append(updated)
    return normalized


def get_general_configuration(conn):
    scenario = get_scenario_generation_config(conn)
    return {
        "ib_price_wait_seconds": get_float_setting(
            conn,
            ANALYSIS_SETTING_IB_PRICE_WAIT_SECONDS,
            DEFAULT_IB_PRICE_WAIT_SECONDS,
            minimum=1.0,
            maximum=30.0,
        ),
        "scenario_multi_pass_enabled": scenario["scenario_multi_pass_enabled"],
        "scenario_pass_count": scenario["scenario_pass_count"],
        "scenario_outlier_filter_enabled": scenario["scenario_outlier_filter_enabled"],
        "rating_settings": get_rating_settings(conn),
        "scenario_probability_settings": get_scenario_probability_settings(conn),
    }


def save_general_configuration(conn, settings):
    if not isinstance(settings, dict):
        raise ValueError("settings must be an object")

    now = utc_now_iso()
    if "ib_price_wait_seconds" in settings:
        try:
            wait_seconds = float(settings.get("ib_price_wait_seconds"))
        except (TypeError, ValueError):
            raise ValueError("ib_price_wait_seconds must be numeric")
        if not math.isfinite(wait_seconds):
            raise ValueError("ib_price_wait_seconds must be finite")
        if wait_seconds < 1 or wait_seconds > 30:
            raise ValueError("ib_price_wait_seconds must be between 1 and 30")
        conn.execute(
            """
            INSERT INTO app_settings (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
              value = excluded.value,
              updated_at = excluded.updated_at
            """,
            (ANALYSIS_SETTING_IB_PRICE_WAIT_SECONDS, str(wait_seconds), now),
        )

    scenario_payload = {}
    if "scenario_multi_pass_enabled" in settings:
        scenario_payload[ANALYSIS_SETTING_SCENARIO_MULTI_PASS_ENABLED] = bool(settings["scenario_multi_pass_enabled"])
    if "scenario_pass_count" in settings:
        scenario_payload[ANALYSIS_SETTING_SCENARIO_PASS_COUNT] = int(settings["scenario_pass_count"])
    if "scenario_outlier_filter_enabled" in settings:
        scenario_payload[ANALYSIS_SETTING_SCENARIO_OUTLIER_FILTER_ENABLED] = bool(settings["scenario_outlier_filter_enabled"])
    scenario_probability_settings = settings.get("scenario_probability_settings")
    if scenario_probability_settings is not None:
        if not isinstance(scenario_probability_settings, dict):
            raise ValueError("scenario_probability_settings must be an object")

        mode = str(scenario_probability_settings.get("probability_source_mode", "hybrid")).strip().lower()
        if mode not in {"ai", "backend", "hybrid"}:
            raise ValueError("probability_source_mode must be ai, backend, or hybrid")

        def _save_setting(key, value):
            conn.execute(
                """
                INSERT INTO app_settings (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                  value = excluded.value,
                  updated_at = excluded.updated_at
                """,
                (key, str(value), now),
            )

        _save_setting(SCENARIO_PROBABILITY_SETTING_SOURCE_MODE, mode)

        for key in (
            SCENARIO_PROBABILITY_SETTING_HYBRID_AI_WEIGHT,
            SCENARIO_PROBABILITY_SETTING_HYBRID_BACKEND_WEIGHT,
            SCENARIO_PROBABILITY_SETTING_BACKEND_BASE_MAX,
            SCENARIO_PROBABILITY_SETTING_BACKEND_BASE_MIN,
        ):
            if key not in scenario_probability_settings:
                continue
            try:
                value = float(scenario_probability_settings[key])
            except (TypeError, ValueError):
                raise ValueError(f"{key} must be numeric")
            if not math.isfinite(value):
                raise ValueError(f"{key} must be finite")
            if key in (SCENARIO_PROBABILITY_SETTING_BACKEND_BASE_MAX, SCENARIO_PROBABILITY_SETTING_BACKEND_BASE_MIN):
                if value < 0 or value > 100:
                    raise ValueError(f"{key} must be between 0 and 100")
            elif value < 0:
                raise ValueError(f"{key} must be >= 0")
            _save_setting(key, value)

    rating_settings_payload = settings.get("rating_settings")
    if rating_settings_payload is not None:
        if not isinstance(rating_settings_payload, dict):
            raise ValueError("rating_settings must be an object")

        for key, default in DEFAULT_RATING_SETTINGS.items():
            if key not in rating_settings_payload:
                continue
            try:
                value = float(rating_settings_payload[key])
            except (TypeError, ValueError):
                raise ValueError(f"{key} must be numeric")
            if not math.isfinite(value):
                raise ValueError(f"{key} must be finite")
            if key in {
                RATING_SETTING_MIN_CONVICTION_HOLD_THRESHOLD,
                RATING_SETTING_STRONG_BUY_MIN_BULLISH_CONFIDENCE,
                RATING_SETTING_BUY_MIN_BULLISH_CONFIDENCE,
                RATING_SETTING_STRONG_SELL_MIN_BEARISH_CONFIDENCE,
                RATING_SETTING_SELL_MIN_BEARISH_CONFIDENCE,
            } and (value < 0 or value > 10):
                raise ValueError(f"{key} must be between 0 and 10")
            conn.execute(
                """
                INSERT INTO app_settings (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                  value = excluded.value,
                  updated_at = excluded.updated_at
                """,
                (key, str(value), now),
            )

    if scenario_payload:
        save_scenario_generation_config(conn, scenario_payload)
    else:
        conn.commit()


def get_ib_price_wait_seconds():
    try:
        conn = get_db_connection()
        try:
            return get_float_setting(
                conn,
                ANALYSIS_SETTING_IB_PRICE_WAIT_SECONDS,
                DEFAULT_IB_PRICE_WAIT_SECONDS,
                minimum=1.0,
                maximum=30.0,
            )
        finally:
            conn.close()
    except Exception:
        return DEFAULT_IB_PRICE_WAIT_SECONDS


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


def render_scenario_prompt(template, values):
    """Render scenario prompt from configured template using placeholder substitution only.

    IMPORTANT: Scenario generation must use exactly the saved "Build Scenario Prompt"
    template plus replacement of the supported placeholders below. Do not inject
    implicit fields (for example Summary/context blocks/instructions) here.
    """
    supported_placeholders = ("$Symbol", "$CompanyName", "$Price", "$BusinessModel", "$KeyVariables")
    substitution_context = {
        placeholder: str(values.get(placeholder, ""))
        for placeholder in supported_placeholders
    }
    return render_prompt_template(template, substitution_context)


def render_recent_event_prompt(template, values):
    """Render recent-event prompt from configured template using placeholder substitution only."""
    supported_placeholders = ("$Symbol", "$CompanyName", "$Price", "$BusinessModel", "$KeyVariables")
    substitution_context = {
        placeholder: str(values.get(placeholder, ""))
        for placeholder in supported_placeholders
    }
    return render_prompt_template(template, substitution_context)


def format_key_variables_for_prompt(key_variables):
    return json.dumps(key_variables, separators=(",", ":"), ensure_ascii=False)


def build_business_model_prompt_value(business_model="", business_summary=""):
    model_text = (business_model or "").strip()
    summary_text = (business_summary or "").strip()
    if model_text and summary_text:
        return f"{model_text}\n\nSummary: {summary_text}"
    if model_text:
        return model_text
    if summary_text:
        return f"Summary: {summary_text}"
    return ""


def build_prompt_context(symbol, price=None, company_name="", business_model="", business_summary="", key_variables=None):
    symbol_value = symbol or "unknown"
    price_value = f"{price:.2f}" if isinstance(price, (int, float)) and math.isfinite(price) else "unknown"
    company_name_value = company_name or "unknown"
    business_value = build_business_model_prompt_value(business_model=business_model, business_summary=business_summary)
    key_vars_value = format_key_variables_for_prompt(key_variables or [])
    return {
        "$Symbol": symbol_value,
        "$Price": price_value,
        "$CompanyName": company_name_value,
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
            CREATE TABLE IF NOT EXISTS analysis_roots (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              symbol TEXT NOT NULL UNIQUE,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS analysis_versions (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              analysis_root_id INTEGER NOT NULL,
              version_number INTEGER NOT NULL,
              symbol TEXT NOT NULL,
              company_name TEXT,
              current_price REAL,
              expected_price REAL NOT NULL,
              upside REAL,
              confidence_level REAL,
              assumptions_text TEXT,
              business_model_text TEXT,
              business_summary_text TEXT,
              raw_ai_response TEXT,
              source_trigger TEXT,
              created_at TEXT NOT NULL,
              FOREIGN KEY (analysis_root_id) REFERENCES analysis_roots(id) ON DELETE CASCADE,
              UNIQUE(analysis_root_id, version_number)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS analysis_version_scenarios (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              analysis_version_id INTEGER NOT NULL,
              scenario_name TEXT NOT NULL,
              price_low REAL NOT NULL,
              price_high REAL NOT NULL,
              cagr_low REAL NOT NULL,
              cagr_high REAL NOT NULL,
              probability REAL NOT NULL,
              created_at TEXT NOT NULL,
              FOREIGN KEY (analysis_version_id) REFERENCES analysis_versions(id) ON DELETE CASCADE,
              UNIQUE(analysis_version_id, scenario_name)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS analysis_version_key_variables (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              analysis_version_id INTEGER NOT NULL,
              variable_text TEXT NOT NULL,
              variable_type TEXT NOT NULL,
              confidence REAL NOT NULL,
              importance REAL NOT NULL,
              created_at TEXT NOT NULL,
              FOREIGN KEY (analysis_version_id) REFERENCES analysis_versions(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS analysis_version_scenario_passes (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              analysis_version_id INTEGER NOT NULL,
              pass_index INTEGER NOT NULL,
              raw_response_text TEXT,
              parsed_json TEXT,
              validation_status TEXT NOT NULL,
              rejection_reason TEXT,
              quality_score REAL,
              is_outlier INTEGER NOT NULL DEFAULT 0,
              created_at TEXT NOT NULL,
              FOREIGN KEY (analysis_version_id) REFERENCES analysis_versions(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS analysis_key_variable_edits (
              analysis_root_id INTEGER PRIMARY KEY,
              based_on_version_id INTEGER NOT NULL,
              key_variables_json TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY (analysis_root_id) REFERENCES analysis_roots(id) ON DELETE CASCADE,
              FOREIGN KEY (based_on_version_id) REFERENCES analysis_versions(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS analysis_business_model_edits (
              analysis_root_id INTEGER PRIMARY KEY,
              based_on_version_id INTEGER NOT NULL,
              business_model_text TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY (analysis_root_id) REFERENCES analysis_roots(id) ON DELETE CASCADE,
              FOREIGN KEY (based_on_version_id) REFERENCES analysis_versions(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS analysis_business_summary_edits (
              analysis_root_id INTEGER PRIMARY KEY,
              based_on_version_id INTEGER NOT NULL,
              business_summary_text TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY (analysis_root_id) REFERENCES analysis_roots(id) ON DELETE CASCADE,
              FOREIGN KEY (based_on_version_id) REFERENCES analysis_versions(id) ON DELETE CASCADE
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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS positions_cache (
              symbol TEXT PRIMARY KEY,
              position REAL,
              price REAL,
              avg_cost REAL,
              change_percent REAL,
              market_value REAL,
              unrealized_pnl REAL,
              daily_pnl REAL,
              currency TEXT,
              updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS thesis_review_alerts (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              symbol TEXT NOT NULL,
              company_name TEXT,
              alert_type TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'New',
              event_date TEXT,
              event_summary TEXT NOT NULL,
              impact_summary TEXT NOT NULL,
              affected_variables_json TEXT NOT NULL,
              suggested_action TEXT,
              prompt_used TEXT,
              raw_response_json TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_alerts_dedupe
            ON thesis_review_alerts(symbol, alert_type, event_summary, impact_summary)
            """
        )
        ensure_column_exists(conn, "analysis_symbols", "company_name", "TEXT")
        ensure_column_exists(conn, "analysis_symbols", "business_model_text", "TEXT")
        ensure_column_exists(conn, "analysis_symbols", "business_summary_text", "TEXT")

        has_roots = conn.execute("SELECT 1 FROM analysis_roots LIMIT 1").fetchone()
        if not has_roots:
            legacy_rows = conn.execute(
                """
                SELECT id, symbol, company_name, current_price, expected_price, upside, overall_confidence,
                       assumptions_text, business_model_text, business_summary_text, raw_ai_response,
                       created_at, updated_at
                FROM analysis_symbols
                ORDER BY symbol ASC
                """
            ).fetchall()

            for row in legacy_rows:
                root_created_at = row["created_at"] or utc_now_iso()
                root_updated_at = row["updated_at"] or root_created_at
                conn.execute(
                    "INSERT INTO analysis_roots (symbol, created_at, updated_at) VALUES (?, ?, ?)",
                    (row["symbol"], root_created_at, root_updated_at),
                )
                root_id = conn.execute("SELECT id FROM analysis_roots WHERE symbol = ?", (row["symbol"],)).fetchone()["id"]
                conn.execute(
                    """
                    INSERT INTO analysis_versions (
                        analysis_root_id, version_number, symbol, company_name, current_price, expected_price,
                        upside, confidence_level, assumptions_text, business_model_text, business_summary_text,
                        raw_ai_response, source_trigger, created_at
                    ) VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'legacy_migration', ?)
                    """,
                    (
                        root_id,
                        row["symbol"],
                        row["company_name"],
                        row["current_price"],
                        row["expected_price"],
                        row["upside"],
                        row["overall_confidence"],
                        row["assumptions_text"],
                        row["business_model_text"],
                        row["business_summary_text"],
                        row["raw_ai_response"],
                        root_created_at,
                    ),
                )
                version_id = conn.execute(
                    "SELECT id FROM analysis_versions WHERE analysis_root_id = ? AND version_number = 1",
                    (root_id,),
                ).fetchone()["id"]

                legacy_scenarios = conn.execute(
                    """
                    SELECT scenario_name, price_low, price_high, cagr_low, cagr_high, probability, created_at
                    FROM analysis_scenarios
                    WHERE analysis_symbol_id = ?
                    ORDER BY id ASC
                    """,
                    (row["id"],),
                ).fetchall()
                for scenario in legacy_scenarios:
                    conn.execute(
                        """
                        INSERT INTO analysis_version_scenarios (
                            analysis_version_id, scenario_name, price_low, price_high, cagr_low,
                            cagr_high, probability, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            version_id,
                            scenario["scenario_name"],
                            scenario["price_low"],
                            scenario["price_high"],
                            scenario["cagr_low"],
                            scenario["cagr_high"],
                            scenario["probability"],
                            scenario["created_at"] or root_created_at,
                        ),
                    )

                legacy_variables = conn.execute(
                    """
                    SELECT variable_text, variable_type, confidence, importance, created_at
                    FROM analysis_key_variables
                    WHERE analysis_symbol_id = ?
                    ORDER BY id ASC
                    """,
                    (row["id"],),
                ).fetchall()
                for variable in legacy_variables:
                    conn.execute(
                        """
                        INSERT INTO analysis_version_key_variables (
                            analysis_version_id, variable_text, variable_type, confidence,
                            importance, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            version_id,
                            variable["variable_text"],
                            variable["variable_type"],
                            variable["confidence"],
                            variable["importance"],
                            variable["created_at"] or root_created_at,
                        ),
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
            ib.sleep(get_ib_price_wait_seconds())
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


def resolve_company_profile_from_tws(symbol):
    """Resolve deterministic company identity from IBKR contract details."""
    ensure_event_loop()
    from ib_insync import Stock

    profile = {
        "symbol": symbol,
        "company_name": None,
        "industry": None,
        "category": None,
        "subcategory": None,
    }

    try:
        ib = get_ib_connection()
        contract = Stock(symbol, "SMART", "USD")
        qualified = ib.qualifyContracts(contract)
        if not qualified:
            logger.info("Company resolution failed for %s (no qualified contract)", symbol)
            return profile

        # Use the first qualified primary match from IBKR.
        details = ib.reqContractDetails(qualified[0])
        if not details:
            logger.info("Company resolution failed for %s (no contract details)", symbol)
            return profile

        detail = details[0]
        company_name = (
            getattr(detail, "longName", None)
            or getattr(detail, "companyName", None)
            or getattr(getattr(detail, "contract", None), "localSymbol", None)
            or getattr(getattr(detail, "contract", None), "symbol", None)
        )

        source = "longName" if getattr(detail, "longName", None) else (
            "companyName" if getattr(detail, "companyName", None) else "contract fallback"
        )

        if company_name and isinstance(company_name, str):
            profile["company_name"] = company_name.strip()
        profile["industry"] = getattr(detail, "industry", None)
        profile["category"] = getattr(detail, "category", None)
        profile["subcategory"] = getattr(detail, "subcategory", None)

        if profile["company_name"]:
            logger.info(
                "Resolved company profile for %s company_name=%s source=%s",
                symbol,
                profile["company_name"],
                source,
            )
        else:
            logger.info("Company resolution returned empty name for %s", symbol)
    except Exception as exc:
        logger.info("Company resolution unavailable for %s (%s)", symbol, exc)

    return profile


def build_analysis_prompt(symbol, current_price=None, template=None, company_name="", business_model="", business_summary="", key_variables=None):
    base_template = template if template is not None else DEFAULT_PROMPT_SCENARIOS
    context = build_prompt_context(
        symbol=symbol,
        price=current_price,
        company_name=company_name,
        business_model=business_model,
        business_summary=business_summary,
        key_variables=key_variables,
    )
    return render_prompt_template(base_template, context)


def build_scenario_generation_prompt(symbol, current_price=None, template=None, company_name="", business_model="", business_summary="", key_variables=None):
    base_template = template if template is not None else DEFAULT_PROMPT_SCENARIOS
    context = build_prompt_context(
        symbol=symbol,
        price=current_price,
        company_name=company_name,
        business_model=business_model,
        business_summary=business_summary,
        key_variables=key_variables,
    )
    return render_scenario_prompt(base_template, context)


def _extract_output_text(raw):
    output_text = raw.get("output_text")
    if output_text:
        return output_text

    for item in raw.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in ("output_text", "text") and content.get("text"):
                return content["text"]
    return None


def build_openai_tools(tool_type=None):
    selected_tool_type = tool_type or OPENAI_WEB_SEARCH_TOOL_CANDIDATES[0]
    return [{"type": selected_tool_type}]


def build_openai_request_body(prompt_text, json_schema, reasoning_effort, supports_temperature, temperature, tool_type=None):
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
        "tools": build_openai_tools(tool_type),
    }
    if supports_temperature:
        body["temperature"] = temperature
    return body


def _looks_like_unsupported_web_tool_error(response_text):
    if not response_text:
        return False
    lower = response_text.lower()
    return "tool" in lower and ("unsupported" in lower or "unknown" in lower or "invalid" in lower) and "web_search" in lower


def get_openai_timeout_seconds_for_step(step_name):
    if step_name == "recent_event_check":
        return max(10.0, OPENAI_RECENT_EVENT_REQUEST_TIMEOUT_SECONDS)
    return max(10.0, OPENAI_REQUEST_TIMEOUT_SECONDS)


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

    tool_candidates = list(OPENAI_WEB_SEARCH_TOOL_CANDIDATES)
    last_exc = None
    request_timeout_seconds = get_openai_timeout_seconds_for_step(step_name)

    for idx, tool_type in enumerate(tool_candidates):
        body = build_openai_request_body(
            prompt_text,
            json_schema,
            reasoning_effort,
            supports_temperature,
            temperature,
            tool_type=tool_type,
        )
        logger.info("OpenAI Analysis request includes web search tool")
        logger.info("OpenAI web search tool type: %s", tool_type)
        logger.info("OpenAI request timeout seconds for step=%s: %.1f", step_name, request_timeout_seconds)

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
            with urlopen(request, timeout=request_timeout_seconds) as response:
                raw = json.loads(response.read().decode("utf-8"))
            output_text = _extract_output_text(raw)
            if not output_text:
                raise RuntimeError(f"AI step {step_name} response did not contain output text")

            payload = extract_json_payload(output_text)
            logger.info("AI step=%s completed", step_name)
            return payload
        except HTTPError as exc:
            response_text = ""
            try:
                response_text = exc.read().decode("utf-8")
            except Exception:
                response_text = ""

            last_exc = RuntimeError(
                f"OpenAI request failed on step {step_name} with status {getattr(exc, 'code', 'unknown')}: {response_text[:400]}"
            )

            can_retry = idx < len(tool_candidates) - 1 and _looks_like_unsupported_web_tool_error(response_text)
            if can_retry:
                logger.warning(
                    "OpenAI web-search tool type unsupported (%s). Retrying with %s",
                    tool_type,
                    tool_candidates[idx + 1],
                )
                continue

            if _looks_like_unsupported_web_tool_error(response_text):
                logger.error("OpenAI web-search tool type appears unsupported: %s", tool_type)
            raise last_exc from exc
        except TimeoutError as exc:
            last_exc = RuntimeError(
                f"OpenAI request timed out on step {step_name} after {request_timeout_seconds:.1f}s"
            )
            raise last_exc from exc

    if last_exc:
        raise last_exc
    raise RuntimeError(f"OpenAI request failed on step {step_name} for unknown reasons")




def validate_step1_business_model(payload):
    symbol = payload.get("symbol")
    company_name = payload.get("company_name")
    business_model = payload.get("business_model")
    business_summary = payload.get("business_summary")

    if not isinstance(symbol, str) or not symbol.strip():
        raise AnalysisValidationError("step1.symbol is required")
    if not isinstance(company_name, str) or not company_name.strip():
        raise AnalysisValidationError("step1.company_name is required")
    if not isinstance(business_model, str) or not business_model.strip():
        raise AnalysisValidationError("step1.business_model is required")
    if not isinstance(business_summary, str) or not business_summary.strip():
        raise AnalysisValidationError("step1.business_summary is required")

    return {
        "symbol": symbol.strip().upper(),
        "company_name": company_name.strip() if isinstance(company_name, str) else None,
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
    if effective_price is None:
        logger.info("Current price unavailable for %s; proceeding with unknown price context", symbol)
    else:
        logger.info("Resolved current price for %s: %.2f", symbol, effective_price)

    company_profile = resolve_company_profile_from_tws(symbol)
    company_name = company_profile.get("company_name")
    if not company_name:
        raise RuntimeError(f"Unable to resolve company name from TWS/IBKR for symbol {symbol}")

    conn = get_db_connection()
    try:
        templates, sources = get_all_prompt_templates(conn)
        scenario_settings = get_scenario_generation_config(conn)
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
                "company_name": {"type": "string"},
                "business_model": {"type": "string"},
                "business_summary": {"type": "string"},
            },
            "required": ["symbol", "company_name", "business_model", "business_summary"],
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

    logger.info("Starting AI step=business_model symbol=%s", symbol)
    prompt1 = build_analysis_prompt(
        symbol,
        effective_price,
        template=templates[ANALYSIS_PROMPT_SETTING_KEY_BUSINESS_MODEL],
        company_name=company_name,
    )
    step1_raw = request_ai_step("business_model", prompt1, schema_step1)
    step1 = validate_step1_business_model(step1_raw)

    logger.info("Starting AI step=key_variables symbol=%s", symbol)
    prompt2 = build_analysis_prompt(
        symbol,
        effective_price,
        template=templates[ANALYSIS_PROMPT_SETTING_KEY_KEY_VARIABLES],
        company_name=company_name,
        business_model=step1["business_model"],
        business_summary=step1["business_summary"],
    )
    step2_raw = request_ai_step("key_variables", prompt2, schema_step2)
    step2 = validate_step2_key_variables(step2_raw)

    logger.info("Starting AI step=scenarios symbol=%s", symbol)
    # Scenario prompt must be sourced strictly from saved scenario template +
    # placeholder substitution only. Do not append implicit summary/context text.
    prompt3 = build_scenario_generation_prompt(
        symbol,
        effective_price,
        template=templates[ANALYSIS_PROMPT_SETTING_KEY_SCENARIOS],
        company_name=company_name,
        business_model=step1["business_model"],
        business_summary=step1["business_summary"],
        key_variables=step2["key_variables"],
    )
    pass_count = scenario_settings["scenario_pass_count"] if scenario_settings["scenario_multi_pass_enabled"] else 1
    scenario_parsed, scenario_runs = generate_scenarios_multi_pass(
        symbol=symbol,
        key_variables=step2["key_variables"],
        prompt_text=prompt3,
        pass_count=pass_count,
        outlier_filter_enabled=scenario_settings["scenario_outlier_filter_enabled"],
    )
    parsed = validate_step3_scenarios(
        {
            "symbol": symbol,
            "assumptions": scenario_parsed["assumptions"],
            "scenarios": [
                {
                    "name": s["scenario_name"],
                    "price_low": s["price_low"],
                    "price_high": s["price_high"],
                    "cagr_low": s["cagr_low"],
                    "cagr_high": s["cagr_high"],
                    "probability": s["probability"],
                }
                for s in scenario_parsed["scenarios"]
            ],
        },
        symbol,
        step2["key_variables"],
    )

    conn = get_db_connection()
    try:
        probability_settings = get_scenario_probability_settings(conn)
    finally:
        conn.close()
    ai_probs = scenario_probabilities_from_scenarios(parsed["scenarios"])
    backend_probs = compute_backend_probabilities(
        step2["key_variables"],
        probability_settings["backend_base_max_probability"],
        probability_settings["backend_base_min_probability"],
    )
    probability_meta = choose_final_probabilities(ai_probs, backend_probs, probability_settings)
    parsed["scenarios"] = apply_final_probabilities_to_scenarios(
        parsed["scenarios"],
        probability_meta["final_scenario_probabilities"],
    )

    return {
        "effective_price": effective_price,
        "company_name": company_name,
        "company_profile": company_profile,
        "business_model": step1,
        "key_variables": step2["key_variables"],
        "parsed": parsed,
        "raw": {
            "step1": step1_raw,
            "step2": step2_raw,
            "step3_prompt": prompt3,
            "probability_meta": probability_meta,
            "step3_runs": [
                {
                    "pass_index": run["pass_index"],
                    "raw_response_text": run["raw_response_text"],
                    "parsed_json": run.get("parsed_json"),
                    "validation_status": run["validation_status"],
                    "rejection_reason": run.get("rejection_reason"),
                    "quality_score": run.get("quality_score"),
                    "is_outlier": run.get("is_outlier", False),
                    "created_at": run["created_at"],
                }
                for run in scenario_runs
            ],
        },
    }


def _build_scenarios_schema():
    return {
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


def compute_scenario_midpoints(scenarios):
    midpoint_by_name = {}
    for item in scenarios:
        midpoint_by_name[item["scenario_name"]] = (item["price_low"] + item["price_high"]) / 2.0
    return midpoint_by_name


def _normalize_probabilities(scenarios):
    total = sum(float(item["probability"]) for item in scenarios)
    if total <= 0:
        raise AnalysisValidationError("Scenario probabilities must sum to a positive value")
    normalized = []
    for item in scenarios:
        cloned = dict(item)
        cloned["probability"] = float(item["probability"]) / total
        normalized.append(cloned)
    return normalized


def validate_scenario_output(payload, symbol):
    """Validation pipeline specifically for scenario-generation pass outputs."""
    if not isinstance(payload, dict):
        return {"ok": False, "reason": "payload_not_json", "parsed": None}

    assumptions = payload.get("assumptions")
    if not isinstance(assumptions, str) or not assumptions.strip():
        return {"ok": False, "reason": "missing_assumptions", "parsed": None}

    scenarios = payload.get("scenarios")
    if not isinstance(scenarios, list) or len(scenarios) != 3:
        return {"ok": False, "reason": "invalid_scenarios_shape", "parsed": None}

    seen = set()
    normalized = []
    prob_sum_pct = 0.0
    for item in scenarios:
        if not isinstance(item, dict):
            return {"ok": False, "reason": "invalid_scenario_item", "parsed": None}

        name = item.get("name")
        if name not in {"Bear", "Base", "Bull"} or name in seen:
            return {"ok": False, "reason": "invalid_scenario_names", "parsed": None}

        try:
            price_low = float(item.get("price_low"))
            price_high = float(item.get("price_high"))
            cagr_low = float(item.get("cagr_low"))
            cagr_high = float(item.get("cagr_high"))
            probability = float(item.get("probability"))
        except (TypeError, ValueError):
            return {"ok": False, "reason": "invalid_numeric_field", "parsed": None}

        if not all(math.isfinite(v) for v in [price_low, price_high, cagr_low, cagr_high, probability]):
            return {"ok": False, "reason": "non_finite_numeric_field", "parsed": None}
        if price_low <= 0 or price_high <= 0:
            return {"ok": False, "reason": "non_positive_price", "parsed": None}
        if probability < 0 or probability > 100:
            return {"ok": False, "reason": "invalid_probability_range", "parsed": None}
        if price_low > price_high:
            return {"ok": False, "reason": "price_low_gt_price_high", "parsed": None}
        if cagr_low > cagr_high:
            return {"ok": False, "reason": "cagr_low_gt_cagr_high", "parsed": None}

        seen.add(name)
        prob_sum_pct += probability
        normalized.append(
            {
                "scenario_name": name,
                "price_low": price_low,
                "price_high": price_high,
                "cagr_low": cagr_low,
                "cagr_high": cagr_high,
                "probability": probability,
            }
        )

    if seen != {"Bear", "Base", "Bull"}:
        return {"ok": False, "reason": "missing_required_scenarios", "parsed": None}
    if prob_sum_pct < 90 or prob_sum_pct > 110:
        return {"ok": False, "reason": "probability_total_out_of_range", "parsed": None}

    normalized = sorted(normalized, key=lambda s: ["Bear", "Base", "Bull"].index(s["scenario_name"]))
    mids = compute_scenario_midpoints(normalized)
    if not (mids["Bear"] <= mids["Base"] <= mids["Bull"]):
        return {"ok": False, "reason": "scenario_midpoint_order_invalid", "parsed": None}

    parsed = {
        "symbol": symbol,
        "assumptions": assumptions.strip(),
        "scenarios": _normalize_probabilities(normalized),
    }
    return {"ok": True, "reason": None, "parsed": parsed}


def score_scenario_run(run, medians=None):
    score = 0.0
    if run.get("validation_status") == "valid":
        score += 5.0
    prob_sum = run.get("probability_total_pct")
    if prob_sum is not None:
        score += max(0.0, 2.0 - abs(prob_sum - 100.0) / 10.0)
    if medians and run.get("midpoints"):
        avg_dev = run.get("avg_relative_deviation")
        if avg_dev is not None:
            score += max(0.0, 2.0 - avg_dev * 5.0)
    if not run.get("is_outlier"):
        score += 1.0
    return score


def filter_outlier_runs(valid_runs, enabled=True):
    if not enabled or len(valid_runs) < 3:
        for run in valid_runs:
            run["is_outlier"] = False
            run["avg_relative_deviation"] = 0.0
        return valid_runs

    bear_medians = statistics.median([r["midpoints"]["Bear"] for r in valid_runs])
    base_medians = statistics.median([r["midpoints"]["Base"] for r in valid_runs])
    bull_medians = statistics.median([r["midpoints"]["Bull"] for r in valid_runs])

    retained = []
    for run in valid_runs:
        bear_dev = abs(run["midpoints"]["Bear"] - bear_medians) / max(abs(bear_medians), 1e-9)
        base_dev = abs(run["midpoints"]["Base"] - base_medians) / max(abs(base_medians), 1e-9)
        bull_dev = abs(run["midpoints"]["Bull"] - bull_medians) / max(abs(bull_medians), 1e-9)
        avg_dev = (bear_dev + base_dev + bull_dev) / 3.0
        run["avg_relative_deviation"] = avg_dev
        run["is_outlier"] = base_dev > SCENARIO_MAX_BASE_DEVIATION or avg_dev > SCENARIO_MAX_AVG_DEVIATION
        if not run["is_outlier"]:
            retained.append(run)

    return retained if retained else valid_runs


def aggregate_scenario_runs(runs, symbol):
    if not runs:
        raise AnalysisValidationError("No scenario runs available for aggregation")
    if len(runs) == 1:
        final = dict(runs[0]["parsed"])
        final["scenarios"] = _normalize_probabilities(final["scenarios"])
        return final

    final_scenarios = []
    for scenario_name in ["Bear", "Base", "Bull"]:
        scenario_values = []
        for run in runs:
            scenario = next(item for item in run["parsed"]["scenarios"] if item["scenario_name"] == scenario_name)
            scenario_values.append(scenario)

        final_scenarios.append(
            {
                "scenario_name": scenario_name,
                "price_low": statistics.median([v["price_low"] for v in scenario_values]),
                "price_high": statistics.median([v["price_high"] for v in scenario_values]),
                "cagr_low": statistics.median([v["cagr_low"] for v in scenario_values]),
                "cagr_high": statistics.median([v["cagr_high"] for v in scenario_values]),
                "probability": sum(v["probability"] for v in scenario_values) / len(scenario_values),
            }
        )

    final_scenarios = _normalize_probabilities(final_scenarios)
    best = max(runs, key=lambda r: r.get("quality_score", 0.0))
    return {
        "symbol": symbol,
        # Keep assumptions from highest-quality retained run.
        "assumptions": best["parsed"]["assumptions"],
        "scenarios": final_scenarios,
    }


def generate_scenarios_multi_pass(symbol, key_variables, prompt_text, pass_count, outlier_filter_enabled):
    runs = []
    for idx in range(pass_count):
        run = {
            "pass_index": idx + 1,
            "raw_response_text": None,
            "parsed_json": None,
            "validation_status": "rejected",
            "rejection_reason": None,
            "created_at": utc_now_iso(),
            "quality_score": 0.0,
            "is_outlier": False,
        }
        try:
            payload = request_ai_step(f"scenarios_pass_{idx + 1}", prompt_text, _build_scenarios_schema())
            run["raw_response_text"] = json.dumps(payload, ensure_ascii=False)
            run["parsed_json"] = payload
            validation = validate_scenario_output(payload, symbol)
            if validation["ok"]:
                run["validation_status"] = "valid"
                run["parsed"] = validation["parsed"]
                run["midpoints"] = compute_scenario_midpoints(validation["parsed"]["scenarios"])
                run["probability_total_pct"] = sum(s["probability"] for s in validation["parsed"]["scenarios"]) * 100.0
            else:
                run["rejection_reason"] = validation["reason"]
        except Exception as exc:
            run["rejection_reason"] = f"request_failed:{exc}"
        runs.append(run)

    valid_runs = [r for r in runs if r["validation_status"] == "valid"]
    retained_runs = filter_outlier_runs(valid_runs, enabled=outlier_filter_enabled)
    retained_ids = {id(r) for r in retained_runs}
    for run in runs:
        if run["validation_status"] == "valid" and id(run) not in retained_ids:
            run["is_outlier"] = True
            run["rejection_reason"] = "outlier"

    if not retained_runs:
        # Fallback: if there's at least one parsed run that can be normalized, keep first parsed one.
        partially_usable = [r for r in runs if isinstance(r.get("parsed_json"), dict)]
        if partially_usable:
            fallback = partially_usable[0]
            validation = validate_scenario_output(fallback["parsed_json"], symbol)
            if validation["ok"]:
                fallback["validation_status"] = "valid"
                fallback["parsed"] = validation["parsed"]
                fallback["midpoints"] = compute_scenario_midpoints(validation["parsed"]["scenarios"])
                retained_runs = [fallback]
            else:
                raise AnalysisValidationError("All scenario passes failed validation")
        else:
            raise AnalysisValidationError("All scenario passes failed validation")

    medians = {
        "Bear": statistics.median([r["midpoints"]["Bear"] for r in retained_runs]),
        "Base": statistics.median([r["midpoints"]["Base"] for r in retained_runs]),
        "Bull": statistics.median([r["midpoints"]["Bull"] for r in retained_runs]),
    }
    for run in runs:
        run["quality_score"] = score_scenario_run(run, medians=medians)

    aggregated = aggregate_scenario_runs(retained_runs, symbol=symbol)
    return aggregated, runs


def list_analysis_symbols(conn):
    rating_settings = get_rating_settings(conn)
    rows = conn.execute(
        """
        SELECT r.symbol, v.current_price, v.expected_price, v.upside, v.confidence_level AS overall_confidence,
               v.version_number AS analysis_version,
               COALESCE(
                   (
                       SELECT COUNT(*)
                       FROM analysis_version_scenario_passes sp
                       WHERE sp.analysis_version_id = v.id
                   ),
                   0
               ) AS scenario_pass_count,
               (
                   SELECT CASE WHEN SUM(kv.importance) > 0
                     THEN SUM(kv.confidence * kv.importance) / SUM(kv.importance)
                     ELSE NULL END
                   FROM analysis_version_key_variables kv
                   WHERE kv.analysis_version_id = v.id AND kv.variable_type = 'Bullish'
               ) AS bullish_confidence,
               (
                   SELECT CASE WHEN SUM(kv.importance) > 0
                     THEN SUM(kv.confidence * kv.importance) / SUM(kv.importance)
                     ELSE NULL END
                   FROM analysis_version_key_variables kv
                   WHERE kv.analysis_version_id = v.id AND kv.variable_type = 'Bearish'
               ) AS bearish_confidence,
               v.created_at AS updated_at
        FROM analysis_roots r
        JOIN analysis_versions v ON v.analysis_root_id = r.id
        WHERE v.id = (
            SELECT id FROM analysis_versions latest
            WHERE latest.analysis_root_id = r.id
            ORDER BY version_number DESC
            LIMIT 1
        )
        ORDER BY r.symbol ASC
        """
    ).fetchall()
    output = []
    for row in rows:
        item = dict(row)
        if (item.get("scenario_pass_count") or 0) <= 0:
            item["scenario_pass_count"] = 1
        rating, confidence_diff = calculate_rating(
            item.get("upside"),
            item.get("bullish_confidence"),
            item.get("bearish_confidence"),
            rating_settings,
        )
        item["confidence_diff"] = confidence_diff
        item["rating"] = rating
        output.append(item)
    return output


def refresh_latest_analysis_market_prices(conn):
    rows = conn.execute(
        """
        SELECT r.symbol, v.id AS version_id, v.expected_price
        FROM analysis_roots r
        JOIN analysis_versions v ON v.analysis_root_id = r.id
        WHERE v.id = (
            SELECT id FROM analysis_versions latest
            WHERE latest.analysis_root_id = r.id
            ORDER BY version_number DESC
            LIMIT 1
        )
        ORDER BY r.symbol ASC
        """
    ).fetchall()

    symbols = [row["symbol"] for row in rows]
    if not symbols:
        return {"updated": 0, "skipped": 0}

    prices, _warnings = fetch_ib_prices(symbols)
    now = utc_now_iso()
    updated = 0
    skipped = 0

    for row in rows:
        latest_price = prices.get(row["symbol"])
        if latest_price is None:
            skipped += 1
            continue
        new_upside = calculate_upside(row["expected_price"], latest_price)
        conn.execute(
            """
            UPDATE analysis_versions
            SET current_price = ?, upside = ?
            WHERE id = ?
            """,
            (latest_price, new_upside, row["version_id"]),
        )
        updated += 1

    if updated:
        conn.execute("UPDATE analysis_roots SET updated_at = ?", (now,))
    conn.commit()
    return {"updated": updated, "skipped": skipped}


def _normalize_manual_key_variables(raw_key_variables):
    if not isinstance(raw_key_variables, list) or not raw_key_variables:
        raise AnalysisValidationError("key_variables must be a non-empty array")

    normalized = []
    for index, item in enumerate(raw_key_variables):
        if not isinstance(item, dict):
            raise AnalysisValidationError(f"key_variables[{index}] must be an object")

        variable_text = (item.get("variable_text") or item.get("variable") or "").strip()
        if not variable_text:
            raise AnalysisValidationError(f"key_variables[{index}].variable_text is required")

        variable_type = item.get("variable_type") or item.get("type")
        if variable_type not in {"Bullish", "Bearish"}:
            raise AnalysisValidationError(f"key_variables[{index}].variable_type must be Bullish or Bearish")

        try:
            confidence = int(round(float(item.get("confidence"))))
            importance = int(round(float(item.get("importance"))))
        except (TypeError, ValueError):
            raise AnalysisValidationError(f"key_variables[{index}] confidence/importance must be numeric")

        if confidence < 0 or confidence > 10:
            raise AnalysisValidationError(f"key_variables[{index}].confidence must be in [0, 10]")
        if importance < 0 or importance > 10:
            raise AnalysisValidationError(f"key_variables[{index}].importance must be in [0, 10]")

        normalized.append(
            {
                "variable_text": variable_text,
                "variable_type": variable_type,
                "confidence": confidence,
                "importance": importance,
            }
        )

    return normalized


def _version_payload(conn, version_row):
    scenarios = conn.execute(
        """
        SELECT scenario_name, price_low, price_high, cagr_low, cagr_high, probability
        FROM analysis_version_scenarios
        WHERE analysis_version_id = ?
        ORDER BY CASE scenario_name WHEN 'Bear' THEN 1 WHEN 'Base' THEN 2 WHEN 'Bull' THEN 3 ELSE 99 END
        """,
        (version_row["id"],),
    ).fetchall()

    key_variables = conn.execute(
        """
        SELECT variable_text, variable_type, confidence, importance
        FROM analysis_version_key_variables
        WHERE analysis_version_id = ?
        ORDER BY id ASC
        """,
        (version_row["id"],),
    ).fetchall()

    scenario_passes = conn.execute(
        """
        SELECT pass_index, raw_response_text, parsed_json, validation_status,
               rejection_reason, quality_score, is_outlier, created_at
        FROM analysis_version_scenario_passes
        WHERE analysis_version_id = ?
        ORDER BY pass_index ASC
        """,
        (version_row["id"],),
    ).fetchall()

    bullish_confidence = calculate_overall_confidence(
        [item for item in [dict(v) for v in key_variables] if item["variable_type"] == "Bullish"]
    )
    bearish_confidence = calculate_overall_confidence(
        [item for item in [dict(v) for v in key_variables] if item["variable_type"] == "Bearish"]
    )

    raw_payload = {}
    try:
        raw_payload = json.loads(version_row["raw_ai_response"] or "{}")
    except Exception:
        raw_payload = {}

    prompt_text = raw_payload.get("step3_prompt")
    if not scenario_passes and isinstance(raw_payload.get("step3_runs"), list):
        scenario_passes = [
            {
                "pass_index": row.get("pass_index"),
                "raw_response_text": row.get("raw_response_text"),
                "parsed_json": json.dumps(row.get("parsed_json")) if isinstance(row.get("parsed_json"), (dict, list)) else row.get("parsed_json"),
                "validation_status": row.get("validation_status", "unknown"),
                "rejection_reason": row.get("rejection_reason"),
                "quality_score": row.get("quality_score"),
                "is_outlier": 1 if row.get("is_outlier") else 0,
                "created_at": row.get("created_at"),
            }
            for row in raw_payload.get("step3_runs", [])
        ]

    rating_settings = get_rating_settings(conn)
    rating, confidence_diff = calculate_rating(version_row["upside"], bullish_confidence, bearish_confidence, rating_settings)

    probability_meta = raw_payload.get("probability_meta") if isinstance(raw_payload.get("probability_meta"), dict) else {}

    return {
        "id": version_row["id"],
        "version_number": version_row["version_number"],
        "symbol": version_row["symbol"],
        "company_name": version_row["company_name"],
        "current_price": version_row["current_price"],
        "expected_price": version_row["expected_price"],
        "upside": version_row["upside"],
        "overall_confidence": version_row["confidence_level"],
        "bullish_confidence": bullish_confidence,
        "bearish_confidence": bearish_confidence,
        "confidence_diff": confidence_diff,
        "rating": rating,
        "assumptions": version_row["assumptions_text"],
        "business_model": version_row["business_model_text"],
        "business_summary": version_row["business_summary_text"],
        "created_at": version_row["created_at"],
        "source_trigger": version_row["source_trigger"],
        "scenario_prompt": prompt_text,
        "ai_scenario_probabilities": probability_meta.get("ai_scenario_probabilities"),
        "backend_scenario_probabilities": probability_meta.get("backend_scenario_probabilities"),
        "final_scenario_probabilities": probability_meta.get("final_scenario_probabilities"),
        "probability_source_mode_used": probability_meta.get("probability_source_mode_used"),
        "scenarios": [dict(s) for s in scenarios],
        "key_variables": [dict(v) for v in key_variables],
        "scenario_passes": [
            {
                "pass_index": row["pass_index"],
                "raw_response_text": row["raw_response_text"],
                "parsed_json": json.loads(row["parsed_json"]) if row["parsed_json"] else None,
                "validation_status": row["validation_status"],
                "rejection_reason": row["rejection_reason"],
                "quality_score": row["quality_score"],
                "is_outlier": bool(row["is_outlier"]),
                "created_at": row["created_at"],
            }
            for row in scenario_passes
        ],
    }


def _get_saved_business_model_edit(conn, root_id):
    draft = conn.execute(
        "SELECT based_on_version_id, business_model_text, updated_at FROM analysis_business_model_edits WHERE analysis_root_id = ?",
        (root_id,),
    ).fetchone()
    if not draft:
        return None
    return {
        "based_on_version_id": draft["based_on_version_id"],
        "business_model": draft["business_model_text"],
        "updated_at": draft["updated_at"],
    }


def _get_saved_business_summary_edit(conn, root_id):
    draft = conn.execute(
        "SELECT based_on_version_id, business_summary_text, updated_at FROM analysis_business_summary_edits WHERE analysis_root_id = ?",
        (root_id,),
    ).fetchone()
    if not draft:
        return None
    return {
        "based_on_version_id": draft["based_on_version_id"],
        "business_summary": draft["business_summary_text"],
        "updated_at": draft["updated_at"],
    }


def get_analysis_detail(conn, symbol, version_id=None):
    root = conn.execute("SELECT id, symbol FROM analysis_roots WHERE symbol = ?", (symbol,)).fetchone()
    if not root:
        return None

    versions = conn.execute(
        """
        SELECT id, version_number, created_at, source_trigger
        FROM analysis_versions
        WHERE analysis_root_id = ?
        ORDER BY version_number ASC
        """,
        (root["id"],),
    ).fetchall()
    if not versions:
        return None

    selected_id = int(version_id) if version_id is not None else versions[-1]["id"]
    selected = conn.execute(
        "SELECT * FROM analysis_versions WHERE id = ? AND analysis_root_id = ?",
        (selected_id, root["id"]),
    ).fetchone()
    if not selected:
        selected = conn.execute(
            "SELECT * FROM analysis_versions WHERE analysis_root_id = ? ORDER BY version_number DESC LIMIT 1",
            (root["id"],),
        ).fetchone()

    draft = conn.execute(
        "SELECT based_on_version_id, key_variables_json, updated_at FROM analysis_key_variable_edits WHERE analysis_root_id = ?",
        (root["id"],),
    ).fetchone()

    return {
        "symbol": root["symbol"],
        "root_id": root["id"],
        "selected_version_id": selected["id"],
        "versions": [dict(v) for v in versions],
        "version": _version_payload(conn, selected),
        "saved_key_variable_edits": {
            "based_on_version_id": draft["based_on_version_id"],
            "updated_at": draft["updated_at"],
            "key_variables": json.loads(draft["key_variables_json"]),
        } if draft else None,
        "saved_business_model_edit": _get_saved_business_model_edit(conn, root["id"]),
        "saved_business_summary_edit": _get_saved_business_summary_edit(conn, root["id"]),
    }


def _insert_analysis_version(
    conn,
    root_id,
    symbol,
    company_name,
    current_price,
    business_model,
    business_summary,
    assumptions,
    scenarios,
    key_variables,
    raw_ai_response,
    source_trigger,
    scenario_passes=None,
):
    latest = conn.execute(
        "SELECT COALESCE(MAX(version_number), 0) AS latest FROM analysis_versions WHERE analysis_root_id = ?",
        (root_id,),
    ).fetchone()["latest"]
    version_number = latest + 1
    now = utc_now_iso()

    expected_price = calculate_expected_price(scenarios)
    upside = calculate_upside(expected_price, current_price)
    confidence = calculate_overall_confidence(key_variables)

    conn.execute(
        """
        INSERT INTO analysis_versions (
            analysis_root_id, version_number, symbol, company_name, current_price, expected_price,
            upside, confidence_level, assumptions_text, business_model_text, business_summary_text,
            raw_ai_response, source_trigger, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            root_id,
            version_number,
            symbol,
            company_name,
            current_price,
            expected_price,
            upside,
            confidence,
            assumptions,
            business_model,
            business_summary,
            raw_ai_response,
            source_trigger,
            now,
        ),
    )
    version_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]

    for scenario in scenarios:
        conn.execute(
            """
            INSERT INTO analysis_version_scenarios (
                analysis_version_id, scenario_name, price_low, price_high, cagr_low,
                cagr_high, probability, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                version_id,
                scenario["scenario_name"],
                scenario["price_low"],
                scenario["price_high"],
                scenario["cagr_low"],
                scenario["cagr_high"],
                scenario["probability"],
                now,
            ),
        )

    for variable in key_variables:
        conn.execute(
            """
            INSERT INTO analysis_version_key_variables (
                analysis_version_id, variable_text, variable_type, confidence, importance, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                version_id,
                variable["variable_text"],
                variable["variable_type"],
                variable["confidence"],
                variable["importance"],
                now,
            ),
        )

    for scenario_pass in scenario_passes or []:
        conn.execute(
            """
            INSERT INTO analysis_version_scenario_passes (
                analysis_version_id, pass_index, raw_response_text, parsed_json,
                validation_status, rejection_reason, quality_score, is_outlier, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                version_id,
                scenario_pass.get("pass_index"),
                scenario_pass.get("raw_response_text"),
                json.dumps(scenario_pass.get("parsed_json")) if scenario_pass.get("parsed_json") is not None else None,
                scenario_pass.get("validation_status", "unknown"),
                scenario_pass.get("rejection_reason"),
                scenario_pass.get("quality_score"),
                1 if scenario_pass.get("is_outlier") else 0,
                scenario_pass.get("created_at", now),
            ),
        )

    conn.execute(
        "UPDATE analysis_roots SET updated_at = ? WHERE id = ?",
        (now, root_id),
    )
    return version_id


def upsert_analysis(conn, symbol, current_price=None):
    ai_result = request_ai_analysis(symbol, current_price=current_price)
    parsed = ai_result["parsed"]

    if parsed["symbol"] != symbol:
        parsed["symbol"] = symbol

    now = utc_now_iso()
    conn.execute("BEGIN")
    try:
        conn.execute(
            """
            INSERT INTO analysis_roots (symbol, created_at, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(symbol) DO NOTHING
            """,
            (symbol, now, now),
        )
        root_id = conn.execute("SELECT id FROM analysis_roots WHERE symbol = ?", (symbol,)).fetchone()["id"]

        _insert_analysis_version(
            conn=conn,
            root_id=root_id,
            symbol=symbol,
            company_name=ai_result["company_name"],
            current_price=ai_result["effective_price"],
            business_model=ai_result["business_model"]["business_model"],
            business_summary=ai_result["business_model"]["business_summary"],
            assumptions=parsed["assumptions"],
            scenarios=parsed["scenarios"],
            key_variables=parsed["key_variables"],
            raw_ai_response=json.dumps(ai_result["raw"]),
            source_trigger="initial_generation",
            scenario_passes=ai_result["raw"].get("step3_runs", []),
        )

        conn.execute("DELETE FROM analysis_key_variable_edits WHERE analysis_root_id = ?", (root_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    return get_analysis_detail(conn, symbol)


def save_key_variable_edits(conn, symbol, version_id, key_variables):
    normalized = _normalize_manual_key_variables(key_variables)
    root = conn.execute("SELECT id FROM analysis_roots WHERE symbol = ?", (symbol,)).fetchone()
    if not root:
        raise ValueError("Analysis symbol not found")

    base = conn.execute(
        "SELECT id FROM analysis_versions WHERE id = ? AND analysis_root_id = ?",
        (version_id, root["id"]),
    ).fetchone()
    if not base:
        raise ValueError("Base version not found")

    now = utc_now_iso()
    conn.execute(
        """
        INSERT INTO analysis_key_variable_edits (analysis_root_id, based_on_version_id, key_variables_json, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(analysis_root_id) DO UPDATE SET
          based_on_version_id = excluded.based_on_version_id,
          key_variables_json = excluded.key_variables_json,
          updated_at = excluded.updated_at
        """,
        (root["id"], version_id, json.dumps(normalized), now),
    )
    conn.commit()
    return get_analysis_detail(conn, symbol, version_id=version_id)


def save_business_model_edit(conn, symbol, version_id, business_model):
    if not isinstance(business_model, str) or not business_model.strip():
        raise AnalysisValidationError("business_model is required")

    root = conn.execute("SELECT id FROM analysis_roots WHERE symbol = ?", (symbol,)).fetchone()
    if not root:
        raise ValueError("Analysis symbol not found")

    base = conn.execute(
        "SELECT id FROM analysis_versions WHERE id = ? AND analysis_root_id = ?",
        (version_id, root["id"]),
    ).fetchone()
    if not base:
        raise ValueError("Base version not found")

    now = utc_now_iso()
    conn.execute(
        """
        INSERT INTO analysis_business_model_edits (analysis_root_id, based_on_version_id, business_model_text, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(analysis_root_id) DO UPDATE SET
          based_on_version_id = excluded.based_on_version_id,
          business_model_text = excluded.business_model_text,
          updated_at = excluded.updated_at
        """,
        (root["id"], version_id, business_model.strip(), now),
    )
    conn.commit()
    return get_analysis_detail(conn, symbol, version_id=version_id)


def save_business_summary_edit(conn, symbol, version_id, business_summary):
    if not isinstance(business_summary, str):
        raise AnalysisValidationError("business_summary must be a string")

    root = conn.execute("SELECT id FROM analysis_roots WHERE symbol = ?", (symbol,)).fetchone()
    if not root:
        raise ValueError("Analysis symbol not found")

    base = conn.execute(
        "SELECT id FROM analysis_versions WHERE id = ? AND analysis_root_id = ?",
        (version_id, root["id"]),
    ).fetchone()
    if not base:
        raise ValueError("Base version not found")

    now = utc_now_iso()
    conn.execute(
        """
        INSERT INTO analysis_business_summary_edits (analysis_root_id, based_on_version_id, business_summary_text, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(analysis_root_id) DO UPDATE SET
          based_on_version_id = excluded.based_on_version_id,
          business_summary_text = excluded.business_summary_text,
          updated_at = excluded.updated_at
        """,
        (root["id"], version_id, business_summary.strip(), now),
    )
    conn.commit()
    return get_analysis_detail(conn, symbol, version_id=version_id)


def rerun_scenarios_from_saved_edits(conn, symbol, base_version_id):
    root = conn.execute("SELECT id FROM analysis_roots WHERE symbol = ?", (symbol,)).fetchone()
    if not root:
        raise ValueError("Analysis symbol not found")

    draft = conn.execute(
        "SELECT based_on_version_id, key_variables_json FROM analysis_key_variable_edits WHERE analysis_root_id = ?",
        (root["id"],),
    ).fetchone()
    if not draft:
        raise ValueError("No saved key variable edits found")
    if int(draft["based_on_version_id"]) != int(base_version_id):
        raise ValueError("Saved key variable edits must match the selected version")

    base_version = conn.execute(
        "SELECT * FROM analysis_versions WHERE id = ? AND analysis_root_id = ?",
        (base_version_id, root["id"]),
    ).fetchone()
    if not base_version:
        raise ValueError("Base version not found")

    key_variables = json.loads(draft["key_variables_json"])

    templates, _sources = get_all_prompt_templates(conn)
    scenario_settings = get_scenario_generation_config(conn)
    business_model_draft = _get_saved_business_model_edit(conn, root["id"])
    business_summary_draft = _get_saved_business_summary_edit(conn, root["id"])
    effective_business_model = base_version["business_model_text"]
    effective_business_summary = base_version["business_summary_text"]
    if business_model_draft and int(business_model_draft["based_on_version_id"]) == int(base_version_id):
        effective_business_model = business_model_draft["business_model"]
    if business_summary_draft and int(business_summary_draft["based_on_version_id"]) == int(base_version_id):
        effective_business_summary = business_summary_draft["business_summary"]
    prompt = build_scenario_generation_prompt(
        symbol,
        base_version["current_price"],
        template=templates[ANALYSIS_PROMPT_SETTING_KEY_SCENARIOS],
        company_name=base_version["company_name"] or "",
        business_model=effective_business_model or "",
        business_summary=effective_business_summary or "",
        key_variables=key_variables,
    )
    pass_count = scenario_settings["scenario_pass_count"] if scenario_settings["scenario_multi_pass_enabled"] else 1
    scenario_parsed, scenario_runs = generate_scenarios_multi_pass(
        symbol=symbol,
        key_variables=key_variables,
        prompt_text=prompt,
        pass_count=pass_count,
        outlier_filter_enabled=scenario_settings["scenario_outlier_filter_enabled"],
    )
    parsed = validate_step3_scenarios(
        {
            "symbol": symbol,
            "assumptions": scenario_parsed["assumptions"],
            "scenarios": [
                {
                    "name": s["scenario_name"],
                    "price_low": s["price_low"],
                    "price_high": s["price_high"],
                    "cagr_low": s["cagr_low"],
                    "cagr_high": s["cagr_high"],
                    "probability": s["probability"],
                }
                for s in scenario_parsed["scenarios"]
            ],
        },
        symbol,
        key_variables,
    )

    probability_settings = get_scenario_probability_settings(conn)
    ai_probs = scenario_probabilities_from_scenarios(parsed["scenarios"])
    backend_probs = compute_backend_probabilities(
        key_variables,
        probability_settings["backend_base_max_probability"],
        probability_settings["backend_base_min_probability"],
    )
    probability_meta = choose_final_probabilities(ai_probs, backend_probs, probability_settings)
    parsed["scenarios"] = apply_final_probabilities_to_scenarios(
        parsed["scenarios"],
        probability_meta["final_scenario_probabilities"],
    )

    conn.execute("BEGIN")
    try:
        new_version_id = _insert_analysis_version(
            conn=conn,
            root_id=root["id"],
            symbol=symbol,
            company_name=base_version["company_name"],
            current_price=base_version["current_price"],
            business_model=effective_business_model,
            business_summary=effective_business_summary,
            assumptions=parsed["assumptions"],
            scenarios=parsed["scenarios"],
            key_variables=key_variables,
            raw_ai_response=json.dumps({"step3_prompt": prompt, "probability_meta": probability_meta, "step3_runs": scenario_runs}),
            source_trigger="rerun_from_key_variable_edit",
            scenario_passes=scenario_runs,
        )
        conn.execute("DELETE FROM analysis_key_variable_edits WHERE analysis_root_id = ?", (root["id"],))
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    return get_analysis_detail(conn, symbol, version_id=new_version_id)


def rerun_scenarios_from_existing_version(conn, symbol, base_version_id):
    root = conn.execute("SELECT id FROM analysis_roots WHERE symbol = ?", (symbol,)).fetchone()
    if not root:
        raise ValueError("Analysis symbol not found")

    base_version = conn.execute(
        "SELECT * FROM analysis_versions WHERE id = ? AND analysis_root_id = ?",
        (base_version_id, root["id"]),
    ).fetchone()
    if not base_version:
        raise ValueError("Base version not found")

    key_variables = [
        dict(row)
        for row in conn.execute(
            """
            SELECT variable_text, variable_type, confidence, importance
            FROM analysis_version_key_variables
            WHERE analysis_version_id = ?
            ORDER BY id ASC
            """,
            (base_version_id,),
        ).fetchall()
    ]
    if not key_variables:
        raise ValueError("No key variables found for base version")

    templates, _sources = get_all_prompt_templates(conn)
    scenario_settings = get_scenario_generation_config(conn)
    business_model_draft = _get_saved_business_model_edit(conn, root["id"])
    business_summary_draft = _get_saved_business_summary_edit(conn, root["id"])
    effective_business_model = base_version["business_model_text"]
    effective_business_summary = base_version["business_summary_text"]
    if business_model_draft and int(business_model_draft["based_on_version_id"]) == int(base_version_id):
        effective_business_model = business_model_draft["business_model"]
    if business_summary_draft and int(business_summary_draft["based_on_version_id"]) == int(base_version_id):
        effective_business_summary = business_summary_draft["business_summary"]
    prompt = build_scenario_generation_prompt(
        symbol,
        base_version["current_price"],
        template=templates[ANALYSIS_PROMPT_SETTING_KEY_SCENARIOS],
        company_name=base_version["company_name"] or "",
        business_model=effective_business_model or "",
        business_summary=effective_business_summary or "",
        key_variables=key_variables,
    )
    pass_count = scenario_settings["scenario_pass_count"] if scenario_settings["scenario_multi_pass_enabled"] else 1
    scenario_parsed, scenario_runs = generate_scenarios_multi_pass(
        symbol=symbol,
        key_variables=key_variables,
        prompt_text=prompt,
        pass_count=pass_count,
        outlier_filter_enabled=scenario_settings["scenario_outlier_filter_enabled"],
    )
    parsed = validate_step3_scenarios(
        {
            "symbol": symbol,
            "assumptions": scenario_parsed["assumptions"],
            "scenarios": [
                {
                    "name": s["scenario_name"],
                    "price_low": s["price_low"],
                    "price_high": s["price_high"],
                    "cagr_low": s["cagr_low"],
                    "cagr_high": s["cagr_high"],
                    "probability": s["probability"],
                }
                for s in scenario_parsed["scenarios"]
            ],
        },
        symbol,
        key_variables,
    )

    probability_settings = get_scenario_probability_settings(conn)
    ai_probs = scenario_probabilities_from_scenarios(parsed["scenarios"])
    backend_probs = compute_backend_probabilities(
        key_variables,
        probability_settings["backend_base_max_probability"],
        probability_settings["backend_base_min_probability"],
    )
    probability_meta = choose_final_probabilities(ai_probs, backend_probs, probability_settings)
    parsed["scenarios"] = apply_final_probabilities_to_scenarios(
        parsed["scenarios"],
        probability_meta["final_scenario_probabilities"],
    )

    conn.execute("BEGIN")
    try:
        new_version_id = _insert_analysis_version(
            conn=conn,
            root_id=root["id"],
            symbol=symbol,
            company_name=base_version["company_name"],
            current_price=base_version["current_price"],
            business_model=effective_business_model,
            business_summary=effective_business_summary,
            assumptions=parsed["assumptions"],
            scenarios=parsed["scenarios"],
            key_variables=key_variables,
            raw_ai_response=json.dumps({"step3_prompt": prompt, "probability_meta": probability_meta, "step3_runs": scenario_runs}),
            source_trigger="rerun_from_analysis_list",
            scenario_passes=scenario_runs,
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    return get_analysis_detail(conn, symbol, version_id=new_version_id)



def get_positions_with_prices():
    ensure_event_loop()
    ib = get_ib_connection()
    positions = ib.positions()
    symbols = sorted({normalize_symbol(p.contract.symbol) for p in positions if p.contract})
    symbols = [s for s in symbols if s]
    prices, _warnings = fetch_ib_prices(symbols)
    return symbols, prices


def merge_positions_with_latest_analysis(positions, analysis_items):
    analysis_by_symbol = {
        normalize_symbol(item.get("symbol")): item
        for item in (analysis_items or [])
        if normalize_symbol(item.get("symbol"))
    }
    merged = []
    for position in positions:
        symbol = normalize_symbol(position.get("symbol"))
        analysis = analysis_by_symbol.get(symbol)
        row = dict(position)
        row["rating"] = analysis.get("rating") if analysis else None
        row["upside"] = analysis.get("upside") if analysis else None
        row["bullish_confidence"] = analysis.get("bullish_confidence") if analysis else None
        row["bearish_confidence"] = analysis.get("bearish_confidence") if analysis else None
        row["confidence_diff"] = analysis.get("confidence_diff") if analysis else None
        merged.append(row)

    with_rating = sum(1 for row in merged if row.get("rating"))
    with_upside = sum(1 for row in merged if isinstance(row.get("upside"), (int, float)))
    with_confidence = sum(1 for row in merged if isinstance(row.get("confidence_diff"), (int, float)))
    logger.info(
        "Positions/analysis merge summary positions=%s analysis_rows=%s with_rating=%s with_upside=%s with_confidence=%s",
        len(positions or []),
        len(analysis_items or []),
        with_rating,
        with_upside,
        with_confidence,
    )
    return merged


def save_positions_cache(conn, positions):
    now = utc_now_iso()
    for row in positions or []:
        symbol = normalize_symbol(row.get("symbol"))
        if not symbol:
            continue
        conn.execute(
            """
            INSERT INTO positions_cache (
              symbol, position, price, avg_cost, change_percent,
              market_value, unrealized_pnl, daily_pnl, currency, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol) DO UPDATE SET
              position = excluded.position,
              price = excluded.price,
              avg_cost = excluded.avg_cost,
              change_percent = excluded.change_percent,
              market_value = excluded.market_value,
              unrealized_pnl = excluded.unrealized_pnl,
              daily_pnl = excluded.daily_pnl,
              currency = excluded.currency,
              updated_at = excluded.updated_at
            """,
            (
                symbol,
                row.get("position"),
                row.get("price"),
                row.get("avgCost"),
                row.get("changePercent"),
                row.get("marketValue"),
                row.get("unrealizedPnL"),
                row.get("dailyPnL"),
                row.get("currency"),
                now,
            ),
        )
    conn.commit()


def load_positions_cache(conn):
    rows = conn.execute(
        """
        SELECT symbol, position, price, avg_cost, change_percent,
               market_value, unrealized_pnl, daily_pnl, currency
        FROM positions_cache
        ORDER BY symbol ASC
        """
    ).fetchall()
    return [
        {
            "symbol": row["symbol"],
            "position": row["position"],
            "price": row["price"],
            "avgCost": row["avg_cost"],
            "changePercent": row["change_percent"],
            "marketValue": row["market_value"],
            "unrealizedPnL": row["unrealized_pnl"],
            "dailyPnL": row["daily_pnl"],
            "currency": row["currency"],
        }
        for row in rows
    ]


def build_positions_payload(conn, positions, data_source, warning=None):
    normalized_positions = []
    for row in positions or []:
        normalized_row = dict(row)
        normalized_row["unrealizedPnLPercent"] = compute_unrealized_pnl_percent(normalized_row)
        normalized_positions.append(normalized_row)

    analysis_items = list_analysis_symbols(conn)
    payload = {
        "positions": merge_positions_with_latest_analysis(normalized_positions, analysis_items),
        "data_source": data_source,
    }
    if warning:
        payload["warning"] = warning
    return payload


def get_latest_analysis_context(conn, symbol):
    row = conn.execute(
        """
        SELECT r.id AS analysis_root_id,
               v.id AS analysis_version_id,
               v.symbol,
               v.company_name,
               v.current_price,
               v.business_model_text,
               v.business_summary_text
        FROM analysis_roots r
        JOIN analysis_versions v ON v.analysis_root_id = r.id
        WHERE r.symbol = ?
        ORDER BY v.version_number DESC
        LIMIT 1
        """,
        (symbol,),
    ).fetchone()
    if not row:
        raise ValueError(f"Analysis for symbol {symbol} not found")

    key_variables = conn.execute(
        """
        SELECT variable_text, variable_type, confidence, importance
        FROM analysis_version_key_variables
        WHERE analysis_version_id = ?
        ORDER BY id ASC
        """,
        (row["analysis_version_id"],),
    ).fetchall()
    return {
        "symbol": row["symbol"],
        "company_name": row["company_name"] or row["symbol"],
        "current_price": row["current_price"],
        "business_model": row["business_model_text"] or "",
        "business_summary": row["business_summary_text"] or "",
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


def _normalize_recent_event_alert(item):
    if not isinstance(item, dict):
        return None
    alert_type = str(item.get("alert_type", "")).strip()
    event_summary = str(item.get("event_summary", "")).strip()
    impact_summary = str(item.get("impact_summary", "")).strip()
    if alert_type not in ALLOWED_ALERT_TYPES or not event_summary or not impact_summary:
        return None
    affected_variables = item.get("affected_variables")
    if isinstance(affected_variables, list):
        affected_variables = [str(value).strip() for value in affected_variables if str(value).strip()]
    else:
        affected_variables = []
    return {
        "alert_type": alert_type,
        "event_summary": event_summary,
        "impact_summary": impact_summary,
        "affected_variables": affected_variables,
        "suggested_action": str(item.get("suggested_action", "")).strip(),
    }


def insert_recent_event_alert(conn, context, alert, prompt_used, raw_response):
    now = utc_now_iso()
    # Deterministic V1 dedupe: keep exactly one alert per
    # (symbol, alert_type, event_summary, impact_summary), regardless of status.
    try:
        conn.execute(
            """
            INSERT INTO thesis_review_alerts (
              symbol, company_name, alert_type, status, event_date, event_summary,
              impact_summary, affected_variables_json, suggested_action,
              prompt_used, raw_response_json, created_at, updated_at
            ) VALUES (?, ?, ?, 'New', ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                context["symbol"],
                context["company_name"],
                alert["alert_type"],
                alert.get("event_date"),
                alert["event_summary"],
                alert["impact_summary"],
                json.dumps(alert["affected_variables"], ensure_ascii=False),
                alert["suggested_action"],
                prompt_used,
                json.dumps(raw_response, ensure_ascii=False),
                now,
                now,
            ),
        )
        return True
    except sqlite3.IntegrityError:
        return False


def run_recent_event_check(conn, symbols):
    templates, _sources = get_all_prompt_templates(conn)
    template = templates[ANALYSIS_PROMPT_SETTING_KEY_RECENT_EVENT_CHECK]
    schema = {
        "name": "analysis_recent_events",
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "symbol": {"type": "string"},
                "alerts": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "alert_type": {"type": "string"},
                            "event_summary": {"type": "string"},
                            "impact_summary": {"type": "string"},
                            "affected_variables": {"type": "array", "items": {"type": "string"}},
                            "suggested_action": {"type": "string"},
                        },
                        "required": ["alert_type", "event_summary", "impact_summary", "affected_variables", "suggested_action"],
                    },
                },
            },
            "required": ["symbol", "alerts"],
        },
    }

    summary = {
        "symbols_checked": 0,
        "alerts_created": 0,
        "no_material_impact_count": 0,
        "errors_count": 0,
        "errors": [],
    }

    for symbol in symbols:
        summary["symbols_checked"] += 1
        try:
            context = get_latest_analysis_context(conn, symbol)
            prompt = render_recent_event_prompt(
                template,
                build_prompt_context(
                    symbol=context["symbol"],
                    price=context["current_price"],
                    company_name=context["company_name"],
                    business_model=context["business_model"],
                    business_summary=context["business_summary"],
                    key_variables=context["key_variables"],
                ),
            )
            response = request_ai_step("recent_event_check", prompt, schema)
            alerts = response.get("alerts") if isinstance(response, dict) else None
            if not isinstance(alerts, list) or not alerts:
                summary["no_material_impact_count"] += 1
                continue

            valid_alert_count = 0
            for raw_alert in alerts:
                normalized = _normalize_recent_event_alert(raw_alert)
                if not normalized:
                    continue
                created = insert_recent_event_alert(conn, context, normalized, prompt, response)
                if created:
                    summary["alerts_created"] += 1
                valid_alert_count += 1

            if valid_alert_count == 0:
                summary["no_material_impact_count"] += 1
        except Exception as exc:
            summary["errors_count"] += 1
            summary["errors"].append({"symbol": symbol, "error": str(exc)})
            logger.exception("Recent-event check failed for %s", symbol)
    conn.commit()
    return summary


def get_alerts(conn):
    rows = conn.execute(
        """
        SELECT id, symbol, company_name, alert_type, status, event_date, event_summary,
               impact_summary, affected_variables_json, suggested_action, created_at, updated_at
        FROM thesis_review_alerts
        ORDER BY datetime(created_at) DESC, id DESC
        """
    ).fetchall()
    alerts = []
    for row in rows:
        affected = []
        try:
            parsed = json.loads(row["affected_variables_json"] or "[]")
            if isinstance(parsed, list):
                affected = parsed
        except Exception:
            affected = []
        alerts.append(
            {
                "id": row["id"],
                "symbol": row["symbol"],
                "company_name": row["company_name"],
                "alert_type": row["alert_type"],
                "status": row["status"],
                "event_date": row["event_date"],
                "event_summary": row["event_summary"],
                "impact_summary": row["impact_summary"],
                "affected_variables": affected,
                "suggested_action": row["suggested_action"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        )
    return alerts


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
            version_id = None
            if parsed_url.query:
                params = dict(item.split("=", 1) for item in parsed_url.query.split("&") if "=" in item)
                version_id = params.get("version_id")
            return self.handle_analysis_detail_get(symbol, version_id=version_id)
        if path == "/api/configuration/prompts":
            return self.handle_configuration_prompts_get()
        if path == "/api/configuration/general":
            return self.handle_configuration_general_get()
        if path == "/api/alerts":
            return self.handle_alerts_get()

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
        if path == "/api/analysis/rerun-scenarios":
            return self.handle_analysis_rerun_scenarios_batch()
        if path == "/api/analysis/refresh-prices":
            return self.handle_analysis_refresh_prices()
        if path.startswith("/api/analysis/") and path.endswith("/key-variables"):
            symbol = normalize_symbol(path[len("/api/analysis/") : -len("/key-variables")])
            if not symbol:
                return self._send_json({"error": "Invalid symbol"}, status=400)
            return self.handle_analysis_key_variables_save(symbol)
        if path.startswith("/api/analysis/") and path.endswith("/business-model"):
            symbol = normalize_symbol(path[len("/api/analysis/") : -len("/business-model")])
            if not symbol:
                return self._send_json({"error": "Invalid symbol"}, status=400)
            return self.handle_analysis_business_model_save(symbol)
        if path.startswith("/api/analysis/") and path.endswith("/business-summary"):
            symbol = normalize_symbol(path[len("/api/analysis/") : -len("/business-summary")])
            if not symbol:
                return self._send_json({"error": "Invalid symbol"}, status=400)
            return self.handle_analysis_business_summary_save(symbol)
        if path.startswith("/api/analysis/") and path.endswith("/rerun-scenarios"):
            symbol = normalize_symbol(path[len("/api/analysis/") : -len("/rerun-scenarios")])
            if not symbol:
                return self._send_json({"error": "Invalid symbol"}, status=400)
            return self.handle_analysis_rerun_scenarios(symbol)
        if path == "/api/analysis/import-from-positions":
            return self.handle_analysis_import_positions()
        if path == "/api/configuration/prompts/preview":
            return self.handle_configuration_prompts_preview()
        if path == "/api/configuration/prompts/reset":
            return self.handle_configuration_prompts_reset()
        if path == "/api/alerts/check-recent-events":
            return self.handle_alerts_check_recent_events()

        self.send_error(404, "Not Found")

    def do_PUT(self):
        path = urlparse(self.path).path
        if path == "/api/configuration/prompts":
            return self.handle_configuration_prompts_put()
        if path == "/api/configuration/general":
            return self.handle_configuration_general_put()
        if path.startswith("/api/alerts/") and path.endswith("/status"):
            alert_id = path[len("/api/alerts/") : -len("/status")]
            return self.handle_alerts_status_put(alert_id)

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
            logger.info("Positions API using live IBKR path positions_count=%s", len(positions))
            contracts = [p.contract for p in positions if p.contract]
            tickers_by_conid = {}

            if contracts:
                qualified = ib.qualifyContracts(*contracts)
                if qualified:
                    tickers = ib.reqTickers(*qualified)
                    ib.sleep(get_ib_price_wait_seconds())
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
                        "symbol": normalize_symbol(contract.symbol),
                        "position": qty,
                        "price": price,
                        "avgCost": avg_cost,
                        "changePercent": change_percent,
                        "marketValue": market_value,
                        "unrealizedPnL": unrealized_pnl,
                        "unrealizedPnLPercent": (
                            (unrealized_pnl / abs(avg_cost * qty)) * 100
                            if unrealized_pnl is not None and avg_cost is not None and qty not in (None, 0) and (avg_cost * qty) != 0
                            else None
                        ),
                        "dailyPnL": daily_pnl,
                        "currency": getattr(contract, "currency", None),
                    }
                )

            conn = get_db_connection()
            try:
                save_positions_cache(conn, data)
                payload = build_positions_payload(conn, data, data_source="live")
                logger.info(
                    "Positions API returning live rows=%s sample_symbols=%s",
                    len(payload["positions"]),
                    [item.get("symbol") for item in payload["positions"][:5]],
                )
                self._send_json(payload)
            finally:
                conn.close()
        except Exception as exc:
            logger.warning("Positions API live path unavailable; client may use cached fallback (%s)", exc)
            conn = get_db_connection()
            try:
                cached_positions = load_positions_cache(conn)
                if cached_positions:
                    payload = build_positions_payload(
                        conn,
                        cached_positions,
                        data_source="cached",
                        warning="TWS offline — showing saved positions.",
                    )
                    logger.info(
                        "Positions API returning cached rows=%s sample_symbols=%s",
                        len(payload["positions"]),
                        [item.get("symbol") for item in payload["positions"][:5]],
                    )
                    self._send_json(payload)
                else:
                    self._send_json(
                        {
                            "positions": [],
                            "data_source": "empty",
                            "warning": "TWS offline and no saved positions available.",
                            "details": str(exc),
                        }
                    )
            finally:
                conn.close()

    def handle_analysis_get(self):
        conn = get_db_connection()
        try:
            refresh_latest_analysis_market_prices(conn)
            self._send_json({"analysis": list_analysis_symbols(conn)})
        except Exception as exc:
            self._send_json(
                {"error": "Unable to fetch analysis list.", "details": str(exc)},
                status=500,
            )
        finally:
            conn.close()

    def handle_analysis_refresh_prices(self):
        conn = get_db_connection()
        try:
            result = refresh_latest_analysis_market_prices(conn)
            self._send_json({"ok": True, **result, "analysis": list_analysis_symbols(conn)})
        except Exception as exc:
            self._send_json(
                {"error": "Unable to refresh analysis prices.", "details": str(exc)},
                status=500,
            )
        finally:
            conn.close()

    def handle_analysis_detail_get(self, symbol, version_id=None):
        conn = get_db_connection()
        try:
            detail = get_analysis_detail(conn, symbol, version_id=version_id)
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
            skipped = []
            failures = []

            existing_symbols = {
                row["symbol"]
                for row in conn.execute("SELECT symbol FROM analysis_roots").fetchall()
            }
            # Legacy fallback (if any rows still only exist in the old table).
            existing_symbols.update(
                row["symbol"]
                for row in conn.execute("SELECT symbol FROM analysis_symbols").fetchall()
            )

            for symbol in symbols:
                if symbol in existing_symbols:
                    skipped.append(symbol)
                    continue
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
                    "skippedSymbols": skipped,
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

    def handle_analysis_key_variables_save(self, symbol):
        payload = self._read_json_body() or {}
        version_id = payload.get("version_id")
        if version_id is None:
            return self._send_json({"error": "version_id is required"}, status=400)

        conn = get_db_connection()
        try:
            detail = save_key_variable_edits(conn, symbol, int(version_id), payload.get("key_variables"))
            self._send_json({"ok": True, "analysis": detail})
        except AnalysisValidationError as exc:
            self._send_json({"error": str(exc)}, status=400)
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=404)
        except Exception as exc:
            logger.exception("Unable to save key variable edits for symbol %s", symbol)
            self._send_json({"error": "Unable to save key variables.", "details": str(exc)}, status=500)
        finally:
            conn.close()

    def handle_analysis_business_model_save(self, symbol):
        payload = self._read_json_body() or {}
        version_id = payload.get("version_id")
        if version_id is None:
            return self._send_json({"error": "version_id is required"}, status=400)

        conn = get_db_connection()
        try:
            detail = save_business_model_edit(conn, symbol, int(version_id), payload.get("business_model"))
            self._send_json({"ok": True, "analysis": detail})
        except AnalysisValidationError as exc:
            self._send_json({"error": str(exc)}, status=400)
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=404)
        except Exception as exc:
            logger.exception("Unable to save business model edit for symbol %s", symbol)
            self._send_json({"error": "Unable to save business model.", "details": str(exc)}, status=500)
        finally:
            conn.close()

    def handle_analysis_business_summary_save(self, symbol):
        payload = self._read_json_body() or {}
        version_id = payload.get("version_id")
        if version_id is None:
            return self._send_json({"error": "version_id is required"}, status=400)

        conn = get_db_connection()
        try:
            detail = save_business_summary_edit(conn, symbol, int(version_id), payload.get("business_summary"))
            self._send_json({"ok": True, "analysis": detail})
        except AnalysisValidationError as exc:
            self._send_json({"error": str(exc)}, status=400)
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=404)
        except Exception as exc:
            logger.exception("Unable to save business summary edit for symbol %s", symbol)
            self._send_json({"error": "Unable to save business summary.", "details": str(exc)}, status=500)
        finally:
            conn.close()

    def handle_analysis_rerun_scenarios(self, symbol):
        payload = self._read_json_body() or {}
        version_id = payload.get("version_id")
        if version_id is None:
            return self._send_json({"error": "version_id is required"}, status=400)

        conn = get_db_connection()
        try:
            root = conn.execute("SELECT id FROM analysis_roots WHERE symbol = ?", (symbol,)).fetchone()
            draft = None
            if root:
                draft = conn.execute(
                    "SELECT based_on_version_id FROM analysis_key_variable_edits WHERE analysis_root_id = ?",
                    (root["id"],),
                ).fetchone()

            if draft and int(draft["based_on_version_id"]) == int(version_id):
                detail = rerun_scenarios_from_saved_edits(conn, symbol, int(version_id))
            else:
                detail = rerun_scenarios_from_existing_version(conn, symbol, int(version_id))
            self._send_json({"ok": True, "analysis": detail}, status=201)
        except AnalysisValidationError as exc:
            self._send_json({"error": str(exc)}, status=400)
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=400)
        except Exception as exc:
            logger.exception("Unable to rerun scenarios for symbol %s", symbol)
            self._send_json({"error": "Unable to re-run scenarios.", "details": str(exc)}, status=500)
        finally:
            conn.close()

    def handle_analysis_rerun_scenarios_batch(self):
        payload = self._read_json_body() or {}
        symbols = payload.get("symbols")
        if not isinstance(symbols, list) or not symbols:
            return self._send_json({"error": "symbols array is required"}, status=400)

        normalized_symbols = []
        for item in symbols:
            symbol = normalize_symbol(item)
            if symbol:
                normalized_symbols.append(symbol)
        if not normalized_symbols:
            return self._send_json({"error": "No valid symbols provided"}, status=400)

        conn = get_db_connection()
        try:
            rerun = []
            failures = []
            for symbol in normalized_symbols:
                try:
                    latest = conn.execute(
                        """
                        SELECT v.id
                        FROM analysis_roots r
                        JOIN analysis_versions v ON v.analysis_root_id = r.id
                        WHERE r.symbol = ?
                        ORDER BY v.version_number DESC
                        LIMIT 1
                        """,
                        (symbol,),
                    ).fetchone()
                    if not latest:
                        raise ValueError("Analysis symbol not found")
                    rerun_scenarios_from_existing_version(conn, symbol, latest["id"])
                    rerun.append(symbol)
                except Exception as exc:
                    logger.exception("Unable to rerun scenarios from list for symbol %s", symbol)
                    failures.append({"symbol": symbol, "error": str(exc)})

            self._send_json(
                {
                    "ok": len(failures) == 0,
                    "rerunSymbols": rerun,
                    "failures": failures,
                },
                status=207 if failures else 200,
            )
        finally:
            conn.close()

    def handle_analysis_delete(self, symbol):
        conn = get_db_connection()
        try:
            conn.execute("DELETE FROM analysis_roots WHERE symbol = ?", (symbol,))
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
            self._send_json(
                {
                    "templates": templates,
                    "sources": sources,
                }
            )
        except Exception as exc:
            self._send_json(
                {"error": "Unable to load prompt configuration.", "details": str(exc)},
                status=500,
            )
        finally:
            conn.close()

    def handle_configuration_prompts_put(self):
        payload = self._read_json_body() or {}
        templates = payload.get("templates", {})
        if not isinstance(templates, dict):
            return self._send_json({"error": "templates must be an object"}, status=400)

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
            self._send_json(
                {
                    "ok": True,
                    "templates": templates,
                    "sources": sources,
                }
            )
        except Exception as exc:
            self._send_json(
                {"error": "Unable to reset prompt configuration.", "details": str(exc)},
                status=500,
            )
        finally:
            conn.close()

    def handle_configuration_general_get(self):
        conn = get_db_connection()
        try:
            self._send_json({"settings": get_general_configuration(conn)})
        except Exception as exc:
            self._send_json(
                {"error": "Unable to load general configuration.", "details": str(exc)},
                status=500,
            )
        finally:
            conn.close()

    def handle_configuration_general_put(self):
        payload = self._read_json_body() or {}
        settings = payload.get("settings", {})
        if not isinstance(settings, dict):
            return self._send_json({"error": "settings must be an object"}, status=400)

        conn = get_db_connection()
        try:
            save_general_configuration(conn, settings)
            self._send_json({"ok": True, "settings": get_general_configuration(conn)})
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=400)
        except Exception as exc:
            self._send_json(
                {"error": "Unable to save general configuration.", "details": str(exc)},
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

        profile = resolve_company_profile_from_tws(symbol)
        company_name = profile.get("company_name")
        if not company_name:
            return self._send_json({"error": f"Unable to resolve company name from TWS/IBKR for symbol {symbol}"}, status=400)

        context = build_prompt_context(symbol=symbol, price=price, company_name=company_name)
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

    def handle_alerts_get(self):
        conn = get_db_connection()
        try:
            self._send_json({"alerts": get_alerts(conn)})
        except Exception as exc:
            self._send_json({"error": "Unable to load alerts.", "details": str(exc)}, status=500)
        finally:
            conn.close()

    def handle_alerts_check_recent_events(self):
        payload = self._read_json_body() or {}
        symbols_payload = payload.get("symbols", [])
        if not isinstance(symbols_payload, list):
            return self._send_json({"error": "symbols must be an array"}, status=400)
        symbols = []
        for value in symbols_payload:
            symbol = normalize_symbol(value)
            if symbol:
                symbols.append(symbol)
        if not symbols:
            return self._send_json({"error": "No valid symbols provided"}, status=400)

        conn = get_db_connection()
        try:
            summary = run_recent_event_check(conn, symbols)
            self._send_json(summary, status=207 if summary["errors_count"] else 200)
        finally:
            conn.close()

    def handle_alerts_status_put(self, raw_alert_id):
        try:
            alert_id = int(raw_alert_id)
        except Exception:
            return self._send_json({"error": "Invalid alert id"}, status=400)
        payload = self._read_json_body() or {}
        status_value = str(payload.get("status", "")).strip()
        if status_value not in {"New", "Reviewed", "Dismissed"}:
            return self._send_json({"error": "status must be one of New, Reviewed, Dismissed"}, status=400)

        conn = get_db_connection()
        try:
            cursor = conn.execute(
                "UPDATE thesis_review_alerts SET status = ?, updated_at = ? WHERE id = ?",
                (status_value, utc_now_iso(), alert_id),
            )
            conn.commit()
            if cursor.rowcount == 0:
                return self._send_json({"error": "Alert not found"}, status=404)
            self._send_json({"ok": True, "id": alert_id, "status": status_value})
        except Exception as exc:
            self._send_json({"error": "Unable to update alert status.", "details": str(exc)}, status=500)
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
