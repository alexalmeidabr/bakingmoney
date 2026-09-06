import asyncio
import json
import logging
import math
import os
import re
import shutil
import sqlite3
import statistics
import tempfile
import time
import uuid
import zipfile
from decimal import Decimal, InvalidOperation, ROUND_FLOOR
from html import unescape
from datetime import date, datetime, timezone
from http.server import HTTPServer, SimpleHTTPRequestHandler
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

from dotenv import load_dotenv

from momentum_service import calculate_momentum_snapshot

from analysis_service import (
    AnalysisValidationError,
    calculate_confidence_breakdown,
    calculate_expected_price,
    calculate_overall_confidence,
    calculate_upside,
    extract_json_payload,
    normalize_driver_category,
    parse_analysis_payload,
)

load_dotenv()

HOST = "127.0.0.1"
PORT = 8080
BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
DB_PATH = BASE_DIR / "bakingmoney.db"
ENV_PATH = BASE_DIR / ".env"
BACKUP_DIR = BASE_DIR / "backups"
UPLOADS_DIR = BASE_DIR / "uploads"
BACKUP_IMPORT_MAX_BYTES = 100 * 1024 * 1024
BACKUP_EXPORT_FILENAME_PREFIX = "bakingmoney-backup"
BACKUP_PACKAGE_DB_FILENAME = "bakingmoney.db"
BACKUP_PACKAGE_ENV_FILENAME = ".env"
BACKUP_PACKAGE_MANIFEST_FILENAME = "manifest.json"
BACKUP_REQUIRED_TABLES = (
    "analysis_symbols",
    "analysis_scenarios",
    "analysis_key_variables",
    "analysis_roots",
    "analysis_versions",
    "analysis_version_scenarios",
    "analysis_version_key_variables",
    "analysis_version_scenario_passes",
    "analysis_external_scenarios",
    "analysis_final_scenario_overlays",
    "analysis_key_variable_edits",
    "analysis_business_model_edits",
    "analysis_business_summary_edits",
    "earnings_watchpoint_sets",
    "earnings_watchpoints",
    "earnings_review_symbols",
    "earnings_reviews",
    "earnings_review_watchpoints",
    "earnings_review_documents",
    "earnings_review_watchpoint_results",
    "earnings_calendar_entries",
    "app_settings",
    "positions_cache",
    "thesis_review_alerts",
    "recent_event_checks",
    "analysis_momentum_snapshots",
)

IB_HOST = os.getenv("IB_HOST", "127.0.0.1")
IB_PORT = int(os.getenv("IB_PORT", "7496"))
IB_CLIENT_ID = int(os.getenv("IB_CLIENT_ID", "7"))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")
OPENAI_REASONING_EFFORT = os.getenv("OPENAI_REASONING_EFFORT", "medium").strip().lower() or "medium"
OPENAI_CORE_EVIDENCE_MODEL = os.getenv("OPENAI_CORE_EVIDENCE_MODEL", "").strip()
OPENAI_CORE_EVIDENCE_REASONING_EFFORT = os.getenv("OPENAI_CORE_EVIDENCE_REASONING_EFFORT", "").strip().lower()
OPENAI_TEMPERATURE_RAW = os.getenv("OPENAI_TEMPERATURE", "0.1")
OPENAI_WEB_SEARCH_TOOL_CANDIDATES = ("web_search", "web_search_preview")
OPENAI_REQUEST_TIMEOUT_SECONDS = float(os.getenv("OPENAI_REQUEST_TIMEOUT_SECONDS", "60"))
OPENAI_RECENT_EVENT_REQUEST_TIMEOUT_SECONDS = float(os.getenv("OPENAI_RECENT_EVENT_REQUEST_TIMEOUT_SECONDS", "120"))
OPENAI_STEP_TIMEOUT_OVERRIDES = {
    "earnings_watchpoint_analysis": {1: 120.0, 2: 180.0},
}
NO_PRICE_WARNING = "No live API market data (delayed/unavailable)"
ANALYSIS_PROMPT_SETTING_KEY_BUSINESS_MODEL = "analysis_prompt_business_model"
ANALYSIS_PROMPT_SETTING_KEY_KEY_VARIABLES = "analysis_prompt_key_variables"
ANALYSIS_PROMPT_SETTING_KEY_SCENARIOS = "analysis_prompt_scenarios"
ANALYSIS_PROMPT_SETTING_KEY_CORE_EVIDENCE_PACK = "analysis_prompt_core_evidence_pack"
ANALYSIS_PROMPT_SETTING_KEY_RECENT_EVENT_CANDIDATE = "analysis_prompt_recent_event_candidate"
ANALYSIS_PROMPT_SETTING_KEY_RECENT_EVENT_CHECK = "analysis_prompt_recent_event_check"
ANALYSIS_PROMPT_SETTING_KEY_EARNINGS_WATCHPOINTS = "earnings_watchpoints"
ANALYSIS_PROMPT_SETTING_KEY_EARNINGS_WATCHPOINT_ANALYSIS = "earnings_watchpoint_analysis"
EARNINGS_REVIEW_STATUS_DRAFT = "Draft"
EARNINGS_REVIEW_STATUS_WATCHPOINTS_GENERATED = "Watchpoints generated"
EARNINGS_REVIEW_STATUS_DOCUMENTS_UPLOADED = "Documents uploaded"
EARNINGS_REVIEW_STATUS_WATCHPOINTS_ANALYSED = "Watchpoints analysed"
EARNINGS_REVIEW_ALLOWED_DOCUMENT_TYPES = (
    "Earnings Release",
    "Shareholder Letter",
    "Presentation",
    "Transcript",
    "Supplemental",
    "Other",
)
EARNINGS_REVIEW_ALLOWED_FILE_EXTENSIONS = {".pdf", ".txt", ".docx", ".csv", ".xlsx", ".html"}
EARNINGS_REVIEW_MAX_DOCUMENT_BYTES = 15 * 1024 * 1024
EARNINGS_WATCHPOINT_ANALYSIS_ALLOWED_STATUSES = {
    "Confirmed",
    "Partially confirmed",
    "Contradicted",
    "Not addressed",
    "Unclear",
}
ANALYSIS_SETTING_SCENARIO_MULTI_PASS_ENABLED = "scenario_multi_pass_enabled"
ANALYSIS_SETTING_SCENARIO_PASS_COUNT = "scenario_pass_count"
ANALYSIS_SETTING_SCENARIO_OUTLIER_FILTER_ENABLED = "scenario_outlier_filter_enabled"
ANALYSIS_SETTING_IB_PRICE_WAIT_SECONDS = "ib_price_wait_seconds"
ANALYSIS_SETTING_IB_DELAYED_PRICE_EXTRA_WAIT_SECONDS = "ib_delayed_price_extra_wait_seconds"
ANALYSIS_SETTING_USE_TWS_DATA = "use_tws_data"

DEFAULT_SCENARIO_MULTI_PASS_ENABLED = False
DEFAULT_SCENARIO_PASS_COUNT = 1
DEFAULT_SCENARIO_OUTLIER_FILTER_ENABLED = True
DEFAULT_IB_PRICE_WAIT_SECONDS = 5
DEFAULT_IB_DELAYED_PRICE_EXTRA_WAIT_SECONDS = 5
DEFAULT_IB_MARKET_DATA_BATCH_SIZE = 25

RATING_SETTING_MIN_CONVICTION_HOLD_THRESHOLD = "min_conviction_hold_threshold"
RATING_SETTING_STRONG_BUY_MIN_UPSIDE = "strong_buy_min_upside"
RATING_SETTING_STRONG_BUY_MIN_DIFF = "strong_buy_min_diff"
RATING_SETTING_STRONG_BUY_MIN_BULLISH_CONFIDENCE = "strong_buy_min_bullish_confidence"
RATING_SETTING_BUY_MIN_UPSIDE = "buy_min_upside"
RATING_SETTING_BUY_MIN_DIFF = "buy_min_diff"
RATING_SETTING_BUY_MIN_BULLISH_CONFIDENCE = "buy_min_bullish_confidence"
RATING_SETTING_SPECULATIVE_BUY_MIN_UPSIDE = "speculative_buy_min_upside"
RATING_SETTING_SPECULATIVE_BUY_MIN_DIFF = "speculative_buy_min_diff"
RATING_SETTING_SPECULATIVE_BUY_MIN_BULLISH_CONFIDENCE = "speculative_buy_min_bullish_confidence"
RATING_SETTING_SPECULATIVE_BUY_MIN_CORE_DIFF_FLOOR = "speculative_buy_min_core_diff_floor"
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

CORE_DRIVER_BACKEND_PROBABILITY_WEIGHT = 1.0
POTENTIAL_DRIVER_BACKEND_PROBABILITY_MAX_WEIGHT = 0.25
POTENTIAL_DRIVER_BACKEND_PROBABILITY_CONFIDENCE_FLOOR = 3.0

DEFAULT_RATING_SETTINGS = {
    RATING_SETTING_MIN_CONVICTION_HOLD_THRESHOLD: 5.0,
    RATING_SETTING_STRONG_BUY_MIN_UPSIDE: 50.0,
    RATING_SETTING_STRONG_BUY_MIN_DIFF: 1.5,
    RATING_SETTING_STRONG_BUY_MIN_BULLISH_CONFIDENCE: 7.0,
    RATING_SETTING_BUY_MIN_UPSIDE: 25.0,
    RATING_SETTING_BUY_MIN_DIFF: 0.5,
    RATING_SETTING_BUY_MIN_BULLISH_CONFIDENCE: 5.5,
    RATING_SETTING_SPECULATIVE_BUY_MIN_UPSIDE: 75.0,
    RATING_SETTING_SPECULATIVE_BUY_MIN_DIFF: 0.1,
    RATING_SETTING_SPECULATIVE_BUY_MIN_BULLISH_CONFIDENCE: 4.5,
    RATING_SETTING_SPECULATIVE_BUY_MIN_CORE_DIFF_FLOOR: -0.5,
    RATING_SETTING_STRONG_SELL_MAX_UPSIDE: 0.0,
    RATING_SETTING_STRONG_SELL_MAX_DIFF: -1.5,
    RATING_SETTING_STRONG_SELL_MIN_BEARISH_CONFIDENCE: 7.0,
    RATING_SETTING_SELL_MAX_UPSIDE: 10.0,
    RATING_SETTING_SELL_MAX_DIFF: -0.5,
    RATING_SETTING_SELL_MIN_BEARISH_CONFIDENCE: 5.5,
}

SCENARIO_MAX_BASE_DEVIATION = 0.40
SCENARIO_MAX_AVG_DEVIATION = 0.30

ACTION_PLAN_DEFAULT_SETTINGS = {
    "action_bucket_strong_buy_target": 35.0,
    "action_bucket_buy_target": 30.0,
    "action_bucket_speculative_buy_target": 15.0,
    "action_bucket_hold_target": 10.0,
    "action_bucket_cash_target": 10.0,
    "action_bucket_sell_target": 0.0,
    "action_bucket_strong_sell_target": 0.0,
    "action_use_dynamic_bucket_sizing": True,
    "action_use_weighted_eligible_count": True,
    "action_min_cash_unallocated_target": 10.0,
    "action_redistribute_post_cap_excess": False,
    "action_weighted_count_min_score": 0.15,
    "action_weighted_count_full_score": 0.75,
    "action_weighted_count_max_contribution": 1.0,
    "action_max_potential_score_contribution": 0.20,
    "action_allocation_upside_weight": 0.60,
    "action_allocation_core_weight": 0.30,
    "action_allocation_potential_weight": 0.10,
    "action_allocation_risk_penalty_strength": 0.60,
    "action_bucket_sizing_upside_weight": 0.50,
    "action_bucket_sizing_core_weight": 0.40,
    "action_bucket_sizing_potential_weight": 0.10,
    "action_bucket_sizing_risk_penalty_strength": 0.50,
    "action_strong_buy_weight_per_effective_stock": 5.0,
    "action_strong_buy_max_effective_count": 6.0,
    "action_strong_buy_max_bucket_target": 45.0,
    "action_strong_buy_compression_weight": 0.25,
    "action_buy_weight_per_effective_stock": 2.5,
    "action_buy_max_effective_count": 14.0,
    "action_buy_max_bucket_target": 35.0,
    "action_buy_compression_weight": 0.75,
    "action_speculative_buy_weight_per_effective_stock": 1.5,
    "action_speculative_buy_max_effective_count": 5.0,
    "action_speculative_buy_max_bucket_target": 7.5,
    "action_speculative_buy_compression_weight": 1.25,
    "action_hold_weight_per_effective_stock": 0.8,
    "action_hold_max_effective_count": 15.0,
    "action_hold_max_bucket_target": 12.0,
    "action_hold_compression_weight": 2.0,
    "action_include_current_positions": True,
    "action_include_strong_buy": True,
    "action_include_buy": True,
    "action_include_speculative_buy": True,
    "action_include_hold_only_if_owned": True,
    "action_include_sell_only_if_owned": True,
    "action_allow_manual_include_exclude": False,
    "action_upside_zero_score": 10.0,
    "action_upside_full_score": 100.0,
    "action_core_diff_zero_score": -0.5,
    "action_core_diff_full_score": 2.0,
    "action_core_bearish_penalty_start": 5.0,
    "action_core_bearish_penalty_full": 8.0,
    "action_max_potential_bonus_weight": 2.0,
    "action_potential_diff_minimum": 0.25,
    "action_potential_diff_full_score": 2.0,
    "action_potential_bullish_confidence_minimum": 4.5,
    "action_potential_bonus_upside_minimum": 50.0,
    "action_max_single_stock_weight": 8.0,
    "action_max_strong_buy_stock_weight": 8.0,
    "action_max_buy_stock_weight": 6.0,
    "action_max_speculative_buy_stock_weight": 3.0,
    "action_max_negative_core_weight": 2.0,
    "action_max_very_negative_core_weight": 1.0,
    "action_min_target_weight_to_show": 0.5,
    "action_band_lower_multiplier": 0.8,
    "action_band_upper_multiplier": 1.2,
    "action_target_band_lower_multiplier": 0.8,
    "action_target_band_upper_multiplier": 1.2,
    "action_speculative_band_lower_multiplier": 0.7,
    "action_speculative_band_upper_multiplier": 1.3,
    "action_min_absolute_band_width": 0.5,
    "action_strong_add_below_target_multiplier": 0.5,
    "action_strong_trim_above_target_multiplier": 1.5,
    "action_min_trade_gap_percent": 0.5,
    "action_min_executable_trade_amount": 100.0,
    "action_starter_buy_max_initial_weight": 1.0,
    "action_use_allocation_based_triggers": True,
    "action_momentum_add_max_raise": 0.08,
    "action_momentum_add_max_lower": 0.10,
    "action_extension_add_max_lower": 0.10,
    "action_momentum_trim_max_raise": 0.15,
    "action_momentum_trim_max_lower": 0.10,
    "action_extension_trim_max_lower": 0.15,
    "action_min_trigger_multiplier": 0.75,
    "action_max_trigger_multiplier": 1.25,
    "action_add_required_upside": 30.0,
    "action_strong_add_required_upside": 50.0,
    "action_starter_buy_required_upside": 75.0,
    "action_trim_remaining_upside": 10.0,
    "action_sell_remaining_upside": 0.0,
    "action_starter_buy_base_required_upside": 0.25,
    "action_add_base_required_upside": 0.30,
    "action_strong_add_base_required_upside": 0.40,
    "action_hold_extra_add_required_upside": 0.50,
    "action_trim_remaining_upside_threshold": 0.10,
    "action_sell_remaining_upside_threshold": 0.00,
    "action_underweight_discount_max": 0.10,
    "action_quality_discount_max": 0.10,
    "action_overweight_penalty_max": 0.15,
    "action_low_quality_penalty_max": 0.15,
    "action_trigger_min_required_upside": 0.10,
    "action_trigger_max_required_upside": 0.80,
    "action_strong_trim_gap_threshold": 0.25,
    "action_redistribute_capped_excess": False,
    "action_allow_bucket_underallocation": True,
    "action_show_unallocated_bucket_amount": True,
    "action_treat_cash_equivalents_as_cash": True,
    "action_cash_equivalent_symbols": "SGOV",
    "linear_allocated_target_total_pct": 100.0,
    "linear_reserve_benchmark_yield_pct": 4.0,
    "linear_min_equity_excess_cagr_pct": 2.0,
    "linear_full_attractiveness_equity_excess_cagr_pct": 7.0,
    "linear_max_reserve_pct": 40.0,
    "linear_min_expected_cagr": 0.0,
    "linear_full_expected_cagr": 15.0,
    "linear_min_upside": 0.0,
    "linear_full_upside": 80.0,
    "linear_min_core_net": -1.0,
    "linear_full_core_net": 2.0,
    "linear_min_potential_net": -1.0,
    "linear_full_potential_net": 1.5,
    "linear_expected_cagr_weight": 40.0,
    "linear_upside_weight": 20.0,
    "linear_core_confidence_weight": 25.0,
    "linear_potential_confidence_weight": 10.0,
    "linear_confidence_quality_weight": 5.0,
    "linear_min_score_threshold": 0.10,
    "linear_score_allocation_power": 1.5,
    "linear_zero_target_if_expected_cagr_negative": True,
    "linear_zero_target_if_upside_negative": True,
    "linear_max_single_stock_pct": 10.0,
    "linear_target_band_tolerance_pct": 15.0,
    "linear_add_band_tolerance_pct": 15.0,
    "linear_trim_band_tolerance_pct": 30.0,
    "linear_enable_risk_caps": True,
    "linear_negative_core_net_cap_pct": 2.0,
    "linear_low_core_net_threshold": 0.5,
    "linear_low_core_net_cap_pct": 4.0,
    # Retained for compatibility with saved configurations from the binary-cap model.
    "linear_high_bearish_confidence_threshold": 8.0,
    "linear_high_bearish_confidence_min_threshold": 4.0,
    "linear_high_bearish_confidence_max_threshold": 8.0,
    "linear_high_bearish_confidence_cap_pct": 5.0,
    "core_confidence_penalty_threshold": 0.5,
    "core_confidence_penalty": 0.15,
    "upside_penalty_threshold": 40.0,
    "upside_penalty": 0.20,
    "potential_confidence_penalty_threshold": 0.0,
    "potential_confidence_penalty": 0.05,
    "hold_rating_penalty_enabled": True,
    "hold_rating_penalty": 0.10,
    "linear_rating_bonus_enabled": True,
    "linear_strong_buy_rating_bonus": 0.05,
    "linear_buy_rating_bonus": 0.02,
    "linear_frontier_optionality_max_boost_pct": 10.0,
    "linear_block_buy_actions_for_hold_rating": True,
    "linear_high_extension_guardrail_enabled": True,
    "linear_high_extension_risk_threshold": 4.0,
    "linear_release_date_warning_days": 30,
}
ACTION_PLAN_BOOL_SETTINGS = {
    "action_include_current_positions",
    "action_include_strong_buy",
    "action_include_buy",
    "action_include_speculative_buy",
    "action_include_hold_only_if_owned",
    "action_include_sell_only_if_owned",
    "action_allow_manual_include_exclude",
    "action_use_dynamic_bucket_sizing",
    "action_use_weighted_eligible_count",
    "action_redistribute_post_cap_excess",
    "action_redistribute_capped_excess",
    "action_allow_bucket_underallocation",
    "action_show_unallocated_bucket_amount",
    "action_treat_cash_equivalents_as_cash",
    "action_use_allocation_based_triggers",
    "linear_zero_target_if_expected_cagr_negative",
    "linear_zero_target_if_upside_negative",
    "linear_enable_risk_caps",
    "hold_rating_penalty_enabled",
    "linear_rating_bonus_enabled",
    "linear_block_buy_actions_for_hold_rating",
    "linear_high_extension_guardrail_enabled",
}
ACTION_PLAN_TEXT_SETTINGS = {
    "action_cash_equivalent_symbols",
}
ACTION_PLAN_BUCKET_KEYS = {
    "Strong Buy": "action_bucket_strong_buy_target",
    "Buy": "action_bucket_buy_target",
    "Speculative Buy": "action_bucket_speculative_buy_target",
    "Hold": "action_bucket_hold_target",
    "Sell": "action_bucket_sell_target",
    "Strong Sell": "action_bucket_strong_sell_target",
}
ACTION_PLAN_ACTION_PRIORITY = {
    "Strong Add": 1,
    "Add": 2,
    "Starter Buy": 3,
    "Trim": 4,
    "Strong Trim": 5,
    "Sell": 6,
    "Watch": 7,
    "Watch / Extended": 7,
    "Hold": 8,
    "Hold / Overweight": 8,
    "Re-evaluate": 9,
}

DEFAULT_PROMPT_BUSINESS_MODEL = """You are an equity analyst.

Describe the business model of the publicly traded company below for use in a 5-year stock scenario analysis.

Company context:
- Symbol: $Symbol
- Company name: $CompanyName
- Current price: $Price USD

Instructions:
- Explain what the company does in the real world. 
- Explain how it makes money.
- Explain the core economic engine that drives revenue, margins, and operating leverage.
- Keep the description practical, concise, and business-focused.
- Focus on the operating business, not stock valuation.
- Write the output as an internal analysis input, not as a research report.

Guidance:
- Focus on:
  - products and services
  - customer base
  - revenue model
  - main cost structure
  - the business drivers that matter for future scenarios
- Prefer plain business language over narrative or promotional wording.
- Do not include citations, links, source attributions, or markdown references in the output.
- Do not mention where the information came from.
- Avoid unnecessary detail that is not useful for scenario building.

Return ONLY valid JSON in this exact structure:
{
  "symbol": "$Symbol",
  "company_name": "$CompanyName",
  "business_model": "concise description of what the company does, how it makes money, and the core economic engine",
  "business_summary": "short summary of the main revenue drivers, cost drivers, and major risks"
}

Rules:
- Be specific and practical.
- business_model should be concise, concrete, and ideally 5 to 8 sentences.
- business_summary should be short, useful for later analysis, and ideally 2 to 4 sentences.
- Do not include links, citations, or source references anywhere in the JSON fields.
- JSON only.
- No markdown.
- No commentary outside JSON."""

DEFAULT_PROMPT_KEY_VARIABLES = """You are an equity analyst.

Using the Company name and business model below, identify the 6 to 8 most important company-specific key variables that could materially push the stock price up or down over the next 5 years.
Company context:
- Symbol: $Symbol
- Company name: $CompanyName
- Current price: $Price USD
- Business model: $BusinessModel

Definitions:
- A key variable is one of the most important company-specific factors that could materially move the stock price over 5 years.
- Confidence means how strong the current evidence is that this variable is acting in that direction now.
- Importance means how much this variable could influence the stock price over the 5-year horizon.
- Driver Category explains whether the variable is tied to the existing material business or to emerging future optionality.
- Core Driver means the variable is tied to the existing material business, current revenue/margin/cash-flow engine, current customer demand, current cost structure, current competitive position, or an already proven/material segment.
- Potential Driver means the variable is tied to emerging optionality, new initiatives, early-stage products, future markets, speculative technologies, new business lines, or not-yet-material drivers that could become material over five years but are not yet strongly proven.

What makes a strong key variable:
- specific
- causal
- business-relevant
- material over 5 years
- clearly Bullish or clearly Bearish
- useful for scenario building

Preferred structure:
[specific driver or risk] + [clear business effect]

Guidance:
- Prefer company-specific drivers such as demand growth, product adoption, pricing power, revenue mix, margins, utilization, capacity expansion, customer concentration, contract pipeline, technology execution, competitive position, capital intensity, funding, dilution, or balance-sheet risk when relevant.
- Focus on variables that are directly tied to the actual business model.
- Avoid generic macro filler such as GDP, inflation, interest rates, or broad market conditions unless they are clearly central to this company’s economics.
- Avoid vague sponsor/management language such as “strong positioning”, “innovation leadership”, or “effective management” unless made specific and causal.
- Avoid variables that are too broad, too trivial, or too thematic without a clear business mechanism.
- Avoid overlap: each variable should represent a distinct concept, not a reworded version of another variable.
- Do not mix bullish and bearish directions in the same variable.
- Most variables should be business drivers or risks, not secondary consequences.
- Use scoring discipline: do not give too many 10/10 scores, do not make everything highly important, and do not overstate confidence for speculative optionality.
- Classify each variable as either Core Driver or Potential Driver.
- Do not classify a normal future growth driver as Potential Driver just because it is forward-looking.
- Use Potential Driver only when the variable is genuinely tied to optionality, emerging initiatives, speculative products, new segments, or not-yet-material future drivers.
- Most companies should normally have more Core Drivers than Potential Drivers.
- Do not force Potential Drivers if the company has no meaningful optionality.
- Potential Drivers should usually have lower confidence unless there is strong current evidence.
- High importance is allowed for Potential Drivers if the possible 5-year upside/downside impact could be large.
- Both Core Drivers and Potential Drivers can be Bullish or Bearish.

ETF-specific guidance:
- If the symbol is an ETF, focus mainly on:
  - what drives the underlying holdings’ earnings, cash flow, or margins
  - adoption/commercialization of the underlying sector/theme
  - valuation rerating or derating of the underlying holdings
  - concentration, liquidity, cyclicality, or funding risk when relevant
- Do not focus on sponsor economics, fee competitiveness, securities lending, or generic active-management language unless truly central.

Return ONLY valid JSON in this exact structure:
{
  "symbol": "$Symbol",
  "key_variables": [
    {
      "variable": "text",
      "type": "Bullish",
      "driver_category": "Core Driver",
      "confidence": 0,
      "importance": 0
    }
  ]
}

Rules:
- Return 6 to 8 key variables only.
- Include both Bullish and Bearish variables.
- The set should focus on the few most material 5-year drivers of the stock.
- Include only the variables that most likely determine the 5-year outcome, exclude secondary variables unless they are clearly more important than a core driver/risk.
- Each variable must be specific, causal, and clearly linked to revenue, margins, cash flow, or valuation.
- Each variable must be clearly and exclusively Bullish or Bearish.
- Each variable must include driver_category.
- driver_category must be exactly one of: Core Driver, Potential Driver.
- Avoid overlap between variables, if two candidate variables describe the same mechanism, keep only the stronger one.
- Keep each variable text concise. Prefer a short phrase or one short sentence, not a full explanation. Do not explicitly include “mechanism:” or “financial consequence:” in the variable text.
- confidence must be an integer from 0 to 10.
- importance must be an integer from 0 to 10.
- Use score discipline: reserve the highest scores for only the most central and well-supported variables.
- JSON only.
- No markdown.
- No commentary outside JSON."""

LEGACY_DEFAULT_PROMPT_SCENARIOS = """You are an equity analyst building a disciplined 5-year stock scenario analysis.

Company context:
- Symbol: $Symbol
- Company name: $CompanyName
- Current price: $Price USD
- Business model: $BusinessModel
- Key variables: $KeyVariables
- If the $Symbol is an ETF, center the analysis on its top holdings.

Task:
Build Bear, Base, and Bull stock price scenarios over a 5-year horizon using the company name, business model, current price, and key variables above.

Definitions:

- Bear = pessimistic but plausible outcome
- Base = most likely central outcome
- Bull = optimistic but plausible outcome

Return ONLY valid JSON in this exact structure:
{
  "symbol": "$Symbol",
  "assumptions": "short explanation of the thesis behind the scenarios",
  "scenarios": [
    {"name": "Bear", "price_low": 0, "price_high": 0, "probability": 0},
    {"name": "Base", "price_low": 0, "price_high": 0, "probability": 0},
    {"name": "Bull", "price_low": 0, "price_high": 0, "probability": 0}
  ]
}

Rules:
- Exactly 3 scenarios in this order: Bear, Base, Bull.
- Build each scenario primarily from the key variables provided and the business model.
- The Bear case should reflect stronger materialization of the most important bearish variables.
- The Bull case should reflect stronger materialization of the most important bullish variables.
- The Base case should represent normal execution and currently visible trajectory, not a scenario where most bullish variables work well.
- Probabilities must sum to 100.
- Do not output CAGR fields. CAGR is calculated by BakingMoney from current price and scenario target prices.

Base-case discipline:

- Do not assume multiple expansion in the Base case unless valuation is clearly undemanding or earnings/cash-flow growth strongly justifies it.
- If the stock already trades at a premium valuation, the Base case may have modest upside even if the business performs well.
- The Base case should usually be closer to the outcome supported by key variables, current guidance, current margins, current growth trajectory, and currently visible backlog/contracts.

Fresh-information rule:
Before building scenarios, review the latest company earnings release and guidance, and consider only recent news or analyst commentary that materially changes the company’s key variables, current expectations, or scenario probabilities. Prioritize primary sources and factual updates over sentiment or low-signal market commentary.

When reviewing company earnings releases, management commentary, and shareholder letters, be cautious because companies often present results in an optimistic way. Prioritize hard financial data, segment performance, margins, cash flow, and guidance over promotional language. Give greater weight to forward guidance, outlook changes, and the quality of revenue/profit drivers than to management’s qualitative enthusiasm. If the release tone is positive but the guidance, margin profile, growth trajectory, or key operating metrics are only moderate or deteriorating, reflect that caution in the scenario assumptions, price ranges, and probabilities.

The key variables are the primary foundation for the scenario analysis. Build the Bear, Base, and Bull scenarios mainly from the highest-importance and highest-confidence key variables, and ensure that the scenario assumptions, price ranges, and probabilities are directly driven by how those variables could evolve over the next 5 years.

Core vs Potential Driver scenario treatment:
- Key variables may include driver_category values of Core Driver or Potential Driver.
- Core Drivers are tied to the existing material business, current revenue/margin/cash-flow engine, current demand, current cost structure, current competitive position, or already proven/material segments.
- Potential Drivers are tied to emerging optionality, new initiatives, early-stage products, future markets, speculative technologies, new business lines, or not-yet-material drivers that could become material over five years but are not yet strongly proven.
- Core Drivers should dominate the Base case, normal execution assumptions, and the central business trajectory.
- Potential Drivers should mainly affect Bull/Bear optionality and scenario range.
- Do not let low-confidence Potential Drivers materially lift or reduce the Base case.
- A Potential Driver may influence the Base case only when its confidence is high and evidence suggests it is becoming material to the business.
- High-importance Potential Drivers may justify a wider Bull or Bear range, but they should not automatically imply a high probability.
- If Potential Drivers are bullish but low confidence, reflect them mainly in the Bull case, not in the Base case.
- If Potential Drivers are bearish but low confidence, reflect them mainly as downside/tail risk, not as the central Base case.
- If a Potential Driver becomes credible and material enough to dominate the Base case, treat that as evidence that it may no longer be merely optionality.
- Do not ignore Potential Drivers, but distinguish clearly between currently proven business drivers and speculative optionality.

Valuation discipline:
- A strong business does not automatically imply high stock upside.
- Current valuation, company size, and already-priced expectations must materially constrain scenario outputs.
- Do not assume extreme 5-year upside unless clearly supported by multiple high-confidence, high-importance bullish variables and limited material bearish constraints.
- High-importance bullish and bearish variables must materially affect price ranges and probabilities, not just the written assumptions.
- If the stock is not obviously expensive relative to its risk, growth profile, and business quality, allow meaningful upside when justified by the variables.

Valuation framework:
- When possible, mentally anchor scenarios to plausible 5-year revenue, earnings, EBITDA, free-cash-flow, or book-value outcomes and a reasonable terminal valuation multiple.
- Do not output price ranges that imply unrealistic revenue growth, margin expansion, or valuation multiples relative to the company’s maturity, industry, cyclicality, leverage, and risk.
- If the current stock price already reflects optimistic growth or margin assumptions, reflect that in lower expected upside, lower Bull probability, or a narrower Bull range.
- If the company is highly speculative, loss-making, capital-intensive, or dependent on external financing, require stronger evidence before assigning high Bull probability.

Current-price anchoring:
- Use the current price to judge how much optimism or pessimism is already priced in.
- A high-quality company can have a Base case below or near the current price if valuation already discounts strong execution.
- A beaten-down company can have a Base case materially above the current price if the key variables and current evidence support recovery.
- Do not mechanically center scenarios around the current price; anchor them to plausible 5-year business value.

Guidance interpretation:
- Treat guidance as more important than backward-looking results when it materially changes the 5-year trajectory.
- A beat with reaffirmed guidance is usually confirmation, not a thesis upgrade.
- A beat with weak or reduced guidance should reduce scenario optimism.
- A miss with raised guidance may still support the thesis if the forward drivers are improving.
- Distinguish between temporary quarterly volatility and durable changes in growth, margins, cash flow, backlog, customer demand, or capital intensity.

Scenario realism:
- Use realistic price ranges that reflect both business performance and valuation constraints.
- Do not let optionality, speculative new products, or long-shot TAM expansion dominate the scenarios unless strongly supported by current evidence.
- Avoid ultra-optimistic outcomes that require near-perfect execution across multiple variables unless such outcomes are assigned a clearly low probability.
- Keep Bull plausible, not aspirational.
- Keep Bear pessimistic, not catastrophic unless the variable set truly supports that.
- The wider and more uncertain the path, the lower the probability should be.
- Use latest earnings release / shareholder letter / earnings call guidance and extract only facts that materially affect the 5-year thesis and current scenario framing.
- Use latest earnings release to understand current company valuation.

Assumptions field rules:

- The assumptions field is a concise 5-year thesis summary for the scenario set, not an earnings recap.
- It must primarily explain which key variables are most likely to determine the 5-year outcome and how they shape the Bear, Base, and Bull cases.
- Use the latest earnings release or guidance only to the extent that it changes, confirms, or weakens those 5-year drivers.
- Do not summarize quarterly results, year-over-year growth rates, or management commentary unless they materially change the 5-year thesis.
- Do not turn the assumptions field into a mini earnings report.
- Do not list multiple quarterly metrics unless one is essential to understanding a durable change in trajectory.
- Prefer a causal 2-part structure:
  1. the core 5-year drivers likely to determine value
  2. the main constraints/risks that limit upside or increase downside
- Keep assumptions concise, ideally 2 to 4 sentences.
- Focus on durable drivers such as growth durability, margin structure, take-rate/pricing power, capital intensity, balance-sheet/leverage risk, competitive pressure, customer concentration, or valuation constraint when relevant.
- If the latest earnings were merely in line with the existing thesis, do not let them dominate the assumptions text.
- A beat with unchanged guidance is usually confirmation, not the main substance of the assumptions field.

Interpretation rules:
- Distinguish clearly between business quality and stock attractiveness.
- A company can be excellent while the stock has limited upside.
- If current price is known, use it as an anchor, but do not force the Base case close to current price when the variable set clearly justifies deviation.
- Scenario probabilities must reflect the weighted balance of key variables using both importance and confidence.
- Avoid generic default probability splits unless the evidence is truly balanced.
- assumptions should be concise and reflect the 5-year business thesis behind the scenarios, driven mainly by the most important Core Drivers, while acknowledging important Potential Drivers only when they materially shape Bull/Bear optionality or scenario range.
- If the symbol is an ETF, reflect the performance drivers and risks of its top holdings.

JSON only.
No markdown.
No commentary outside JSON."""

DEFAULT_PROMPT_CORE_EVIDENCE_PACK = """You are an equity research analyst gathering the factual evidence needed for a disciplined 5-year stock scenario analysis.

TASK

Research the company using the supplied company information and key variables.

Build a concise Core Evidence Pack containing the most recent and materially relevant factual information that should be known by any analyst constructing 5-year Bear, Base, and Bull scenarios.

The Core Evidence Pack is NOT a scenario analysis.

Do not:
- produce Bear, Base, or Bull scenarios;
- estimate future stock prices;
- assign scenario probabilities;
- make Buy/Sell recommendations;
- decide whether the stock is attractive;
- create a new investment thesis that replaces the supplied key variables.

Its purpose is to establish a common factual baseline while leaving scenario interpretation to a later analysis step.

RESEARCH PRIORITIES

Prioritize authoritative and recent sources in this order when available:

1. latest earnings release or shareholder letter;
2. latest company guidance or outlook;
3. SEC/regulatory filings or equivalent official filings;
4. company investor-relations disclosures;
5. material company announcements;
6. recent factual reporting about developments that materially affect the supplied key variables;
7. industry or analyst research only when it adds material factual context unavailable from primary sources.

Prioritize primary sources over commentary.

Research as much as necessary to establish a reliable factual baseline.

Do not waste research on:
- routine stock-price movements;
- generic analyst sentiment;
- price-target changes;
- promotional management statements without supporting facts;
- immaterial quarterly fluctuations;
- duplicate reporting of facts already established from stronger sources.

KEY-VARIABLE DISCIPLINE

The supplied key variables define the existing BakingMoney thesis framework.

Use them to determine which evidence is material.

For each important key variable, identify recent factual evidence that:

- confirms it;
- weakens it;
- contradicts it;
- materially changes its magnitude;
- or provides important new context.

Do not rewrite or replace the key variables.

Do not infer that a key variable is correct merely because management describes the business positively.

Give greater weight to:
- reported financial data;
- guidance;
- margins;
- cash flow;
- backlog;
- contracts;
- customer demand;
- unit economics;
- capital requirements;
- balance-sheet changes;
- competitive developments;
- regulatory developments.

CORE VS POTENTIAL DRIVERS

Key variables may be classified as Core Driver or Potential Driver.

For Core Drivers, prioritize evidence relating to the company's existing material revenue, margins, cash flow, demand, competitive position, cost structure, and proven business segments.

For Potential Drivers, distinguish clearly between:
- demonstrated material progress;
- early evidence;
- management expectations;
- and still-speculative optionality.

Do not treat an emerging opportunity as proven merely because its potential market is large.

FRESHNESS

Prefer the latest available evidence.

When a newer source materially supersedes older information, use the newer information.

Distinguish:
- current reported facts;
- current company guidance;
- announced but not yet realized developments;
- third-party estimates.

VALUATION CONTEXT

Include factual valuation context when useful for the later scenario analysis.

Examples may include:
- current market capitalization;
- enterprise value;
- relevant current valuation multiples;
- net cash or debt;
- share count/dilution;
- capital requirements.

Do not decide whether the valuation is cheap or expensive unless that conclusion follows directly from factual context. Leave scenario valuation judgments to the scenario-generation step.

MATERIALITY

Be selective.

The evidence pack should contain information capable of materially affecting a 5-year valuation or the supplied key variables.

Do not turn it into an earnings recap or general company profile.

OUTPUT

Return ONLY valid JSON in exactly this structure:

{
  "symbol": "",
  "as_of": "",
  "reporting_context": {
    "latest_reporting_period": "",
    "latest_release_date": "",
    "facts": []
  },
  "guidance": {
    "facts": []
  },
  "key_variable_evidence": [
    {
      "key_variable": "",
      "driver_category": "",
      "evidence_status": "",
      "facts": []
    }
  ],
  "other_material_facts": [],
  "valuation_context": [],
  "sources": [
    {
      "title": "",
      "date": "",
      "source_type": "",
      "url": ""
    }
  ]
}

Rules:

- Set symbol to the supplied symbol.
- as_of should reflect the date of the research.
- evidence_status should use one of:
  "Confirms",
  "Weakens",
  "Contradicts",
  "Mixed",
  "New context",
  "No material new evidence".
- Facts should be concise factual statements, not investment conclusions.
- Avoid duplicating the same fact across multiple sections unless necessary.
- Include only materially relevant sources.
- Do not fabricate unavailable dates, values, or URLs.
- Use empty arrays when no material evidence exists.
- JSON only.
- No markdown.
- No commentary outside JSON.

COMPANY INPUT

Symbol: $Symbol
Company name: $CompanyName
Current price: $Price USD

Business model:
$BusinessModel

Key variables:
$KeyVariables"""

DEFAULT_PROMPT_SCENARIOS = """You are an equity analyst building a disciplined 5-year stock scenario analysis.

TASK

Build exactly three stock-price scenarios over a 5-year horizon:

- Bear = pessimistic but plausible outcome
- Base = most likely central outcome
- Bull = optimistic but plausible outcome

The purpose is to estimate realistic 5-year stock-value ranges and probabilities based primarily on the supplied business model, key variables, current valuation, Core Evidence Pack, and any additional material information you determine is necessary.

OUTPUT

Return ONLY valid JSON in exactly this structure:

{
  "symbol": "",
  "assumptions": "concise 5-year thesis summary",
  "scenarios": [
    {"name": "Bear", "price_low": 0, "price_high": 0, "probability": 0},
    {"name": "Base", "price_low": 0, "price_high": 0, "probability": 0},
    {"name": "Bull", "price_low": 0, "price_high": 0, "probability": 0}
  ]
}

Rules:
- Set "symbol" to the supplied company symbol.
- Return exactly 3 scenarios in this order: Bear, Base, Bull.
- Probabilities must sum to 100.
- price_low must be less than or equal to price_high for every scenario.
- Return JSON only. No markdown or commentary outside the JSON.

KEY-VARIABLE DISCIPLINE

The supplied key variables are the primary foundation of the analysis.

- Give the greatest influence to variables with the highest importance and confidence.
- High-importance bullish and bearish variables must materially affect scenario prices, ranges, and probabilities, not merely the assumptions text.
- Bear should reflect stronger materialization of the most important bearish variables.
- Bull should reflect stronger materialization of the most important bullish variables.
- Base should represent normal execution and the currently visible central trajectory. It must not assume that most bullish variables succeed.

CORE VS POTENTIAL DRIVERS

Key variables may be classified as Core Driver or Potential Driver.

Core Drivers:
- Represent the existing material business, revenue, margins, cash flow, demand, cost structure, competitive position, or proven segments.
- Must dominate the Base case and normal execution assumptions.

Potential Drivers:
- Represent emerging optionality, new products, new initiatives, future markets, speculative technologies, new business lines, or not-yet-material drivers.
- Should primarily affect Bull/Bear optionality and scenario range.
- Low-confidence Potential Drivers should not materially influence Base.
- A Potential Driver may materially influence Base only when confidence is high and current evidence indicates it is becoming economically material.
- High-importance Potential Drivers may widen scenario ranges without necessarily increasing their probability.
- If a Potential Driver becomes sufficiently credible and material to dominate Base, that is evidence that it may no longer be merely optionality.

BASE-CASE DISCIPLINE

Base is the central expected business trajectory, not an optimistic execution case.

- Base should primarily reflect Core Drivers, current guidance, visible demand, margins, backlog/contracts, competitive position, and normal execution.
- A strong business does not automatically imply large stock upside.
- Do not assume valuation multiple expansion in Base unless valuation is clearly undemanding or future earnings/free-cash-flow growth strongly justifies it.
- If current valuation already discounts strong execution, Base may be near or below the current stock price.
- If the stock is depressed but durable fundamentals support recovery, Base may be materially above the current price.
- A quarterly earnings beat with unchanged guidance is normally confirmation, not a reason to materially raise Base.

VALUATION DISCIPLINE

Stock-price scenarios must reflect both business outcomes and valuation.

When practical, mentally anchor the scenarios to plausible 5-year outcomes for one or more of:
- revenue
- earnings
- EBITDA
- free cash flow
- book value
- margins
- capital intensity

Then apply a reasonable terminal valuation consistent with:
- company maturity
- growth
- business quality
- cyclicality
- competitive position
- leverage
- financing needs
- industry characteristics
- risk

Do not produce price ranges that require unrealistic revenue growth, margin expansion, market share, capital efficiency, or valuation multiples.

Use the current stock price only to judge what optimism or pessimism is already priced in. Do not mechanically center scenarios around the current price.

If the stock already reflects optimistic assumptions:
- constrain Base upside;
- reduce Bull probability when appropriate;
- or require stronger operating outcomes to justify Bull.

If the company is speculative, loss-making, capital-intensive, highly leveraged, or dependent on external financing, require stronger evidence before assigning high Bull probability.

SCENARIO REALISM

- Bull must be optimistic but plausible, not aspirational.
- Bear must be pessimistic but plausible, not automatically catastrophic.
- Do not let speculative optionality or long-shot TAM expansion dominate unless supported by strong current evidence.
- Outcomes requiring near-perfect execution across several variables should receive low probability.
- Greater uncertainty should generally produce wider ranges and/or lower probability for extreme outcomes.
- Distinguish business quality from stock attractiveness.

CORE EVIDENCE PACK AND FRESH INFORMATION

A Core Evidence Pack is supplied with the company input.

It contains recent factual research gathered once for this analysis and should be treated as the common factual baseline for all scenario passes.

Use the Core Evidence Pack to avoid unnecessarily rediscovering information that has already been established.

However, the Core Evidence Pack is not guaranteed to be exhaustive.

You may perform as much additional independent research as you determine is necessary when:
- important information is missing;
- a fact needs verification;
- more recent evidence may exist;
- conflicting evidence exists;
- a material competitive, regulatory, financial, operational, or valuation consideration is not adequately represented;
- or additional evidence is needed to properly evaluate one of the supplied key variables.

Each scenario analysis must independently judge the relevance and implications of the evidence.

Do not assume that conclusions implied by the Core Evidence Pack are correct merely because the information is shared. The pack should primarily contain facts; scenario interpretation remains your responsibility.

Prioritize:
1. primary company disclosures;
2. regulatory filings;
3. factual recent developments materially relevant to the key variables;
4. industry or analyst commentary only when it contributes material evidence or valuation context.

Do not turn the analysis into an earnings recap.

Focus on information that materially affects durable 5-year drivers such as:
- revenue trajectory
- margins
- free cash flow
- backlog or contracts
- pricing power
- unit economics
- customer concentration
- competitive position
- capital intensity
- leverage or financing risk
- regulatory risk
- valuation

Treat management commentary cautiously. Give greater weight to hard financial data, guidance, margins, cash flow, demand, backlog, and operating metrics than to promotional language.

Guidance matters more than backward-looking quarterly results when it changes the durable trajectory.

Examples:
- Beat + unchanged guidance = usually confirmation.
- Beat + reduced guidance = reason for caution.
- Miss + raised guidance may still support the thesis if durable forward drivers improve.

ASSUMPTIONS FIELD

The assumptions field must be a concise 5-year thesis summary, ideally 2 to 4 sentences.

It should explain:
1. the main durable drivers likely to determine 5-year value;
2. the main constraints or risks that limit upside or increase downside.

The assumptions field must:
- be driven primarily by the most important Core Drivers;
- mention important Potential Drivers only when they materially shape Bull/Bear optionality;
- avoid becoming a quarterly earnings summary;
- avoid listing many short-term metrics;
- explain causally why the Bear, Base, and Bull outcomes differ.

ETF RULE

If the supplied symbol represents an ETF, center the analysis on the performance drivers, risks, and concentration of its major holdings rather than treating it like an operating company.

COMPANY INPUT

Symbol: $Symbol
Company name: $CompanyName
Current price: $Price USD

Business model:
$BusinessModel

Key variables:
$KeyVariables

Core Evidence Pack:
$CoreEvidencePack"""

DEFAULT_PROMPT_RECENT_EVENT_CANDIDATE = """You are an equity analyst assistant preparing candidate recent events for later thesis-review analysis.

Company context:
- Symbol: $Symbol
- Company name: $CompanyName
- Current price: $Price USD
- Business model: $BusinessModel
- Key variables: $KeyVariables

Search context:
- Only consider events after this cutoff date/time: $EventSearchCutoff

Task:
Identify recent company-specific candidate events that may be relevant for later thesis review.

Definitions:
- A candidate event is a recent company-specific development that could potentially matter to the business, key variables, or scenario outlook, but this step should not yet decide whether an alert must be created.
- Focus on collecting structured event candidates and their sources.
- Ignore events older than the cutoff.
- Ignore generic market commentary unless it is clearly company-specific.

Guidance:
- Look for company-specific developments such as:
  - earnings or guidance changes
  - major customer wins or losses
  - large contracts or backlog changes
  - acquisitions or divestitures
  - financing, dilution, or capital raising
  - product launches or technical milestones
  - regulatory decisions central to the business
  - major competitive developments
  - management changes if clearly material
- Prefer primary or highly reliable sources when available.
- If multiple sources describe the same event, include them under the same candidate event rather than creating duplicates.
- Keep summaries concise and factual.

Return ONLY valid JSON in this exact structure:
{
  "symbol": "$Symbol",
  "event_candidates": [
    {
      "event_title": "text",
      "event_summary": "text",
      "event_date": "YYYY-MM-DD",
      "event_sources": [
        {
          "title": "text",
          "url": "text",
          "source_name": "text",
          "published_at": "YYYY-MM-DD"
        }
      ]
    }
  ]
}

Rules:
- Return only events newer than the cutoff.
- Do not create duplicate candidate events for the same underlying development.
- event_summary should be concise and factual.
- event_sources should include the most relevant supporting sources available.
- This step should identify candidates only, not decide whether an alert should be created.
- If no relevant candidate events are found, return an empty event_candidates array.
- JSON only.
- No markdown.
- No commentary outside JSON."""

DEFAULT_PROMPT_RECENT_EVENT_CHECK = """You are an equity analyst reviewing whether recent company-specific event candidates may materially affect an existing 5-year stock thesis.

Company context:
- Symbol: $Symbol
- Company name: $CompanyName
- Current price: $Price USD
- Business model: $BusinessModel
- Key variables: $KeyVariables
- Event candidates: $EventCandidates

Task:
Review the provided recent event candidates and determine whether any should trigger a manual thesis-review alert.

Definitions:
- A thesis-review alert should be created only if an event candidate may materially strengthen, weaken, challenge, or add to the current 5-year key-variable framework.
- Material means the event could plausibly affect revenue growth, margins, cash flow, valuation, capital needs, competitive position, or scenario probabilities over a multi-year horizon.
- Do not create alerts for short-term noise that does not change the long-term thesis.

Guidance:
- Check whether each candidate event:
  - strengthens an existing key variable
  - weakens an existing key variable
  - suggests a missing key variable
  - suggests that a current key variable has become less relevant
- Focus on thesis impact, not general news summarization.
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
      "suggested_action": "text",
      "event_date": "YYYY-MM-DD",
      "event_sources": [
        {
          "title": "text",
          "url": "text",
          "source_name": "text",
          "published_at": "YYYY-MM-DD"
        }
      ]
    }
  ]
}

Rules:
- Return only alerts for material thesis-impacting event candidates.
- If no material event is found, return an empty alerts array.
- alert_type must be exactly one of:
  - Strengthens existing variable
  - Weakens existing variable
  - Potential new variable
  - Potentially obsolete variable
- affected_variables should list the impacted current variable text(s) when applicable.
- Keep event_summary and impact_summary concise.
- If the alert strengthens or weakens an existing variable, include in suggested_action a concise recommendation on whether confidence and/or importance should be reviewed.
- Do not modify the variables directly.
- Base the analysis only on the provided candidate events and their sources.
- JSON only.
- No markdown.
- No commentary outside JSON."""

DEFAULT_PROMPT_EARNINGS_WATCHPOINTS = """You are helping maintain an investment thesis after future earnings releases.

Your task is to generate “Earnings Watchpoints” from the current thesis for $Symbol ($CompanyName).

Business context:
$BusinessModel

Current key variables:
$KeyVariables

Instructions:
- For each key variable, generate only the most relevant and high-signal earnings watchpoints.
- The number of watchpoints must vary naturally depending on the variable.
- Some variables may justify only 1–2 meaningful watchpoints. Others may justify more.
- Do NOT aim for consistency in count across variables.
- Do NOT add extra watchpoints for balance or completeness.

Core objective:
- Generate watchpoints that are easy to evaluate later from earnings materials.
- Each watchpoint should be designed so that, after earnings, it can realistically be classified as:
  - Confirmed
  - Partially confirmed
  - Contradicted
  - Not addressed
  - Unclear

Key watchpoint design rules:
- Each watchpoint must be directly linked to the specific key variable and reflect how that variable would be validated or challenged during an earnings release.
- Each watchpoint should represent one main observable signal.
- Strongly prefer a single clear metric, trend, disclosure, or management commentary topic per watchpoint.
- Avoid combining multiple independent ideas into one watchpoint.
- Avoid writing watchpoints that require several separate disclosures to be fully satisfied.
- If a concept has two or three distinct observable parts, prefer splitting them into separate watchpoints rather than combining them into one.
- A good watchpoint should be specific enough to evaluate, but not so narrow that it depends on a disclosure the company rarely provides or on a metric being explicitly labeled in a specific way.

- Prefer watchpoints that can be evaluated from either:
  - directly disclosed earnings metrics, or
  - simple calculations from standard disclosed earnings data (for example, revenue, deliveries, margins, deployments, customer counts, backlog, guidance tables, or similar standard company-reported operating metrics).
- Avoid watchpoints that depend on management explicitly presenting a custom metric if the same concept could be tracked through a more standard disclosed signal.
- When possible, phrase the watchpoint around the underlying business signal rather than requiring a company-specific label.

Use only realistically observable earnings information:
- Focus ONLY on information that can realistically and consistently be observed in:
  - earnings releases
  - shareholder letters
  - management commentary / earnings calls
  - company-provided guidance
  - company-provided tables, KPI summaries, charts, and operating metric disclosures

Strongly prefer watchpoints based on:
- commonly reported metrics (revenue growth, margins, bookings, ARR, deliveries, deployments, churn/retention, customer counts, etc.)
- management commentary (demand, pipeline, pricing, customer behavior, deal dynamics, adoption, ramp timing)
- forward guidance (raised, maintained, lowered expectations)
- product adoption, commercial rollout, or pricing signals that are typically discussed
- trends that can be inferred from disclosed operating or financial data

Avoid weak watchpoints:
- Avoid watchpoints that depend on information companies rarely disclose explicitly (for example: detailed internal splits, exact pipeline composition, precise unit economics, or very specific internal cost allocations).
- Avoid watchpoints that are too broad to evaluate cleanly.
- Avoid watchpoints that are too narrow to be realistically discussed in most earnings cycles.
- Avoid generic items such as “watch revenue” unless clearly tied to the key variable.
- Avoid repeating the same idea with different wording.
- Avoid watchpoints that merely restate the key variable without identifying a concrete earnings signal.
- Avoid watchpoints that require both an exact metric and a separate explicit management statement if either one alone would already provide a meaningful earnings signal.
- Avoid writing watchpoints that become untestable unless management discloses a very specific internal breakdown.
- Prefer observable signals that can be assessed from standard earnings tables, KPI summaries, and guidance disclosures.

Forward-looking emphasis:
- Include forward-looking elements when relevant, especially:
  - changes in guidance
  - management tone about future demand, growth, margins, adoption, or timing
  - confirmation or revision of previously stated expectations
- Guidance-related watchpoints are encouraged when they are one of the clearest ways to validate the variable.

Usability requirements:
- Prefer concise, high-signal wording that is easy to scan in a UI.
- Prefer fewer, stronger watchpoints over exhaustive coverage.
- Each watchpoint should be useful later for re-evaluating the related key variable.
- If a watchpoint would likely lead to a vague later conclusion, do not generate it.
- If multiple candidate watchpoints are closely related, keep only the strongest one unless separate evaluation would clearly add value.

Examples of strong watchpoint style:
- a disclosed trend in a key operating metric
- a change in a directly relevant margin or growth metric
- management commentary on demand, pricing, adoption, or ramp timing
- a change in company guidance relevant to the variable

Examples of weak watchpoint style:
- a watchpoint that asks for three unrelated disclosures at once
- a watchpoint that depends on a metric rarely disclosed
- a watchpoint that is so generic it could apply to almost any company
- a watchpoint that cannot later be evaluated cleanly from earnings materials

Do not generate overall earnings summaries.
Do not evaluate outcomes yet.
Only generate watchpoints to monitor in a future earnings review.

Output requirements:
- Return valid JSON only.
- Use this structure:

{
  "watchpoints_by_variable": [
    {
      "key_variable": "exact key variable text",
      "type": "Bullish or Bearish if known, otherwise empty string",
      "watchpoints": [
        "watchpoint 1",
        "watchpoint 2"
      ]
    }
  ]
}

Rules:
- Preserve the exact key variable text when possible.
- Ensure each watchpoint is concrete, observable, and realistically checkable in earnings materials.
- Ensure each watchpoint focuses on one main observable signal.
- Prefer fewer, stronger watchpoints over exhaustive lists.
- If only one or two watchpoints truly matter, return only those.
- Do not force symmetry across variables.
- Make sure the output is specific to the company and thesis provided.
- If multiple watchpoints are closely related, consolidate them into a single stronger watchpoint instead of listing them separately.
- Do not generate a watchpoint that mainly depends on information the company is unlikely to disclose during normal earnings materials.
- Prefer watchpoints that remain evaluable even if the company provides the relevant signal through standard tables or disclosed inputs rather than through explicit narrative commentary."""

DEFAULT_PROMPT_EARNINGS_WATCHPOINT_ANALYSIS = """You are reviewing an investment thesis after an earnings release.

Your task is to evaluate the existing Earnings Watchpoints for $Symbol ($CompanyName) using the uploaded earnings documents.

Business context:
$BusinessModel

Key variables:
$KeyVariables

Earnings watchpoints:
$EarningsWatchpoints

Uploaded earnings documents:
$EarningsDocuments

Instructions:
- Evaluate each watchpoint using only the information available in the uploaded earnings documents.
- Return exactly one result for each provided watchpoint_id.
- Preserve watchpoint_id exactly as provided.
- Do not omit any watchpoint_id and do not add extra watchpoint_ids.
- For each watchpoint, assign exactly one of these statuses:
  - Confirmed
  - Partially confirmed
  - Contradicted
  - Not addressed
  - Unclear

Core interpretation rules:
- Evaluate each watchpoint based on the substance of the information in the uploaded earnings documents, not exact wording.
- A watchpoint is considered addressed if the documents provide the underlying metric, fact, trend, table, chart, KPI, management statement, or standard disclosed inputs needed to evaluate it, even if the wording does not exactly match the watchpoint and even if the metric must be directly calculated or inferred from clearly disclosed data.
- Treat tables, charts, KPI summaries, operating metrics, financial summaries, and management commentary as valid sources for evaluating a watchpoint.
- Do not require the company to use the same labels or terminology as the watchpoint.
- If the documents contain enough information to evaluate at least one meaningful part of a watchpoint, do not classify it as “Not addressed” unless the uncovered portion is so material that no meaningful conclusion can be drawn.
- If a watchpoint asks for multiple elements and one important element is clearly disclosed while other elements are missing, prefer “Partially confirmed” over “Not addressed.”
- If the documents provide enough information to evaluate the main economic signal of the watchpoint, do not use “Not addressed” just because one secondary sub-element is missing.
- Use “Not addressed” only when the main economic signal itself cannot be evaluated from the uploaded documents.

Status definitions:
- Confirmed:
  The uploaded documents clearly support the watchpoint in substance.
- Partially confirmed:
  The uploaded documents support an important part of the watchpoint, but not all of it, or support it with meaningful caveats.
- Contradicted:
  The uploaded documents clearly go against the watchpoint in substance.
- Not addressed:
  The uploaded documents do not provide enough meaningful information to evaluate the watchpoint in substance.
- Unclear:
  The uploaded documents contain related information, but the signal is too ambiguous, mixed, or inconclusive to classify confidently.

Important decision rules:
- Prefer “Partially confirmed” over “Not addressed” when some meaningful part of the watchpoint is addressed.
- If a watchpoint contains multiple sub-points, do not classify it as “Not addressed” just because not every sub-point is covered.
- If one or more important parts are addressed but other parts are missing, use “Partially confirmed.”
- Use “Not addressed” only when the documents truly do not provide enough meaningful information to assess the watchpoint.
- Use “Unclear” only when the documents provide related information but the conclusion is genuinely ambiguous or mixed.
- Do not use “Unclear” because document text is unreadable or missing.
- If documents are unreadable, the system should fail before analysis.
- Be careful not to confuse “not explicitly labeled” with “not disclosed.” If the necessary business information is present in standard earnings materials, the watchpoint is addressed.

Result text requirements:
- Keep result_text concise, practical, and useful for later key-variable re-evaluation.
- result_text must not be generic.
- When available, include the actual disclosed fact, metric, trend, or management statement that drove the classification.
- When available, indicate directionality such as up, down, improved, weakened, accelerating, slowing, stronger, or softer.
- Briefly explain why the disclosed information supports, partially supports, contradicts, or fails to address the watchpoint.
- Prefer 1 to 2 short sentences.
- Do not quote the documents.
- Do not include evidence excerpts or document source references.
- Do not restate the entire watchpoint unless needed for clarity.
- When a watchpoint is evaluated using disclosed inputs rather than an explicitly labeled company metric, say so clearly in result_text.

Examples of good result_text:
- “The company disclosed the relevant operating metric and it improved versus the prior period, which supports this watchpoint.”
- “Management discussed part of this issue and provided directional commentary, but the documents did not include the full quantitative breakout, so the watchpoint is only partially confirmed.”
- “The disclosed trend moved in the opposite direction from what this watchpoint expected, so the watchpoint is contradicted.”
- “The documents did not provide enough meaningful disclosure on this topic to evaluate the watchpoint.”
- “The documents discussed the topic, but the signals were mixed and not conclusive enough to classify more confidently.”
- “The company disclosed the underlying revenue and volume inputs, which allow the relevant trend to be calculated even though the metric was not explicitly labeled.”
- “The documents addressed the main operating signal relevant to this watchpoint, but did not provide all requested sub-details, so the watchpoint is only partially confirmed.”

Examples of bad result_text:
- “The documents discuss this topic.”
- “This watchpoint was addressed.”
- “Metrics were provided.”
- “Relevant commentary was included.”
- “The materials mention this area.”

Scope rules:
- Do not re-evaluate the key variables yet.
- Do not re-run scenarios.
- Do not infer beyond what the uploaded documents reasonably support.
- Do not invent data not present in the uploaded documents.
- Focus only on evaluating the watchpoints.

Output requirements:
- Return valid JSON only.
- Use this structure:

{
  "watchpoint_results": [
    {
      "watchpoint_id": "exact watchpoint_id from input",
      "key_variable": "exact key variable text",
      "watchpoint": "exact watchpoint text",
      "status": "Confirmed",
      "result_text": "Short evaluation text explaining the outcome."
    }
  ]
}

Rules:
- Preserve watchpoint_id exactly as provided.
- Preserve the exact watchpoint text when possible.
- Keep result_text concise, ideally 1 to 2 short sentences.
- Make sure every existing watchpoint receives exactly one result.
- Do not omit any watchpoint_id.
- Do not add extra watchpoint_ids.
- Do not invent data not present in the uploaded documents.
- Do not default to “Not addressed” just because the company did not disclose the exact metric wording requested.
- When the documents provide the underlying fact, trend, table, chart, KPI, or management disclosure needed to assess the watchpoint, treat the watchpoint as addressed.
- When a watchpoint is classified as Confirmed, Partially confirmed, or Contradicted, make the result_text specific enough to help a later re-evaluation of the related key variable.
- Do not classify a watchpoint as “Not addressed” when the uploaded documents provide standard disclosed inputs that clearly allow the main trend or conclusion to be calculated or reasonably inferred."""


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
        "required_vars": ["$Symbol", "$CompanyName", "$BusinessModel", "$KeyVariables", "$CoreEvidencePack"],
    },
    ANALYSIS_PROMPT_SETTING_KEY_CORE_EVIDENCE_PACK: {
        "default": DEFAULT_PROMPT_CORE_EVIDENCE_PACK,
        "required_vars": ["$Symbol", "$CompanyName", "$Price", "$BusinessModel", "$KeyVariables"],
    },
    ANALYSIS_PROMPT_SETTING_KEY_RECENT_EVENT_CANDIDATE: {
        "default": DEFAULT_PROMPT_RECENT_EVENT_CANDIDATE,
        "required_vars": ["$Symbol", "$CompanyName", "$Price", "$BusinessModel", "$KeyVariables", "$EventSearchCutoff"],
    },
    ANALYSIS_PROMPT_SETTING_KEY_RECENT_EVENT_CHECK: {
        "default": DEFAULT_PROMPT_RECENT_EVENT_CHECK,
        "required_vars": ["$Symbol", "$CompanyName", "$Price", "$BusinessModel", "$KeyVariables", "$EventCandidates"],
    },
    ANALYSIS_PROMPT_SETTING_KEY_EARNINGS_WATCHPOINTS: {
        "default": DEFAULT_PROMPT_EARNINGS_WATCHPOINTS,
        "required_vars": ["$Symbol", "$CompanyName", "$BusinessModel", "$KeyVariables"],
    },
    ANALYSIS_PROMPT_SETTING_KEY_EARNINGS_WATCHPOINT_ANALYSIS: {
        "default": DEFAULT_PROMPT_EARNINGS_WATCHPOINT_ANALYSIS,
        "required_vars": [
            "$Symbol",
            "$CompanyName",
            "$BusinessModel",
            "$KeyVariables",
            "$EarningsWatchpoints",
            "$EarningsDocuments",
        ],
    },
}

ANALYSIS_WORKFLOW_PROMPT_KEYS = (
    ANALYSIS_PROMPT_SETTING_KEY_BUSINESS_MODEL,
    ANALYSIS_PROMPT_SETTING_KEY_KEY_VARIABLES,
    ANALYSIS_PROMPT_SETTING_KEY_CORE_EVIDENCE_PACK,
    ANALYSIS_PROMPT_SETTING_KEY_SCENARIOS,
)

RECENT_EVENT_WORKFLOW_PROMPT_KEYS = (
    ANALYSIS_PROMPT_SETTING_KEY_RECENT_EVENT_CANDIDATE,
    ANALYSIS_PROMPT_SETTING_KEY_RECENT_EVENT_CHECK,
)

EARNINGS_REVIEW_WORKFLOW_PROMPT_KEYS = (
    ANALYSIS_PROMPT_SETTING_KEY_EARNINGS_WATCHPOINTS,
    ANALYSIS_PROMPT_SETTING_KEY_EARNINGS_WATCHPOINT_ANALYSIS,
)



LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s - %(message)s"

_ib = None
logger = logging.getLogger(__name__)


def configure_bakingmoney_logging(level=logging.INFO, force=False):
    logging.basicConfig(level=level, format=LOG_FORMAT, force=force)
    logger.setLevel(level)
    logger.propagate = True


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


def is_valid_market_price(value):
    numeric = safe_number(value)
    return numeric is not None and numeric > 0


def normalize_market_price(value):
    numeric = safe_number(value)
    if not is_valid_market_price(numeric):
        return None
    return safe_number(numeric)


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
        market_price = normalize_market_price(ticker.marketPrice())
    return first_valid_number(
        normalize_market_price(market_price),
        normalize_market_price(getattr(ticker, "last", None)),
        normalize_market_price(getattr(ticker, "close", None)),
        normalize_market_price(getattr(ticker, "prevClose", None)),
    )


def extract_close(ticker):
    if not ticker:
        return None
    return first_valid_number(
        normalize_market_price(getattr(ticker, "close", None)),
        normalize_market_price(getattr(ticker, "prevClose", None)),
    )


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


def compute_cost_basis(position_row):
    if not isinstance(position_row, dict):
        return None
    qty = safe_number(position_row.get("position"))
    avg_cost = safe_number(position_row.get("avgCost"))
    if qty is None or avg_cost is None:
        return None
    return abs(qty * avg_cost)


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


def _is_probably_sqlite_file(path):
    try:
        with open(path, "rb") as handle:
            header = handle.read(16)
        return header == b"SQLite format 3\x00"
    except OSError:
        return False


def _validate_backup_db_file(path):
    if not _is_probably_sqlite_file(path):
        raise ValueError("Uploaded file is not a valid SQLite database file")

    conn = sqlite3.connect(path)
    try:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        missing_tables = [name for name in BACKUP_REQUIRED_TABLES if name not in tables]
        if missing_tables:
            raise ValueError(f"Backup is missing required table(s): {', '.join(missing_tables)}")

        integrity_row = conn.execute("PRAGMA integrity_check").fetchone()
        integrity_result = integrity_row[0] if integrity_row else ""
        if str(integrity_result).lower() != "ok":
            raise ValueError("SQLite integrity_check failed for uploaded backup")

        current_schema_version = conn.execute("PRAGMA user_version").fetchone()[0]
        if current_schema_version < 0:
            raise ValueError("Invalid SQLite schema version in uploaded backup")
    finally:
        conn.close()


def _create_db_backup_snapshot(source_path, destination_path):
    source_conn = sqlite3.connect(source_path)
    destination_conn = sqlite3.connect(destination_path)
    try:
        source_conn.backup(destination_conn)
    finally:
        destination_conn.close()
        source_conn.close()


def _build_backup_manifest(includes_env):
    schema_version = 0
    conn = None
    try:
        conn = get_db_connection()
        row = conn.execute("PRAGMA user_version").fetchone()
        schema_version = int(row[0]) if row else 0
    except Exception:
        schema_version = 0
    finally:
        if conn:
            conn.close()
    return {
        "app_name": "BakingMoney",
        "exported_at": utc_now_iso(),
        "schema_version": schema_version,
        "includes_env": bool(includes_env),
    }


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


def get_all_prompt_templates(conn, purpose="prompt_configuration_ui"):
    return get_prompt_templates_for_keys(conn, PROMPT_TEMPLATE_CONFIG.keys(), purpose=purpose)


def get_prompt_templates_for_keys(conn, keys, purpose="custom"):
    templates = {}
    sources = {}
    resolved_keys = tuple(keys)
    logger.info("Resolving prompt templates purpose=%s keys=%s", purpose, ",".join(resolved_keys))
    for key in resolved_keys:
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


def _score_or_none(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _confidence_pair_or_fallback(primary_bullish, primary_bearish, fallback_bullish, fallback_bearish):
    bullish = _score_or_none(primary_bullish)
    bearish = _score_or_none(primary_bearish)
    if bullish is not None and bearish is not None:
        return bullish, bearish, bullish - bearish

    fallback_bullish_value = _score_or_none(fallback_bullish)
    fallback_bearish_value = _score_or_none(fallback_bearish)
    if fallback_bullish_value is None:
        fallback_bullish_value = 0.0
    if fallback_bearish_value is None:
        fallback_bearish_value = 0.0
    return fallback_bullish_value, fallback_bearish_value, fallback_bullish_value - fallback_bearish_value


def calculate_rating(upside, bullish_confidence, bearish_confidence, rating_settings, confidence_context=None):
    confidence_context = confidence_context or {}
    upside_value = _coerce_score(upside)

    combined_bullish_value = _coerce_score(bullish_confidence)
    combined_bearish_value = _coerce_score(bearish_confidence)
    combined_confidence_diff = combined_bullish_value - combined_bearish_value

    core_bullish_value, core_bearish_value, core_confidence_diff = _confidence_pair_or_fallback(
        confidence_context.get("core_bullish_confidence"),
        confidence_context.get("core_bearish_confidence"),
        bullish_confidence,
        bearish_confidence,
    )
    potential_bullish_value = _score_or_none(confidence_context.get("potential_bullish_confidence"))
    potential_bearish_value = _score_or_none(confidence_context.get("potential_bearish_confidence"))
    potential_confidence_diff = None
    if potential_bullish_value is not None and potential_bearish_value is not None:
        potential_confidence_diff = potential_bullish_value - potential_bearish_value

    if (
        upside_value >= rating_settings[RATING_SETTING_STRONG_BUY_MIN_UPSIDE]
        and core_confidence_diff >= rating_settings[RATING_SETTING_STRONG_BUY_MIN_DIFF]
        and core_bullish_value >= rating_settings[RATING_SETTING_STRONG_BUY_MIN_BULLISH_CONFIDENCE]
    ):
        return "Strong Buy", combined_confidence_diff

    if (
        upside_value >= rating_settings[RATING_SETTING_BUY_MIN_UPSIDE]
        and core_confidence_diff >= rating_settings[RATING_SETTING_BUY_MIN_DIFF]
        and core_bullish_value >= rating_settings[RATING_SETTING_BUY_MIN_BULLISH_CONFIDENCE]
    ):
        return "Buy", combined_confidence_diff

    if (
        upside_value <= rating_settings[RATING_SETTING_STRONG_SELL_MAX_UPSIDE]
        and core_confidence_diff <= rating_settings[RATING_SETTING_STRONG_SELL_MAX_DIFF]
        and core_bearish_value >= rating_settings[RATING_SETTING_STRONG_SELL_MIN_BEARISH_CONFIDENCE]
    ):
        return "Strong Sell", combined_confidence_diff

    if (
        upside_value <= rating_settings[RATING_SETTING_SELL_MAX_UPSIDE]
        and core_confidence_diff <= rating_settings[RATING_SETTING_SELL_MAX_DIFF]
        and core_bearish_value >= rating_settings[RATING_SETTING_SELL_MIN_BEARISH_CONFIDENCE]
    ):
        return "Sell", combined_confidence_diff

    speculative_core_path = (
        core_confidence_diff >= rating_settings[RATING_SETTING_SPECULATIVE_BUY_MIN_DIFF]
        and core_bullish_value >= rating_settings[RATING_SETTING_SPECULATIVE_BUY_MIN_BULLISH_CONFIDENCE]
    )
    speculative_potential_path = (
        potential_confidence_diff is not None
        and potential_bullish_value is not None
        and potential_confidence_diff >= rating_settings[RATING_SETTING_SPECULATIVE_BUY_MIN_DIFF]
        and potential_bullish_value >= rating_settings[RATING_SETTING_SPECULATIVE_BUY_MIN_BULLISH_CONFIDENCE]
    )
    if (
        upside_value >= rating_settings[RATING_SETTING_SPECULATIVE_BUY_MIN_UPSIDE]
        and core_confidence_diff >= rating_settings[RATING_SETTING_SPECULATIVE_BUY_MIN_CORE_DIFF_FLOOR]
        and (speculative_core_path or speculative_potential_path)
    ):
        return "Speculative Buy", combined_confidence_diff

    # Phase 4: the low-conviction guardrail intentionally remains after the
    # Speculative Buy check so it cannot short-circuit valid speculative cases.
    max_confidence = max(core_bullish_value, core_bearish_value, combined_bullish_value, combined_bearish_value)
    if max_confidence < rating_settings[RATING_SETTING_MIN_CONVICTION_HOLD_THRESHOLD]:
        return "Hold", combined_confidence_diff

    return "Hold", combined_confidence_diff


def get_rating_settings(conn):
    settings = {}
    for key, default in DEFAULT_RATING_SETTINGS.items():
        settings[key] = get_float_setting(conn, key, default, minimum=-10000.0, maximum=10000.0)

    for confidence_key in (
        RATING_SETTING_MIN_CONVICTION_HOLD_THRESHOLD,
        RATING_SETTING_STRONG_BUY_MIN_BULLISH_CONFIDENCE,
        RATING_SETTING_BUY_MIN_BULLISH_CONFIDENCE,
        RATING_SETTING_SPECULATIVE_BUY_MIN_BULLISH_CONFIDENCE,
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


def _safe_probability_number(value, default=0.0):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _key_variable_type_for_probability(item):
    return item.get("variable_type") or item.get("type")


def calculate_effective_potential_driver_probability_weight(
    key_variables,
    max_weight=POTENTIAL_DRIVER_BACKEND_PROBABILITY_MAX_WEIGHT,
    confidence_floor=POTENTIAL_DRIVER_BACKEND_PROBABILITY_CONFIDENCE_FLOOR,
):
    potential_confidences = []
    potential_importances = []
    for item in key_variables or []:
        if safe_driver_category(item.get("driver_category")) != "Potential Driver":
            continue
        potential_confidences.append(_safe_probability_number(item.get("confidence")))
        potential_importances.append(_safe_probability_number(item.get("importance")))

    if not potential_confidences:
        return {
            "effective_potential_driver_probability_weight": 0.0,
            "median_potential_confidence": None,
            "median_potential_importance": None,
        }

    median_confidence = statistics.median(potential_confidences)
    median_importance = statistics.median(potential_importances)
    if median_confidence < confidence_floor:
        effective_weight = 0.0
    else:
        effective_weight = float(max_weight) * (median_confidence / 10.0) * (median_importance / 10.0)
    effective_weight = max(0.0, min(float(max_weight), effective_weight))
    return {
        "effective_potential_driver_probability_weight": effective_weight,
        "median_potential_confidence": median_confidence,
        "median_potential_importance": median_importance,
    }


def compute_backend_probability_details(key_variables, base_max, base_min):
    weight_meta = calculate_effective_potential_driver_probability_weight(key_variables)
    potential_weight = weight_meta["effective_potential_driver_probability_weight"]
    core_bull_score = 0.0
    core_bear_score = 0.0
    potential_bull_raw_score = 0.0
    potential_bear_raw_score = 0.0

    for item in key_variables or []:
        confidence = _safe_probability_number(item.get("confidence"))
        importance = _safe_probability_number(item.get("importance"))
        score = confidence * importance
        variable_type = _key_variable_type_for_probability(item)
        category = safe_driver_category(item.get("driver_category"))
        if category == "Potential Driver":
            if variable_type == "Bullish":
                potential_bull_raw_score += score
            elif variable_type == "Bearish":
                potential_bear_raw_score += score
        elif variable_type == "Bullish":
            core_bull_score += score * CORE_DRIVER_BACKEND_PROBABILITY_WEIGHT
        elif variable_type == "Bearish":
            core_bear_score += score * CORE_DRIVER_BACKEND_PROBABILITY_WEIGHT

    potential_bull_weighted_score = potential_bull_raw_score * potential_weight
    potential_bear_weighted_score = potential_bear_raw_score * potential_weight
    bull_score = core_bull_score + potential_bull_weighted_score
    bear_score = core_bear_score + potential_bear_weighted_score

    total = bull_score + bear_score
    if total <= 0:
        probabilities = {"Bear": 20.0, "Base": 60.0, "Bull": 20.0}
    else:
        bull_share = bull_score / total
        bear_share = bear_score / total
        imbalance = abs(bull_share - bear_share)
        base = float(base_max) - imbalance * (float(base_max) - float(base_min))
        base = max(0.0, min(100.0, base))
        remaining = max(0.0, 100.0 - base)
        bull = remaining * bull_share
        bear = remaining * bear_share
        probabilities = normalize_probabilities({"Bear": bear, "Base": base, "Bull": bull})

    return {
        "probabilities": probabilities,
        "meta": {
            **weight_meta,
            "core_driver_backend_probability_weight": CORE_DRIVER_BACKEND_PROBABILITY_WEIGHT,
            "potential_driver_backend_probability_max_weight": POTENTIAL_DRIVER_BACKEND_PROBABILITY_MAX_WEIGHT,
            "potential_driver_backend_probability_confidence_floor": POTENTIAL_DRIVER_BACKEND_PROBABILITY_CONFIDENCE_FLOOR,
            "core_bull_score": core_bull_score,
            "core_bear_score": core_bear_score,
            "potential_bull_raw_score": potential_bull_raw_score,
            "potential_bear_raw_score": potential_bear_raw_score,
            "potential_bull_weighted_score": potential_bull_weighted_score,
            "potential_bear_weighted_score": potential_bear_weighted_score,
            "bull_score": bull_score,
            "bear_score": bear_score,
        },
    }


def compute_backend_probabilities(key_variables, base_max, base_min):
    return compute_backend_probability_details(key_variables, base_max, base_min)["probabilities"]


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


def get_action_plan_numeric_setting(conn, key, default):
    raw = _get_setting_value(conn, key)
    if raw is None:
        return float(default)
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return float(default)
    if not math.isfinite(value):
        return float(default)
    return value


def get_action_plan_settings(conn):
    settings = {}
    for key, default in ACTION_PLAN_DEFAULT_SETTINGS.items():
        if key in ACTION_PLAN_BOOL_SETTINGS:
            settings[key] = get_bool_setting(conn, key, bool(default))
        elif key in ACTION_PLAN_TEXT_SETTINGS:
            raw = _get_setting_value(conn, key)
            settings[key] = str(raw if raw is not None else default)
        else:
            settings[key] = get_action_plan_numeric_setting(conn, key, float(default))
    legacy_tolerance = safe_number(_get_setting_value(conn, "linear_target_band_tolerance_pct"))
    if legacy_tolerance is not None:
        if _get_setting_value(conn, "linear_add_band_tolerance_pct") is None:
            settings["linear_add_band_tolerance_pct"] = legacy_tolerance
        if _get_setting_value(conn, "linear_trim_band_tolerance_pct") is None:
            settings["linear_trim_band_tolerance_pct"] = max(legacy_tolerance, ACTION_PLAN_DEFAULT_SETTINGS["linear_trim_band_tolerance_pct"])

    min_key = "linear_high_bearish_confidence_min_threshold"
    max_key = "linear_high_bearish_confidence_max_threshold"
    legacy_key = "linear_high_bearish_confidence_threshold"
    raw_min = _get_setting_value(conn, min_key)
    raw_max = _get_setting_value(conn, max_key)
    raw_legacy = _get_setting_value(conn, legacy_key)

    def finite_setting_value(raw):
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return None
        return value if math.isfinite(value) else None

    legacy_value = finite_setting_value(raw_legacy)
    if raw_legacy is not None and legacy_value is None:
        logger.warning("Invalid legacy %s setting; using progressive bearish-cap defaults", legacy_key)
    if raw_min is not None and finite_setting_value(raw_min) is None:
        logger.warning("Invalid %s setting; using the safe default", min_key)
    if raw_max is not None and finite_setting_value(raw_max) is None:
        logger.warning("Invalid %s setting; using the safe default", max_key)
    if raw_min is None and legacy_value is not None:
        settings[min_key] = legacy_value
    if raw_max is None and legacy_value is not None:
        settings[max_key] = legacy_value
    if settings[min_key] > settings[max_key]:
        logger.warning(
            "Invalid progressive bearish-cap thresholds (%s > %s); using defaults",
            settings[min_key],
            settings[max_key],
        )
        settings[min_key] = ACTION_PLAN_DEFAULT_SETTINGS[min_key]
        settings[max_key] = ACTION_PLAN_DEFAULT_SETTINGS[max_key]
    return settings


def validate_action_plan_settings(settings):
    if not isinstance(settings, dict):
        raise ValueError("action_plan_settings must be an object")
    effective = {**ACTION_PLAN_DEFAULT_SETTINGS, **settings}
    legacy_bearish_key = "linear_high_bearish_confidence_threshold"
    min_bearish_key = "linear_high_bearish_confidence_min_threshold"
    max_bearish_key = "linear_high_bearish_confidence_max_threshold"
    legacy_bearish_compatibility = (
        min_bearish_key not in settings
        and max_bearish_key not in settings
        and legacy_bearish_key in settings
    )
    if legacy_bearish_compatibility:
        effective[min_bearish_key] = settings[legacy_bearish_key]
        effective[max_bearish_key] = settings[legacy_bearish_key]
    if "linear_add_band_tolerance_pct" not in settings:
        legacy_tolerance = safe_number(settings.get("linear_target_band_tolerance_pct"))
        if legacy_tolerance is not None:
            effective["linear_add_band_tolerance_pct"] = legacy_tolerance
    if "linear_trim_band_tolerance_pct" not in settings:
        legacy_tolerance = safe_number(settings.get("linear_target_band_tolerance_pct"))
        if legacy_tolerance is not None:
            effective["linear_trim_band_tolerance_pct"] = max(legacy_tolerance, ACTION_PLAN_DEFAULT_SETTINGS["linear_trim_band_tolerance_pct"])
    if "linear_rating_bonus_enabled" in settings and not isinstance(settings.get("linear_rating_bonus_enabled"), bool):
        raise ValueError("linear_rating_bonus_enabled must be boolean")
    if "linear_block_buy_actions_for_hold_rating" in settings and not isinstance(settings.get("linear_block_buy_actions_for_hold_rating"), bool):
        raise ValueError("linear_block_buy_actions_for_hold_rating must be boolean")
    if "linear_high_extension_guardrail_enabled" in settings and not isinstance(settings.get("linear_high_extension_guardrail_enabled"), bool):
        raise ValueError("linear_high_extension_guardrail_enabled must be boolean")
    for key, default in ACTION_PLAN_DEFAULT_SETTINGS.items():
        if key in ACTION_PLAN_BOOL_SETTINGS or key in ACTION_PLAN_TEXT_SETTINGS:
            if key in ACTION_PLAN_TEXT_SETTINGS:
                raw_symbols = str(effective.get(key, "") or "")
                normalized_symbols = sorted({normalize_symbol(part) for part in raw_symbols.split(",") if normalize_symbol(part)})
                effective[key] = ",".join(normalized_symbols)
            continue
        try:
            value = float(effective[key])
        except (TypeError, ValueError):
            raise ValueError(f"{key} must be numeric")
        if not math.isfinite(value):
            raise ValueError(f"{key} must be finite")
        if value < 0 and key not in {"action_core_diff_zero_score", "action_core_diff_full_score", "action_trim_remaining_upside_threshold", "action_sell_remaining_upside_threshold", "linear_reserve_benchmark_yield_pct", "linear_min_equity_excess_cagr_pct", "linear_full_attractiveness_equity_excess_cagr_pct", "linear_min_core_net", "linear_min_potential_net", "linear_low_core_net_threshold", "core_confidence_penalty_threshold", "potential_confidence_penalty_threshold", "linear_strong_buy_rating_bonus", "linear_buy_rating_bonus", "linear_frontier_optionality_max_boost_pct", "linear_score_allocation_power", "linear_add_band_tolerance_pct", "linear_trim_band_tolerance_pct"}:
            raise ValueError(f"{key} cannot be negative")
        effective[key] = value

    for min_key, full_key in (
        ("linear_min_equity_excess_cagr_pct", "linear_full_attractiveness_equity_excess_cagr_pct"),
        ("linear_min_expected_cagr", "linear_full_expected_cagr"),
        ("linear_min_upside", "linear_full_upside"),
        ("linear_min_core_net", "linear_full_core_net"),
        ("linear_min_potential_net", "linear_full_potential_net"),
    ):
        if effective[full_key] <= effective[min_key]:
            raise ValueError(f"{full_key} must be greater than {min_key}")
    if effective["action_min_cash_unallocated_target"] < 0.0 or effective["action_min_cash_unallocated_target"] > 100.0:
        raise ValueError("action_min_cash_unallocated_target must be between 0 and 100")
    for key in ("core_confidence_penalty", "upside_penalty", "potential_confidence_penalty", "hold_rating_penalty", "linear_strong_buy_rating_bonus", "linear_buy_rating_bonus"):
        if effective[key] < 0 or effective[key] > 1:
            raise ValueError(f"{key} must be between 0 and 1")
    if effective["linear_frontier_optionality_max_boost_pct"] < 0.0 or effective["linear_frontier_optionality_max_boost_pct"] > 20.0:
        raise ValueError("linear_frontier_optionality_max_boost_pct must be between 0 and 20")

    linear_weight_total = sum(effective[key] for key in (
        "linear_expected_cagr_weight",
        "linear_upside_weight",
        "linear_core_confidence_weight",
        "linear_potential_confidence_weight",
        "linear_confidence_quality_weight",
    ))
    if linear_weight_total <= 0:
        raise ValueError("Linear Allocation weights must total more than 0")
    for key in (
        "linear_allocated_target_total_pct",
        "linear_max_reserve_pct",
        "linear_max_single_stock_pct",
        "linear_target_band_tolerance_pct",
        "linear_add_band_tolerance_pct",
        "linear_trim_band_tolerance_pct",
        "linear_negative_core_net_cap_pct",
        "linear_low_core_net_cap_pct",
        "linear_high_bearish_confidence_cap_pct",
    ):
        if effective[key] < 0.0 or effective[key] > 100.0:
            raise ValueError(f"{key} must be between 0 and 100")
    if effective["linear_release_date_warning_days"] < 0 or effective["linear_release_date_warning_days"] > 365 or not effective["linear_release_date_warning_days"].is_integer():
        raise ValueError("linear_release_date_warning_days must be a whole number between 0 and 365")
    if effective["action_min_cash_unallocated_target"] > effective["linear_max_reserve_pct"]:
        raise ValueError("linear_max_reserve_pct must be greater than or equal to action_min_cash_unallocated_target")
    if effective["linear_score_allocation_power"] < 0.5 or effective["linear_score_allocation_power"] > 5.0:
        raise ValueError("linear_score_allocation_power must be between 0.5 and 5.0")
    for threshold_key in (min_bearish_key, max_bearish_key):
        if effective[threshold_key] < 0.0 or effective[threshold_key] > 10.0:
            raise ValueError(f"{threshold_key} must be between 0 and 10")
    if effective[min_bearish_key] > effective[max_bearish_key] or (
        effective[min_bearish_key] == effective[max_bearish_key]
        and not legacy_bearish_compatibility
    ):
        raise ValueError(
            "linear_high_bearish_confidence_max_threshold must be greater than "
            "linear_high_bearish_confidence_min_threshold"
        )
    if effective["linear_high_extension_risk_threshold"] < 0.0 or effective["linear_high_extension_risk_threshold"] > 5.0:
        raise ValueError("linear_high_extension_risk_threshold must be between 0 and 5")
    if effective["action_upside_full_score"] <= effective["action_upside_zero_score"]:
        raise ValueError("action_upside_full_score must be greater than action_upside_zero_score")
    if effective["action_core_diff_full_score"] <= effective["action_core_diff_zero_score"]:
        raise ValueError("action_core_diff_full_score must be greater than action_core_diff_zero_score")
    if effective["action_core_bearish_penalty_full"] <= effective["action_core_bearish_penalty_start"]:
        raise ValueError("action_core_bearish_penalty_full must be greater than action_core_bearish_penalty_start")
    if effective["action_potential_diff_full_score"] <= effective["action_potential_diff_minimum"]:
        raise ValueError("action_potential_diff_full_score must be greater than action_potential_diff_minimum")
    allocation_weight_total = sum(effective[key] for key in (
        "action_allocation_upside_weight",
        "action_allocation_core_weight",
        "action_allocation_potential_weight",
    ))
    if allocation_weight_total <= 0:
        raise ValueError("Allocation weights must total more than 0")
    if effective["action_allocation_risk_penalty_strength"] > 1.0:
        raise ValueError("action_allocation_risk_penalty_strength must be between 0 and 1")
    for key in (
        "action_starter_buy_base_required_upside",
        "action_add_base_required_upside",
        "action_strong_add_base_required_upside",
        "action_hold_extra_add_required_upside",
    ):
        if effective[key] > 2.0:
            raise ValueError(f"{key} must be between 0 and 2")
    for key in ("action_trim_remaining_upside_threshold", "action_sell_remaining_upside_threshold"):
        if effective[key] < -1.0 or effective[key] > 2.0:
            raise ValueError(f"{key} must be between -1 and 2")
    for key in (
        "action_underweight_discount_max",
        "action_quality_discount_max",
        "action_overweight_penalty_max",
        "action_low_quality_penalty_max",
        "action_strong_trim_gap_threshold",
    ):
        if effective[key] > 1.0:
            raise ValueError(f"{key} must be between 0 and 1")
    for key in (
        "action_momentum_add_max_raise",
        "action_momentum_add_max_lower",
        "action_extension_add_max_lower",
        "action_momentum_trim_max_raise",
        "action_momentum_trim_max_lower",
        "action_extension_trim_max_lower",
    ):
        if effective[key] < 0.0 or effective[key] > 1.0:
            raise ValueError(f"{key} must be between 0 and 1")
    if effective["action_min_trigger_multiplier"] <= 0.0 or effective["action_min_trigger_multiplier"] > 1.0:
        raise ValueError("action_min_trigger_multiplier must be > 0 and <= 1")
    if effective["action_max_trigger_multiplier"] < 1.0 or effective["action_max_trigger_multiplier"] > 2.0:
        raise ValueError("action_max_trigger_multiplier must be >= 1 and <= 2")
    if effective["action_max_trigger_multiplier"] <= effective["action_min_trigger_multiplier"]:
        raise ValueError("action_max_trigger_multiplier must be greater than action_min_trigger_multiplier")
    if effective["action_trigger_max_required_upside"] <= effective["action_trigger_min_required_upside"]:
        raise ValueError("action_trigger_max_required_upside must be greater than action_trigger_min_required_upside")
    if effective["action_target_band_lower_multiplier"] >= 1.0:
        raise ValueError("action_target_band_lower_multiplier must be >= 0 and < 1")
    if effective["action_target_band_upper_multiplier"] <= 1.0:
        raise ValueError("action_target_band_upper_multiplier must be greater than 1")
    for key in (
        "action_band_lower_multiplier",
        "action_band_upper_multiplier",
        "action_target_band_lower_multiplier",
        "action_target_band_upper_multiplier",
        "action_speculative_band_lower_multiplier",
        "action_speculative_band_upper_multiplier",
        "action_strong_add_below_target_multiplier",
        "action_strong_trim_above_target_multiplier",
    ):
        if effective[key] <= 0:
            raise ValueError(f"{key} must be greater than 0")
    if effective.get("action_use_dynamic_bucket_sizing", True):
        if effective["action_min_cash_unallocated_target"] > 50.0:
            raise ValueError("action_min_cash_unallocated_target must be between 0 and 50")
        if effective["action_weighted_count_full_score"] <= effective["action_weighted_count_min_score"]:
            raise ValueError("action_weighted_count_full_score must be greater than action_weighted_count_min_score")
        if effective["action_weighted_count_min_score"] > 1.0 or effective["action_weighted_count_full_score"] > 1.0:
            raise ValueError("weighted count score thresholds must be between 0 and 1")
        if effective["action_weighted_count_max_contribution"] <= 0 or effective["action_weighted_count_max_contribution"] > 1.0:
            raise ValueError("action_weighted_count_max_contribution must be > 0 and <= 1")
        if effective["action_max_potential_score_contribution"] > 1.0:
            raise ValueError("action_max_potential_score_contribution must be between 0 and 1")
        bucket_sizing_weight_total = sum(effective[key] for key in (
            "action_bucket_sizing_upside_weight",
            "action_bucket_sizing_core_weight",
            "action_bucket_sizing_potential_weight",
        ))
        if bucket_sizing_weight_total <= 0:
            raise ValueError("Bucket sizing weights must total more than 0")
        if effective["action_bucket_sizing_risk_penalty_strength"] > 1.0:
            raise ValueError("action_bucket_sizing_risk_penalty_strength must be between 0 and 1")
        for bucket_key in ("strong_buy", "buy", "speculative_buy", "hold"):
            for suffix in ("weight_per_effective_stock", "max_effective_count"):
                if effective[f"action_{bucket_key}_{suffix}"] < 0:
                    raise ValueError(f"action_{bucket_key}_{suffix} must be >= 0")
            if effective[f"action_{bucket_key}_max_bucket_target"] > 100.0:
                raise ValueError(f"action_{bucket_key}_max_bucket_target must be between 0 and 100")
            if effective[f"action_{bucket_key}_compression_weight"] <= 0:
                raise ValueError(f"action_{bucket_key}_compression_weight must be > 0")
    else:
        bucket_total = sum(float(effective[key]) for key in ACTION_PLAN_BUCKET_KEYS.values()) + float(effective["action_bucket_cash_target"])
        if bucket_total > 100.0 + 1e-9:
            raise ValueError("Action Plan bucket targets cannot total more than 100%")
    return effective


def save_action_plan_settings(conn, settings, now=None):
    now = now or utc_now_iso()
    effective = validate_action_plan_settings(settings)
    for key in ACTION_PLAN_DEFAULT_SETTINGS:
        if key not in settings:
            continue
        value = effective[key]
        if key in ACTION_PLAN_BOOL_SETTINGS:
            stored = "1" if value else "0"
        else:
            stored = str(value)
        conn.execute(
            """
            INSERT INTO app_settings (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
              value = excluded.value,
              updated_at = excluded.updated_at
            """,
            (key, stored, now),
        )


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
        "use_tws_data": get_bool_setting(
            conn,
            ANALYSIS_SETTING_USE_TWS_DATA,
            False,
        ),
        "ib_price_wait_seconds": get_float_setting(
            conn,
            ANALYSIS_SETTING_IB_PRICE_WAIT_SECONDS,
            DEFAULT_IB_PRICE_WAIT_SECONDS,
            minimum=1.0,
            maximum=30.0,
        ),
        "ib_delayed_price_extra_wait_seconds": get_float_setting(
            conn,
            ANALYSIS_SETTING_IB_DELAYED_PRICE_EXTRA_WAIT_SECONDS,
            DEFAULT_IB_DELAYED_PRICE_EXTRA_WAIT_SECONDS,
            minimum=0.0,
            maximum=30.0,
        ),
        "scenario_multi_pass_enabled": scenario["scenario_multi_pass_enabled"],
        "scenario_pass_count": scenario["scenario_pass_count"],
        "scenario_outlier_filter_enabled": scenario["scenario_outlier_filter_enabled"],
        "rating_settings": get_rating_settings(conn),
        "scenario_probability_settings": get_scenario_probability_settings(conn),
        "action_plan_settings": get_action_plan_settings(conn),
    }


def save_general_configuration(conn, settings):
    if not isinstance(settings, dict):
        raise ValueError("settings must be an object")

    now = utc_now_iso()
    if "use_tws_data" in settings:
        requested = bool(settings["use_tws_data"])
        effective = requested
        if requested:
            try:
                ib = get_ib_connection()
                effective = bool(ib and ib.isConnected())
            except Exception:
                logger.warning("Unable to enable use_tws_data because TWS/IBKR is unavailable")
                effective = False
        conn.execute(
            """
            INSERT INTO app_settings (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
              value = excluded.value,
              updated_at = excluded.updated_at
            """,
            (ANALYSIS_SETTING_USE_TWS_DATA, "1" if effective else "0", now),
        )

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

    if "ib_delayed_price_extra_wait_seconds" in settings:
        try:
            delayed_wait_seconds = float(settings.get("ib_delayed_price_extra_wait_seconds"))
        except (TypeError, ValueError):
            raise ValueError("ib_delayed_price_extra_wait_seconds must be numeric")
        if not math.isfinite(delayed_wait_seconds):
            raise ValueError("ib_delayed_price_extra_wait_seconds must be finite")
        if delayed_wait_seconds < 0 or delayed_wait_seconds > 30:
            raise ValueError("ib_delayed_price_extra_wait_seconds must be between 0 and 30")
        conn.execute(
            """
            INSERT INTO app_settings (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
              value = excluded.value,
              updated_at = excluded.updated_at
            """,
            (ANALYSIS_SETTING_IB_DELAYED_PRICE_EXTRA_WAIT_SECONDS, str(delayed_wait_seconds), now),
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
                RATING_SETTING_SPECULATIVE_BUY_MIN_BULLISH_CONFIDENCE,
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

    action_plan_settings_payload = settings.get("action_plan_settings")
    if action_plan_settings_payload is not None:
        save_action_plan_settings(conn, action_plan_settings_payload, now=now)

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


def get_ib_delayed_price_extra_wait_seconds():
    try:
        conn = get_db_connection()
        try:
            return get_float_setting(
                conn,
                ANALYSIS_SETTING_IB_DELAYED_PRICE_EXTRA_WAIT_SECONDS,
                DEFAULT_IB_DELAYED_PRICE_EXTRA_WAIT_SECONDS,
                minimum=0.0,
                maximum=30.0,
            )
        finally:
            conn.close()
    except Exception:
        return DEFAULT_IB_DELAYED_PRICE_EXTRA_WAIT_SECONDS


def is_tws_data_enabled():
    try:
        conn = get_db_connection()
        try:
            return get_bool_setting(conn, ANALYSIS_SETTING_USE_TWS_DATA, False)
        finally:
            conn.close()
    except Exception:
        return False


def get_ib_market_data_batch_size():
    raw = os.getenv("IB_MARKET_DATA_BATCH_SIZE", str(DEFAULT_IB_MARKET_DATA_BATCH_SIZE))
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_IB_MARKET_DATA_BATCH_SIZE
    return max(1, min(90, value))


def batched(items, size):
    step = max(1, int(size or 1))
    for idx in range(0, len(items), step):
        yield items[idx : idx + step]


def classify_ib_market_data_error(code, message):
    text = str(message or "")
    if code == 10167:
        return {
            "severity": "warning",
            "fatal": False,
            "reason": "Delayed market data warning; waiting for delayed price",
            "delayed": True,
        }
    if code == 10090:
        return {
            "severity": "warning",
            "fatal": False,
            "reason": "Partial/delayed market data warning; waiting for available price",
            "delayed": True,
        }
    if code == 10089:
        return {
            "severity": "error",
            "fatal": True,
            "reason": "Market data subscription/API permission issue",
            "delayed": False,
        }
    if code == 200 or "contract" in text.lower() and "not found" in text.lower():
        return {
            "severity": "error",
            "fatal": True,
            "reason": "Contract not found",
            "delayed": False,
        }
    return {
        "severity": "warning",
        "fatal": False,
        "reason": "TWS market data warning",
        "delayed": False,
    }


def make_price_skip_detail(symbol, warning=None):
    if isinstance(warning, dict):
        return {
            "symbol": symbol,
            "reason": warning.get("reason") or "No valid market price returned before timeout",
            "error_code": warning.get("error_code"),
            "message": warning.get("message") or "No marketPrice, last, close, or previous close available",
            "severity": warning.get("severity") or "warning",
            "fatal": bool(warning.get("fatal")),
            "source": warning.get("source"),
        }
    return {
        "symbol": symbol,
        "reason": warning or "No valid market price returned before timeout",
        "error_code": None,
        "message": "No marketPrice, last, close, or previous close available",
        "severity": "warning",
        "fatal": False,
        "source": None,
    }


def _ticker_price_source(ticker):
    if not ticker:
        return None
    if hasattr(ticker, "marketPrice") and normalize_market_price(ticker.marketPrice()) is not None:
        return "marketPrice"
    for field in ("last", "close", "prevClose"):
        if normalize_market_price(getattr(ticker, field, None)) is not None:
            return field
    return None


def _safe_cancel_market_data(ib, contract, purpose):
    try:
        ib.cancelMktData(contract)
        logger.debug(
            "Cancelled IBKR market data purpose=%s conid=%s symbol=%s",
            purpose,
            getattr(contract, "conId", None),
            getattr(contract, "symbol", None),
        )
    except Exception as exc:
        message = str(exc)
        if "No reqId found" in message:
            logger.debug("Ignoring stale IBKR cancelMktData request purpose=%s symbol=%s", purpose, getattr(contract, "symbol", None))
        else:
            logger.warning("Unable to cancel IBKR market data purpose=%s symbol=%s error=%s", purpose, getattr(contract, "symbol", None), message)


def request_ib_tickers_batched(ib, qualified_contracts, purpose):
    if not qualified_contracts:
        return [], {}

    batch_size = get_ib_market_data_batch_size()
    batches = list(batched(list(qualified_contracts), batch_size))
    logger.info(
        "IBKR market data request purpose=%s contracts=%s batch_size=%s batches=%s",
        purpose,
        len(qualified_contracts),
        batch_size,
        len(batches),
    )

    tickers = []
    diagnostics = {}
    for batch_idx, batch in enumerate(batches, start=1):
        logger.info(
            "IBKR market data batch purpose=%s index=%s/%s size=%s",
            purpose,
            batch_idx,
            len(batches),
            len(batch),
        )
        batch_symbol_by_req_id = {}
        batch_symbols = {normalize_symbol(getattr(contract, "symbol", None)) for contract in batch}
        delayed_warning_seen = False

        def handle_error(req_id, code, message, contract=None):
            nonlocal delayed_warning_seen
            symbol = None
            if req_id in batch_symbol_by_req_id:
                symbol = batch_symbol_by_req_id.get(req_id)
            if not symbol and contract is not None:
                symbol = normalize_symbol(getattr(contract, "symbol", None))
            classification = classify_ib_market_data_error(code, message)
            delayed_warning_seen = delayed_warning_seen or bool(classification.get("delayed"))
            if symbol and (symbol in batch_symbols):
                previous = diagnostics.get(symbol)
                detail = {
                    "symbol": symbol,
                    "error_code": code,
                    "message": str(message or ""),
                    "severity": classification["severity"],
                    "fatal": classification["fatal"],
                    "reason": classification["reason"],
                    "source": "tws_error_event",
                    "delayed": classification["delayed"],
                }
                if previous is None or (detail["fatal"] and not previous.get("fatal")):
                    diagnostics[symbol] = detail
            logger.info(
                "IBKR market data event purpose=%s req_id=%s code=%s symbol=%s fatal=%s message=%s",
                purpose,
                req_id,
                code,
                symbol or "unknown",
                classification["fatal"],
                message,
            )

        subscribed = False
        if hasattr(ib, "errorEvent"):
            try:
                ib.errorEvent += handle_error
                subscribed = True
            except Exception:
                subscribed = False
        try:
            if hasattr(ib, "reqMktData"):
                batch_tickers = []
                for contract in batch:
                    ticker = ib.reqMktData(contract, "", False, False)
                    ticker_contract = getattr(ticker, "contract", None) or contract
                    if getattr(ticker, "contract", None) is None:
                        try:
                            ticker.contract = ticker_contract
                        except Exception:
                            pass
                    req_id = getattr(ticker, "tickerId", None)
                    symbol = normalize_symbol(getattr(ticker_contract, "symbol", None))
                    if req_id is not None and symbol:
                        batch_symbol_by_req_id[req_id] = symbol
                    batch_tickers.append(ticker)
                base_wait = get_ib_price_wait_seconds()
                extra_wait = get_ib_delayed_price_extra_wait_seconds()
                deadline = time.monotonic() + base_wait
                extended_deadline = deadline + extra_wait
                unresolved = set(range(len(batch_tickers)))
                while unresolved and time.monotonic() < (extended_deadline if delayed_warning_seen else deadline):
                    for idx in list(unresolved):
                        if extract_price(batch_tickers[idx]) is not None:
                            unresolved.remove(idx)
                    if unresolved:
                        ib.sleep(0.25)
                tickers.extend(batch_tickers)
            else:
                batch_tickers = ib.reqTickers(*batch)
                ib.sleep(get_ib_price_wait_seconds())
                tickers.extend(batch_tickers or [])
        finally:
            if subscribed:
                try:
                    ib.errorEvent -= handle_error
                except Exception:
                    pass
        for contract in batch:
            _safe_cancel_market_data(ib, contract, purpose)
    return tickers, diagnostics


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


def migrate_legacy_default_prompt_templates(conn):
    row = conn.execute("SELECT value FROM app_settings WHERE key = ?", (ANALYSIS_PROMPT_SETTING_KEY_SCENARIOS,)).fetchone()
    if row and row["value"] == LEGACY_DEFAULT_PROMPT_SCENARIOS:
        conn.execute(
            """
            UPDATE app_settings
            SET value = ?, updated_at = ?
            WHERE key = ?
            """,
            (DEFAULT_PROMPT_SCENARIOS, utc_now_iso(), ANALYSIS_PROMPT_SETTING_KEY_SCENARIOS),
        )
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
    supported_placeholders = ("$Symbol", "$CompanyName", "$Price", "$BusinessModel", "$KeyVariables", "$CoreEvidencePack")
    substitution_context = {
        placeholder: str(values.get(placeholder, ""))
        for placeholder in supported_placeholders
    }
    return render_prompt_template(template, substitution_context)


def render_recent_event_prompt(template, values):
    """Render recent-event prompt from configured template using placeholder substitution only."""
    supported_placeholders = ("$Symbol", "$CompanyName", "$Price", "$BusinessModel", "$KeyVariables", "$EventSearchCutoff", "$EventCandidates")
    substitution_context = {
        placeholder: str(values.get(placeholder, ""))
        for placeholder in supported_placeholders
    }
    return render_prompt_template(template, substitution_context)


def normalized_driver_category(value):
    return normalize_driver_category(value)


def safe_driver_category(value):
    try:
        return normalized_driver_category(value)
    except AnalysisValidationError:
        return "Core Driver"


def normalize_key_variables_for_payload(key_variables):
    normalized = []
    for item in key_variables or []:
        if not isinstance(item, dict):
            continue
        variable_text = item.get("variable_text") or item.get("variable") or ""
        variable_type = item.get("variable_type") or item.get("type") or "Bullish"
        driver_category = safe_driver_category(item.get("driver_category"))
        normalized.append(
            {
                "variable_text": variable_text,
                "variable_type": variable_type,
                "driver_category": driver_category,
                "confidence": item.get("confidence"),
                "importance": item.get("importance"),
            }
        )
    return normalized


def format_key_variables_for_prompt(key_variables):
    return json.dumps(normalize_key_variables_for_payload(key_variables), separators=(",", ":"), ensure_ascii=False)


def serialize_core_evidence_pack_for_prompt(core_evidence_pack):
    if not isinstance(core_evidence_pack, dict):
        raise AnalysisValidationError("Core Evidence Pack is required before scenario generation")
    return json.dumps(core_evidence_pack, ensure_ascii=False, indent=2, sort_keys=True)


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


def build_prompt_context(
    symbol,
    price=None,
    company_name="",
    business_model="",
    business_summary="",
    key_variables=None,
    event_search_cutoff="",
    event_candidates="",
    earnings_watchpoints="",
    earnings_documents="",
    core_evidence_pack=None,
):

    symbol_value = symbol or "unknown"
    price_value = f"{price:.2f}" if isinstance(price, (int, float)) and math.isfinite(price) else "unknown"
    company_name_value = company_name or "unknown"
    business_value = build_business_model_prompt_value(business_model=business_model, business_summary=business_summary)
    key_vars_value = format_key_variables_for_prompt(key_variables or [])
    event_candidates_value = event_candidates
    if not isinstance(event_candidates_value, str):
        event_candidates_value = json.dumps(event_candidates_value or [], separators=(",", ":"), ensure_ascii=False)
    core_evidence_value = ""
    if core_evidence_pack is not None:
        core_evidence_value = serialize_core_evidence_pack_for_prompt(core_evidence_pack)
    return {
        "$Symbol": symbol_value,
        "$Price": price_value,
        "$CompanyName": company_name_value,
        "$BusinessModel": business_value,
        "$KeyVariables": key_vars_value,
        "$EventSearchCutoff": str(event_search_cutoff or ""),
        "$EventCandidates": event_candidates_value,
        "$EarningsWatchpoints": str(earnings_watchpoints or ""),
        "$EarningsDocuments": str(earnings_documents or ""),
        "$CoreEvidencePack": core_evidence_value,
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
              expected_cagr REAL,
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
              price_mid REAL,
              price_high REAL NOT NULL,
              cagr_low REAL NOT NULL,
              cagr_mid REAL,
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
              driver_category TEXT NOT NULL DEFAULT 'Core Driver',
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
              expected_cagr REAL,
              upside REAL,
              confidence_level REAL,
              assumptions_text TEXT,
              business_model_text TEXT,
              business_summary_text TEXT,
              raw_ai_response TEXT,
              core_evidence_pack_json TEXT,
              core_evidence_generated_at TEXT,
              core_evidence_model TEXT,
              core_evidence_reasoning_effort TEXT,
              core_evidence_telemetry_json TEXT,
              scenario_generation_wall_duration_ms REAL,
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
              price_mid REAL,
              price_high REAL NOT NULL,
              cagr_low REAL NOT NULL,
              cagr_mid REAL,
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
              driver_category TEXT NOT NULL DEFAULT 'Core Driver',
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
              telemetry_json TEXT,
              created_at TEXT NOT NULL,
              FOREIGN KEY (analysis_version_id) REFERENCES analysis_versions(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS analysis_external_scenarios (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              analysis_version_id INTEGER NOT NULL,
              title TEXT NOT NULL,
              source_notes TEXT,
              external_weight REAL NOT NULL,
              scenarios_json TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY (analysis_version_id) REFERENCES analysis_versions(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_analysis_external_scenarios_version
            ON analysis_external_scenarios(analysis_version_id)
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS analysis_final_scenario_overlays (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              analysis_version_id INTEGER NOT NULL UNIQUE,
              bakingmoney_weight REAL NOT NULL,
              external_total_weight REAL NOT NULL,
              final_scenarios_json TEXT NOT NULL,
              expected_price REAL,
              expected_cagr REAL,
              upside REAL,
              recalculated_at TEXT NOT NULL,
              is_stale INTEGER NOT NULL DEFAULT 0,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
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
            CREATE TABLE IF NOT EXISTS analysis_frontier_optionality (
              symbol TEXT PRIMARY KEY,
              frontier_optionality_score REAL NOT NULL DEFAULT 0,
              frontier_optionality_notes TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY (symbol) REFERENCES analysis_roots(symbol) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS earnings_watchpoint_sets (
              symbol TEXT PRIMARY KEY,
              generated_at TEXT NOT NULL,
              prompt_key TEXT NOT NULL,
              prompt_source TEXT,
              prompt_used TEXT,
              raw_response_json TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY (symbol) REFERENCES analysis_roots(symbol) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS earnings_watchpoints (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              symbol TEXT NOT NULL,
              key_variable_text TEXT NOT NULL,
              key_variable_type TEXT,
              watchpoints_json TEXT NOT NULL,
              display_order INTEGER NOT NULL DEFAULT 0,
              generated_at TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY (symbol) REFERENCES analysis_roots(symbol) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_earnings_watchpoints_symbol_variable
            ON earnings_watchpoints(symbol, key_variable_text)
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS earnings_reviews (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              symbol TEXT NOT NULL,
              company_name_snapshot TEXT,
              fiscal_year INTEGER NOT NULL,
              fiscal_quarter TEXT NOT NULL,
              release_date TEXT,
              status TEXT NOT NULL,
              thesis_snapshot_json TEXT NOT NULL,
              watchpoints_generated_at TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY (symbol) REFERENCES analysis_roots(symbol) ON DELETE CASCADE,
              UNIQUE(symbol, fiscal_year, fiscal_quarter)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS earnings_review_symbols (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              symbol TEXT NOT NULL UNIQUE,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY (symbol) REFERENCES analysis_roots(symbol) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS earnings_review_watchpoints (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              earnings_review_id INTEGER NOT NULL,
              key_variable_text TEXT NOT NULL,
              key_variable_type TEXT,
              watchpoints_json TEXT NOT NULL,
              display_order INTEGER NOT NULL DEFAULT 0,
              generated_at TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY (earnings_review_id) REFERENCES earnings_reviews(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_earnings_review_watchpoints_unique
            ON earnings_review_watchpoints(earnings_review_id, key_variable_text)
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS earnings_review_documents (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              earnings_review_id INTEGER NOT NULL,
              original_file_name TEXT NOT NULL,
              storage_path TEXT NOT NULL,
              document_type TEXT NOT NULL,
              mime_type TEXT,
              file_size INTEGER,
              uploaded_at TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY (earnings_review_id) REFERENCES earnings_reviews(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS earnings_review_watchpoint_results (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              earnings_review_id INTEGER NOT NULL,
              key_variable_text TEXT NOT NULL,
              watchpoint_text TEXT NOT NULL,
              status TEXT NOT NULL,
              result_text TEXT NOT NULL,
              analysed_at TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY (earnings_review_id) REFERENCES earnings_reviews(id) ON DELETE CASCADE,
              UNIQUE(earnings_review_id, key_variable_text, watchpoint_text)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS earnings_release_schedule (
              symbol TEXT PRIMARY KEY,
              release_date TEXT,
              release_timing TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY (symbol) REFERENCES analysis_roots(symbol) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS earnings_release_calendar_exclusions (
              symbol TEXT PRIMARY KEY,
              created_at TEXT NOT NULL,
              FOREIGN KEY (symbol) REFERENCES analysis_roots(symbol) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS earnings_calendar_entries (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              symbol TEXT NOT NULL,
              fiscal_year INTEGER NOT NULL,
              fiscal_quarter TEXT NOT NULL CHECK (fiscal_quarter IN ('Q1', 'Q2', 'Q3', 'Q4')),
              release_date TEXT,
              release_timing TEXT CHECK (release_timing IS NULL OR release_timing IN ('Before Open', 'After Close')),
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              UNIQUE(symbol, fiscal_year, fiscal_quarter)
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_earnings_calendar_entries_symbol
            ON earnings_calendar_entries(symbol)
            """
        )
        conn.execute(
            """
            INSERT INTO earnings_review_symbols (symbol, created_at, updated_at)
            SELECT DISTINCT er.symbol, ?, ?
            FROM earnings_reviews er
            WHERE NOT EXISTS (
                SELECT 1 FROM earnings_review_symbols ers WHERE ers.symbol = er.symbol
            )
            """,
            (utc_now_iso(), utc_now_iso()),
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
            CREATE TABLE IF NOT EXISTS portfolio_summary_cache (
              id INTEGER PRIMARY KEY CHECK (id = 1),
              account_id TEXT,
              base_currency TEXT,
              net_liquidation REAL,
              total_cash_value REAL,
              settled_cash REAL,
              available_funds REAL,
              buying_power REAL,
              excess_liquidity REAL,
              ledger_cash_usd REAL,
              actual_cash REAL,
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
              event_sources_json TEXT,
              search_cutoff_used TEXT,
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
            CREATE TABLE IF NOT EXISTS recent_event_checks (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              symbol TEXT NOT NULL,
              checked_at TEXT NOT NULL,
              cutoff_used TEXT,
              alerts_created_count INTEGER NOT NULL DEFAULT 0,
              events_found_count INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS analysis_momentum_snapshots (
              symbol TEXT PRIMARY KEY,
              benchmark_symbol TEXT,
              duration TEXT,
              momentum_score REAL,
              momentum_label TEXT,
              extension_risk REAL,
              extension_label TEXT,
              momentum_status TEXT,
              warning TEXT,
              bars INTEGER,
              first_date TEXT,
              last_date TEXT,
              latest_close REAL,
              trend_score REAL,
              relative_strength_score REAL,
              volume_score REAL,
              price_structure_score REAL,
              metrics_json TEXT,
              components_json TEXT,
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
        ensure_column_exists(conn, "thesis_review_alerts", "event_sources_json", "TEXT")
        ensure_column_exists(conn, "thesis_review_alerts", "search_cutoff_used", "TEXT")
        ensure_column_exists(conn, "analysis_symbols", "company_name", "TEXT")
        ensure_column_exists(conn, "analysis_symbols", "business_model_text", "TEXT")
        ensure_column_exists(conn, "analysis_symbols", "business_summary_text", "TEXT")
        ensure_column_exists(conn, "analysis_symbols", "expected_cagr", "REAL")
        ensure_column_exists(conn, "analysis_versions", "expected_cagr", "REAL")
        ensure_column_exists(conn, "analysis_versions", "core_evidence_pack_json", "TEXT")
        ensure_column_exists(conn, "analysis_versions", "core_evidence_generated_at", "TEXT")
        ensure_column_exists(conn, "analysis_versions", "core_evidence_model", "TEXT")
        ensure_column_exists(conn, "analysis_versions", "core_evidence_reasoning_effort", "TEXT")
        ensure_column_exists(conn, "analysis_versions", "core_evidence_telemetry_json", "TEXT")
        ensure_column_exists(conn, "analysis_versions", "scenario_generation_wall_duration_ms", "REAL")
        ensure_column_exists(conn, "analysis_scenarios", "price_mid", "REAL")
        ensure_column_exists(conn, "analysis_scenarios", "cagr_mid", "REAL")
        ensure_column_exists(conn, "analysis_version_scenarios", "price_mid", "REAL")
        ensure_column_exists(conn, "analysis_version_scenarios", "cagr_mid", "REAL")
        ensure_column_exists(conn, "analysis_version_scenario_passes", "telemetry_json", "TEXT")
        ensure_column_exists(conn, "analysis_key_variables", "driver_category", "TEXT NOT NULL DEFAULT 'Core Driver'")
        ensure_column_exists(conn, "analysis_version_key_variables", "driver_category", "TEXT NOT NULL DEFAULT 'Core Driver'")
        ensure_column_exists(conn, "portfolio_summary_cache", "ledger_cash_usd", "REAL")
        ensure_column_exists(conn, "portfolio_summary_cache", "actual_cash", "REAL")
        migrate_legacy_default_prompt_templates(conn)

        has_roots = conn.execute("SELECT 1 FROM analysis_roots LIMIT 1").fetchone()
        if not has_roots:
            legacy_rows = conn.execute(
                """
                SELECT id, symbol, company_name, current_price, expected_price, expected_cagr, upside, overall_confidence,
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
                        analysis_root_id, version_number, symbol, company_name, current_price, expected_price, expected_cagr,
                        upside, confidence_level, assumptions_text, business_model_text, business_summary_text,
                        raw_ai_response, source_trigger, created_at
                    ) VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'legacy_migration', ?)
                    """,
                    (
                        root_id,
                        row["symbol"],
                        row["company_name"],
                        row["current_price"],
                        row["expected_price"],
                        row["expected_cagr"],
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
                    SELECT scenario_name, price_low, price_mid, price_high, cagr_low, cagr_mid, cagr_high, probability, created_at
                    FROM analysis_scenarios
                    WHERE analysis_symbol_id = ?
                    ORDER BY id ASC
                    """,
                    (row["id"],),
                ).fetchall()
                for scenario in legacy_scenarios:
                    enriched_scenario = enrich_scenario_with_midpoints(
                        {
                            "scenario_name": scenario["scenario_name"],
                            "price_low": scenario["price_low"],
                            "price_mid": scenario["price_mid"],
                            "price_high": scenario["price_high"],
                            "cagr_low": scenario.get("cagr_low"),
                            "cagr_mid": scenario.get("cagr_mid"),
                            "cagr_high": scenario.get("cagr_high"),
                            "probability": scenario["probability"],
                        },
                        current_price=row["current_price"],
                    )
                    conn.execute(
                        """
                        INSERT INTO analysis_version_scenarios (
                            analysis_version_id, scenario_name, price_low, price_mid, price_high, cagr_low,
                            cagr_mid, cagr_high, probability, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            version_id,
                            enriched_scenario["scenario_name"],
                            enriched_scenario["price_low"],
                            enriched_scenario.get("price_mid"),
                            enriched_scenario["price_high"],
                            enriched_scenario.get("cagr_low"),
                            enriched_scenario.get("cagr_mid"),
                            enriched_scenario.get("cagr_high"),
                            enriched_scenario["probability"],
                            scenario["created_at"] or root_created_at,
                        ),
                    )

                legacy_variables = conn.execute(
                    """
                    SELECT variable_text, variable_type, COALESCE(driver_category, 'Core Driver') AS driver_category, confidence, importance, created_at
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
                            analysis_version_id, variable_text, variable_type, driver_category, confidence,
                            importance, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            version_id,
                            variable["variable_text"],
                            variable["variable_type"],
                            variable["driver_category"],
                            variable["confidence"],
                            variable["importance"],
                            variable["created_at"] or root_created_at,
                        ),
                    )
        migrate_legacy_earnings_release_calendar(conn)
        conn.commit()
    finally:
        conn.close()



MOMENTUM_DEFAULT_BENCHMARK = "QQQ"
MOMENTUM_DEFAULT_DURATION = "1 Y"


def fetch_historical_daily_bars(symbol, duration=MOMENTUM_DEFAULT_DURATION):
    """Fetch daily historical TRADES bars from TWS/IBKR for deterministic momentum."""
    normalized_symbol = normalize_symbol(symbol)
    if not normalized_symbol:
        raise ValueError("symbol is required")
    ensure_event_loop()
    from ib_insync import Stock

    ib = get_ib_connection()
    contract = Stock(normalized_symbol, "SMART", "USD")
    qualified = ib.qualifyContracts(contract)
    request_contract = qualified[0] if qualified else contract
    bars = ib.reqHistoricalData(
        request_contract,
        endDateTime="",
        durationStr=duration or MOMENTUM_DEFAULT_DURATION,
        barSizeSetting="1 day",
        whatToShow="TRADES",
        useRTH=True,
        formatDate=1,
        keepUpToDate=False,
    )
    return [
        {
            "date": getattr(bar, "date", None),
            "open": safe_number(getattr(bar, "open", None)),
            "high": safe_number(getattr(bar, "high", None)),
            "low": safe_number(getattr(bar, "low", None)),
            "close": safe_number(getattr(bar, "close", None)),
            "volume": safe_number(getattr(bar, "volume", None)),
        }
        for bar in bars
    ]


def save_momentum_snapshot(conn, symbol, benchmark_symbol, duration, snapshot):
    now = utc_now_iso()
    metrics = snapshot.get("metrics") or {}
    components = snapshot.get("components") or {}
    conn.execute(
        """
        INSERT INTO analysis_momentum_snapshots (
          symbol, benchmark_symbol, duration, momentum_score, momentum_label, extension_risk, extension_label,
          momentum_status, warning, bars, first_date, last_date, latest_close, trend_score,
          relative_strength_score, volume_score, price_structure_score, metrics_json, components_json, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(symbol) DO UPDATE SET
          benchmark_symbol=excluded.benchmark_symbol,
          duration=excluded.duration,
          momentum_score=excluded.momentum_score,
          momentum_label=excluded.momentum_label,
          extension_risk=excluded.extension_risk,
          extension_label=excluded.extension_label,
          momentum_status=excluded.momentum_status,
          warning=excluded.warning,
          bars=excluded.bars,
          first_date=excluded.first_date,
          last_date=excluded.last_date,
          latest_close=excluded.latest_close,
          trend_score=excluded.trend_score,
          relative_strength_score=excluded.relative_strength_score,
          volume_score=excluded.volume_score,
          price_structure_score=excluded.price_structure_score,
          metrics_json=excluded.metrics_json,
          components_json=excluded.components_json,
          updated_at=excluded.updated_at
        """,
        (
            normalize_symbol(symbol),
            normalize_symbol(benchmark_symbol),
            duration,
            snapshot.get("momentum_score"),
            snapshot.get("momentum_label"),
            snapshot.get("extension_risk"),
            snapshot.get("extension_label"),
            snapshot.get("momentum_status"),
            snapshot.get("warning"),
            metrics.get("bars"),
            metrics.get("first_date"),
            metrics.get("last_date"),
            metrics.get("latest_close"),
            components.get("trend_score"),
            components.get("relative_strength_score"),
            components.get("volume_score"),
            components.get("price_structure_score"),
            json.dumps(metrics),
            json.dumps(components),
            now,
        ),
    )
    return now


def summarize_momentum_snapshot(symbol, snapshot, updated_at):
    return {
        "symbol": normalize_symbol(symbol),
        "momentum_score": snapshot.get("momentum_score"),
        "momentum_label": snapshot.get("momentum_label"),
        "extension_risk": snapshot.get("extension_risk"),
        "extension_label": snapshot.get("extension_label"),
        "momentum_status": snapshot.get("momentum_status"),
        "warning": snapshot.get("warning"),
        "updated_at": updated_at,
    }


def fetch_ib_prices(symbols, return_details=False):
    prices = {symbol: None for symbol in symbols}
    warnings = {symbol: None for symbol in symbols}
    price_sources = {symbol: None for symbol in symbols}
    diagnostics = {symbol: None for symbol in symbols}
    if not symbols:
        return {"prices": prices, "warnings": warnings, "price_sources": price_sources, "diagnostics": diagnostics, "skipped_symbols": []} if return_details else (prices, warnings)
    if not is_tws_data_enabled():
        logger.info("Skipping IBKR price fetch because use_tws_data is disabled symbols=%s", len(symbols))
        for symbol in symbols:
            warnings[symbol] = {
                "symbol": symbol,
                "reason": NO_PRICE_WARNING,
                "error_code": None,
                "message": "TWS data is disabled or unavailable",
                "severity": "warning",
                "fatal": False,
                "source": "tws_disabled",
            }
            diagnostics[symbol] = warnings[symbol]
        skipped_symbols = [make_price_skip_detail(symbol, warnings[symbol]) for symbol in symbols]
        if return_details:
            return {"prices": prices, "warnings": warnings, "price_sources": price_sources, "diagnostics": diagnostics, "skipped_symbols": skipped_symbols}
        return prices, {symbol: (detail.get("reason") if isinstance(detail, dict) else detail) for symbol, detail in warnings.items()}

    ensure_event_loop()
    from ib_insync import Stock

    try:
        ib = get_ib_connection()
        position_contracts_by_symbol = {}
        portfolio_price_by_symbol = {}
        try:
            for position in ib.positions():
                contract = getattr(position, "contract", None)
                contract_symbol = normalize_symbol(getattr(contract, "symbol", None))
                if contract and contract_symbol and contract_symbol not in position_contracts_by_symbol:
                    position_contracts_by_symbol[contract_symbol] = contract
        except Exception:
            position_contracts_by_symbol = {}
        try:
            for item in ib.portfolio():
                contract = getattr(item, "contract", None)
                symbol = normalize_symbol(getattr(contract, "symbol", None))
                market_price = normalize_market_price(getattr(item, "marketPrice", None))
                if symbol and market_price is not None:
                    portfolio_price_by_symbol[symbol] = market_price
        except Exception:
            portfolio_price_by_symbol = {}

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
            tickers, request_diagnostics = request_ib_tickers_batched(
                ib,
                qualified,
                purpose="price_fetch",
            )
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
                if symbol in request_diagnostics:
                    diagnostics[symbol] = request_diagnostics[symbol]
                if price is not None:
                    warnings[symbol] = None
                    if isinstance(request_diagnostics.get(symbol), dict) and request_diagnostics[symbol].get("delayed"):
                        price_sources[symbol] = "delayed_market_data"
                    else:
                        price_sources[symbol] = _ticker_price_source(ticker) or "market_data"
                elif symbol in request_diagnostics:
                    warnings[symbol] = request_diagnostics[symbol]
                if price is None:
                    raw_market_price = safe_number(ticker.marketPrice()) if hasattr(ticker, "marketPrice") else None
                    raw_last = safe_number(getattr(ticker, "last", None))
                    raw_close = safe_number(getattr(ticker, "close", None))
                    raw_prev_close = safe_number(getattr(ticker, "prevClose", None))
                    for invalid_candidate in (raw_market_price, raw_last, raw_close, raw_prev_close):
                        if invalid_candidate is not None and invalid_candidate <= 0:
                            logger.info("Ignoring invalid TWS price symbol=%s price=%s", symbol, invalid_candidate)
                    logger.info("Keeping previous valid price for symbol=%s", symbol)
                    if warnings[symbol] is None:
                        warnings[symbol] = {
                            "symbol": symbol,
                            "reason": "No valid market price returned before timeout",
                            "error_code": None,
                            "message": "No marketPrice, last, close, or previous close available",
                            "severity": "warning",
                            "fatal": False,
                            "source": "market_data_timeout",
                        }
                    diagnostics[symbol] = warnings[symbol]

        for symbol in symbols:
            if prices[symbol] is None and portfolio_price_by_symbol.get(symbol) is not None:
                prices[symbol] = portfolio_price_by_symbol[symbol]
                price_sources[symbol] = "portfolio_market_price_fallback"
                warnings[symbol] = None
            if prices[symbol] is None and warnings[symbol] is None:
                warnings[symbol] = {
                    "symbol": symbol,
                    "reason": "No valid market price returned before timeout",
                    "error_code": None,
                    "message": "No marketPrice, last, close, or previous close available",
                    "severity": "warning",
                    "fatal": False,
                    "source": "market_data_timeout",
                }
                diagnostics[symbol] = warnings[symbol]
    except Exception:
        logger.exception("Unable to fetch IBKR prices")
        for symbol in symbols:
            warnings[symbol] = {
                "symbol": symbol,
                "reason": NO_PRICE_WARNING,
                "error_code": None,
                "message": "IBKR/TWS price fetch failed",
                "severity": "error",
                "fatal": False,
                "source": "fetch_exception",
            }
            diagnostics[symbol] = warnings[symbol]

    skipped_symbols = [make_price_skip_detail(symbol, warnings[symbol]) for symbol in symbols if prices.get(symbol) is None]
    if return_details:
        return {
            "prices": prices,
            "warnings": warnings,
            "price_sources": price_sources,
            "diagnostics": diagnostics,
            "skipped_symbols": skipped_symbols,
        }
    return prices, {symbol: (detail.get("reason") if isinstance(detail, dict) else detail) for symbol, detail in warnings.items()}


def fetch_latest_historical_close(symbol):
    normalized_symbol = normalize_symbol(symbol)
    if not normalized_symbol:
        return None, {"reason": "Invalid symbol", "message": "Symbol could not be normalized"}
    if not is_tws_data_enabled():
        return None, {"reason": NO_PRICE_WARNING, "message": "TWS data is disabled or unavailable"}

    ensure_event_loop()
    from ib_insync import Stock

    try:
        ib = get_ib_connection()
        contracts = ib.qualifyContracts(Stock(normalized_symbol, "SMART", "USD"))
        if not contracts:
            return None, {"reason": "Contract not found", "message": "Unable to qualify contract for historical close fallback"}
        bars = ib.reqHistoricalData(
            contracts[0],
            endDateTime="",
            durationStr="5 D",
            barSizeSetting="1 day",
            whatToShow="TRADES",
            useRTH=True,
            formatDate=1,
            keepUpToDate=False,
        )
        for bar in reversed(list(bars or [])):
            close = normalize_market_price(getattr(bar, "close", None))
            if close is not None:
                return close, None
        return None, {"reason": "No valid historical close returned", "message": "Historical daily bars did not include a valid close"}
    except Exception as exc:
        logger.info("Historical close fallback failed symbol=%s error=%s", normalized_symbol, exc)
        return None, {"reason": "Historical close fallback failed", "message": str(exc)}


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


def build_scenario_generation_prompt(symbol, current_price=None, template=None, company_name="", business_model="", business_summary="", key_variables=None, core_evidence_pack=None):
    base_template = template if template is not None else DEFAULT_PROMPT_SCENARIOS
    context = build_prompt_context(
        symbol=symbol,
        price=current_price,
        company_name=company_name,
        business_model=business_model,
        business_summary=business_summary,
        key_variables=key_variables,
        core_evidence_pack=core_evidence_pack,
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


def build_openai_request_body(prompt_text, json_schema, reasoning_effort, supports_temperature, temperature, tool_type=None, model=None):
    request_model = model or OPENAI_MODEL
    body = {
        "model": request_model,
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


def get_ai_step_timeout(step_name, attempt=1):
    override = OPENAI_STEP_TIMEOUT_OVERRIDES.get(step_name, {})
    if attempt in override:
        return max(10.0, float(override[attempt]))
    if step_name in {"recent_event_check", "recent_event_candidates"}:
        return max(10.0, OPENAI_RECENT_EVENT_REQUEST_TIMEOUT_SECONDS)
    return max(10.0, OPENAI_REQUEST_TIMEOUT_SECONDS)


def get_openai_timeout_seconds_for_step(step_name):
    # Backward compatible shim.
    return get_ai_step_timeout(step_name, attempt=1)


class OpenAITelemetryError(RuntimeError):
    def __init__(self, message, telemetry=None):
        super().__init__(message)
        self.telemetry = telemetry or {}


def _finite_number_or_none(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return value
    return None


def _nested_usage_number(data, *paths):
    if not isinstance(data, dict):
        return None
    for path in paths:
        current = data
        for key in path:
            if not isinstance(current, dict) or key not in current:
                current = None
                break
            current = current[key]
        value = _finite_number_or_none(current)
        if value is not None:
            return value
    return None


def extract_openai_usage_telemetry(raw):
    usage = raw.get("usage") if isinstance(raw, dict) else {}
    if not isinstance(usage, dict):
        usage = {}
    return {
        "input_tokens": _nested_usage_number(usage, ("input_tokens",)),
        "cached_input_tokens": _nested_usage_number(
            usage,
            ("input_tokens_details", "cached_tokens"),
            ("input_tokens_details", "cached_input_tokens"),
            ("cached_input_tokens",),
        ),
        "cache_write_tokens": _nested_usage_number(
            usage,
            ("input_tokens_details", "cache_write_tokens"),
            ("input_tokens_details", "cache_write_input_tokens"),
            ("cache_write_tokens",),
        ),
        "output_tokens": _nested_usage_number(usage, ("output_tokens",)),
        "reasoning_tokens": _nested_usage_number(
            usage,
            ("output_tokens_details", "reasoning_tokens"),
            ("reasoning_tokens",),
        ),
        "total_tokens": _nested_usage_number(usage, ("total_tokens",)),
    }


def count_openai_web_search_calls(raw):
    if not isinstance(raw, dict):
        return 0

    def is_web_search_item(item):
        if not isinstance(item, dict):
            return False
        for key in ("type", "name", "tool_name"):
            value = item.get(key)
            if isinstance(value, str) and "web_search" in value.lower():
                return True
        return False

    def walk(value):
        if isinstance(value, dict):
            if is_web_search_item(value):
                return 1
            return sum(walk(child) for child in value.values())
        if isinstance(value, list):
            return sum(walk(child) for child in value)
        return 0

    return walk(raw.get("output", []))


def build_openai_step_telemetry(step_name, raw=None, status="completed", duration_ms=None, retry_count=0, error=None, model=None, reasoning_effort=None):
    request_model = model or OPENAI_MODEL
    request_reasoning_effort = normalize_reasoning_effort(reasoning_effort or OPENAI_REASONING_EFFORT)
    telemetry = {
        "step_name": step_name,
        "model": request_model,
        "reasoning_effort": request_reasoning_effort,
        "status": status,
        "duration_ms": duration_ms,
        "retry_count": retry_count,
        "web_search_call_count": count_openai_web_search_calls(raw),
        **extract_openai_usage_telemetry(raw or {}),
    }
    if error:
        telemetry["error"] = str(error)
    return telemetry


def _format_log_value(value):
    if value is None:
        return "-"
    return value


def _format_log_duration(duration_ms):
    if _finite_number_or_none(duration_ms) is None:
        return "-"
    return f"{duration_ms / 1000.0:.1f}s"


def log_openai_step_completion(step_name, telemetry):
    logger.info(
        "Completed AI step=%s model=%s duration=%s input_tokens=%s cached_tokens=%s output_tokens=%s reasoning_tokens=%s web_searches=%s retries=%s",
        step_name,
        telemetry.get("model") or "-",
        _format_log_duration(telemetry.get("duration_ms")),
        _format_log_value(telemetry.get("input_tokens")),
        _format_log_value(telemetry.get("cached_input_tokens")),
        _format_log_value(telemetry.get("output_tokens")),
        _format_log_value(telemetry.get("reasoning_tokens")),
        _format_log_value(telemetry.get("web_search_call_count")),
        _format_log_value(telemetry.get("retry_count")),
    )


def log_openai_step_failure(step_name, telemetry):
    logger.warning(
        "Failed AI step=%s model=%s duration=%s retries=%s error=%s",
        step_name,
        telemetry.get("model") or "-",
        _format_log_duration(telemetry.get("duration_ms")),
        _format_log_value(telemetry.get("retry_count")),
        telemetry.get("error") or "-",
    )


def request_ai_step_with_telemetry(step_name, prompt_text, json_schema, attempt=1, model=None, reasoning_effort=None):
    request_model = model or OPENAI_MODEL
    temperature = parse_temperature(OPENAI_TEMPERATURE_RAW)
    request_reasoning_effort = normalize_reasoning_effort(reasoning_effort or OPENAI_REASONING_EFFORT)
    supports_temperature = model_supports_temperature(request_model)
    started_at = time.monotonic()

    logger.info(
        "Starting AI step=%s model=%s temp=%s reasoning=%s",
        step_name,
        request_model,
        f"{temperature:.2f}" if supports_temperature else "omitted",
        request_reasoning_effort,
    )

    tool_candidates = list(OPENAI_WEB_SEARCH_TOOL_CANDIDATES)
    last_exc = None
    request_timeout_seconds = get_ai_step_timeout(step_name, attempt=attempt)

    for idx, tool_type in enumerate(tool_candidates):
        body = build_openai_request_body(
            prompt_text,
            json_schema,
            request_reasoning_effort,
            supports_temperature,
            temperature,
            tool_type=tool_type,
            model=request_model,
        )
        logger.info("OpenAI Analysis request includes web search tool")
        logger.info("OpenAI web search tool type: %s", tool_type)
        logger.info(
            "OpenAI request timeout seconds for step=%s attempt=%s: %.1f",
            step_name,
            attempt,
            request_timeout_seconds,
        )

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
            telemetry = build_openai_step_telemetry(
                step_name,
                raw=raw,
                status="completed",
                duration_ms=round((time.monotonic() - started_at) * 1000),
                retry_count=idx,
                model=request_model,
                reasoning_effort=request_reasoning_effort,
            )
            log_openai_step_completion(step_name, telemetry)
            return payload, telemetry
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
            telemetry = build_openai_step_telemetry(
                step_name,
                status="failed",
                duration_ms=round((time.monotonic() - started_at) * 1000),
                retry_count=idx,
                error=last_exc,
                model=request_model,
                reasoning_effort=request_reasoning_effort,
            )
            log_openai_step_failure(step_name, telemetry)
            raise OpenAITelemetryError(str(last_exc), telemetry=telemetry) from exc
        except TimeoutError as exc:
            last_exc = RuntimeError(
                f"OpenAI request timed out on step {step_name} attempt {attempt} after {request_timeout_seconds:.1f}s"
            )
            telemetry = build_openai_step_telemetry(
                step_name,
                status="failed",
                duration_ms=round((time.monotonic() - started_at) * 1000),
                retry_count=idx,
                error=last_exc,
                model=request_model,
                reasoning_effort=request_reasoning_effort,
            )
            log_openai_step_failure(step_name, telemetry)
            raise OpenAITelemetryError(str(last_exc), telemetry=telemetry) from exc

    if last_exc:
        telemetry = build_openai_step_telemetry(
            step_name,
            status="failed",
            duration_ms=round((time.monotonic() - started_at) * 1000),
            retry_count=max(0, len(tool_candidates) - 1),
            error=last_exc,
            model=request_model,
            reasoning_effort=request_reasoning_effort,
        )
        log_openai_step_failure(step_name, telemetry)
        raise OpenAITelemetryError(str(last_exc), telemetry=telemetry)
    message = f"OpenAI request failed on step {step_name} for unknown reasons"
    telemetry = build_openai_step_telemetry(
        step_name,
        status="failed",
        duration_ms=round((time.monotonic() - started_at) * 1000),
        retry_count=0,
        error=message,
        model=request_model,
        reasoning_effort=request_reasoning_effort,
    )
    log_openai_step_failure(step_name, telemetry)
    raise OpenAITelemetryError(message, telemetry=telemetry)


def request_ai_step(step_name, prompt_text, json_schema, attempt=1):
    payload, _telemetry = request_ai_step_with_telemetry(step_name, prompt_text, json_schema, attempt=attempt)
    return payload


CORE_EVIDENCE_STATUSES = (
    "Confirms",
    "Weakens",
    "Contradicts",
    "Mixed",
    "New context",
    "No material new evidence",
)


def resolve_core_evidence_model():
    return OPENAI_CORE_EVIDENCE_MODEL or OPENAI_MODEL


def resolve_core_evidence_reasoning_effort():
    return normalize_reasoning_effort(OPENAI_CORE_EVIDENCE_REASONING_EFFORT or OPENAI_REASONING_EFFORT)


def _string_array_schema():
    return {"type": "array", "items": {"type": "string"}}


def build_core_evidence_schema():
    return {
        "name": "core_evidence_pack",
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "symbol": {"type": "string"},
                "as_of": {"type": "string"},
                "reporting_context": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "latest_reporting_period": {"type": "string"},
                        "latest_release_date": {"type": "string"},
                        "facts": _string_array_schema(),
                    },
                    "required": ["latest_reporting_period", "latest_release_date", "facts"],
                },
                "guidance": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {"facts": _string_array_schema()},
                    "required": ["facts"],
                },
                "key_variable_evidence": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "key_variable": {"type": "string"},
                            "driver_category": {"type": "string"},
                            "evidence_status": {"type": "string", "enum": list(CORE_EVIDENCE_STATUSES)},
                            "facts": _string_array_schema(),
                        },
                        "required": ["key_variable", "driver_category", "evidence_status", "facts"],
                    },
                },
                "other_material_facts": _string_array_schema(),
                "valuation_context": _string_array_schema(),
                "sources": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "title": {"type": "string"},
                            "date": {"type": "string"},
                            "source_type": {"type": "string"},
                            "url": {"type": "string"},
                        },
                        "required": ["title", "date", "source_type", "url"],
                    },
                },
            },
            "required": [
                "symbol",
                "as_of",
                "reporting_context",
                "guidance",
                "key_variable_evidence",
                "other_material_facts",
                "valuation_context",
                "sources",
            ],
        },
    }


def _require_string(value, field_name):
    if not isinstance(value, str):
        raise AnalysisValidationError(f"Core Evidence Pack field {field_name} must be a string")
    return value


def _require_string_list(value, field_name):
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise AnalysisValidationError(f"Core Evidence Pack field {field_name} must be an array of strings")
    return list(value)


def validate_core_evidence_pack(payload, symbol):
    if not isinstance(payload, dict):
        raise AnalysisValidationError("Core Evidence Pack must be a JSON object")
    normalized = {
        "symbol": _require_string(payload.get("symbol"), "symbol"),
        "as_of": _require_string(payload.get("as_of"), "as_of"),
    }
    if normalize_symbol(normalized["symbol"]) != normalize_symbol(symbol):
        raise AnalysisValidationError("Core Evidence Pack symbol does not match requested symbol")
    reporting = payload.get("reporting_context")
    if not isinstance(reporting, dict):
        raise AnalysisValidationError("Core Evidence Pack reporting_context must be an object")
    normalized["reporting_context"] = {
        "latest_reporting_period": _require_string(reporting.get("latest_reporting_period"), "reporting_context.latest_reporting_period"),
        "latest_release_date": _require_string(reporting.get("latest_release_date"), "reporting_context.latest_release_date"),
        "facts": _require_string_list(reporting.get("facts"), "reporting_context.facts"),
    }
    guidance = payload.get("guidance")
    if not isinstance(guidance, dict):
        raise AnalysisValidationError("Core Evidence Pack guidance must be an object")
    normalized["guidance"] = {"facts": _require_string_list(guidance.get("facts"), "guidance.facts")}
    key_variable_evidence = payload.get("key_variable_evidence")
    if not isinstance(key_variable_evidence, list):
        raise AnalysisValidationError("Core Evidence Pack key_variable_evidence must be an array")
    normalized_items = []
    for idx, item in enumerate(key_variable_evidence):
        if not isinstance(item, dict):
            raise AnalysisValidationError(f"Core Evidence Pack key_variable_evidence[{idx}] must be an object")
        evidence_status = _require_string(item.get("evidence_status"), f"key_variable_evidence[{idx}].evidence_status")
        if evidence_status not in CORE_EVIDENCE_STATUSES:
            raise AnalysisValidationError(f"Invalid Core Evidence Pack evidence_status: {evidence_status}")
        normalized_items.append(
            {
                "key_variable": _require_string(item.get("key_variable"), f"key_variable_evidence[{idx}].key_variable"),
                "driver_category": _require_string(item.get("driver_category"), f"key_variable_evidence[{idx}].driver_category"),
                "evidence_status": evidence_status,
                "facts": _require_string_list(item.get("facts"), f"key_variable_evidence[{idx}].facts"),
            }
        )
    normalized["key_variable_evidence"] = normalized_items
    normalized["other_material_facts"] = _require_string_list(payload.get("other_material_facts"), "other_material_facts")
    normalized["valuation_context"] = _require_string_list(payload.get("valuation_context"), "valuation_context")
    sources = payload.get("sources")
    if not isinstance(sources, list):
        raise AnalysisValidationError("Core Evidence Pack sources must be an array")
    normalized_sources = []
    for idx, source in enumerate(sources):
        if not isinstance(source, dict):
            raise AnalysisValidationError(f"Core Evidence Pack sources[{idx}] must be an object")
        normalized_sources.append(
            {
                "title": _require_string(source.get("title"), f"sources[{idx}].title"),
                "date": _require_string(source.get("date"), f"sources[{idx}].date"),
                "source_type": _require_string(source.get("source_type"), f"sources[{idx}].source_type"),
                "url": _require_string(source.get("url"), f"sources[{idx}].url"),
            }
        )
    normalized["sources"] = normalized_sources
    return normalized


def build_core_evidence_prompt(symbol, current_price=None, template=None, company_name="", business_model="", business_summary="", key_variables=None):
    base_template = template if template is not None else DEFAULT_PROMPT_CORE_EVIDENCE_PACK
    context = build_prompt_context(
        symbol=symbol,
        price=current_price,
        company_name=company_name,
        business_model=business_model,
        business_summary=business_summary,
        key_variables=key_variables,
    )
    return render_prompt_template(base_template, context)


def generate_core_evidence_pack(symbol, current_price, company_name, business_model, business_summary, key_variables, template):
    prompt_text = build_core_evidence_prompt(
        symbol,
        current_price,
        template=template,
        company_name=company_name,
        business_model=business_model,
        business_summary=business_summary,
        key_variables=key_variables,
    )
    payload, telemetry = request_ai_step_with_telemetry(
        "core_evidence_pack",
        prompt_text,
        build_core_evidence_schema(),
        model=resolve_core_evidence_model(),
        reasoning_effort=resolve_core_evidence_reasoning_effort(),
    )
    evidence_pack = validate_core_evidence_pack(payload, symbol)
    telemetry["status"] = "valid"
    return {
        "prompt": prompt_text,
        "pack": evidence_pack,
        "generated_at": utc_now_iso(),
        "model": telemetry.get("model"),
        "reasoning_effort": telemetry.get("reasoning_effort"),
        "telemetry": telemetry,
    }



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
            {"name": "Bear", "price_low": 1, "price_high": 2, "probability": 34},
            {"name": "Base", "price_low": 2, "price_high": 3, "probability": 33},
            {"name": "Bull", "price_low": 3, "price_high": 4, "probability": 33},
        ],
        "key_variables": key_variables,
    }

    parsed = parse_analysis_payload(combined)
    return {
        "symbol": parsed["symbol"],
        "key_variables": parsed["key_variables"],
    }


def validate_step3_scenarios(payload, symbol, key_variables):
    validation = validate_scenario_output(payload, symbol, current_price=payload.get("current_price"))
    if not validation["ok"]:
        raise AnalysisValidationError(f"step3.scenarios invalid: {validation['reason']}")

    normalized_key_variables = []
    for item in key_variables:
        if "variable_text" in item:
            normalized_key_variables.append(
                {
                    "variable_text": item["variable_text"],
                    "variable_type": item["variable_type"],
                    "driver_category": safe_driver_category(item.get("driver_category")),
                    "confidence": item["confidence"],
                    "importance": item["importance"],
                }
            )
        else:
            normalized_key_variables.append(
                {
                    "variable_text": item["variable"],
                    "variable_type": item["type"],
                    "driver_category": safe_driver_category(item.get("driver_category")),
                    "confidence": item["confidence"],
                    "importance": item["importance"],
                }
            )

    return {
        "symbol": symbol,
        "assumptions": validation["parsed"]["assumptions"],
        "scenarios": validation["parsed"]["scenarios"],
        "key_variables": normalized_key_variables,
    }


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
        templates, sources = get_prompt_templates_for_keys(
            conn,
            ANALYSIS_WORKFLOW_PROMPT_KEYS,
            purpose="analysis_execution",
        )
        scenario_settings = get_scenario_generation_config(conn)
    finally:
        conn.close()

    logger.info(
        "Prompt sources business_model=%s key_variables=%s core_evidence=%s scenarios=%s",
        sources[ANALYSIS_PROMPT_SETTING_KEY_BUSINESS_MODEL],
        sources[ANALYSIS_PROMPT_SETTING_KEY_KEY_VARIABLES],
        sources[ANALYSIS_PROMPT_SETTING_KEY_CORE_EVIDENCE_PACK],
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
                            "driver_category": {"type": "string", "enum": ["Core Driver", "Potential Driver"]},
                            "confidence": {"type": "integer", "minimum": 0, "maximum": 10},
                            "importance": {"type": "integer", "minimum": 0, "maximum": 10},
                        },
                        "required": ["variable", "type", "driver_category", "confidence", "importance"],
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
                            "probability": {"type": "number"},
                        },
                        "required": ["name", "price_low", "price_high", "probability"],
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

    logger.info("Starting AI step=core_evidence_pack symbol=%s", symbol)
    scenario_wall_started_at = time.monotonic()
    core_evidence = generate_core_evidence_pack(
        symbol=symbol,
        current_price=effective_price,
        company_name=company_name,
        business_model=step1["business_model"],
        business_summary=step1["business_summary"],
        key_variables=step2["key_variables"],
        template=templates[ANALYSIS_PROMPT_SETTING_KEY_CORE_EVIDENCE_PACK],
    )

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
        core_evidence_pack=core_evidence["pack"],
    )
    pass_count = scenario_settings["scenario_pass_count"] if scenario_settings["scenario_multi_pass_enabled"] else 1
    scenario_parsed, scenario_runs = generate_scenarios_multi_pass(
        symbol=symbol,
        key_variables=step2["key_variables"],
        prompt_text=prompt3,
        pass_count=pass_count,
        outlier_filter_enabled=scenario_settings["scenario_outlier_filter_enabled"],
        current_price=effective_price,
    )
    scenario_generation_wall_duration_ms = round((time.monotonic() - scenario_wall_started_at) * 1000)
    parsed = validate_step3_scenarios(
        {
            "symbol": symbol,
            "current_price": effective_price,
            "assumptions": scenario_parsed["assumptions"],
            "scenarios": [
                {
                    "name": s["scenario_name"],
                    "price_low": s["price_low"],
                    "price_high": s["price_high"],
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
    backend_probability_details = compute_backend_probability_details(
        step2["key_variables"],
        probability_settings["backend_base_max_probability"],
        probability_settings["backend_base_min_probability"],
    )
    backend_probs = backend_probability_details["probabilities"]
    probability_meta = choose_final_probabilities(ai_probs, backend_probs, probability_settings)
    probability_meta["backend_probability_meta"] = backend_probability_details["meta"]
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
            "core_evidence_prompt": core_evidence["prompt"],
            "core_evidence_pack": core_evidence["pack"],
            "core_evidence_generated_at": core_evidence["generated_at"],
            "core_evidence_model": core_evidence["model"],
            "core_evidence_reasoning_effort": core_evidence["reasoning_effort"],
            "core_evidence_telemetry": core_evidence["telemetry"],
            "scenario_generation_wall_duration_ms": scenario_generation_wall_duration_ms,
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
                    "telemetry": run.get("telemetry"),
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
                            "probability": {"type": "number"},
                        },
                        "required": ["name", "price_low", "price_high", "probability"],
                    },
                },
            },
            "required": ["symbol", "assumptions", "scenarios"],
        },
    }


def compute_scenario_cagr(price_target, current_price, years=5):
    try:
        price = float(price_target)
        current = float(current_price)
        years_value = float(years)
    except (TypeError, ValueError):
        return None

    if not all(math.isfinite(v) for v in (price, current, years_value)):
        return None
    if price <= 0 or current <= 0 or years_value <= 0:
        return None

    return ((price / current) ** (1 / years_value) - 1) * 100


def compute_price_mid(price_low, price_high):
    try:
        low = float(price_low)
        high = float(price_high)
    except (TypeError, ValueError):
        return None

    if not all(math.isfinite(v) for v in (low, high)):
        return None
    return (low + high) / 2.0


def enrich_scenario_with_midpoints(scenario, current_price, years=5, default_cagr=0.0):
    normalized = dict(scenario)
    price_mid = compute_price_mid(normalized.get("price_low"), normalized.get("price_high"))
    cagr_low = compute_scenario_cagr(normalized.get("price_low"), current_price, years=years)
    cagr_mid = compute_scenario_cagr(price_mid, current_price, years=years) if price_mid is not None else None
    cagr_high = compute_scenario_cagr(normalized.get("price_high"), current_price, years=years)

    normalized.update(
        price_mid=price_mid,
        cagr_low=cagr_low if cagr_low is not None else default_cagr,
        cagr_mid=cagr_mid if cagr_mid is not None else default_cagr,
        cagr_high=cagr_high if cagr_high is not None else default_cagr,
    )
    return normalized


def enrich_scenarios_with_midpoints(scenarios, current_price, years=5, default_cagr=0.0):
    populated = []
    for item in scenarios or []:
        populated.append(
            enrich_scenario_with_midpoints(
                item,
                current_price=current_price,
                years=years,
                default_cagr=default_cagr,
            )
        )
    return populated


def calculate_expected_cagr_from_price(expected_price, current_price, years=5):
    return compute_scenario_cagr(expected_price, current_price, years=years)


def calculate_expected_cagr(scenarios):
    # Backward-compatible fallback for legacy callers only. New analysis and
    # overlay flows derive expected CAGR from expected_price/current_price.
    weighted = 0.0
    total_prob = 0.0
    for scenario in scenarios or []:
        try:
            probability = float(scenario.get("probability"))
            cagr_mid = float(scenario.get("cagr_mid"))
        except (TypeError, ValueError):
            continue
        if not all(math.isfinite(v) for v in (probability, cagr_mid)):
            continue
        weighted += cagr_mid * probability
        total_prob += probability

    if total_prob <= 0:
        return None
    return weighted / total_prob


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


def validate_scenario_output(payload, symbol, current_price=None):
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
            probability = float(item.get("probability"))
        except (TypeError, ValueError):
            return {"ok": False, "reason": "invalid_numeric_field", "parsed": None}

        if not all(math.isfinite(v) for v in [price_low, price_high, probability]):
            return {"ok": False, "reason": "non_finite_numeric_field", "parsed": None}
        if price_low <= 0 or price_high <= 0:
            return {"ok": False, "reason": "non_positive_price", "parsed": None}
        probability_normalized = probability / 100.0 if probability > 1 else probability
        if probability_normalized < 0 or probability_normalized > 1:
            return {"ok": False, "reason": "invalid_probability_range", "parsed": None}
        if price_low > price_high:
            return {"ok": False, "reason": "price_low_gt_price_high", "parsed": None}

        seen.add(name)
        prob_sum_pct += probability_normalized
        normalized.append(
            {
                "scenario_name": name,
                "price_low": price_low,
                "price_high": price_high,
                "probability": probability_normalized,
            }
        )

    if seen != {"Bear", "Base", "Bull"}:
        return {"ok": False, "reason": "missing_required_scenarios", "parsed": None}
    if prob_sum_pct < 0.9 or prob_sum_pct > 1.1:
        return {"ok": False, "reason": "probability_total_out_of_range", "parsed": None}

    normalized = sorted(normalized, key=lambda s: ["Bear", "Base", "Bull"].index(s["scenario_name"]))
    normalized = enrich_scenarios_with_midpoints(normalized, current_price=current_price)
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


def aggregate_scenario_runs(runs, symbol, current_price=None):
    if not runs:
        raise AnalysisValidationError("No scenario runs available for aggregation")
    if len(runs) == 1:
        final = dict(runs[0]["parsed"])
        final["scenarios"] = _normalize_probabilities(final["scenarios"])
        final["scenarios"] = enrich_scenarios_with_midpoints(final["scenarios"], current_price=current_price)
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
                "probability": sum(v["probability"] for v in scenario_values) / len(scenario_values),
            }
        )

    final_scenarios = _normalize_probabilities(final_scenarios)
    final_scenarios = enrich_scenarios_with_midpoints(final_scenarios, current_price=current_price)
    best = max(runs, key=lambda r: r.get("quality_score", 0.0))
    return {
        "symbol": symbol,
        # Keep assumptions from highest-quality retained run.
        "assumptions": best["parsed"]["assumptions"],
        "scenarios": final_scenarios,
    }


def generate_scenarios_multi_pass(symbol, key_variables, prompt_text, pass_count, outlier_filter_enabled, current_price=None):
    runs = []
    for idx in range(pass_count):
        pass_number = idx + 1
        run = {
            "pass_index": pass_number,
            "raw_response_text": None,
            "parsed_json": None,
            "validation_status": "rejected",
            "rejection_reason": None,
            "created_at": utc_now_iso(),
            "quality_score": 0.0,
            "is_outlier": False,
            "telemetry": None,
        }
        logger.info("Scenario pass %s/%s starting", pass_number, pass_count)
        try:
            payload, telemetry = request_ai_step_with_telemetry(
                f"scenarios_pass_{pass_number}",
                prompt_text,
                _build_scenarios_schema(),
            )
            telemetry["pass_number"] = pass_number
            run["raw_response_text"] = json.dumps(payload, ensure_ascii=False)
            run["parsed_json"] = payload
            validation = validate_scenario_output(payload, symbol, current_price=current_price)
            if validation["ok"]:
                run["validation_status"] = "valid"
                run["parsed"] = validation["parsed"]
                run["midpoints"] = compute_scenario_midpoints(validation["parsed"]["scenarios"])
                run["probability_total_pct"] = sum(s["probability"] for s in validation["parsed"]["scenarios"]) * 100.0
            else:
                run["rejection_reason"] = validation["reason"]
            telemetry["status"] = run["validation_status"]
            if run["rejection_reason"]:
                telemetry["rejection_reason"] = run["rejection_reason"]
            run["telemetry"] = telemetry
            logger.info(
                "Scenario pass %s/%s completed in %s status=%s",
                pass_number,
                pass_count,
                _format_log_duration(telemetry.get("duration_ms")),
                run["validation_status"],
            )
        except OpenAITelemetryError as exc:
            telemetry = dict(exc.telemetry or {})
            telemetry["pass_number"] = pass_number
            telemetry["status"] = "failed"
            telemetry["rejection_reason"] = f"request_failed:{exc}"
            run["telemetry"] = telemetry
            run["rejection_reason"] = f"request_failed:{exc}"
            logger.warning(
                "Scenario pass %s/%s failed in %s",
                pass_number,
                pass_count,
                _format_log_duration(telemetry.get("duration_ms")),
            )
        except Exception as exc:
            run["telemetry"] = build_openai_step_telemetry(
                f"scenarios_pass_{pass_number}",
                status="failed",
                duration_ms=None,
                retry_count=0,
                error=exc,
            )
            run["telemetry"]["pass_number"] = pass_number
            run["telemetry"]["rejection_reason"] = f"request_failed:{exc}"
            run["rejection_reason"] = f"request_failed:{exc}"
            logger.warning("Scenario pass %s/%s failed: %s", pass_number, pass_count, exc)
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
            validation = validate_scenario_output(fallback["parsed_json"], symbol, current_price=current_price)
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

    aggregated = aggregate_scenario_runs(retained_runs, symbol=symbol, current_price=current_price)
    return aggregated, runs


def get_latest_earnings_release_dates_by_symbol(conn):
    rows = conn.execute(
        """
        SELECT symbol, MAX(release_date) AS latest_release_date
        FROM earnings_calendar_entries
        WHERE release_date IS NOT NULL AND release_date != ''
        GROUP BY symbol
        """
    ).fetchall()
    return {
        normalize_symbol(row["symbol"]): row["latest_release_date"]
        for row in rows
        if normalize_symbol(row["symbol"])
    }


def get_next_earnings_releases_by_symbol(conn, today=None):
    today_value = today or datetime.now(timezone.utc).date().isoformat()
    rows = conn.execute(
        """
        SELECT symbol, release_date, release_timing
        FROM earnings_calendar_entries
        WHERE release_date IS NOT NULL AND release_date != ''
        ORDER BY symbol ASC, release_date ASC
        """
    ).fetchall()
    releases = {}
    for row in rows:
        symbol = normalize_symbol(row["symbol"])
        if not symbol:
            continue
        release = {"release_date": row["release_date"], "release_timing": row["release_timing"]}
        existing = releases.get(symbol)
        if row["release_date"] >= today_value:
            if existing is None or existing["release_date"] < today_value or row["release_date"] < existing["release_date"]:
                releases[symbol] = release
        elif existing is None:
            releases[symbol] = release
        elif existing["release_date"] < today_value and row["release_date"] > existing["release_date"]:
            releases[symbol] = release
    return releases


def _diff_or_none(bullish, bearish):
    if bullish is None or bearish is None:
        return None
    return bullish - bearish


# Phase 2 separates confidence views by driver category for display/API payloads.
# Rating basis remains on the existing combined confidence fields intentionally.
def _confidence_sql(variable_type, driver_category=None):
    category_filter = ""
    if driver_category == "Core Driver":
        category_filter = " AND COALESCE(NULLIF(kv.driver_category, ''), 'Core Driver') != 'Potential Driver'"
    elif driver_category == "Potential Driver":
        category_filter = " AND kv.driver_category = 'Potential Driver'"
    return f"""
               (
                   SELECT CASE WHEN SUM(kv.importance) > 0
                     THEN SUM(kv.confidence * kv.importance) / SUM(kv.importance)
                     ELSE NULL END
                   FROM analysis_version_key_variables kv
                   WHERE kv.analysis_version_id = v.id AND kv.variable_type = '{variable_type}'{category_filter}
               )
    """


def list_analysis_symbols(conn):
    rating_settings = get_rating_settings(conn)
    latest_release_dates = get_latest_earnings_release_dates_by_symbol(conn)
    next_releases = get_next_earnings_releases_by_symbol(conn)
    rows = conn.execute(
        f"""
        SELECT r.symbol, v.company_name, v.current_price, v.expected_price, v.expected_cagr, v.upside, v.confidence_level AS overall_confidence,
               v.id AS analysis_version_id,
               v.version_number AS analysis_version,
               COALESCE(
                   (
                       SELECT COUNT(*)
                       FROM analysis_version_scenario_passes sp
                       WHERE sp.analysis_version_id = v.id
                   ),
                   0
               ) AS scenario_pass_count,
               {_confidence_sql('Bullish')} AS bullish_confidence,
               {_confidence_sql('Bearish')} AS bearish_confidence,
               {_confidence_sql('Bullish', 'Core Driver')} AS core_bullish_confidence,
               {_confidence_sql('Bearish', 'Core Driver')} AS core_bearish_confidence,
               {_confidence_sql('Bullish', 'Potential Driver')} AS potential_bullish_confidence,
               {_confidence_sql('Bearish', 'Potential Driver')} AS potential_bearish_confidence,
               (
                   SELECT MAX(rc.checked_at)
                   FROM recent_event_checks rc
                   WHERE rc.symbol = r.symbol
               ) AS last_recent_event_check_at,
               m.momentum_score,
               m.momentum_label,
               m.extension_risk,
               m.extension_label,
               m.momentum_status,
               m.updated_at AS momentum_updated_at,
               f.frontier_optionality_score,
               f.frontier_optionality_notes,
               v.created_at AS updated_at
        FROM analysis_roots r
        JOIN analysis_versions v ON v.analysis_root_id = r.id
        LEFT JOIN analysis_momentum_snapshots m ON m.symbol = r.symbol
        LEFT JOIN analysis_frontier_optionality f ON f.symbol = r.symbol
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
        item["frontier_optionality_score"] = normalize_frontier_optionality_score(item.get("frontier_optionality_score"))
        item["frontier_optionality_notes"] = item.get("frontier_optionality_notes") or ""
        item["core_confidence_diff"] = _diff_or_none(item.get("core_bullish_confidence"), item.get("core_bearish_confidence"))
        item["potential_confidence_diff"] = _diff_or_none(item.get("potential_bullish_confidence"), item.get("potential_bearish_confidence"))
        item.update(
            get_effective_analysis_metrics(
                conn,
                item.get("analysis_version_id"),
                item.get("expected_price"),
                item.get("expected_cagr"),
                item.get("upside"),
            )
        )
        effective_scenarios, effective_scenario_source = get_effective_analysis_scenarios(
            conn,
            item.get("analysis_version_id"),
        )
        item["effective_scenarios"] = effective_scenarios
        item["effective_scenario_source"] = effective_scenario_source
        rating, confidence_diff = calculate_rating(
            item.get("upside"),
            item.get("bullish_confidence"),
            item.get("bearish_confidence"),
            rating_settings,
            confidence_context=item,
        )
        item["confidence_diff"] = confidence_diff
        item["rating"] = rating
        item["latest_release_date"] = latest_release_dates.get(normalize_symbol(item.get("symbol")))
        next_release = next_releases.get(normalize_symbol(item.get("symbol"))) or {}
        item["release_date"] = next_release.get("release_date")
        item["release_timing"] = next_release.get("release_timing")
        scenario_updated = _parse_iso_datetime(item.get("updated_at"))
        event_checked = _parse_iso_datetime(item.get("last_recent_event_check_at"))
        activity_candidates = [dt for dt in (scenario_updated, event_checked) if dt is not None]
        item["last_activity_at"] = max(activity_candidates).isoformat() if activity_candidates else None
        output.append(item)
    return output


def _normalize_release_timing(value):
    if value is None:
        return None
    normalized = str(value).strip()
    if not normalized:
        return None
    allowed = {"Before Open", "After Close"}
    if normalized not in allowed:
        raise ValueError("release_timing must be one of: Before Open, After Close")
    return normalized


def _normalize_release_date(value):
    if value is None:
        return None
    normalized = str(value).strip()
    if not normalized:
        return None
    try:
        date.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError("release_date must be a valid date in YYYY-MM-DD format") from exc
    return normalized


def migrate_legacy_earnings_release_calendar(conn):
    """Backfill pre-redesign symbol-level calendar rows as 2026 Q1 entries.

    Phase 2 intentionally treats every old current Earnings Calendar row as FY2026 Q1.
    The old current calendar was derived from analyzed symbols, with optional symbol-level
    release dates/timing in earnings_release_schedule and removals tracked in
    earnings_release_calendar_exclusions.
    """
    now = utc_now_iso()
    source_rows = conn.execute(
        """
        SELECT
          r.symbol,
          r.created_at AS root_created_at,
          r.updated_at AS root_updated_at,
          s.release_date,
          s.release_timing,
          s.created_at AS schedule_created_at,
          s.updated_at AS schedule_updated_at
        FROM analysis_roots r
        LEFT JOIN earnings_release_schedule s ON s.symbol = r.symbol
        WHERE EXISTS (
          SELECT 1
          FROM analysis_versions v
          WHERE v.analysis_root_id = r.id
        )
          AND NOT EXISTS (
            SELECT 1
            FROM earnings_release_calendar_exclusions e
            WHERE e.symbol = r.symbol
          )
        ORDER BY r.symbol ASC
        """
    ).fetchall()

    migrated = 0
    skipped = 0
    invalid = 0
    for row in source_rows:
        symbol = normalize_symbol(row["symbol"])
        if not symbol:
            invalid += 1
            continue
        exists = conn.execute(
            """
            SELECT 1
            FROM earnings_calendar_entries
            WHERE symbol = ? AND fiscal_year = 2026 AND fiscal_quarter = 'Q1'
            """,
            (symbol,),
        ).fetchone()
        if exists:
            skipped += 1
            continue
        try:
            release_date = _normalize_release_date(row["release_date"])
            release_timing = _normalize_release_timing(row["release_timing"])
        except ValueError:
            invalid += 1
            logger.warning("Skipping legacy earnings calendar migration row with invalid schedule data for %s", symbol)
            continue
        created_at = row["schedule_created_at"] or row["root_created_at"] or now
        updated_at = row["schedule_updated_at"] or row["schedule_created_at"] or row["root_updated_at"] or created_at
        conn.execute(
            """
            INSERT INTO earnings_calendar_entries (
              symbol, fiscal_year, fiscal_quarter, release_date, release_timing, created_at, updated_at
            ) VALUES (?, 2026, 'Q1', ?, ?, ?, ?)
            """,
            (symbol, release_date, release_timing, created_at, updated_at),
        )
        migrated += 1

    if source_rows:
        logger.info(
            "Legacy earnings calendar migration to 2026 Q1: migrated %s row(s), skipped %s existing row(s), ignored %s invalid row(s).",
            migrated,
            skipped,
            invalid,
        )
    return {"migrated": migrated, "skipped": skipped, "invalid": invalid, "source_count": len(source_rows)}


def _validate_fiscal_year(value):
    try:
        year = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("fiscal_year must be a valid integer") from exc
    if year < 1900 or year > 2200:
        raise ValueError("fiscal_year must be between 1900 and 2200")
    return year


def _get_analysis_enrichment_by_symbol(conn):
    return {
        normalize_symbol(item.get("symbol")): item
        for item in list_analysis_symbols(conn)
        if normalize_symbol(item.get("symbol"))
    }


def _get_portfolio_symbols(conn):
    return {
        normalize_symbol(item.get("symbol"))
        for item in load_positions_cache(conn)
        if normalize_symbol(item.get("symbol")) and abs(safe_number(item.get("position")) or 0.0) > 0
    }


def _serialize_earnings_calendar_entry(row, analysis_by_symbol, portfolio_symbols):
    entry = dict(row)
    symbol = normalize_symbol(entry.get("symbol")) or ""
    analysis = analysis_by_symbol.get(symbol) or {}
    in_portfolio = symbol in portfolio_symbols
    return {
        "id": entry.get("id"),
        "symbol": symbol,
        "company_name": analysis.get("company_name"),
        "has_analysis": bool(analysis),
        "in_portfolio": in_portfolio,
        "inPortfolio": in_portfolio,
        "upside": analysis.get("upside"),
        "confidence_diff": analysis.get("confidence_diff"),
        "bullish_confidence": analysis.get("bullish_confidence"),
        "bearish_confidence": analysis.get("bearish_confidence"),
        "core_bullish_confidence": analysis.get("core_bullish_confidence"),
        "core_bearish_confidence": analysis.get("core_bearish_confidence"),
        "core_confidence_diff": analysis.get("core_confidence_diff"),
        "potential_bullish_confidence": analysis.get("potential_bullish_confidence"),
        "potential_bearish_confidence": analysis.get("potential_bearish_confidence"),
        "potential_confidence_diff": analysis.get("potential_confidence_diff"),
        "rating": analysis.get("rating"),
        "fiscal_year": entry.get("fiscal_year"),
        "fiscal_quarter": entry.get("fiscal_quarter"),
        "release_date": entry.get("release_date"),
        "release_timing": entry.get("release_timing"),
        "created_at": entry.get("created_at"),
        "updated_at": entry.get("updated_at"),
    }


def list_earnings_release_calendar(conn):
    rows = conn.execute(
        """
        SELECT id, symbol, fiscal_year, fiscal_quarter, release_date, release_timing, created_at, updated_at
        FROM earnings_calendar_entries
        ORDER BY fiscal_year DESC,
                 CASE fiscal_quarter WHEN 'Q4' THEN 4 WHEN 'Q3' THEN 3 WHEN 'Q2' THEN 2 ELSE 1 END DESC,
                 symbol ASC,
                 id ASC
        """
    ).fetchall()
    analysis_by_symbol = _get_analysis_enrichment_by_symbol(conn)
    portfolio_symbols = _get_portfolio_symbols(conn)
    return [_serialize_earnings_calendar_entry(row, analysis_by_symbol, portfolio_symbols) for row in rows]


def create_earnings_calendar_entry(conn, symbol, fiscal_year, fiscal_quarter, release_date=None, release_timing=None):
    normalized_symbol = normalize_symbol(symbol)
    if not normalized_symbol:
        raise ValueError("symbol is required")
    year = _validate_fiscal_year(fiscal_year)
    quarter = _validate_fiscal_quarter(fiscal_quarter)
    normalized_date = _normalize_release_date(release_date)
    normalized_timing = _normalize_release_timing(release_timing)
    now = utc_now_iso()
    try:
        cursor = conn.execute(
            """
            INSERT INTO earnings_calendar_entries (
              symbol, fiscal_year, fiscal_quarter, release_date, release_timing, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (normalized_symbol, year, quarter, normalized_date, normalized_timing, now, now),
        )
        conn.commit()
    except sqlite3.IntegrityError as exc:
        if "UNIQUE" in str(exc).upper():
            raise ValueError(f"Calendar entry for {normalized_symbol} {year} {quarter} already exists") from exc
        raise ValueError(str(exc)) from exc
    return get_earnings_calendar_entry(conn, cursor.lastrowid)


def get_earnings_calendar_entry(conn, entry_id):
    try:
        normalized_id = int(entry_id)
    except (TypeError, ValueError) as exc:
        raise ValueError("calendar entry id must be a valid integer") from exc
    row = conn.execute(
        """
        SELECT id, symbol, fiscal_year, fiscal_quarter, release_date, release_timing, created_at, updated_at
        FROM earnings_calendar_entries
        WHERE id = ?
        """,
        (normalized_id,),
    ).fetchone()
    if not row:
        raise ValueError("Calendar entry not found")
    analysis_by_symbol = _get_analysis_enrichment_by_symbol(conn)
    portfolio_symbols = _get_portfolio_symbols(conn)
    return _serialize_earnings_calendar_entry(row, analysis_by_symbol, portfolio_symbols)


def update_earnings_calendar_entry(conn, entry_id, fiscal_year, fiscal_quarter, release_date=None, release_timing=None):
    try:
        normalized_id = int(entry_id)
    except (TypeError, ValueError) as exc:
        raise ValueError("calendar entry id must be a valid integer") from exc
    existing = conn.execute("SELECT symbol FROM earnings_calendar_entries WHERE id = ?", (normalized_id,)).fetchone()
    if not existing:
        raise ValueError("Calendar entry not found")
    year = _validate_fiscal_year(fiscal_year)
    quarter = _validate_fiscal_quarter(fiscal_quarter)
    normalized_date = _normalize_release_date(release_date)
    normalized_timing = _normalize_release_timing(release_timing)
    now = utc_now_iso()
    try:
        conn.execute(
            """
            UPDATE earnings_calendar_entries
            SET fiscal_year = ?, fiscal_quarter = ?, release_date = ?, release_timing = ?, updated_at = ?
            WHERE id = ?
            """,
            (year, quarter, normalized_date, normalized_timing, now, normalized_id),
        )
        conn.commit()
    except sqlite3.IntegrityError as exc:
        if "UNIQUE" in str(exc).upper():
            symbol = existing["symbol"]
            raise ValueError(f"Calendar entry for {symbol} {year} {quarter} already exists") from exc
        raise ValueError(str(exc)) from exc
    return get_earnings_calendar_entry(conn, normalized_id)


def delete_earnings_calendar_entry(conn, entry_id):
    try:
        normalized_id = int(entry_id)
    except (TypeError, ValueError) as exc:
        raise ValueError("calendar entry id must be a valid integer") from exc
    row = conn.execute(
        "SELECT id, symbol, fiscal_year, fiscal_quarter FROM earnings_calendar_entries WHERE id = ?",
        (normalized_id,),
    ).fetchone()
    if not row:
        raise ValueError("Calendar entry not found")
    conn.execute("DELETE FROM earnings_calendar_entries WHERE id = ?", (normalized_id,))
    conn.commit()
    return {"id": row["id"], "symbol": row["symbol"], "fiscal_year": row["fiscal_year"], "fiscal_quarter": row["fiscal_quarter"], "removed": True}


# Backwards-compatible helper names now operate on standalone quarter-specific entries.
def save_earnings_release_schedule(conn, symbol, release_date=None, release_timing=None, fiscal_year=None, fiscal_quarter=None, entry_id=None):
    if entry_id is not None:
        return update_earnings_calendar_entry(conn, entry_id, fiscal_year, fiscal_quarter, release_date, release_timing)
    return create_earnings_calendar_entry(conn, symbol, fiscal_year, fiscal_quarter, release_date, release_timing)


def remove_earnings_release_calendar_symbol(conn, entry_id):
    return delete_earnings_calendar_entry(conn, entry_id)




def recalculate_version_dynamic_price_metrics(conn, version_id, current_price):
    scenario_rows = conn.execute(
        """
        SELECT id, scenario_name, price_low, price_high, probability
        FROM analysis_version_scenarios
        WHERE analysis_version_id = ?
        ORDER BY CASE scenario_name WHEN 'Bear' THEN 1 WHEN 'Base' THEN 2 WHEN 'Bull' THEN 3 ELSE 99 END
        """,
        (version_id,),
    ).fetchall()
    scenarios = enrich_scenarios_with_midpoints([dict(row) for row in scenario_rows], current_price=current_price)
    for scenario in scenarios:
        conn.execute(
            """
            UPDATE analysis_version_scenarios
            SET price_mid = ?, cagr_low = ?, cagr_mid = ?, cagr_high = ?
            WHERE id = ?
            """,
            (
                scenario.get("price_mid"),
                scenario.get("cagr_low"),
                scenario.get("cagr_mid"),
                scenario.get("cagr_high"),
                scenario.get("id"),
            ),
        )
    version = conn.execute("SELECT expected_price FROM analysis_versions WHERE id = ?", (version_id,)).fetchone()
    expected_price = version["expected_price"] if version else calculate_expected_price(scenarios)
    expected_cagr = calculate_expected_cagr_from_price(expected_price, current_price)
    upside = calculate_upside(expected_price, current_price)
    conn.execute(
        """
        UPDATE analysis_versions
        SET expected_cagr = ?, upside = ?
        WHERE id = ?
        """,
        (expected_cagr, upside, version_id),
    )

    overlay = conn.execute(
        "SELECT final_scenarios_json, expected_price, is_stale FROM analysis_final_scenario_overlays WHERE analysis_version_id = ?",
        (version_id,),
    ).fetchone()
    if overlay and not bool(overlay["is_stale"]):
        try:
            final_scenarios = json.loads(overlay["final_scenarios_json"] or "[]")
        except json.JSONDecodeError:
            final_scenarios = []
        enriched_final = enrich_scenarios_with_midpoints(final_scenarios, current_price=current_price, default_cagr=None)
        final_expected_price = overlay["expected_price"] if overlay["expected_price"] is not None else calculate_expected_price(enriched_final)
        final_expected_cagr = calculate_expected_cagr_from_price(final_expected_price, current_price)
        final_upside = calculate_upside(final_expected_price, current_price)
        conn.execute(
            """
            UPDATE analysis_final_scenario_overlays
            SET final_scenarios_json = ?, expected_cagr = ?, upside = ?, updated_at = ?
            WHERE analysis_version_id = ?
            """,
            (json.dumps(enriched_final), final_expected_cagr, final_upside, utc_now_iso(), version_id),
        )


def refresh_latest_analysis_market_prices(conn):
    rows = conn.execute(
        """
        SELECT r.symbol, v.id AS version_id, v.current_price, v.expected_price
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

    fetch_details = fetch_ib_prices(symbols, return_details=True)
    if isinstance(fetch_details, tuple):
        prices, warnings = fetch_details
        skipped_details_by_symbol = {
            symbol: make_price_skip_detail(symbol, warnings.get(symbol) if isinstance(warnings, dict) else None)
            for symbol in symbols
            if prices.get(symbol) is None
        }
        price_sources = {}
        diagnostics = {}
    else:
        prices = fetch_details["prices"]
        skipped_details_by_symbol = {item["symbol"]: item for item in fetch_details.get("skipped_symbols", [])}
        price_sources = fetch_details.get("price_sources", {})
        diagnostics = fetch_details.get("diagnostics", {})
    now = utc_now_iso()
    updated = 0
    skipped = 0
    kept_previous = 0
    skipped_symbols = []
    updated_symbols = []
    fallback_symbols = []
    kept_previous_symbols = []

    previous_price_by_symbol = {
        row["symbol"]: safe_number(row["current_price"])
        for row in rows
    }

    for symbol in symbols:
        if prices.get(symbol) is not None:
            continue
        historical_price, historical_warning = fetch_latest_historical_close(symbol)
        if historical_price is not None:
            prices[symbol] = historical_price
            price_sources[symbol] = "historical_daily_close_fallback"
            warning_message = None
            direct_warning = diagnostics.get(symbol) or skipped_details_by_symbol.get(symbol)
            if direct_warning:
                code = direct_warning.get("error_code") if isinstance(direct_warning, dict) else None
                warning_message = f"Direct market data failed{f' with {code}' if code else ''}; used historical daily close fallback."
            diagnostics[symbol] = {
                "symbol": symbol,
                "reason": warning_message or "Used historical daily close fallback",
                "error_code": (direct_warning or {}).get("error_code") if isinstance(direct_warning, dict) else None,
                "message": (direct_warning or {}).get("message") if isinstance(direct_warning, dict) else None,
                "severity": "warning",
                "fatal": False,
                "source": "historical_daily_close_fallback",
            }
            continue
        if historical_warning:
            existing = skipped_details_by_symbol.get(symbol)
            if existing is None:
                skipped_details_by_symbol[symbol] = make_price_skip_detail(symbol, {
                    "symbol": symbol,
                    "reason": historical_warning.get("reason"),
                    "message": historical_warning.get("message"),
                    "source": "historical_daily_close_fallback",
                })

    for row in rows:
        symbol = row["symbol"]
        latest_price = prices.get(symbol)
        if latest_price is None:
            previous_price = previous_price_by_symbol.get(symbol)
            if previous_price is not None and previous_price > 0:
                kept_previous += 1
                source_counts_key = "previous_stored_price"
                kept_previous_symbols.append({
                    "symbol": symbol,
                    "price": previous_price,
                    "source": source_counts_key,
                    "warning": "All TWS refresh sources failed; kept previous stored current_price.",
                })
                continue
            skipped += 1
            skipped_symbols.append(skipped_details_by_symbol.get(symbol) or make_price_skip_detail(symbol))
            continue
        conn.execute(
            "UPDATE analysis_versions SET current_price = ? WHERE id = ?",
            (latest_price, row["version_id"]),
        )
        recalculate_version_dynamic_price_metrics(conn, row["version_id"], latest_price)
        source = price_sources.get(symbol) or "unknown"
        direct_warning = diagnostics.get(symbol)
        warning = None
        if source in {"portfolio_market_price_fallback", "historical_daily_close_fallback"}:
            if isinstance(direct_warning, dict) and direct_warning.get("error_code"):
                warning = f"Direct market data failed with {direct_warning.get('error_code')}; used {source}."
            else:
                warning = f"Used {source}."
        updated_symbols.append({
            "symbol": symbol,
            "price": latest_price,
            "source": source,
            "warning": warning,
        })
        if source in {"portfolio_market_price_fallback", "historical_daily_close_fallback"}:
            fallback_symbols.append({
                "symbol": symbol,
                "price": latest_price,
                "source": source,
                "warning": warning,
            })
        updated += 1

    if updated:
        conn.execute("UPDATE analysis_roots SET updated_at = ?", (now,))
    conn.commit()
    source_counts = {}
    for symbol, price in prices.items():
        if price is None:
            continue
        source = price_sources.get(symbol) or "unknown"
        source_counts[source] = source_counts.get(source, 0) + 1
    if kept_previous:
        source_counts["previous_stored_price"] = kept_previous
    logger.info(
        "Price refresh summary requested=%s updated=%s skipped=%s kept_previous=%s fallback=%s skipped_symbols=%s source_counts=%s",
        len(symbols),
        updated,
        skipped,
        kept_previous,
        len(fallback_symbols),
        ",".join(item["symbol"] for item in skipped_symbols) or "none",
        source_counts,
    )
    for item in fallback_symbols:
        logger.info(
            "Price refresh fallback symbol=%s source=%s reason=%s",
            item.get("symbol"),
            item.get("source"),
            item.get("warning"),
        )
    for item in skipped_symbols:
        logger.info(
            "Price refresh skipped symbol=%s reason=%s error_code=%s message=%s",
            item.get("symbol"),
            item.get("reason"),
            item.get("error_code"),
            item.get("message"),
        )
    return {
        "updated": updated,
        "skipped": skipped,
        "kept_previous": kept_previous,
        "updated_symbols": updated_symbols,
        "fallback_symbols": fallback_symbols,
        "kept_previous_symbols": kept_previous_symbols,
        "skipped_symbols": skipped_symbols,
        "source_counts": source_counts,
        "price_source_counts": source_counts,
    }


def _normalize_imported_key_variables_payload(payload):
    if not isinstance(payload, dict):
        raise AnalysisValidationError("Import payload must be a JSON object")
    raw_key_variables = payload.get("key_variables")
    if not isinstance(raw_key_variables, list):
        raise AnalysisValidationError("key_variables must be an array")
    if not raw_key_variables:
        raise AnalysisValidationError("key_variables must contain at least 1 item")

    normalized = []
    for index, item in enumerate(raw_key_variables, start=1):
        if not isinstance(item, dict):
            raise AnalysisValidationError(f"Row {index}: key variable must be an object")

        variable_text = (item.get("variable") or item.get("variable_text") or "").strip()
        if not variable_text:
            raise AnalysisValidationError(f"Row {index}: variable must be non-empty text")

        variable_type = item.get("type") or item.get("variable_type")
        if variable_type not in {"Bullish", "Bearish"}:
            raise AnalysisValidationError(f"Row {index}: type must be Bullish or Bearish")

        try:
            driver_category = normalized_driver_category(item.get("driver_category"))
        except AnalysisValidationError:
            raise AnalysisValidationError(f"Row {index}: driver_category must be Core Driver or Potential Driver")

        confidence = _strict_import_score(item.get("confidence"), f"Row {index}: confidence")
        importance = _strict_import_score(item.get("importance"), f"Row {index}: importance")
        normalized.append(
            {
                "variable_text": variable_text,
                "variable_type": variable_type,
                "driver_category": driver_category,
                "confidence": confidence,
                "importance": importance,
            }
        )

    return normalized


def _strict_import_score(value, label):
    if isinstance(value, bool):
        raise AnalysisValidationError(f"{label} must be an integer from 0 to 10")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise AnalysisValidationError(f"{label} must be an integer from 0 to 10")
    if not math.isfinite(number) or not number.is_integer():
        raise AnalysisValidationError(f"{label} must be an integer from 0 to 10")
    integer = int(number)
    if integer < 0 or integer > 10:
        raise AnalysisValidationError(f"{label} must be an integer from 0 to 10")
    return integer


def import_key_variable_edits(conn, symbol, version_id, import_payload):
    normalized = _normalize_imported_key_variables_payload(import_payload)
    return save_key_variable_edits(conn, symbol, version_id, normalized)


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
            driver_category = normalized_driver_category(item.get("driver_category"))
        except AnalysisValidationError:
            raise AnalysisValidationError(f"key_variables[{index}].driver_category must be Core Driver or Potential Driver")

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
                "driver_category": driver_category,
                "confidence": confidence,
                "importance": importance,
            }
        )

    return normalized


def _version_payload(conn, version_row):
    scenarios = conn.execute(
        """
        SELECT scenario_name, price_low, price_mid, price_high, cagr_low, cagr_mid, cagr_high, probability
        FROM analysis_version_scenarios
        WHERE analysis_version_id = ?
        ORDER BY CASE scenario_name WHEN 'Bear' THEN 1 WHEN 'Base' THEN 2 WHEN 'Bull' THEN 3 ELSE 99 END
        """,
        (version_row["id"],),
    ).fetchall()

    key_variables = conn.execute(
        """
        SELECT variable_text, variable_type, COALESCE(driver_category, 'Core Driver') AS driver_category, confidence, importance
        FROM analysis_version_key_variables
        WHERE analysis_version_id = ?
        ORDER BY id ASC
        """,
        (version_row["id"],),
    ).fetchall()

    scenario_passes = conn.execute(
        """
        SELECT pass_index, raw_response_text, parsed_json, validation_status,
               rejection_reason, quality_score, is_outlier, telemetry_json, created_at
        FROM analysis_version_scenario_passes
        WHERE analysis_version_id = ?
        ORDER BY pass_index ASC
        """,
        (version_row["id"],),
    ).fetchall()

    enriched_scenarios = enrich_scenarios_with_midpoints([dict(s) for s in scenarios], current_price=version_row["current_price"], default_cagr=None)

    confidence_breakdown = calculate_confidence_breakdown([dict(v) for v in key_variables])
    bullish_confidence = confidence_breakdown["bullish_confidence"]
    bearish_confidence = confidence_breakdown["bearish_confidence"]

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
                "telemetry_json": json.dumps(row.get("telemetry")) if isinstance(row.get("telemetry"), dict) else None,
                "created_at": row.get("created_at"),
            }
            for row in raw_payload.get("step3_runs", [])
        ]

    effective_metrics = get_effective_analysis_metrics(
        conn,
        version_row["id"],
        version_row["expected_price"],
        version_row["expected_cagr"],
        version_row["upside"],
    )
    rating_settings = get_rating_settings(conn)
    rating, confidence_diff = calculate_rating(
        effective_metrics["upside"],
        bullish_confidence,
        bearish_confidence,
        rating_settings,
        confidence_context=confidence_breakdown,
    )

    probability_meta = raw_payload.get("probability_meta") if isinstance(raw_payload.get("probability_meta"), dict) else {}

    def parse_json_object_or_none(value):
        if isinstance(value, dict):
            return value
        if not value:
            return None
        try:
            parsed = json.loads(value)
        except Exception:
            return None
        return parsed if isinstance(parsed, dict) else None

    def parse_scenario_pass_telemetry(row):
        telemetry_json = row["telemetry_json"] if "telemetry_json" in row.keys() else None
        if not telemetry_json:
            return None
        try:
            telemetry = json.loads(telemetry_json)
        except Exception:
            return None
        return telemetry if isinstance(telemetry, dict) else None

    core_evidence_pack = parse_json_object_or_none(version_row["core_evidence_pack_json"]) or parse_json_object_or_none(raw_payload.get("core_evidence_pack"))
    core_evidence_telemetry = parse_json_object_or_none(version_row["core_evidence_telemetry_json"]) or parse_json_object_or_none(raw_payload.get("core_evidence_telemetry"))
    core_evidence_generated_at = version_row["core_evidence_generated_at"] or raw_payload.get("core_evidence_generated_at")
    core_evidence_model = version_row["core_evidence_model"] or raw_payload.get("core_evidence_model")
    core_evidence_reasoning_effort = version_row["core_evidence_reasoning_effort"] or raw_payload.get("core_evidence_reasoning_effort")
    scenario_generation_wall_duration_ms = version_row["scenario_generation_wall_duration_ms"] or raw_payload.get("scenario_generation_wall_duration_ms")

    return {
        "id": version_row["id"],
        "version_number": version_row["version_number"],
        "symbol": version_row["symbol"],
        "company_name": version_row["company_name"],
        "current_price": version_row["current_price"],
        **effective_metrics,
        "overall_confidence": version_row["confidence_level"],
        "bullish_confidence": bullish_confidence,
        "bearish_confidence": bearish_confidence,
        "confidence_diff": confidence_diff,
        "core_bullish_confidence": confidence_breakdown["core_bullish_confidence"],
        "core_bearish_confidence": confidence_breakdown["core_bearish_confidence"],
        "core_confidence_diff": confidence_breakdown["core_confidence_diff"],
        "potential_bullish_confidence": confidence_breakdown["potential_bullish_confidence"],
        "potential_bearish_confidence": confidence_breakdown["potential_bearish_confidence"],
        "potential_confidence_diff": confidence_breakdown["potential_confidence_diff"],
        "rating": rating,
        "assumptions": version_row["assumptions_text"],
        "business_model": version_row["business_model_text"],
        "business_summary": version_row["business_summary_text"],
        "created_at": version_row["created_at"],
        "source_trigger": version_row["source_trigger"],
        "scenario_prompt": prompt_text,
        "core_evidence_pack": core_evidence_pack,
        "core_evidence_generated_at": core_evidence_generated_at,
        "core_evidence_model": core_evidence_model,
        "core_evidence_reasoning_effort": core_evidence_reasoning_effort,
        "core_evidence_telemetry": core_evidence_telemetry,
        "scenario_generation_wall_duration_ms": scenario_generation_wall_duration_ms,
        "ai_scenario_probabilities": probability_meta.get("ai_scenario_probabilities"),
        "backend_scenario_probabilities": probability_meta.get("backend_scenario_probabilities"),
        "final_scenario_probabilities": probability_meta.get("final_scenario_probabilities"),
        "probability_source_mode_used": probability_meta.get("probability_source_mode_used"),
        "backend_probability_meta": probability_meta.get("backend_probability_meta"),
        "scenarios": enriched_scenarios,
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
                "telemetry": parse_scenario_pass_telemetry(row),
                "created_at": row["created_at"],
            }
            for row in scenario_passes
        ],
    }


EXTERNAL_SCENARIO_NAMES = ("Bear", "Base", "Bull")

def _analysis_version_exists(conn, version_id):
    try:
        normalized_id = int(version_id)
    except (TypeError, ValueError):
        raise ValueError("Invalid analysis version id")
    row = conn.execute("SELECT id FROM analysis_versions WHERE id = ?", (normalized_id,)).fetchone()
    if not row:
        raise ValueError("Analysis version not found")
    return normalized_id


def _normalize_external_weight(value):
    try:
        weight = float(value)
    except (TypeError, ValueError):
        raise ValueError("External scenario weight must be numeric")
    if not math.isfinite(weight):
        raise ValueError("External scenario weight must be numeric")
    if weight < 0:
        raise ValueError("External scenario weight cannot be negative")
    if weight > 100:
        raise ValueError("External scenario weight cannot exceed 100%")
    return weight / 100.0 if weight > 1.0 else weight


def _safe_external_float(value, field_name):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be numeric")
    if not math.isfinite(number):
        raise ValueError(f"{field_name} must be numeric")
    return number


def _normalize_external_scenario_payload(raw_scenarios, current_price=None):
    if isinstance(raw_scenarios, str):
        try:
            raw_scenarios = json.loads(raw_scenarios)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Scenario JSON is invalid: {exc.msg}")
    if not isinstance(raw_scenarios, dict):
        raise ValueError("Scenario JSON must be an object")
    scenarios = raw_scenarios.get("scenarios")
    if not isinstance(scenarios, list):
        raise ValueError("Scenario JSON must include a scenarios array")
    if len(scenarios) != 3:
        raise ValueError("Scenario JSON must include exactly 3 scenarios")

    by_name = {}
    for index, item in enumerate(scenarios):
        if not isinstance(item, dict):
            raise ValueError(f"scenarios[{index}] must be an object")
        name = item.get("name") or item.get("scenario_name")
        if name not in EXTERNAL_SCENARIO_NAMES:
            raise ValueError("Scenario names must be exactly Bear, Base, and Bull")
        if name in by_name:
            raise ValueError("Duplicate scenario names are not allowed")
        price_low = _safe_external_float(item.get("price_low"), f"{name}.price_low")
        price_high = _safe_external_float(item.get("price_high"), f"{name}.price_high")
        probability = _safe_external_float(item.get("probability"), f"{name}.probability")
        if price_low <= 0 or price_high <= 0:
            raise ValueError(f"{name} price values must be greater than 0")
        if price_low > price_high:
            raise ValueError(f"{name} price_low cannot exceed price_high")
        if probability < 0:
            raise ValueError(f"{name} probability cannot be negative")
        by_name[name] = {
            "scenario_name": name,
            "price_low": price_low,
            "price_high": price_high,
            "probability": probability,
        }

    missing = [name for name in EXTERNAL_SCENARIO_NAMES if name not in by_name]
    if missing:
        raise ValueError("Scenario JSON must include Bear, Base, and Bull")

    probability_sum = sum(item["probability"] for item in by_name.values())
    if abs(probability_sum - 100.0) <= 0.05:
        divisor = 100.0
    elif abs(probability_sum - 1.0) <= 0.0005:
        divisor = 1.0
    else:
        raise ValueError("Scenario probabilities must sum to 100 or 1")

    normalized = []
    for name in EXTERNAL_SCENARIO_NAMES:
        item = dict(by_name[name])
        item["probability"] = item["probability"] / divisor
        normalized.append(enrich_scenario_with_midpoints(item, current_price=current_price, default_cagr=None))
    return _normalize_probabilities(normalized)


def _populate_external_scenario_midpoints(item, current_price=None):
    return enrich_scenario_with_midpoints(item, current_price=current_price, default_cagr=None)


def _external_scenario_json_for_edit(scenarios):
    payload = {
        "scenarios": [
            {
                "name": item.get("scenario_name") or item.get("name"),
                "price_low": item.get("price_low"),
                "price_high": item.get("price_high"),
                "probability": round(float(item.get("probability") or 0) * 100.0, 6),
            }
            for item in scenarios
        ]
    }
    return json.dumps(payload, indent=2)


def _serialize_external_scenario_row(row):
    scenarios = json.loads(row["scenarios_json"] or "[]")
    return {
        "id": row["id"],
        "analysis_version_id": row["analysis_version_id"],
        "title": row["title"],
        "source_notes": row["source_notes"],
        "external_weight": row["external_weight"],
        "external_weight_percent": row["external_weight"] * 100.0,
        "scenarios": scenarios,
        "scenario_json": _external_scenario_json_for_edit(scenarios),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def list_external_scenarios(conn, version_id):
    version_id = _analysis_version_exists(conn, version_id)
    rows = conn.execute(
        """
        SELECT id, analysis_version_id, title, source_notes, external_weight, scenarios_json, created_at, updated_at
        FROM analysis_external_scenarios
        WHERE analysis_version_id = ?
        ORDER BY created_at ASC, id ASC
        """,
        (version_id,),
    ).fetchall()
    return [_serialize_external_scenario_row(row) for row in rows]


def _mark_final_scenario_overlay_stale(conn, version_id):
    conn.execute(
        "UPDATE analysis_final_scenario_overlays SET is_stale = 1, updated_at = ? WHERE analysis_version_id = ?",
        (utc_now_iso(), version_id),
    )


def _delete_final_overlay_if_no_external_scenarios(conn, version_id):
    remaining = conn.execute(
        "SELECT COUNT(*) AS count FROM analysis_external_scenarios WHERE analysis_version_id = ?",
        (version_id,),
    ).fetchone()["count"]
    if remaining == 0:
        conn.execute("DELETE FROM analysis_final_scenario_overlays WHERE analysis_version_id = ?", (version_id,))
        return True
    _mark_final_scenario_overlay_stale(conn, version_id)
    return False


def _normalize_external_scenario_record_payload(payload, current_price=None):
    payload = payload or {}
    title = str(payload.get("title") or "").strip()
    if not title:
        raise ValueError("External scenario title is required")
    weight_value = payload.get("external_weight", payload.get("weight"))
    external_weight = _normalize_external_weight(weight_value)
    source_notes = payload.get("source_notes", payload.get("notes"))
    source_notes = str(source_notes).strip() if source_notes is not None else None
    raw_scenarios = payload.get("scenario_json")
    if raw_scenarios is None:
        raw_scenarios = payload.get("scenarios_json")
    if raw_scenarios is None:
        raw_scenarios = {"scenarios": payload.get("scenarios")}
    scenarios = _normalize_external_scenario_payload(raw_scenarios, current_price=current_price)
    return title, source_notes, external_weight, scenarios


def create_external_scenario(conn, version_id, payload):
    version_id = _analysis_version_exists(conn, version_id)
    version = conn.execute("SELECT current_price FROM analysis_versions WHERE id = ?", (version_id,)).fetchone()
    title, source_notes, external_weight, scenarios = _normalize_external_scenario_record_payload(payload, current_price=version["current_price"] if version else None)
    now = utc_now_iso()
    cur = conn.execute(
        """
        INSERT INTO analysis_external_scenarios (
            analysis_version_id, title, source_notes, external_weight, scenarios_json, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (version_id, title, source_notes, external_weight, json.dumps(scenarios), now, now),
    )
    _mark_final_scenario_overlay_stale(conn, version_id)
    conn.commit()
    row = conn.execute("SELECT * FROM analysis_external_scenarios WHERE id = ?", (cur.lastrowid,)).fetchone()
    return _serialize_external_scenario_row(row)


def update_external_scenario(conn, version_id, external_id, payload):
    version_id = _analysis_version_exists(conn, version_id)
    try:
        external_id = int(external_id)
    except (TypeError, ValueError):
        raise ValueError("Invalid external scenario id")
    existing = conn.execute(
        "SELECT id FROM analysis_external_scenarios WHERE id = ? AND analysis_version_id = ?",
        (external_id, version_id),
    ).fetchone()
    if not existing:
        raise ValueError("External scenario not found")
    version = conn.execute("SELECT current_price FROM analysis_versions WHERE id = ?", (version_id,)).fetchone()
    title, source_notes, external_weight, scenarios = _normalize_external_scenario_record_payload(payload, current_price=version["current_price"] if version else None)
    now = utc_now_iso()
    conn.execute(
        """
        UPDATE analysis_external_scenarios
        SET title = ?, source_notes = ?, external_weight = ?, scenarios_json = ?, updated_at = ?
        WHERE id = ? AND analysis_version_id = ?
        """,
        (title, source_notes, external_weight, json.dumps(scenarios), now, external_id, version_id),
    )
    _mark_final_scenario_overlay_stale(conn, version_id)
    conn.commit()
    row = conn.execute("SELECT * FROM analysis_external_scenarios WHERE id = ?", (external_id,)).fetchone()
    return _serialize_external_scenario_row(row)


def delete_external_scenario(conn, version_id, external_id):
    version_id = _analysis_version_exists(conn, version_id)
    try:
        external_id = int(external_id)
    except (TypeError, ValueError):
        raise ValueError("Invalid external scenario id")
    row = conn.execute(
        "SELECT id, title FROM analysis_external_scenarios WHERE id = ? AND analysis_version_id = ?",
        (external_id, version_id),
    ).fetchone()
    if not row:
        raise ValueError("External scenario not found")
    conn.execute("DELETE FROM analysis_external_scenarios WHERE id = ? AND analysis_version_id = ?", (external_id, version_id))
    deleted_overlay = _delete_final_overlay_if_no_external_scenarios(conn, version_id)
    conn.commit()
    return {"id": external_id, "title": row["title"], "deleted_final_overlay": deleted_overlay}


def get_effective_analysis_metrics(conn, version_id, expected_price, expected_cagr, upside):
    original = {
        "expected_price_original": expected_price,
        "expected_cagr_original": expected_cagr,
        "upside_original": upside,
    }
    row = conn.execute(
        """
        SELECT expected_price, expected_cagr, upside, is_stale
        FROM analysis_final_scenario_overlays
        WHERE analysis_version_id = ?
        """,
        (version_id,),
    ).fetchone()
    uses_overlay = bool(row and not row["is_stale"])
    effective_price = row["expected_price"] if uses_overlay else expected_price
    effective_cagr = row["expected_cagr"] if uses_overlay else expected_cagr
    effective_upside = row["upside"] if uses_overlay else upside
    return {
        **original,
        "expected_price_effective": effective_price,
        "expected_cagr_effective": effective_cagr,
        "upside_effective": effective_upside,
        "expected_price": effective_price,
        "expected_cagr": effective_cagr,
        "upside": effective_upside,
        "uses_final_scenario_overlay": uses_overlay,
        "final_scenario_stale": bool(row and row["is_stale"]),
    }


def get_effective_analysis_scenarios(conn, version_id):
    """Return the same internal/final scenario set used by the active analysis view."""
    overlay = conn.execute(
        """
        SELECT final_scenarios_json, is_stale
        FROM analysis_final_scenario_overlays
        WHERE analysis_version_id = ?
        """,
        (version_id,),
    ).fetchone()
    if overlay and not overlay["is_stale"]:
        try:
            scenarios = json.loads(overlay["final_scenarios_json"] or "[]")
        except (TypeError, ValueError, json.JSONDecodeError):
            scenarios = []
        return scenarios, "final_scenario_overlay"

    rows = conn.execute(
        """
        SELECT scenario_name, price_low, price_high, probability
        FROM analysis_version_scenarios
        WHERE analysis_version_id = ?
        ORDER BY CASE scenario_name WHEN 'Bear' THEN 1 WHEN 'Base' THEN 2 WHEN 'Bull' THEN 3 ELSE 99 END
        """,
        (version_id,),
    ).fetchall()
    return [dict(row) for row in rows], "internal_scenarios"


def _serialize_final_overlay_row(row):
    if not row:
        return None
    return {
        "id": row["id"],
        "analysis_version_id": row["analysis_version_id"],
        "bakingmoney_weight": row["bakingmoney_weight"],
        "bakingmoney_weight_percent": row["bakingmoney_weight"] * 100.0,
        "external_total_weight": row["external_total_weight"],
        "external_total_weight_percent": row["external_total_weight"] * 100.0,
        "scenarios": json.loads(row["final_scenarios_json"] or "[]"),
        "expected_price": row["expected_price"],
        "expected_cagr": row["expected_cagr"],
        "upside": row["upside"],
        "recalculated_at": row["recalculated_at"],
        "is_stale": bool(row["is_stale"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def get_final_scenario_overlay(conn, version_id):
    version_id = _analysis_version_exists(conn, version_id)
    row = conn.execute("SELECT * FROM analysis_final_scenario_overlays WHERE analysis_version_id = ?", (version_id,)).fetchone()
    return _serialize_final_overlay_row(row)


def _external_overlay_summary(conn, version_id):
    external_scenarios = list_external_scenarios(conn, version_id)
    external_total_weight = sum(float(item["external_weight"] or 0) for item in external_scenarios)
    overlay = get_final_scenario_overlay(conn, version_id)
    return {
        "external_scenarios": external_scenarios,
        "final_scenario_overlay": overlay,
        "final_scenario_stale": bool(overlay and overlay.get("is_stale")),
        "external_total_weight": external_total_weight,
        "external_total_weight_percent": external_total_weight * 100.0,
        "bakingmoney_weight": max(0.0, 1.0 - external_total_weight),
        "bakingmoney_weight_percent": max(0.0, 1.0 - external_total_weight) * 100.0,
    }


def recalculate_final_scenario_overlay(conn, version_id):
    version_id = _analysis_version_exists(conn, version_id)
    version = conn.execute("SELECT id, current_price FROM analysis_versions WHERE id = ?", (version_id,)).fetchone()
    bakingmoney_rows = conn.execute(
        """
        SELECT scenario_name, price_low, price_mid, price_high, cagr_low, cagr_mid, cagr_high, probability
        FROM analysis_version_scenarios
        WHERE analysis_version_id = ?
        ORDER BY CASE scenario_name WHEN 'Bear' THEN 1 WHEN 'Base' THEN 2 WHEN 'Bull' THEN 3 ELSE 99 END
        """,
        (version_id,),
    ).fetchall()
    if len(bakingmoney_rows) != 3:
        raise ValueError("BakingMoney scenario must include Bear, Base, and Bull before recalculating")
    bakingmoney = {row["scenario_name"]: dict(row) for row in bakingmoney_rows}
    external_scenarios = list_external_scenarios(conn, version_id)
    if not external_scenarios:
        raise ValueError("Add at least one external scenario before recalculating")
    total_external_weight = sum(float(item["external_weight"] or 0) for item in external_scenarios)
    if total_external_weight > 1.0 + 1e-9:
        raise ValueError("External scenario weights total more than 100%. Reduce weights before recalculating.")
    bakingmoney_weight = max(0.0, 1.0 - total_external_weight)

    final_scenarios = []
    for name in EXTERNAL_SCENARIO_NAMES:
        base = bakingmoney[name]
        blended = {
            "scenario_name": name,
            "price_low": float(base["price_low"]) * bakingmoney_weight,
            "price_high": float(base["price_high"]) * bakingmoney_weight,
            "probability": float(base["probability"]) * bakingmoney_weight,
        }
        for external in external_scenarios:
            scenario = next(item for item in external["scenarios"] if item["scenario_name"] == name)
            weight = float(external["external_weight"] or 0)
            blended["price_low"] += float(scenario["price_low"]) * weight
            blended["price_high"] += float(scenario["price_high"]) * weight
            blended["probability"] += float(scenario["probability"]) * weight
        final_scenarios.append(blended)

    final_scenarios = [
        enrich_scenario_with_midpoints(item, current_price=version["current_price"], default_cagr=None)
        for item in _normalize_probabilities(final_scenarios)
    ]
    expected_price = calculate_expected_price(final_scenarios)
    expected_cagr = calculate_expected_cagr_from_price(expected_price, version["current_price"])
    upside = calculate_upside(expected_price, version["current_price"])
    now = utc_now_iso()
    conn.execute(
        """
        INSERT INTO analysis_final_scenario_overlays (
            analysis_version_id, bakingmoney_weight, external_total_weight, final_scenarios_json,
            expected_price, expected_cagr, upside, recalculated_at, is_stale, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
        ON CONFLICT(analysis_version_id) DO UPDATE SET
          bakingmoney_weight = excluded.bakingmoney_weight,
          external_total_weight = excluded.external_total_weight,
          final_scenarios_json = excluded.final_scenarios_json,
          expected_price = excluded.expected_price,
          expected_cagr = excluded.expected_cagr,
          upside = excluded.upside,
          recalculated_at = excluded.recalculated_at,
          is_stale = 0,
          updated_at = excluded.updated_at
        """,
        (
            version_id,
            bakingmoney_weight,
            total_external_weight,
            json.dumps(final_scenarios),
            expected_price,
            expected_cagr,
            upside,
            now,
            now,
            now,
        ),
    )
    conn.commit()
    return get_final_scenario_overlay(conn, version_id)


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


def get_earnings_calendar_release_history_for_symbol(conn, symbol):
    normalized_symbol = normalize_symbol(symbol)
    if not normalized_symbol:
        return []
    rows = conn.execute(
        """
        SELECT id, fiscal_year, fiscal_quarter, release_date, release_timing
        FROM earnings_calendar_entries
        WHERE symbol = ?
        ORDER BY CASE WHEN release_date IS NULL OR release_date = '' THEN 1 ELSE 0 END ASC,
                 release_date DESC,
                 fiscal_year DESC,
                 CASE fiscal_quarter WHEN 'Q4' THEN 4 WHEN 'Q3' THEN 3 WHEN 'Q2' THEN 2 ELSE 1 END DESC,
                 id DESC
        """,
        (normalized_symbol,),
    ).fetchall()
    return [dict(row) for row in rows]



def get_momentum_snapshot_for_symbol(conn, symbol):
    row = conn.execute(
        """
        SELECT symbol, benchmark_symbol, duration, momentum_score, momentum_label, extension_risk,
               extension_label, momentum_status, warning, bars, first_date, last_date, latest_close,
               trend_score, relative_strength_score, volume_score, price_structure_score, updated_at AS momentum_updated_at
        FROM analysis_momentum_snapshots
        WHERE symbol = ?
        """,
        (normalize_symbol(symbol),),
    ).fetchone()
    return dict(row) if row else None

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

    momentum_snapshot = get_momentum_snapshot_for_symbol(conn, root["symbol"])
    version_payload = _version_payload(conn, selected)
    version_payload.update({
        "momentum_score": momentum_snapshot.get("momentum_score") if momentum_snapshot else None,
        "momentum_label": momentum_snapshot.get("momentum_label") if momentum_snapshot else None,
        "extension_risk": momentum_snapshot.get("extension_risk") if momentum_snapshot else None,
        "extension_label": momentum_snapshot.get("extension_label") if momentum_snapshot else None,
        "momentum_status": momentum_snapshot.get("momentum_status") if momentum_snapshot else None,
        "momentum_updated_at": momentum_snapshot.get("momentum_updated_at") if momentum_snapshot else None,
    })
    frontier_optionality = get_frontier_optionality(conn, root["symbol"])
    version_payload.update({
        "frontier_optionality_score": frontier_optionality["frontier_optionality_score"],
        "frontier_optionality_notes": frontier_optionality["frontier_optionality_notes"],
    })
    detail = {
        "symbol": root["symbol"],
        "root_id": root["id"],
        "selected_version_id": selected["id"],
        "versions": [dict(v) for v in versions],
        "version": version_payload,
        "momentum": momentum_snapshot,
        "saved_key_variable_edits": {
            "based_on_version_id": draft["based_on_version_id"],
            "updated_at": draft["updated_at"],
            "key_variables": normalize_key_variables_for_payload(json.loads(draft["key_variables_json"])),
        } if draft else None,
        "saved_business_model_edit": _get_saved_business_model_edit(conn, root["id"]),
        "saved_business_summary_edit": _get_saved_business_summary_edit(conn, root["id"]),
        "frontier_optionality": frontier_optionality,
        "release_history": get_earnings_calendar_release_history_for_symbol(conn, root["symbol"]),
    }
    detail.update(_external_overlay_summary(conn, selected["id"]))
    return detail


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
    core_evidence_pack=None,
    core_evidence_generated_at=None,
    core_evidence_model=None,
    core_evidence_reasoning_effort=None,
    core_evidence_telemetry=None,
    scenario_generation_wall_duration_ms=None,
):
    latest = conn.execute(
        "SELECT COALESCE(MAX(version_number), 0) AS latest FROM analysis_versions WHERE analysis_root_id = ?",
        (root_id,),
    ).fetchone()["latest"]
    version_number = latest + 1
    now = utc_now_iso()

    scenarios_with_cagr = enrich_scenarios_with_midpoints(scenarios, current_price=current_price)
    expected_price = calculate_expected_price(scenarios_with_cagr)
    expected_cagr = calculate_expected_cagr_from_price(expected_price, current_price)
    upside = calculate_upside(expected_price, current_price)
    confidence = calculate_overall_confidence(key_variables)

    conn.execute(
        """
        INSERT INTO analysis_versions (
            analysis_root_id, version_number, symbol, company_name, current_price, expected_price,
            expected_cagr, upside, confidence_level, assumptions_text, business_model_text, business_summary_text,
            raw_ai_response, core_evidence_pack_json, core_evidence_generated_at, core_evidence_model,
            core_evidence_reasoning_effort, core_evidence_telemetry_json, scenario_generation_wall_duration_ms,
            source_trigger, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            root_id,
            version_number,
            symbol,
            company_name,
            current_price,
            expected_price,
            expected_cagr,
            upside,
            confidence,
            assumptions,
            business_model,
            business_summary,
            raw_ai_response,
            json.dumps(core_evidence_pack, ensure_ascii=False) if isinstance(core_evidence_pack, dict) else None,
            core_evidence_generated_at,
            core_evidence_model,
            core_evidence_reasoning_effort,
            json.dumps(core_evidence_telemetry, ensure_ascii=False) if isinstance(core_evidence_telemetry, dict) else None,
            scenario_generation_wall_duration_ms,
            source_trigger,
            now,
        ),
    )
    version_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]

    for scenario in scenarios_with_cagr:
        conn.execute(
            """
            INSERT INTO analysis_version_scenarios (
                analysis_version_id, scenario_name, price_low, price_mid, price_high, cagr_low,
                cagr_mid, cagr_high, probability, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                version_id,
                scenario["scenario_name"],
                scenario["price_low"],
                scenario.get("price_mid"),
                scenario["price_high"],
                scenario.get("cagr_low"),
                scenario.get("cagr_mid"),
                scenario.get("cagr_high"),
                scenario["probability"],
                now,
            ),
        )

    for variable in key_variables:
        conn.execute(
            """
            INSERT INTO analysis_version_key_variables (
                analysis_version_id, variable_text, variable_type, driver_category, confidence, importance, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                version_id,
                variable["variable_text"],
                variable["variable_type"],
                normalized_driver_category(variable.get("driver_category")),
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
                validation_status, rejection_reason, quality_score, is_outlier, telemetry_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                json.dumps(scenario_pass.get("telemetry"), ensure_ascii=False)
                if isinstance(scenario_pass.get("telemetry"), dict)
                else None,
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
            core_evidence_pack=ai_result["raw"].get("core_evidence_pack"),
            core_evidence_generated_at=ai_result["raw"].get("core_evidence_generated_at"),
            core_evidence_model=ai_result["raw"].get("core_evidence_model"),
            core_evidence_reasoning_effort=ai_result["raw"].get("core_evidence_reasoning_effort"),
            core_evidence_telemetry=ai_result["raw"].get("core_evidence_telemetry"),
            scenario_generation_wall_duration_ms=ai_result["raw"].get("scenario_generation_wall_duration_ms"),
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


def normalize_frontier_optionality_score(value):
    if value is None or value == "":
        return 0.0
    try:
        score = float(value)
    except (TypeError, ValueError):
        raise ValueError("frontier_optionality_score must be numeric")
    if not math.isfinite(score):
        raise ValueError("frontier_optionality_score must be numeric")
    if score < 0.0:
        raise ValueError("frontier_optionality_score cannot be below 0")
    if score > 5.0:
        raise ValueError("frontier_optionality_score cannot exceed 5")
    return score


def get_frontier_optionality(conn, symbol):
    normalized = normalize_symbol(symbol)
    if not normalized:
        return {
            "symbol": normalized,
            "frontier_optionality_score": 0.0,
            "frontier_optionality_notes": "",
            "created_at": None,
            "updated_at": None,
        }
    row = conn.execute(
        """
        SELECT symbol, frontier_optionality_score, frontier_optionality_notes, created_at, updated_at
        FROM analysis_frontier_optionality
        WHERE symbol = ?
        """,
        (normalized,),
    ).fetchone()
    if row:
        payload = dict(row)
        payload["frontier_optionality_score"] = normalize_frontier_optionality_score(payload.get("frontier_optionality_score"))
        payload["frontier_optionality_notes"] = payload.get("frontier_optionality_notes") or ""
        return payload
    return {
        "symbol": normalized,
        "frontier_optionality_score": 0.0,
        "frontier_optionality_notes": "",
        "created_at": None,
        "updated_at": None,
    }


def save_frontier_optionality(conn, symbol, score, notes=None):
    normalized = normalize_symbol(symbol)
    if not normalized:
        raise ValueError("Symbol is required")
    root = conn.execute("SELECT symbol FROM analysis_roots WHERE symbol = ?", (normalized,)).fetchone()
    if not root:
        raise ValueError("Analysis symbol not found")
    normalized_score = normalize_frontier_optionality_score(score)
    if notes is None:
        existing = conn.execute(
            "SELECT frontier_optionality_notes FROM analysis_frontier_optionality WHERE symbol = ?",
            (normalized,),
        ).fetchone()
        normalized_notes = existing["frontier_optionality_notes"] if existing else ""
    else:
        normalized_notes = str(notes or "").strip()
    now = utc_now_iso()
    conn.execute(
        """
        INSERT INTO analysis_frontier_optionality (
            symbol, frontier_optionality_score, frontier_optionality_notes, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(symbol) DO UPDATE SET
          frontier_optionality_score = excluded.frontier_optionality_score,
          frontier_optionality_notes = excluded.frontier_optionality_notes,
          updated_at = excluded.updated_at
        """,
        (normalized, normalized_score, normalized_notes, now, now),
    )
    conn.commit()
    return get_analysis_detail(conn, normalized)


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

    key_variables = normalize_key_variables_for_payload(json.loads(draft["key_variables_json"]))

    templates, _sources = get_prompt_templates_for_keys(
        conn,
        (ANALYSIS_PROMPT_SETTING_KEY_CORE_EVIDENCE_PACK, ANALYSIS_PROMPT_SETTING_KEY_SCENARIOS),
        purpose="analysis_scenario_rerun_from_saved_edits",
    )
    scenario_settings = get_scenario_generation_config(conn)
    business_model_draft = _get_saved_business_model_edit(conn, root["id"])
    business_summary_draft = _get_saved_business_summary_edit(conn, root["id"])
    effective_business_model = base_version["business_model_text"]
    effective_business_summary = base_version["business_summary_text"]
    if business_model_draft and int(business_model_draft["based_on_version_id"]) == int(base_version_id):
        effective_business_model = business_model_draft["business_model"]
    if business_summary_draft and int(business_summary_draft["based_on_version_id"]) == int(base_version_id):
        effective_business_summary = business_summary_draft["business_summary"]
    scenario_wall_started_at = time.monotonic()
    core_evidence = generate_core_evidence_pack(
        symbol=symbol,
        current_price=base_version["current_price"],
        company_name=base_version["company_name"] or "",
        business_model=effective_business_model or "",
        business_summary=effective_business_summary or "",
        key_variables=key_variables,
        template=templates[ANALYSIS_PROMPT_SETTING_KEY_CORE_EVIDENCE_PACK],
    )
    prompt = build_scenario_generation_prompt(
        symbol,
        base_version["current_price"],
        template=templates[ANALYSIS_PROMPT_SETTING_KEY_SCENARIOS],
        company_name=base_version["company_name"] or "",
        business_model=effective_business_model or "",
        business_summary=effective_business_summary or "",
        key_variables=key_variables,
        core_evidence_pack=core_evidence["pack"],
    )
    pass_count = scenario_settings["scenario_pass_count"] if scenario_settings["scenario_multi_pass_enabled"] else 1
    scenario_parsed, scenario_runs = generate_scenarios_multi_pass(
        symbol=symbol,
        key_variables=key_variables,
        prompt_text=prompt,
        pass_count=pass_count,
        outlier_filter_enabled=scenario_settings["scenario_outlier_filter_enabled"],
        current_price=base_version["current_price"],
    )
    scenario_generation_wall_duration_ms = round((time.monotonic() - scenario_wall_started_at) * 1000)
    parsed = validate_step3_scenarios(
        {
            "symbol": symbol,
            "current_price": base_version["current_price"],
            "assumptions": scenario_parsed["assumptions"],
            "scenarios": [
                {
                    "name": s["scenario_name"],
                    "price_low": s["price_low"],
                    "price_high": s["price_high"],
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
    backend_probability_details = compute_backend_probability_details(
        key_variables,
        probability_settings["backend_base_max_probability"],
        probability_settings["backend_base_min_probability"],
    )
    backend_probs = backend_probability_details["probabilities"]
    probability_meta = choose_final_probabilities(ai_probs, backend_probs, probability_settings)
    probability_meta["backend_probability_meta"] = backend_probability_details["meta"]
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
            raw_ai_response=json.dumps({
                "core_evidence_prompt": core_evidence["prompt"],
                "core_evidence_pack": core_evidence["pack"],
                "core_evidence_generated_at": core_evidence["generated_at"],
                "core_evidence_model": core_evidence["model"],
                "core_evidence_reasoning_effort": core_evidence["reasoning_effort"],
                "core_evidence_telemetry": core_evidence["telemetry"],
                "scenario_generation_wall_duration_ms": scenario_generation_wall_duration_ms,
                "step3_prompt": prompt,
                "probability_meta": probability_meta,
                "step3_runs": scenario_runs,
            }),
            source_trigger="rerun_from_key_variable_edit",
            scenario_passes=scenario_runs,
            core_evidence_pack=core_evidence["pack"],
            core_evidence_generated_at=core_evidence["generated_at"],
            core_evidence_model=core_evidence["model"],
            core_evidence_reasoning_effort=core_evidence["reasoning_effort"],
            core_evidence_telemetry=core_evidence["telemetry"],
            scenario_generation_wall_duration_ms=scenario_generation_wall_duration_ms,
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
            SELECT variable_text, variable_type, COALESCE(driver_category, 'Core Driver') AS driver_category, confidence, importance
            FROM analysis_version_key_variables
            WHERE analysis_version_id = ?
            ORDER BY id ASC
            """,
            (base_version_id,),
        ).fetchall()
    ]
    if not key_variables:
        raise ValueError("No key variables found for base version")

    templates, _sources = get_prompt_templates_for_keys(
        conn,
        (ANALYSIS_PROMPT_SETTING_KEY_CORE_EVIDENCE_PACK, ANALYSIS_PROMPT_SETTING_KEY_SCENARIOS),
        purpose="analysis_scenario_rerun_from_existing_version",
    )
    scenario_settings = get_scenario_generation_config(conn)
    business_model_draft = _get_saved_business_model_edit(conn, root["id"])
    business_summary_draft = _get_saved_business_summary_edit(conn, root["id"])
    effective_business_model = base_version["business_model_text"]
    effective_business_summary = base_version["business_summary_text"]
    if business_model_draft and int(business_model_draft["based_on_version_id"]) == int(base_version_id):
        effective_business_model = business_model_draft["business_model"]
    if business_summary_draft and int(business_summary_draft["based_on_version_id"]) == int(base_version_id):
        effective_business_summary = business_summary_draft["business_summary"]
    scenario_wall_started_at = time.monotonic()
    core_evidence = generate_core_evidence_pack(
        symbol=symbol,
        current_price=base_version["current_price"],
        company_name=base_version["company_name"] or "",
        business_model=effective_business_model or "",
        business_summary=effective_business_summary or "",
        key_variables=key_variables,
        template=templates[ANALYSIS_PROMPT_SETTING_KEY_CORE_EVIDENCE_PACK],
    )
    prompt = build_scenario_generation_prompt(
        symbol,
        base_version["current_price"],
        template=templates[ANALYSIS_PROMPT_SETTING_KEY_SCENARIOS],
        company_name=base_version["company_name"] or "",
        business_model=effective_business_model or "",
        business_summary=effective_business_summary or "",
        key_variables=key_variables,
        core_evidence_pack=core_evidence["pack"],
    )
    pass_count = scenario_settings["scenario_pass_count"] if scenario_settings["scenario_multi_pass_enabled"] else 1
    scenario_parsed, scenario_runs = generate_scenarios_multi_pass(
        symbol=symbol,
        key_variables=key_variables,
        prompt_text=prompt,
        pass_count=pass_count,
        outlier_filter_enabled=scenario_settings["scenario_outlier_filter_enabled"],
        current_price=base_version["current_price"],
    )
    scenario_generation_wall_duration_ms = round((time.monotonic() - scenario_wall_started_at) * 1000)
    parsed = validate_step3_scenarios(
        {
            "symbol": symbol,
            "current_price": base_version["current_price"],
            "assumptions": scenario_parsed["assumptions"],
            "scenarios": [
                {
                    "name": s["scenario_name"],
                    "price_low": s["price_low"],
                    "price_high": s["price_high"],
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
    backend_probability_details = compute_backend_probability_details(
        key_variables,
        probability_settings["backend_base_max_probability"],
        probability_settings["backend_base_min_probability"],
    )
    backend_probs = backend_probability_details["probabilities"]
    probability_meta = choose_final_probabilities(ai_probs, backend_probs, probability_settings)
    probability_meta["backend_probability_meta"] = backend_probability_details["meta"]
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
            raw_ai_response=json.dumps({
                "core_evidence_prompt": core_evidence["prompt"],
                "core_evidence_pack": core_evidence["pack"],
                "core_evidence_generated_at": core_evidence["generated_at"],
                "core_evidence_model": core_evidence["model"],
                "core_evidence_reasoning_effort": core_evidence["reasoning_effort"],
                "core_evidence_telemetry": core_evidence["telemetry"],
                "scenario_generation_wall_duration_ms": scenario_generation_wall_duration_ms,
                "step3_prompt": prompt,
                "probability_meta": probability_meta,
                "step3_runs": scenario_runs,
            }),
            source_trigger="rerun_from_analysis_list",
            scenario_passes=scenario_runs,
            core_evidence_pack=core_evidence["pack"],
            core_evidence_generated_at=core_evidence["generated_at"],
            core_evidence_model=core_evidence["model"],
            core_evidence_reasoning_effort=core_evidence["reasoning_effort"],
            core_evidence_telemetry=core_evidence["telemetry"],
            scenario_generation_wall_duration_ms=scenario_generation_wall_duration_ms,
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
        row["expected_price"] = analysis.get("expected_price") if analysis else None
        row["expected_cagr"] = analysis.get("expected_cagr") if analysis else None
        row["upside_original"] = analysis.get("upside_original") if analysis else None
        row["expected_price_original"] = analysis.get("expected_price_original") if analysis else None
        row["expected_cagr_original"] = analysis.get("expected_cagr_original") if analysis else None
        row["upside_effective"] = analysis.get("upside_effective") if analysis else None
        row["expected_price_effective"] = analysis.get("expected_price_effective") if analysis else None
        row["expected_cagr_effective"] = analysis.get("expected_cagr_effective") if analysis else None
        row["uses_final_scenario_overlay"] = analysis.get("uses_final_scenario_overlay") if analysis else False
        row["final_scenario_stale"] = analysis.get("final_scenario_stale") if analysis else False
        row["bullish_confidence"] = analysis.get("bullish_confidence") if analysis else None
        row["bearish_confidence"] = analysis.get("bearish_confidence") if analysis else None
        row["confidence_diff"] = analysis.get("confidence_diff") if analysis else None
        row["core_bullish_confidence"] = analysis.get("core_bullish_confidence") if analysis else None
        row["core_bearish_confidence"] = analysis.get("core_bearish_confidence") if analysis else None
        row["core_confidence_diff"] = analysis.get("core_confidence_diff") if analysis else None
        row["potential_bullish_confidence"] = analysis.get("potential_bullish_confidence") if analysis else None
        row["potential_bearish_confidence"] = analysis.get("potential_bearish_confidence") if analysis else None
        row["potential_confidence_diff"] = analysis.get("potential_confidence_diff") if analysis else None
        row["latest_release_date"] = analysis.get("latest_release_date") if analysis else None
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
    active_symbols = set()
    for row in positions or []:
        symbol = normalize_symbol(row.get("symbol"))
        if not symbol:
            continue
        qty = safe_number(row.get("position"))
        if abs(qty or 0.0) <= 0:
            conn.execute("DELETE FROM positions_cache WHERE symbol = ?", (symbol,))
            continue
        active_symbols.add(symbol)
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
    if active_symbols:
        placeholders = ", ".join(["?"] * len(active_symbols))
        conn.execute(
            f"DELETE FROM positions_cache WHERE symbol NOT IN ({placeholders})",
            tuple(sorted(active_symbols)),
        )
    else:
        conn.execute("DELETE FROM positions_cache")
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
        if abs(safe_number(row["position"]) or 0.0) > 0
    ]


def _account_summary_item_value(item):
    raw_value = getattr(item, "value", None)
    numeric = safe_number(raw_value)
    if numeric is not None:
        return numeric
    if isinstance(raw_value, str):
        cleaned = raw_value.replace(",", "").strip()
        try:
            value = float(cleaned)
        except ValueError:
            return None
        return value if math.isfinite(value) else None
    return None


def _account_summary_currency(item):
    currency = (getattr(item, "currency", None) or "").strip().upper()
    return currency or None


def _account_summary_number(summary_items, tag, currency=None):
    wanted_currency = currency.upper() if currency else None
    for item in summary_items or []:
        if getattr(item, "tag", None) != tag:
            continue
        if wanted_currency and _account_summary_currency(item) != wanted_currency:
            continue
        value = _account_summary_item_value(item)
        if value is not None:
            return value
    return None


def _account_summary_number_preferred(summary_items, tag, preferred_currency="USD", fallback_currency=None):
    for currency in (preferred_currency, fallback_currency):
        if not currency:
            continue
        value = _account_summary_number(summary_items, tag, currency)
        if value is not None:
            return value
    return _account_summary_number(summary_items, tag)


def _choose_account_cash(summary_items, base_currency=None):
    preferred = ("USD", base_currency)
    cash_preferences = (
        ("CashBalance", "ibkr_ledger_cash_balance"),
        ("TotalCashBalance", "ibkr_ledger_total_cash_balance"),
        ("SettledCash", "ibkr_settled_cash"),
        ("TotalCashValue", "ibkr_total_cash"),
    )
    for tag, source in cash_preferences:
        for currency in preferred:
            if not currency:
                continue
            value = _account_summary_number(summary_items, tag, currency)
            if value is not None:
                return value, source, tag, currency.upper()
    for tag, source in cash_preferences:
        value = _account_summary_number(summary_items, tag)
        if value is not None:
            return value, source, tag, None
    return None, "unknown", None, None


def fetch_ib_portfolio_summary(ib):
    items = ib.accountSummary() or []
    tag_currency_pairs = sorted({
        f"{getattr(item, 'tag', '')}:{_account_summary_currency(item) or 'NO_CURRENCY'}"
        for item in items
    })
    logger.info("IBKR account summary returned %s rows; tags/currencies=%s", len(items), tag_currency_pairs[:80])
    account_id = next((getattr(item, "account", None) for item in items if getattr(item, "account", None)), None)
    base_currency = next((
        _account_summary_currency(item)
        for item in items
        if _account_summary_currency(item) and getattr(item, "tag", None) in {"NetLiquidation", "TotalCashValue", "SettledCash"}
    ), None)
    net_liquidation = _account_summary_number_preferred(items, "NetLiquidation", "USD", base_currency)
    total_cash_value = _account_summary_number_preferred(items, "TotalCashValue", "USD", base_currency)
    settled_cash = _account_summary_number_preferred(items, "SettledCash", "USD", base_currency)
    ledger_cash_usd = _account_summary_number(items, "CashBalance", "USD")
    if ledger_cash_usd is None:
        ledger_cash_usd = _account_summary_number(items, "TotalCashBalance", "USD")
    actual_cash, actual_cash_source, actual_cash_tag, actual_cash_currency = _choose_account_cash(items, base_currency)
    if actual_cash is None and items:
        logger.warning("IBKR account summary returned rows but no cash tags were usable; tags/currencies=%s", tag_currency_pairs[:80])
    return {
        "account_id": account_id,
        "base_currency": base_currency or "USD",
        "net_liquidation": net_liquidation,
        "total_cash_value": total_cash_value,
        "settled_cash": settled_cash,
        "available_funds": _account_summary_number_preferred(items, "AvailableFunds", "USD", base_currency),
        "buying_power": _account_summary_number_preferred(items, "BuyingPower", "USD", base_currency),
        "excess_liquidity": _account_summary_number_preferred(items, "ExcessLiquidity", "USD", base_currency),
        "ledger_cash_usd": ledger_cash_usd,
        "actual_cash": actual_cash,
        "actual_cash_source": actual_cash_source,
        "actual_cash_tag": actual_cash_tag,
        "actual_cash_currency": actual_cash_currency,
        "available_tags": tag_currency_pairs,
    }


def save_portfolio_summary_cache(conn, summary):
    if not isinstance(summary, dict):
        return
    conn.execute(
        """
        INSERT INTO portfolio_summary_cache (
          id, account_id, base_currency, net_liquidation, total_cash_value, settled_cash,
          available_funds, buying_power, excess_liquidity, ledger_cash_usd, actual_cash, updated_at
        ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
          account_id = excluded.account_id,
          base_currency = excluded.base_currency,
          net_liquidation = excluded.net_liquidation,
          total_cash_value = excluded.total_cash_value,
          settled_cash = excluded.settled_cash,
          available_funds = excluded.available_funds,
          buying_power = excluded.buying_power,
          excess_liquidity = excluded.excess_liquidity,
          ledger_cash_usd = excluded.ledger_cash_usd,
          actual_cash = excluded.actual_cash,
          updated_at = excluded.updated_at
        """,
        (
            summary.get("account_id"),
            summary.get("base_currency"),
            summary.get("net_liquidation"),
            summary.get("total_cash_value"),
            summary.get("settled_cash"),
            summary.get("available_funds"),
            summary.get("buying_power"),
            summary.get("excess_liquidity"),
            summary.get("ledger_cash_usd"),
            summary.get("actual_cash"),
            utc_now_iso(),
        ),
    )
    conn.commit()


def load_portfolio_summary_cache(conn):
    row = conn.execute(
        """
        SELECT account_id, base_currency, net_liquidation, total_cash_value, settled_cash,
               available_funds, buying_power, excess_liquidity, ledger_cash_usd, actual_cash, updated_at
        FROM portfolio_summary_cache
        WHERE id = 1
        """
    ).fetchone()
    return dict(row) if row else None


def _parse_cash_equivalent_symbols(settings):
    raw = settings.get("action_cash_equivalent_symbols", "")
    return sorted({normalize_symbol(part) for part in str(raw or "").split(",") if normalize_symbol(part)})


def build_portfolio_cash_summary(conn, positions, settings=None):
    if settings is None:
        try:
            settings = get_action_plan_settings(conn)
        except AttributeError:
            settings = dict(ACTION_PLAN_DEFAULT_SETTINGS)
    try:
        portfolio_summary = load_portfolio_summary_cache(conn) or {}
    except AttributeError:
        portfolio_summary = {}
    positions = positions or []
    positions_by_symbol = {normalize_symbol(row.get("symbol")): row for row in positions if normalize_symbol(row.get("symbol"))}
    positions_market_value = sum(abs(safe_number(row.get("marketValue")) or 0.0) for row in positions)

    actual_cash = safe_number(portfolio_summary.get("actual_cash"))
    actual_cash_source = "ibkr_actual_cash" if actual_cash is not None else "unknown"
    if actual_cash is None:
        actual_cash = safe_number(portfolio_summary.get("ledger_cash_usd"))
        actual_cash_source = "ibkr_ledger_cash" if actual_cash is not None else "unknown"
    if actual_cash is None:
        actual_cash = safe_number(portfolio_summary.get("settled_cash"))
        actual_cash_source = "ibkr_settled_cash" if actual_cash is not None else "unknown"
    if actual_cash is None:
        actual_cash = safe_number(portfolio_summary.get("total_cash_value"))
        actual_cash_source = "ibkr_total_cash" if actual_cash is not None else "unknown"
    if actual_cash is None:
        actual_cash = 0.0

    cash_equivalent_symbols = _parse_cash_equivalent_symbols(settings)
    treat_cash_equivalents = bool(settings.get("action_treat_cash_equivalents_as_cash", True))
    cash_equivalent_positions = []
    cash_equivalent_value = 0.0
    if treat_cash_equivalents:
        for symbol in cash_equivalent_symbols:
            position = positions_by_symbol.get(symbol)
            if not position:
                continue
            market_value = abs(safe_number(position.get("marketValue")) or 0.0)
            cash_equivalent_value += market_value
            cash_equivalent_positions.append({
                "symbol": symbol,
                "market_value": market_value,
                "position": position.get("position"),
                "price": position.get("price"),
            })

    cash_like_available = actual_cash + cash_equivalent_value
    net_liquidation = safe_number(portfolio_summary.get("net_liquidation"))
    if net_liquidation is not None and net_liquidation > 0:
        total_portfolio_value = net_liquidation
        portfolio_value_source = "ibkr_net_liquidation"
        portfolio_value_warning = None
    elif positions_market_value > 0 and actual_cash_source != "unknown":
        total_portfolio_value = positions_market_value + actual_cash
        portfolio_value_source = "positions_plus_cash"
        portfolio_value_warning = None
    else:
        total_portfolio_value = positions_market_value
        portfolio_value_source = "positions_only"
        portfolio_value_warning = "Portfolio value is based only on cached positions; cash is not included because IBKR account summary is unavailable."

    return {
        "total_portfolio_value": total_portfolio_value,
        "portfolio_value_used": total_portfolio_value,
        "portfolio_value_source": portfolio_value_source,
        "portfolio_value_warning": portfolio_value_warning,
        "actual_cash": actual_cash,
        "actual_cash_source": actual_cash_source,
        "cash_equivalent_symbols": cash_equivalent_symbols,
        "cash_equivalent_value": cash_equivalent_value,
        "cash_like_available": cash_like_available,
        "cash_like_available_percent": (cash_like_available / total_portfolio_value * 100.0) if total_portfolio_value > 0 else None,
        "cash_equivalent_positions": cash_equivalent_positions,
    }


def _clamp(value, low=0.0, high=1.0):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return low
    if not math.isfinite(number):
        return low
    return max(low, min(high, number))


def _score_range(value, low, high):
    if high <= low:
        return 0.0
    return _clamp((float(value or 0.0) - low) / (high - low), 0.0, 1.0)


def _trigger_price(expected_price, required_upside):
    expected = safe_number(expected_price)
    required = safe_number(required_upside)
    if expected is None or required is None or expected <= 0:
        return None
    denominator = 1.0 + required / 100.0
    return expected / denominator if denominator > 0 else None


def _distance_to_trigger(current_price, trigger_price):
    current = safe_number(current_price)
    trigger = safe_number(trigger_price)
    if current is None or trigger is None or trigger <= 0:
        return None
    return ((current / trigger) - 1.0) * 100.0


def _format_action_amount_label(direction, amount):
    numeric_amount = safe_number(amount)
    if numeric_amount is None or numeric_amount <= 0:
        return "—"
    rounded = f"${numeric_amount:,.2f}"
    if direction == "add":
        return f"Add about {rounded}"
    if direction == "trim":
        return f"Trim about {rounded}"
    if direction == "sell":
        return f"Sell about {rounded}"
    return "—"


WHOLE_SHARE_FLOOR_TOLERANCE = Decimal("1e-9")


def _finite_decimal(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return number if number.is_finite() else None


def whole_shares_for_amount(amount, current_price):
    amount_decimal = _finite_decimal(amount)
    price_decimal = _finite_decimal(current_price)
    if amount_decimal is None or price_decimal is None or amount_decimal <= 0 or price_decimal <= 0:
        return 0
    ratio = amount_decimal / price_decimal
    return max(0, int((ratio + WHOLE_SHARE_FLOOR_TOLERANCE).to_integral_value(rounding=ROUND_FLOOR)))


def _whole_shares_from_quantity(quantity):
    quantity_decimal = _finite_decimal(quantity)
    if quantity_decimal is None or quantity_decimal <= 0:
        return 0
    floored = quantity_decimal.to_integral_value(rounding=ROUND_FLOOR)
    if quantity_decimal - floored >= Decimal("1") - WHOLE_SHARE_FLOOR_TOLERANCE:
        floored += 1
    return max(0, int(floored))


def _whole_share_amount(share_count, current_price):
    shares = max(0, int(share_count or 0))
    price_decimal = _finite_decimal(current_price)
    if shares <= 0 or price_decimal is None or price_decimal <= 0:
        return 0.0
    return float(Decimal(shares) * price_decimal)


def _owned_whole_share_fields(row):
    quantity = _finite_decimal(row.get("owned_share_quantity"))
    warning = None
    if quantity is not None:
        if quantity <= 0:
            return 0, "position_quantity", None
        whole_shares = _whole_shares_from_quantity(quantity)
        if abs(quantity - Decimal(whole_shares)) > WHOLE_SHARE_FLOOR_TOLERANCE:
            warning = "Stored position quantity is fractional; executable trim/sell quantity is capped at the whole-share portion."
        return whole_shares, "position_quantity", warning
    fallback = whole_shares_for_amount(row.get("current_position_market_value"), row.get("current_price"))
    return fallback, "market_value_fallback", None


def _mark_whole_share_action_non_executable(row, action, funding_status, diagnostic_reason):
    row["whole_share_original_action"] = row.get("action")
    row["action"] = action
    row["action_priority"] = ACTION_PLAN_ACTION_PRIORITY.get(action, 99)
    row["action_amount_direction"] = "none"
    row["suggested_share_count"] = 0
    row["action_amount"] = 0.0
    row["executable_action_amount"] = 0.0
    row["action_amount_label"] = "—"
    row["funding_status"] = funding_status
    row["whole_share_diagnostic_reason"] = diagnostic_reason


def _mark_unfunded_add_as_watch(row):
    """Expose a non-executable funded result without losing its desired action."""
    add_actions = {"Strong Add", "Add", "Starter Buy"}
    desired_action = row.get("action")
    funded_shares = int(row.get("suggested_share_count") or 0)
    if (
        desired_action not in add_actions
        or row.get("funding_status") != "Unfunded / Watch"
        or funded_shares > 0
    ):
        return

    row["desired_action"] = row.get("desired_action") or desired_action
    row["executable_action"] = "Watch"
    row["action"] = "Watch"
    row["action_priority"] = ACTION_PLAN_ACTION_PRIORITY.get("Watch", 99)
    row["action_amount_direction"] = "none"


def _mark_minimum_trade_amount_non_executable(row, action):
    """Keep a desired Add/Trim visible while preventing an undersized execution."""
    desired_action = row.get("desired_action") or row.get("action")
    row["desired_action"] = desired_action
    row["minimum_trade_size_blocked"] = True
    row["minimum_trade_size_reason"] = (
        "Final executable amount is below the configured minimum executable trade amount."
    )
    _mark_whole_share_action_non_executable(
        row,
        action,
        "Below minimum trade amount",
        row["minimum_trade_size_reason"],
    )
    row["minimum_trade_size_blocked"] = True
    row["minimum_trade_size_blocked_by_configured_minimum"] = True


def _prepare_whole_share_execution(row):
    direction = row.get("action_amount_direction") or "none"
    raw_amount = max(0.0, safe_number(row.get("raw_action_amount")) or 0.0)
    row["raw_action_amount"] = raw_amount
    row.setdefault("target_gap_amount", raw_amount)
    row["desired_share_count"] = 0
    row["desired_whole_share_amount"] = 0.0
    row["suggested_share_count"] = 0
    row["minimum_trade_size_blocked"] = False
    row["minimum_trade_size_blocked_by_configured_minimum"] = False
    row["minimum_trade_size_reason"] = None
    row["whole_share_diagnostic_reason"] = row.get("whole_share_diagnostic_reason")
    row["whole_share_diagnostic_warning"] = row.get("whole_share_diagnostic_warning")
    row["owned_whole_share_count"] = 0
    row["owned_share_quantity_source"] = None

    if direction not in {"add", "trim", "sell"}:
        return

    price = safe_number(row.get("current_price"))
    if price is None or price <= 0:
        safe_action = "Watch" if direction == "add" else ("Hold" if direction == "trim" else "Re-evaluate")
        _mark_whole_share_action_non_executable(
            row,
            safe_action,
            "Price unavailable",
            "Cannot calculate whole-share action because current price is unavailable.",
        )
        return

    owned_shares, quantity_source, quantity_warning = _owned_whole_share_fields(row)
    row["owned_whole_share_count"] = owned_shares
    row["owned_share_quantity_source"] = quantity_source
    row["whole_share_diagnostic_warning"] = quantity_warning

    if direction == "sell":
        row["desired_share_count"] = owned_shares
        row["desired_whole_share_amount"] = _whole_share_amount(owned_shares, price)
        if owned_shares < 1:
            _mark_whole_share_action_non_executable(
                row,
                "Re-evaluate",
                "No whole shares available",
                "Cannot identify at least one whole share for the requested full exit.",
            )
            return
        row["suggested_share_count"] = owned_shares
        row["action_amount"] = row["desired_whole_share_amount"]
        return

    desired_shares = whole_shares_for_amount(raw_amount, price)
    row["desired_share_count"] = desired_shares
    row["desired_whole_share_amount"] = _whole_share_amount(desired_shares, price)
    if desired_shares < 1:
        row["minimum_trade_size_blocked"] = True
        row["minimum_trade_size_reason"] = (
            "Calculated add amount is below the price of one whole share."
            if direction == "add"
            else "Calculated trim amount is below the price of one whole share."
        )
        _mark_whole_share_action_non_executable(
            row,
            "Watch" if direction == "add" else "Hold",
            "Below one-share minimum",
            row["minimum_trade_size_reason"],
        )
        return

    if direction == "trim":
        suggested_shares = min(desired_shares, owned_shares)
        if suggested_shares < 1:
            _mark_whole_share_action_non_executable(
                row,
                "Hold",
                "No whole shares available",
                "Cannot identify at least one owned whole share for the requested trim.",
            )
            return
        row["suggested_share_count"] = suggested_shares
        row["action_amount"] = _whole_share_amount(suggested_shares, price)


def _action_amount_fields(action, current_weight, target_mid, total_portfolio_value, market_value):
    total = safe_number(total_portfolio_value)
    current = safe_number(current_weight)
    target = safe_number(target_mid)
    market = safe_number(market_value)
    amount_to_mid = None
    if total is not None and total > 0 and current is not None and target is not None:
        amount_to_mid = abs(target - current) / 100.0 * total

    direction = "none"
    amount = None
    if action in {"Strong Add", "Add", "Starter Buy"}:
        direction = "add"
        if total is not None and total > 0 and current is not None and target is not None and target > current:
            amount = (target - current) / 100.0 * total
    elif action in {"Strong Trim", "Trim"}:
        direction = "trim"
        if total is not None and total > 0 and current is not None and target is not None and current > target:
            amount = (current - target) / 100.0 * total
    elif action in {"Sell", "Strong Sell"}:
        direction = "sell"
        if market is not None and market > 0:
            amount = market
        elif total is not None and total > 0 and current is not None:
            amount = current / 100.0 * total

    return {
        "raw_action_amount": amount,
        "action_amount": amount,
        "action_amount_label": _format_action_amount_label(direction, amount),
        "action_amount_direction": direction,
        "action_amount_to_mid": amount_to_mid,
    }



def _funding_priority_score(row, total_portfolio_value):
    base_priority = {
        ("Strong Buy", "Strong Add"): 100,
        ("Strong Buy", "Add"): 90,
        ("Strong Buy", "Starter Buy"): 80,
        ("Buy", "Strong Add"): 70,
        ("Buy", "Add"): 60,
        ("Buy", "Starter Buy"): 50,
        ("Speculative Buy", "Strong Add"): 40,
        ("Speculative Buy", "Add"): 35,
        ("Hold", "Add"): 20,
    }.get((row.get("rating"), row.get("action")), 0)
    gap = safe_number(row.get("target_gap_amount")) or 0.0
    total = safe_number(total_portfolio_value) or 0.0
    normalized_gap_score = min(gap / total / 0.05, 1.0) if total > 0 else 0.0
    return (
        base_priority
        + 20.0 * (safe_number(row.get("allocation_score")) or 0.0)
        + 10.0 * (safe_number(row.get("bucket_sizing_score")) or 0.0)
        + 10.0 * (safe_number(row.get("trigger_quality_score")) or 0.0)
        + 10.0 * normalized_gap_score
    )


def _apply_cash_constrained_execution_layer(rows, total_portfolio_value, cash_like_available, settings):
    total = safe_number(total_portfolio_value) or 0.0
    cash_available = safe_number(cash_like_available) or 0.0
    minimum_cash_reserve_amount = total * (safe_number(settings.get("action_min_cash_unallocated_target")) or 0.0) / 100.0
    buy_actions = {"Strong Add", "Add", "Starter Buy"}
    sell_trim_actions = {"Sell", "Strong Sell", "Trim", "Strong Trim"}
    executable_sell_trim_proceeds = 0.0

    for row in rows:
        row["raw_action_amount"] = max(0.0, safe_number(row.get("raw_action_amount")) or safe_number(row.get("action_amount")) or 0.0)
        row["target_gap_amount"] = row["raw_action_amount"]
        _prepare_whole_share_execution(row)
        direction = row.get("action_amount_direction")
        row["executable_action_amount"] = 0.0
        row["unfunded_action_amount"] = 0.0
        row["unfunded_share_count"] = 0
        row["funding_priority_score"] = 0.0
        if row.get("minimum_trade_size_blocked"):
            row["funding_status"] = "Below one-share minimum"
        elif row.get("whole_share_diagnostic_reason") and direction == "none":
            row["funding_status"] = row.get("funding_status") or "No executable action"
        elif row.get("action") in sell_trim_actions or direction in {"trim", "sell"}:
            executable = max(0.0, safe_number(row.get("action_amount")) or 0.0)
            row["executable_action_amount"] = executable
            row["funding_status"] = "Generates proceeds" if executable > 0 else "No funding needed"
            executable_sell_trim_proceeds += executable
        elif row.get("action") in buy_actions and direction == "add" and row.get("desired_share_count", 0) > 0:
            row["funding_status"] = "Unfunded / Watch"
        else:
            row["funding_status"] = "No funding needed"

    available_buy_budget = max(0.0, cash_available + executable_sell_trim_proceeds - minimum_cash_reserve_amount)
    buy_candidates = [
        row for row in rows
        if row.get("action") in buy_actions
        and row.get("action_amount_direction") == "add"
        and row.get("desired_share_count", 0) > 0
    ]
    total_add_demand = sum(row.get("desired_whole_share_amount", 0.0) for row in buy_candidates)
    min_trade = safe_number(settings.get("action_min_executable_trade_amount")) or 0.0
    remaining_budget = available_buy_budget
    for row in buy_candidates:
        row["funding_priority_score"] = _funding_priority_score(row, total)
    sorted_buy_candidates = sorted(
        buy_candidates,
        key=lambda row: (
            -(safe_number(row.get("funding_priority_score")) or 0.0),
            ACTION_PLAN_ACTION_PRIORITY.get(row.get("action"), 99),
            -(safe_number(row.get("allocation_score")) or 0.0),
            -(safe_number(row.get("upside")) or 0.0),
            row.get("symbol") or "",
        ),
    )
    for index, row in enumerate(sorted_buy_candidates):
        desired_shares = int(row.get("desired_share_count") or 0)
        price = safe_number(row.get("current_price"))
        affordable_shares = whole_shares_for_amount(remaining_budget, price)
        funded_shares = min(desired_shares, affordable_shares)
        amount = _whole_share_amount(funded_shares, price)
        is_last_candidate = index == len(sorted_buy_candidates) - 1
        if amount < min_trade and not (is_last_candidate and amount > 0):
            funded_shares = 0
            amount = 0.0
        unfunded_shares = max(0, desired_shares - funded_shares)
        row["suggested_share_count"] = funded_shares
        row["executable_action_amount"] = amount
        row["unfunded_share_count"] = unfunded_shares
        row["unfunded_action_amount"] = _whole_share_amount(unfunded_shares, price)
        if funded_shares == desired_shares and desired_shares > 0:
            row["funding_status"] = "Fully funded"
        elif funded_shares > 0:
            row["funding_status"] = "Partially funded"
        else:
            row["funding_status"] = "Unfunded / Watch"
        remaining_budget = max(0.0, remaining_budget - amount)

    funded_add_amount = sum(row.get("executable_action_amount", 0.0) for row in buy_candidates)
    unfunded_add_demand = sum(row.get("unfunded_action_amount", 0.0) for row in buy_candidates)
    for row in rows:
        executable = safe_number(row.get("executable_action_amount")) or 0.0
        row["action_amount"] = executable
        row["action_amount_label"] = _format_action_amount_label(row.get("action_amount_direction"), executable)
        row["available_buy_budget"] = available_buy_budget
        row["total_add_demand"] = total_add_demand
        row["funded_add_amount"] = funded_add_amount
        row["unfunded_add_demand"] = unfunded_add_demand
        row["executable_sell_trim_proceeds"] = executable_sell_trim_proceeds
        row["minimum_cash_reserve_amount"] = minimum_cash_reserve_amount
        if row.get("minimum_trade_size_blocked"):
            row["action_amount_cash_note"] = row.get("minimum_trade_size_reason")
        elif row.get("whole_share_diagnostic_reason") and row.get("action_amount_direction") == "none":
            row["action_amount_cash_note"] = row.get("whole_share_diagnostic_reason")
        elif row.get("action_amount_direction") == "add":
            if row["funding_status"] == "Fully funded":
                row["action_amount_cash_note"] = f"Add about ${executable:,.2f} to reach the calculated target midpoint."
            elif row["funding_status"] == "Partially funded":
                row["action_amount_cash_note"] = f"Target gap is ${row['target_gap_amount']:,.2f}, but only ${executable:,.2f} is executable now based on available cash and higher-priority actions."
            else:
                row["action_amount_cash_note"] = f"Target gap is ${row['target_gap_amount']:,.2f}, but no whole share is currently funded based on available cash and higher-priority actions."
        elif row.get("action_amount_direction") in {"trim", "sell"}:
            row["action_amount_cash_note"] = f"Sell/trim about ${executable:,.2f}. This action generates proceeds that can fund buy actions." if executable > 0 else "No funding needed."
        else:
            row["action_amount_cash_note"] = "No funding needed."
        _mark_unfunded_add_as_watch(row)
    return {
        "available_buy_budget": available_buy_budget,
        "total_add_demand": total_add_demand,
        "funded_add_amount": funded_add_amount,
        "unfunded_add_demand": unfunded_add_demand,
        "executable_sell_trim_proceeds": executable_sell_trim_proceeds,
        "minimum_cash_reserve_amount": minimum_cash_reserve_amount,
    }

def _trigger_price_from_required_upside(expected_price, required_upside_ratio):
    expected = safe_number(expected_price)
    required = safe_number(required_upside_ratio)
    if expected is None or required is None or expected <= 0:
        return None
    denominator = 1.0 + required
    return expected / denominator if denominator > 0 else None


def _trigger_price_distance_label(current_price, trigger_price, trigger_type):
    current = safe_number(current_price)
    trigger = safe_number(trigger_price)
    if current is None or trigger is None or trigger <= 0:
        return "N/A"
    pct = abs((current - trigger) / trigger * 100.0)
    direction = "below" if current < trigger else "above"
    label_type = (trigger_type or "trigger").replace("_", " ").title()
    return f"Price is {pct:.2f}% {direction} {label_type} trigger"


def _position_status(current_weight, target_low, target_mid, target_high):
    if target_mid <= 0:
        return "NO_TARGET"
    if current_weight < target_low:
        return "BELOW_TARGET"
    if current_weight > target_high:
        return "ABOVE_TARGET"
    return "INSIDE_TARGET"


def _trigger_quality_score(row):
    return _clamp(
        0.60 * (safe_number(row.get("allocation_score")) or 0.0)
        + 0.30 * (safe_number(row.get("bucket_sizing_score")) or 0.0)
        + 0.10 * (safe_number(row.get("weighted_count")) or 0.0),
        0.0,
        1.0,
    )


def calculate_dynamic_required_upside(action_type, base_required_upside, current_weight, target_low, target_mid, target_high, allocation_score, bucket_sizing_score, weighted_count, settings):
    trigger_quality_score = _clamp(
        0.60 * (safe_number(allocation_score) or 0.0)
        + 0.30 * (safe_number(bucket_sizing_score) or 0.0)
        + 0.10 * (safe_number(weighted_count) or 0.0),
        0.0,
        1.0,
    )
    current = safe_number(current_weight) or 0.0
    target = safe_number(target_mid) or 0.0
    underweight_strength = _clamp((target - current) / target, 0.0, 1.0) if target > 0 and current < target else 0.0
    overweight_strength = _clamp((current - target) / target, 0.0, 1.0) if target > 0 and current > target else 0.0
    dynamic_required = (
        float(base_required_upside or 0.0)
        - underweight_strength * settings["action_underweight_discount_max"]
        - trigger_quality_score * settings["action_quality_discount_max"]
        + overweight_strength * settings["action_overweight_penalty_max"]
        + (1.0 - trigger_quality_score) * settings["action_low_quality_penalty_max"]
    )
    return _clamp(dynamic_required, settings["action_trigger_min_required_upside"], settings["action_trigger_max_required_upside"]), trigger_quality_score



def _allocation_trigger_price(current_price, current_market_value, portfolio_value, target_weight_pct):
    price = safe_number(current_price)
    market_value = safe_number(current_market_value)
    portfolio = safe_number(portfolio_value)
    target_pct = safe_number(target_weight_pct)
    if price is None or price <= 0 or market_value is None or market_value <= 0 or portfolio is None or portfolio <= 0 or target_pct is None:
        return None
    target_weight = target_pct / 100.0
    if target_weight <= 0 or target_weight >= 1:
        return None
    shares = market_value / price
    if shares <= 0:
        return None
    other_value = max(0.0, portfolio - market_value)
    denominator = shares * (1.0 - target_weight)
    if denominator <= 0:
        return None
    return (target_weight * other_value) / denominator


def _action_momentum_inputs(row):
    momentum = safe_number(row.get("momentum_score"))
    extension = safe_number(row.get("extension_risk"))
    reason = None
    if momentum is None:
        momentum = 2.5
        reason = "Momentum unavailable; neutral adjustment used."
    if extension is None:
        extension = 2.0
        reason = "Momentum unavailable; neutral adjustment used."
    return momentum, row.get("momentum_label"), extension, row.get("extension_label"), reason


def _trigger_multiplier_for_action(row, trigger_family, settings):
    momentum, momentum_label_value, extension, extension_label_value, neutral_reason = _action_momentum_inputs(row)
    momentum_signal = _clamp((momentum - 2.5) / 2.5, -1.0, 1.0)
    extension_signal = _clamp(extension / 5.0, 0.0, 1.0)
    if trigger_family == "add":
        healthy_momentum_signal = max(momentum_signal, 0.0) * (1.0 - extension_signal)
        weak_momentum_signal = max(-momentum_signal, 0.0)
        raw_multiplier = (
            1.0
            + healthy_momentum_signal * settings["action_momentum_add_max_raise"]
            - weak_momentum_signal * settings["action_momentum_add_max_lower"]
            - extension_signal * settings["action_extension_add_max_lower"]
        )
    else:
        positive_momentum_signal = max(momentum_signal, 0.0)
        weak_momentum_signal = max(-momentum_signal, 0.0)
        raw_multiplier = (
            1.0
            + positive_momentum_signal * settings["action_momentum_trim_max_raise"]
            - weak_momentum_signal * settings["action_momentum_trim_max_lower"]
            - extension_signal * settings["action_extension_trim_max_lower"]
        )
    multiplier = _clamp(raw_multiplier, settings["action_min_trigger_multiplier"], settings["action_max_trigger_multiplier"])
    parts = [
        neutral_reason,
        f"Momentum {momentum:.1f}/5 ({momentum_label_value or 'unlabeled'}); Extension Risk {extension:.1f}/5 ({extension_label_value or 'unlabeled'}).",
        f"{trigger_family.title()} trigger multiplier {multiplier:.3f} from raw {raw_multiplier:.3f}.",
    ]
    return multiplier, " ".join(part for part in parts if part), momentum, momentum_label_value, extension, extension_label_value


def _allocation_based_trigger_context(row, settings):
    current_weight = safe_number(row.get("current_position_weight")) or 0.0
    target_low = safe_number(row.get("target_weight_low")) or 0.0
    target_mid = safe_number(row.get("target_weight_mid")) or 0.0
    target_high = safe_number(row.get("target_weight_high")) or 0.0
    current_price = safe_number(row.get("current_price"))
    expected_price = safe_number(row.get("expected_price"))
    upside = safe_number(row.get("upside"))
    portfolio_value = safe_number(row.get("total_portfolio_value")) or 0.0
    market_value = safe_number(row.get("current_position_market_value"))
    if market_value is None and portfolio_value > 0:
        market_value = current_weight / 100.0 * portfolio_value
    market_value = market_value or 0.0
    status = _position_status(current_weight, target_low, target_mid, target_high)
    remaining_upside = (expected_price / current_price - 1.0) if current_price and expected_price else None
    quality = _trigger_quality_score(row)

    add_base = _allocation_trigger_price(current_price, market_value, portfolio_value, target_low)
    trim_base = _allocation_trigger_price(current_price, market_value, portfolio_value, target_high)
    add_multiplier, add_reason, momentum, momentum_label_value, extension, extension_label_value = _trigger_multiplier_for_action(row, "add", settings)
    trim_multiplier, trim_reason, _, _, _, _ = _trigger_multiplier_for_action(row, "trim", settings)
    add_trigger = add_base * add_multiplier if add_base is not None else None
    trim_trigger = trim_base * trim_multiplier if trim_base is not None else None

    starter_trigger = None
    starter_reason = "Starter buy fallback; no existing shares."
    if market_value <= 0 and current_price is not None and target_mid > 0:
        starter_trigger = current_price
        add_trigger = current_price
        add_base = current_price
    sell_trigger = current_price
    return {
        "position_status": status,
        "remaining_upside": remaining_upside,
        "trigger_quality_score": quality,
        "starter_buy_required_upside": None,
        "add_required_upside": None,
        "strong_add_required_upside": None,
        "starter_buy_trigger_price": starter_trigger,
        "add_trigger_price": add_trigger,
        "strong_add_trigger_price": add_trigger,
        "trim_trigger_price": trim_trigger,
        "sell_trigger_price": sell_trigger,
        "base_trigger_price": add_base if status == "BELOW_TARGET" else trim_base if status == "ABOVE_TARGET" else None,
        "adjusted_trigger_price": add_trigger if status == "BELOW_TARGET" else trim_trigger if status == "ABOVE_TARGET" else None,
        "trigger_multiplier": add_multiplier if status == "BELOW_TARGET" else trim_multiplier if status == "ABOVE_TARGET" else None,
        "trigger_adjustment_reason": add_reason if status == "BELOW_TARGET" else trim_reason if status == "ABOVE_TARGET" else None,
        "trigger_anchor": "Target Low" if status == "BELOW_TARGET" else "Target High" if status == "ABOVE_TARGET" else "Hold",
        "momentum_score": momentum,
        "momentum_label": momentum_label_value,
        "extension_risk": extension,
        "extension_label": extension_label_value,
        "starter_buy_fallback_reason": starter_reason if market_value <= 0 else None,
        "trigger_formula": "Allocation-based trigger anchored to Target Low/Target High and adjusted by stored Momentum/Extension Risk.",
    }


def _action_plan_trigger_context(row, settings):
    if settings.get("action_use_allocation_based_triggers", True):
        return _allocation_based_trigger_context(row, settings)
    current_weight = safe_number(row.get("current_position_weight")) or 0.0
    target_low = safe_number(row.get("target_weight_low")) or 0.0
    target_mid = safe_number(row.get("target_weight_mid")) or 0.0
    target_high = safe_number(row.get("target_weight_high")) or 0.0
    current_price = safe_number(row.get("current_price"))
    expected_price = safe_number(row.get("expected_price"))
    remaining_upside = (expected_price / current_price - 1.0) if current_price and expected_price else None
    status = _position_status(current_weight, target_low, target_mid, target_high)
    starter_required, quality = calculate_dynamic_required_upside(
        "starter_buy",
        settings["action_starter_buy_base_required_upside"],
        current_weight,
        target_low,
        target_mid,
        target_high,
        row.get("allocation_score"),
        row.get("bucket_sizing_score"),
        row.get("weighted_count"),
        settings,
    )
    add_required, _ = calculate_dynamic_required_upside(
        "add",
        settings["action_add_base_required_upside"],
        current_weight,
        target_low,
        target_mid,
        target_high,
        row.get("allocation_score"),
        row.get("bucket_sizing_score"),
        row.get("weighted_count"),
        settings,
    )
    strong_required, _ = calculate_dynamic_required_upside(
        "strong_add",
        settings["action_strong_add_base_required_upside"],
        current_weight,
        target_low,
        target_mid,
        target_high,
        row.get("allocation_score"),
        row.get("bucket_sizing_score"),
        row.get("weighted_count"),
        settings,
    )
    trim_trigger = _trigger_price_from_required_upside(expected_price, settings["action_trim_remaining_upside_threshold"])
    sell_trigger = _trigger_price_from_required_upside(expected_price, settings["action_sell_remaining_upside_threshold"])
    return {
        "position_status": status,
        "remaining_upside": remaining_upside,
        "trigger_quality_score": quality,
        "starter_buy_required_upside": starter_required,
        "add_required_upside": add_required,
        "strong_add_required_upside": strong_required,
        "starter_buy_trigger_price": _trigger_price_from_required_upside(expected_price, starter_required),
        "add_trigger_price": _trigger_price_from_required_upside(expected_price, add_required),
        "strong_add_trigger_price": _trigger_price_from_required_upside(expected_price, strong_required),
        "trim_trigger_price": trim_trigger,
        "sell_trigger_price": sell_trigger,
    }


def _action_plan_trigger_breakdown(row):
    trigger_type = row.get("relevant_trigger_type")
    trigger_price = row.get("relevant_trigger_price")
    return {
        "position_status": row.get("position_status"),
        "remaining_upside": row.get("remaining_upside"),
        "trigger_quality_score": row.get("trigger_quality_score"),
        "dynamic_required_upside": row.get("dynamic_required_upside"),
        "starter_buy_required_upside": row.get("starter_buy_required_upside"),
        "add_required_upside": row.get("add_required_upside"),
        "strong_add_required_upside": row.get("strong_add_required_upside"),
        "starter_buy_trigger_price": row.get("starter_buy_trigger_price"),
        "add_trigger_price": row.get("add_trigger_price"),
        "strong_add_trigger_price": row.get("strong_add_trigger_price"),
        "trim_trigger_price": row.get("trim_trigger_price"),
        "sell_trigger_price": row.get("sell_trigger_price"),
        "base_trigger_price": row.get("base_trigger_price"),
        "adjusted_trigger_price": row.get("adjusted_trigger_price"),
        "trigger_multiplier": row.get("trigger_multiplier"),
        "trigger_adjustment_reason": row.get("trigger_adjustment_reason"),
        "trigger_anchor": row.get("trigger_anchor"),
        "momentum_score": row.get("momentum_score"),
        "momentum_label": row.get("momentum_label"),
        "extension_risk": row.get("extension_risk"),
        "extension_label": row.get("extension_label"),
        "relevant_trigger_price": trigger_price,
        "relevant_trigger_type": trigger_type,
        "distance_to_relevant_trigger_percent": _distance_to_trigger(row.get("current_price"), trigger_price),
        "distance_to_relevant_trigger_label": _trigger_price_distance_label(row.get("current_price"), trigger_price, trigger_type),
        "formula": row.get("trigger_formula") or "Legacy buy triggers use allocation-aware required upside; trim/sell triggers use remaining-upside thresholds.",
    }


def _action_plan_decision_path(row, action):
    path = []
    if row.get("final_scenario_stale"):
        path.append({"status": "warning", "text": "Final Scenario overlay is stale."})
    path.append({"status": "pass", "text": f"Rating is {row.get('rating') or 'Hold'}."})
    current_weight = safe_number(row.get("current_position_weight")) or 0.0
    target_low = safe_number(row.get("target_weight_low")) or 0.0
    target_high = safe_number(row.get("target_weight_high")) or 0.0
    target_mid = safe_number(row.get("target_weight_mid")) or 0.0
    if current_weight < target_low:
        path.append({"status": "pass", "text": "Current position is below the target band."})
    elif current_weight > target_high:
        path.append({"status": "pass", "text": "Current position is above the target band."})
    else:
        path.append({"status": "pass", "text": "Current position is inside the target band."})
    if action in {"Strong Add", "Add", "Starter Buy"}:
        path.append({"status": "pass", "text": "Current price is at or below the relevant buy trigger."})
    elif action in {"Trim", "Strong Trim", "Sell"}:
        path.append({"status": "pass", "text": "Position reduction rule is active for this symbol."})
    elif action == "Watch":
        path.append({"status": "fail", "text": "Current price is above the relevant buy trigger."})
    elif action == "Re-evaluate":
        path.append({"status": "warning", "text": "Required price, upside, portfolio, or scenario freshness data is incomplete."})
    else:
        path.append({"status": "pass", "text": f"Current weight {current_weight:.2f}% is near target midpoint {target_mid:.2f}%."})
    path.append({"status": "result", "text": f"Action = {action}."})
    return path


def _is_action_plan_eligible(analysis, owned, settings):
    rating = analysis.get("rating") or "Hold"
    if owned and settings["action_include_current_positions"]:
        return True
    if rating == "Strong Buy" and settings["action_include_strong_buy"]:
        return True
    if rating == "Buy" and settings["action_include_buy"]:
        return True
    if rating == "Speculative Buy" and settings["action_include_speculative_buy"]:
        return True
    if rating == "Hold" and owned and settings["action_include_hold_only_if_owned"]:
        return True
    if rating in {"Sell", "Strong Sell"} and owned and settings["action_include_sell_only_if_owned"]:
        return True
    return False


def _rating_cap_for_action_plan(rating, settings):
    caps = [settings["action_max_single_stock_weight"]]
    if rating == "Strong Buy":
        caps.append(settings["action_max_strong_buy_stock_weight"])
    elif rating == "Buy":
        caps.append(settings["action_max_buy_stock_weight"])
    elif rating == "Speculative Buy":
        caps.append(settings["action_max_speculative_buy_stock_weight"])
    elif rating == "Hold":
        caps.append(min(settings["action_max_buy_stock_weight"], settings["action_max_single_stock_weight"]))
    elif rating in {"Sell", "Strong Sell"}:
        caps.append(0.0)
    return min(caps)


def _target_band(target_mid, rating, settings):
    target = safe_number(target_mid) or 0.0
    if target <= 0:
        return 0.0, 0.0
    if rating == "Speculative Buy":
        low_multiplier = settings["action_speculative_band_lower_multiplier"]
        high_multiplier = settings["action_speculative_band_upper_multiplier"]
    else:
        low_multiplier = settings.get("action_target_band_lower_multiplier", settings["action_band_lower_multiplier"])
        high_multiplier = settings.get("action_target_band_upper_multiplier", settings["action_band_upper_multiplier"])
    low = target * low_multiplier
    high = target * high_multiplier
    min_width = settings["action_min_absolute_band_width"]
    if high - low < min_width:
        half = min_width / 2.0
        low = min(low, target - half)
        high = max(high, target + half)
    low = max(0.0, min(low, target))
    high = max(target, high)
    return low, high


def _choose_action_plan_decision(row, settings):
    rating = row["rating"]
    current_weight = safe_number(row.get("current_position_weight")) or 0.0
    target_mid = safe_number(row.get("target_weight_mid")) or 0.0
    target_low = safe_number(row.get("target_weight_low")) or 0.0
    target_high = safe_number(row.get("target_weight_high")) or 0.0
    current_price = safe_number(row.get("current_price"))
    expected_price = safe_number(row.get("expected_price"))
    upside = safe_number(row.get("upside"))
    if row.get("final_scenario_stale"):
        return "Re-evaluate", None, None, None, "Final Scenario overlay is stale; re-evaluate before taking action."
    if current_price is None or expected_price is None or upside is None:
        return "Re-evaluate", None, None, None, "Missing current price, expected price, or upside."

    context = _action_plan_trigger_context(row, settings)
    row.update(context)
    position_status = context["position_status"]
    strong_trigger = context["strong_add_trigger_price"]
    add_trigger = context["add_trigger_price"]
    starter_trigger = context["starter_buy_trigger_price"]
    trim_trigger = context["trim_trigger_price"]
    sell_trigger = context["sell_trigger_price"]
    quality = context["trigger_quality_score"]

    def choose(action, trigger, trigger_type, required, reason):
        row["relevant_trigger_price"] = trigger
        row["relevant_trigger_type"] = trigger_type
        row["dynamic_required_upside"] = required
        if trigger is not None:
            row["adjusted_trigger_price"] = trigger
        return action, trigger, "below" if trigger_type in {"strong_add", "add", "starter_buy"} else "above", _distance_to_trigger(current_price, trigger), reason

    if rating == "Strong Sell":
        row["trigger_anchor"] = "Sell Override"
        row["trigger_adjustment_reason"] = "Sell override used; momentum does not block explicit exits."
        return choose("Sell", sell_trigger, "sell", settings.get("action_sell_remaining_upside_threshold"), "Rating is Strong Sell; target allocation should be zero or near zero.")
    if rating == "Sell" or target_mid <= 0:
        row["trigger_anchor"] = "Sell Override"
        row["trigger_adjustment_reason"] = "Sell override used; momentum does not block explicit exits."
        return choose("Sell", sell_trigger, "sell", settings.get("action_sell_remaining_upside_threshold"), "Target allocation is zero or rating is Sell.")

    if position_status == "BELOW_TARGET":
        if upside is None or upside <= 0 or target_mid <= 0 or current_price is None or expected_price is None:
            return choose("Watch", add_trigger, "add", context.get("add_required_upside"), "Fundamental guardrail: Add is blocked because upside, target, current price, or expected price is unavailable/unattractive.")
        if rating == "Hold" and current_weight <= 0:
            return choose("Watch", add_trigger, "add", context.get("add_required_upside"), "Starter Buy guardrail: Hold-rated non-owned stocks are not starter buys.")
        if rating in {"Sell", "Strong Sell"}:
            return choose("Watch", add_trigger, "add", context.get("add_required_upside"), "Fundamental guardrail: Sell-rated stocks are not Add candidates.")
        if current_weight <= 0:
            if safe_number(context.get("extension_risk")) is not None and safe_number(context.get("extension_risk")) >= 4.0:
                return choose("Watch", starter_trigger, "starter_buy", context.get("starter_buy_required_upside"), "Starter buy fallback blocked because Extension Risk is high.")
            if safe_number(context.get("momentum_score")) is not None and safe_number(context.get("momentum_score")) < 2.0:
                return choose("Watch", starter_trigger, "starter_buy", context.get("starter_buy_required_upside"), "Starter buy fallback blocked because Momentum is weak.")
        if strong_trigger is not None and current_price <= strong_trigger and quality >= 0.50:
            return choose("Strong Add", strong_trigger, "strong_add", context["strong_add_required_upside"], "Position is below target band, trigger quality is high, and current price is below the allocation-based Strong Add trigger.")
        if add_trigger is not None and current_price <= add_trigger:
            return choose("Add", add_trigger, "add", context["add_required_upside"], "Position is below target band and current price is below the allocation-based Add trigger.")
        if current_weight <= settings["action_starter_buy_max_initial_weight"] and starter_trigger is not None and current_price <= starter_trigger:
            return choose("Starter Buy", starter_trigger, "starter_buy", context["starter_buy_required_upside"], "Position is below target band and current price is below the allocation-based Starter Buy trigger.")
        return choose("Watch", add_trigger, "add", context["add_required_upside"], "Position is below target band, but current price is above the allocation-based Add trigger.")

    if position_status == "INSIDE_TARGET":
        room_to_mid = target_mid - current_weight
        if room_to_mid > settings["action_min_trade_gap_percent"] and strong_trigger is not None and current_price <= strong_trigger and quality >= 0.80:
            return choose("Add", strong_trigger, "strong_add", context["strong_add_required_upside"], "Position is inside target band but price is extremely attractive and there is room toward target mid.")
        row["relevant_trigger_price"] = None
        row["relevant_trigger_type"] = "hold"
        row["dynamic_required_upside"] = None
        return "Hold", None, None, None, "Position is inside target band."

    if position_status == "ABOVE_TARGET":
        overweight_ratio = ((current_weight - target_high) / target_mid) if target_mid > 0 else 0.0
        hard_cap = _rating_cap_for_action_plan(rating, settings)
        hard_cap_exceeded = current_weight > hard_cap + settings["action_min_trade_gap_percent"]
        trim_reached = trim_trigger is not None and current_price >= trim_trigger
        if trim_reached:
            action = "Strong Trim" if overweight_ratio >= settings["action_strong_trim_gap_threshold"] or hard_cap_exceeded else "Trim"
            reason = "Position is above target band and current price has reached the Trim trigger."
            if hard_cap_exceeded:
                reason = "Position is above target band, current price has reached the Trim trigger, and the hard risk cap is exceeded."
            return choose(action, trim_trigger, "trim", settings["action_trim_remaining_upside_threshold"], reason)
        row["relevant_trigger_price"] = trim_trigger
        row["relevant_trigger_type"] = "trim"
        row["dynamic_required_upside"] = settings["action_trim_remaining_upside_threshold"]
        return "Hold / Overweight", trim_trigger, "above", _distance_to_trigger(current_price, trim_trigger), "Position is above target band, but current price is below the Trim trigger and remaining upside is still attractive."

    row["relevant_trigger_price"] = None
    row["relevant_trigger_type"] = "hold"
    row["dynamic_required_upside"] = None
    return "Hold", None, None, None, "No allocation-based trigger condition is active."


def _action_plan_cap_details(rating, core_diff, settings):
    cap_options = [(settings["action_max_single_stock_weight"], f"Capped at {settings['action_max_single_stock_weight']:.2f}% max single stock")]
    if rating == "Strong Buy":
        cap_options.append((settings["action_max_strong_buy_stock_weight"], f"Capped at {settings['action_max_strong_buy_stock_weight']:.2f}% Strong Buy max"))
    elif rating == "Buy":
        cap_options.append((settings["action_max_buy_stock_weight"], f"Capped at {settings['action_max_buy_stock_weight']:.2f}% Buy max"))
    elif rating == "Speculative Buy":
        cap_options.append((settings["action_max_speculative_buy_stock_weight"], f"Capped at {settings['action_max_speculative_buy_stock_weight']:.2f}% Speculative Buy max"))
    elif rating == "Hold":
        hold_cap = min(settings["action_max_buy_stock_weight"], settings["action_max_single_stock_weight"])
        cap_options.append((hold_cap, f"Capped at {hold_cap:.2f}% Hold max"))
    elif rating in {"Sell", "Strong Sell"}:
        cap_options.append((0.0, "Capped at 0.00% Sell/Strong Sell target"))
    if core_diff < -0.5:
        cap_options.append((settings["action_max_very_negative_core_weight"], f"Capped at {settings['action_max_very_negative_core_weight']:.2f}% very negative core cap"))
    elif core_diff < 0:
        cap_options.append((settings["action_max_negative_core_weight"], f"Capped at {settings['action_max_negative_core_weight']:.2f}% negative core cap"))
    return min(cap_options, key=lambda item: item[0])


def _dynamic_bucket_setting_prefix(bucket):
    return {
        "Strong Buy": "strong_buy",
        "Buy": "buy",
        "Speculative Buy": "speculative_buy",
        "Hold": "hold",
    }.get(bucket)



def _action_plan_bucket_sizing_details(bucket, weighted_eligible_count, raw_target, settings, dynamic_mode=True):
    raw_weighted_count = safe_number(weighted_eligible_count) or 0.0
    raw_bucket_target = safe_number(raw_target) or 0.0
    prefix = _dynamic_bucket_setting_prefix(bucket)
    if dynamic_mode and prefix:
        bucket_weight = settings[f"action_{prefix}_weight_per_effective_stock"]
        max_effective_count = settings[f"action_{prefix}_max_effective_count"]
        bucket_max_target = settings[f"action_{prefix}_max_bucket_target"]
        weighted_count_used = min(raw_weighted_count, max_effective_count)
        uncapped_bucket_target = weighted_count_used * bucket_weight
        raw_bucket_target = min(uncapped_bucket_target, bucket_max_target)
    else:
        bucket_weight = None
        max_effective_count = None
        bucket_max_target = raw_bucket_target
        weighted_count_used = raw_weighted_count
        uncapped_bucket_target = raw_bucket_target
    return {
        "weighted_eligible_count": raw_weighted_count,
        "max_effective_count": max_effective_count,
        "weighted_count_used": weighted_count_used,
        "effective_weighted_count_used": weighted_count_used,
        "bucket_weight_per_effective_stock": bucket_weight,
        "uncapped_bucket_target": uncapped_bucket_target,
        "raw_bucket_target": raw_bucket_target,
        "bucket_max_target": bucket_max_target,
        "max_bucket_target": bucket_max_target,
    }

def _compress_action_plan_bucket_targets(raw_targets, settings):
    effective = {bucket: max(0.0, float(value or 0.0)) for bucket, value in raw_targets.items()}
    max_equity = max(0.0, 100.0 - settings["action_min_cash_unallocated_target"])
    raw_total = sum(effective.values())
    if raw_total <= max_equity + 1e-9:
        return effective, {bucket: 0.0 for bucket in effective}, 0.0
    remaining = raw_total - max_equity
    compression = {bucket: 0.0 for bucket in effective}
    while remaining > 1e-9:
        weighted = []
        for bucket, value in effective.items():
            prefix = _dynamic_bucket_setting_prefix(bucket)
            if value > 1e-9 and prefix:
                weighted.append((bucket, value * settings[f"action_{prefix}_compression_weight"]))
        weight_total = sum(weight for _, weight in weighted)
        if weight_total <= 0:
            break
        reduced = 0.0
        for bucket, weight in weighted:
            share = remaining * weight / weight_total
            reduction = min(effective[bucket], share)
            effective[bucket] -= reduction
            compression[bucket] += reduction
            reduced += reduction
        if reduced <= 1e-9:
            break
        remaining -= reduced
    return effective, compression, raw_total - sum(effective.values())

def _linear_score_range(value, minimum, full):
    numeric = safe_number(value)
    minimum = safe_number(minimum)
    full = safe_number(full)
    if numeric is None or minimum is None or full is None or full <= minimum:
        return 0.0
    return _clamp((numeric - minimum) / (full - minimum), 0.0, 1.0)


def calculate_probability_weighted_expected_cagr(scenarios, current_price, years=5):
    """Calculate expected CAGR from every effective scenario midpoint and probability."""
    current = safe_number(current_price)
    if current is None or current <= 0:
        return None, "Missing or invalid current price"
    if not isinstance(scenarios, list) or not scenarios:
        return None, "Missing effective scenario data"

    validated = []
    for index, scenario in enumerate(scenarios):
        if not isinstance(scenario, dict):
            return None, f"Invalid scenario data at index {index}"
        low = safe_number(scenario.get("price_low"))
        high = safe_number(scenario.get("price_high"))
        probability = safe_number(scenario.get("probability"))
        if low is None or high is None or low <= 0 or high <= 0 or low > high:
            return None, f"Invalid scenario prices for {scenario.get('scenario_name') or scenario.get('name') or index}"
        if probability is None or probability < 0:
            return None, f"Invalid scenario probability for {scenario.get('scenario_name') or scenario.get('name') or index}"
        probability = probability / 100.0 if probability > 1.0 else probability
        if probability > 1.0:
            return None, f"Invalid scenario probability for {scenario.get('scenario_name') or scenario.get('name') or index}"
        midpoint = compute_price_mid(low, high)
        scenario_cagr = compute_scenario_cagr(midpoint, current, years=years)
        if scenario_cagr is None:
            return None, f"Unable to calculate scenario CAGR for {scenario.get('scenario_name') or scenario.get('name') or index}"
        validated.append({"probability": probability, "scenario_cagr": scenario_cagr})

    probability_total = sum(item["probability"] for item in validated)
    if probability_total < 0.9 or probability_total > 1.1:
        return None, "Scenario probabilities must total approximately 100%"
    try:
        normalized = _normalize_probabilities(validated)
    except (AnalysisValidationError, TypeError, ValueError, OverflowError):
        return None, "Invalid scenario probability distribution"
    expected_cagr = sum(item["probability"] * item["scenario_cagr"] for item in normalized)
    if not math.isfinite(expected_cagr):
        return None, "Probability-weighted expected CAGR is not finite"
    return expected_cagr, None


def _linear_absolute_attractiveness(expected_equity_cagr, benchmark_yield, minimum_excess, full_excess):
    expected = safe_number(expected_equity_cagr)
    benchmark = safe_number(benchmark_yield)
    minimum = safe_number(minimum_excess)
    full = safe_number(full_excess)
    if expected is None or benchmark is None or minimum is None or full is None:
        return 0.0
    excess = expected - benchmark
    if full < minimum:
        return 0.0
    if full == minimum:
        return 1.0 if excess >= minimum else 0.0
    return _clamp((excess - minimum) / (full - minimum), 0.0, 1.0)


def _linear_portfolio_opportunity_score(rows, settings):
    benchmark = safe_number(settings.get("linear_reserve_benchmark_yield_pct"))
    minimum_excess = safe_number(settings.get("linear_min_equity_excess_cagr_pct"))
    full_excess = safe_number(settings.get("linear_full_attractiveness_equity_excess_cagr_pct"))
    configuration_diagnostic = None
    if benchmark is None:
        configuration_diagnostic = "Invalid reserve benchmark yield"
    elif minimum_excess is None or full_excess is None:
        configuration_diagnostic = "Missing equity excess CAGR threshold"
    elif full_excess < minimum_excess:
        configuration_diagnostic = "Minimum equity excess CAGR exceeds full-attractiveness threshold"
    elif full_excess == minimum_excess:
        configuration_diagnostic = "Equal equity excess CAGR thresholds use binary compatibility behavior"
    weighted_attractiveness = 0.0
    total_weight = 0.0
    for row in rows:
        weight = max(0.0, safe_number(row.get("pre_reserve_target_mid")) or 0.0)
        expected_cagr, diagnostic = calculate_probability_weighted_expected_cagr(
            row.get("effective_scenarios"),
            row.get("current_price"),
        )
        if diagnostic is None and configuration_diagnostic is not None:
            diagnostic = configuration_diagnostic
        excess_cagr = expected_cagr - benchmark if expected_cagr is not None and benchmark is not None else None
        attractiveness = _linear_absolute_attractiveness(
            expected_cagr,
            benchmark,
            minimum_excess,
            full_excess,
        )
        row.update({
            "expected_equity_cagr": expected_cagr,
            "equity_excess_cagr": excess_cagr,
            "absolute_attractiveness": attractiveness,
            "opportunity_weight": weight,
            "absolute_attractiveness_diagnostic": diagnostic,
        })
        total_weight += weight
        weighted_attractiveness += weight * attractiveness
    if total_weight <= 0:
        return 0.0
    return _clamp(weighted_attractiveness / total_weight, 0.0, 1.0)


def _linear_dynamic_reserve(opportunity_score, minimum_reserve, maximum_reserve):
    score = _clamp(safe_number(opportunity_score) or 0.0, 0.0, 1.0)
    minimum = safe_number(minimum_reserve)
    maximum = safe_number(maximum_reserve)
    if minimum is None or maximum is None:
        return 100.0
    minimum = _clamp(minimum, 0.0, 100.0)
    maximum = _clamp(maximum, 0.0, 100.0)
    if maximum < minimum:
        return minimum
    return _clamp(minimum + (1.0 - score) * (maximum - minimum), minimum, maximum)


def _apply_linear_dynamic_reserve(rows, settings):
    pre_reserve_total_mid = sum(max(0.0, safe_number(row.get("pre_reserve_target_mid")) or 0.0) for row in rows)
    opportunity_score = _linear_portfolio_opportunity_score(rows, settings)
    minimum_reserve = safe_number(settings.get("action_min_cash_unallocated_target")) or 0.0
    maximum_reserve = safe_number(settings.get("linear_max_reserve_pct"))
    if maximum_reserve is None:
        maximum_reserve = ACTION_PLAN_DEFAULT_SETTINGS["linear_max_reserve_pct"]
    benchmark = safe_number(settings.get("linear_reserve_benchmark_yield_pct"))
    minimum_excess = safe_number(settings.get("linear_min_equity_excess_cagr_pct"))
    full_excess = safe_number(settings.get("linear_full_attractiveness_equity_excess_cagr_pct"))
    configuration_valid = (
        0.0 <= minimum_reserve <= maximum_reserve <= 100.0
        and benchmark is not None
        and minimum_excess is not None
        and full_excess is not None
        and minimum_excess < full_excess
    )
    dynamic_reserve = _linear_dynamic_reserve(opportunity_score, minimum_reserve, maximum_reserve)
    maximum_deployable_equity = max(0.0, 100.0 - dynamic_reserve)
    reserve_scale_factor = 1.0
    if pre_reserve_total_mid > maximum_deployable_equity + 1e-9:
        reserve_scale_factor = maximum_deployable_equity / pre_reserve_total_mid if pre_reserve_total_mid > 0 else 1.0
    reserve_scale_factor = _clamp(reserve_scale_factor, 0.0, 1.0)
    for row in rows:
        final_low = (safe_number(row.get("pre_reserve_target_low")) or 0.0) * reserve_scale_factor
        final_mid = (safe_number(row.get("pre_reserve_target_mid")) or 0.0) * reserve_scale_factor
        final_high = (safe_number(row.get("pre_reserve_target_high")) or 0.0) * reserve_scale_factor
        row.update({
            "final_target_low": final_low,
            "final_target_mid": final_mid,
            "final_target_high": final_high,
            "target_weight_low": final_low,
            "target_weight_mid": final_mid,
            "target_weight_high": final_high,
            "linear_target_weight_low": final_low,
            "linear_target_weight_mid": final_mid,
            "linear_target_weight_high": final_high,
            "linear_target_mid": final_mid,
            "adjusted_target_low": final_low,
            "adjusted_target_mid": final_mid,
            "adjusted_target_high": final_high,
            "reserve_scale_factor": reserve_scale_factor,
        })
    final_total_mid = sum(safe_number(row.get("final_target_mid")) or 0.0 for row in rows)
    return {
        "reserve_benchmark_yield": safe_number(settings.get("linear_reserve_benchmark_yield_pct")),
        "minimum_equity_excess_cagr": safe_number(settings.get("linear_min_equity_excess_cagr_pct")),
        "full_attractiveness_equity_excess_cagr": safe_number(settings.get("linear_full_attractiveness_equity_excess_cagr_pct")),
        "minimum_reserve_pct": minimum_reserve,
        "maximum_reserve_pct": maximum_reserve,
        "reserve_configuration_valid": configuration_valid,
        "portfolio_opportunity_score": opportunity_score,
        "dynamic_reserve_pct": dynamic_reserve,
        "maximum_deployable_equity_pct": maximum_deployable_equity,
        "pre_reserve_total_target_mid": pre_reserve_total_mid,
        "reserve_scale_factor": reserve_scale_factor,
        "final_total_target_mid": final_total_mid,
    }


def _linear_confidence_quality_score(core_bullish, core_bearish, potential_bullish, potential_bearish):
    core_bullish = safe_number(core_bullish) or 0.0
    core_bearish = safe_number(core_bearish) or 0.0
    potential_bullish = safe_number(potential_bullish) or 0.0
    potential_bearish = safe_number(potential_bearish) or 0.0
    quality = (0.55 * (core_bullish / 10.0)) + (0.25 * (potential_bullish / 10.0)) + (0.20 * (1.0 - max(core_bearish, potential_bearish) / 10.0))
    return _clamp(quality, 0.0, 1.0)


def _linear_progressive_bearish_cap_details(row, uncapped_midpoint, settings):
    uncapped_midpoint = safe_number(uncapped_midpoint)
    bearish_confidence = safe_number(row.get("core_bearish_confidence"))
    min_threshold = safe_number(settings.get("linear_high_bearish_confidence_min_threshold"))
    max_threshold = safe_number(settings.get("linear_high_bearish_confidence_max_threshold"))
    full_cap = safe_number(settings.get("linear_high_bearish_confidence_cap_pct"))
    details = {
        "bearish_confidence": bearish_confidence,
        "bearish_confidence_min_threshold": min_threshold,
        "bearish_confidence_max_threshold": max_threshold,
        "bearish_cap_progress": 0.0,
        "bearish_cap_full_limit": full_cap,
        "bearish_cap_candidate_mid": uncapped_midpoint,
        "bearish_cap_applied": False,
        "bearish_cap_configuration_valid": True,
        "bearish_cap_diagnostic": None,
    }
    if min_threshold is None or max_threshold is None or full_cap is None or full_cap < 0:
        details["bearish_cap_configuration_valid"] = False
        details["bearish_cap_diagnostic"] = "Invalid or missing progressive bearish-cap setting; cap not applied"
        return details
    if min_threshold > max_threshold:
        details["bearish_cap_configuration_valid"] = False
        details["bearish_cap_diagnostic"] = "Minimum bearish threshold exceeds maximum; cap not applied"
        return details
    if uncapped_midpoint is None or bearish_confidence is None:
        if bearish_confidence is None:
            details["bearish_cap_diagnostic"] = "Missing bearish confidence; cap not applied"
        return details
    if min_threshold == max_threshold:
        progress = 1.0 if bearish_confidence >= min_threshold else 0.0
    else:
        progress = _clamp((bearish_confidence - min_threshold) / (max_threshold - min_threshold), 0.0, 1.0)
    details["bearish_cap_progress"] = progress
    if uncapped_midpoint <= full_cap or progress <= 0.0:
        return details
    adjusted_midpoint = (
        full_cap
        if progress >= 1.0
        else uncapped_midpoint + progress * (full_cap - uncapped_midpoint)
    )
    details["bearish_cap_candidate_mid"] = min(uncapped_midpoint, adjusted_midpoint)
    return details


def _linear_cap_details(row, settings):
    cap = safe_number(settings.get("linear_max_single_stock_pct")) or 0.0
    reason = "Linear max single-stock cap"
    if not settings.get("linear_enable_risk_caps", True):
        return cap, reason
    core_net = safe_number(row.get("core_confidence_diff")) or 0.0
    risk_caps = []
    if core_net < 0:
        risk_caps.append((safe_number(settings.get("linear_negative_core_net_cap_pct")) or cap, "Negative core net cap"))
    if core_net < (safe_number(settings.get("linear_low_core_net_threshold")) or 0.0):
        risk_caps.append((safe_number(settings.get("linear_low_core_net_cap_pct")) or cap, "Low core net cap"))
    for candidate_cap, candidate_reason in risk_caps:
        if candidate_cap < cap:
            cap = candidate_cap
            reason = candidate_reason
    return max(0.0, cap), reason


def _apply_linear_caps_and_redistribute(rows, target_total, settings):
    allocation_power = safe_number(settings.get("linear_score_allocation_power")) or 1.0
    allocation_power = _clamp(allocation_power, 0.5, 5.0)
    min_score_threshold = safe_number(settings.get("linear_min_score_threshold")) or 0.0
    positive_rows = []
    for row in rows:
        row["linear_target_mid_before_caps"] = 0.0
        row["linear_target_mid"] = 0.0
        row["linear_cap_applied"] = 0.0
        row["linear_cap_reason"] = "—"
        row.update(_linear_progressive_bearish_cap_details(row, 0.0, settings))
        allocation_score_input = max(0.0, (safe_number(row.get("linear_allocation_score")) or 0.0) - min_score_threshold)
        row["linear_allocation_score_input"] = allocation_score_input
        row["linear_allocation_weight"] = allocation_score_input ** allocation_power if allocation_score_input > 0 else 0.0
        row["linear_powered_score"] = row["linear_allocation_weight"]
        row["linear_score_allocation_power"] = allocation_power
        row["linear_target_allocation_pool"] = target_total
        if row["linear_allocation_weight"] > 0:
            positive_rows.append(row)
    total_weight = sum(row["linear_allocation_weight"] for row in positive_rows)
    for row in rows:
        row["linear_total_powered_score"] = total_weight
    if target_total <= 0 or total_weight <= 0:
        return 0.0
    for row in positive_rows:
        uncapped_midpoint = target_total * row["linear_allocation_weight"] / total_weight
        row["linear_target_mid_before_caps"] = uncapped_midpoint
        bearish_details = _linear_progressive_bearish_cap_details(row, uncapped_midpoint, settings)
        row.update(bearish_details)
        bearish_candidate = safe_number(bearish_details.get("bearish_cap_candidate_mid"))
        existing_cap = safe_number(row.get("linear_effective_cap"))
        if (
            settings.get("linear_enable_risk_caps", True)
            and bearish_candidate is not None
            and existing_cap is not None
            and bearish_candidate < existing_cap - 1e-9
            and bearish_candidate < uncapped_midpoint - 1e-9
        ):
            row["linear_effective_cap"] = bearish_candidate
            row["linear_effective_cap_reason"] = (
                f"Progressive high bearish confidence cap ({bearish_details['bearish_cap_progress']:.0%})"
            )
            row["bearish_cap_applied"] = True
    remaining_target = target_total
    uncapped = list(positive_rows)
    capped_allocated = 0.0
    for _ in range(len(positive_rows) + 1):
        weight_total = sum(row["linear_allocation_weight"] for row in uncapped)
        if weight_total <= 0 or remaining_target <= 1e-9:
            break
        newly_capped = []
        provisional = []
        for row in uncapped:
            target = remaining_target * row["linear_allocation_weight"] / weight_total
            cap = safe_number(row.get("linear_effective_cap")) or 0.0
            if target > cap + 1e-9:
                row["linear_target_mid"] = cap
                row["linear_cap_applied"] = max(0.0, row["linear_target_mid_before_caps"] - cap)
                row["linear_cap_reason"] = row.get("linear_effective_cap_reason") or "Cap applied"
                newly_capped.append(row)
                capped_allocated += cap
            else:
                provisional.append((row, target))
        if not newly_capped:
            for row, target in provisional:
                row["linear_target_mid"] = target
                row["linear_cap_reason"] = "—"
            break
        remaining_target = max(0.0, target_total - capped_allocated)
        uncapped = [row for row in uncapped if row not in newly_capped]
    return sum(safe_number(row.get("linear_target_mid")) or 0.0 for row in rows)


def _apply_linear_cash_constrained_execution_layer(rows, total_portfolio_value, cash_like_available, settings, dynamic_reserve_pct=None):
    total = safe_number(total_portfolio_value) or 0.0
    cash_available = safe_number(cash_like_available) or 0.0
    minimum_cash_reserve_amount = total * (safe_number(settings.get("action_min_cash_unallocated_target")) or 0.0) / 100.0
    effective_reserve_pct = safe_number(dynamic_reserve_pct)
    if effective_reserve_pct is None:
        effective_reserve_pct = safe_number(settings.get("action_min_cash_unallocated_target")) or 0.0
    effective_reserve_pct = _clamp(effective_reserve_pct, 0.0, 100.0)
    target_reserve_amount = total * effective_reserve_pct / 100.0
    buy_actions = {"Strong Add", "Add", "Starter Buy"}
    sell_trim_actions = {"Sell", "Strong Sell", "Trim", "Strong Trim"}
    min_trade = safe_number(settings.get("action_min_executable_trade_amount")) or 0.0
    executable_sell_trim_proceeds = 0.0
    for row in rows:
        _prepare_whole_share_execution(row)
        row["executable_action_amount"] = 0.0
        row["unfunded_action_amount"] = 0.0
        row["unfunded_share_count"] = 0
        if row.get("minimum_trade_size_blocked"):
            row["funding_status"] = row.get("funding_status") or "Below one-share minimum"
        elif row.get("whole_share_diagnostic_reason") and row.get("action_amount_direction") == "none":
            row["funding_status"] = row.get("funding_status") or "No executable action"
        elif row.get("action") in sell_trim_actions:
            executable = max(0.0, safe_number(row.get("action_amount")) or 0.0)
            if row.get("action_amount_direction") == "trim" and 0.0 < executable < min_trade:
                _mark_minimum_trade_amount_non_executable(row, "Hold")
                continue
            row["executable_action_amount"] = executable
            row["funding_status"] = "Generates proceeds" if executable > 0 else "No funding needed"
            executable_sell_trim_proceeds += executable
        elif row.get("action") in buy_actions and row.get("desired_share_count", 0) > 0:
            row["funding_status"] = "Unfunded / Watch"
        elif row.get("action") == "Watch / Extended" and row.get("target_gap_amount", 0.0) > 0:
            row["funding_status"] = "Extension guardrail"
        elif row.get("action") == "Watch / Rating Guardrail" and row.get("target_gap_amount", 0.0) > 0:
            row["funding_status"] = "Rating blocks add"
        elif row.get("action") in {"Watch", "Watch / Underweight", "Hold / Overweight"} and row.get("target_gap_amount", 0.0) > 0:
            row["funding_status"] = "No executable add"
        else:
            row["funding_status"] = "No funding needed"
    projected_cash_before_buys = cash_available + executable_sell_trim_proceeds
    available_buy_budget = max(0.0, projected_cash_before_buys - target_reserve_amount)
    reserve_shortfall = max(0.0, target_reserve_amount - projected_cash_before_buys)
    reserve_excess = max(0.0, projected_cash_before_buys - target_reserve_amount)
    buy_candidates = [
        row for row in rows
        if row.get("action") in buy_actions
        and row.get("action_amount_direction") == "add"
        and row.get("desired_share_count", 0) > 0
    ]
    for row in buy_candidates:
        gap_score = min((row["desired_whole_share_amount"] / total / 0.05), 1.0) if total > 0 else 0.0
        row["linear_action_priority"] = (
            (safe_number(row.get("linear_allocation_score")) or 0.0) * 0.50
            + gap_score * 0.20
            + (safe_number(row.get("linear_expected_cagr_score")) or 0.0) * 0.20
            + (safe_number(row.get("linear_core_net_score")) or 0.0) * 0.10
        )
        row["funding_priority_score"] = row["linear_action_priority"]
    remaining_budget = available_buy_budget
    sorted_candidates = sorted(buy_candidates, key=lambda row: (-(safe_number(row.get("linear_action_priority")) or 0.0), -(safe_number(row.get("linear_allocation_score")) or 0.0), -(safe_number(row.get("expected_cagr")) or 0.0), -(safe_number(row.get("upside")) or 0.0), row.get("symbol") or ""))
    for row in sorted_candidates:
        desired_shares = int(row.get("desired_share_count") or 0)
        price = safe_number(row.get("current_price"))
        affordable_shares = whole_shares_for_amount(remaining_budget, price)
        funded_shares = min(desired_shares, affordable_shares)
        amount = _whole_share_amount(funded_shares, price)
        below_minimum_trade_amount = 0.0 < amount < min_trade
        if below_minimum_trade_amount:
            funded_shares = 0
            amount = 0.0
        unfunded_shares = max(0, desired_shares - funded_shares)
        row["suggested_share_count"] = funded_shares
        row["executable_action_amount"] = amount
        row["unfunded_share_count"] = unfunded_shares
        row["unfunded_action_amount"] = _whole_share_amount(unfunded_shares, price)
        row["funding_status"] = "Fully funded" if funded_shares == desired_shares and desired_shares > 0 else ("Partially funded" if funded_shares > 0 else "Unfunded / Watch")
        if below_minimum_trade_amount:
            _mark_minimum_trade_amount_non_executable(row, "Watch")
        remaining_budget = max(0.0, remaining_budget - amount)
    total_add_demand = sum(row.get("desired_whole_share_amount", 0.0) for row in buy_candidates)
    funded_add_amount = sum(row.get("executable_action_amount", 0.0) for row in buy_candidates)
    unfunded_add_demand = sum(row.get("unfunded_action_amount", 0.0) for row in buy_candidates)
    for row in rows:
        executable = safe_number(row.get("executable_action_amount")) or 0.0
        row["action_amount"] = executable
        row["action_amount_label"] = _format_action_amount_label(row.get("action_amount_direction"), executable)
        row["available_buy_budget"] = available_buy_budget
        row["total_add_demand"] = total_add_demand
        row["funded_add_amount"] = funded_add_amount
        row["unfunded_add_demand"] = unfunded_add_demand
        row["executable_sell_trim_proceeds"] = executable_sell_trim_proceeds
        row["minimum_cash_reserve_amount"] = minimum_cash_reserve_amount
        row["target_reserve_amount"] = target_reserve_amount
        row["current_cash_unallocated"] = cash_available
        row["projected_cash_before_buys"] = projected_cash_before_buys
        row["reserve_shortfall"] = reserve_shortfall
        row["reserve_excess"] = reserve_excess
        row["cash_available_for_linear_buys"] = available_buy_budget
        _mark_unfunded_add_as_watch(row)
    return {
        "available_buy_budget": available_buy_budget,
        "cash_available_for_linear_buys": available_buy_budget,
        "total_add_demand": total_add_demand,
        "funded_add_amount": funded_add_amount,
        "unfunded_add_demand": unfunded_add_demand,
        "executable_sell_trim_proceeds": executable_sell_trim_proceeds,
        "minimum_cash_reserve_amount": minimum_cash_reserve_amount,
        "target_reserve_amount": target_reserve_amount,
        "current_cash_unallocated": cash_available,
        "projected_cash_before_buys": projected_cash_before_buys,
        "reserve_shortfall": reserve_shortfall,
        "reserve_excess": reserve_excess,
    }



def _linear_action_amount_fields(action, target_mid, target_high, total_portfolio_value, market_value):
    total = safe_number(total_portfolio_value)
    market = safe_number(market_value) or 0.0
    mid = safe_number(target_mid)
    high = safe_number(target_high)
    direction = "none"
    target_gap_amount = 0.0
    action_amount_to_mid = None
    if total is not None and total > 0 and mid is not None:
        target_mid_value = total * mid / 100.0
        action_amount_to_mid = abs(target_mid_value - market)
        if action in {"Strong Add", "Add", "Starter Buy"}:
            direction = "add"
            target_gap_amount = max(0.0, target_mid_value - market)
        elif action in {"Strong Trim", "Trim"}:
            direction = "trim"
            target_high_value = total * (high if high is not None else mid) / 100.0
            target_gap_amount = max(0.0, market - target_high_value)
        elif action in {"Sell", "Strong Sell"}:
            direction = "sell"
            target_high_value = total * (high if high is not None else 0.0) / 100.0
            target_gap_amount = max(0.0, market - target_high_value)
    elif action in {"Sell", "Strong Sell"} and market > 0:
        direction = "sell"
        target_gap_amount = market
        action_amount_to_mid = market
    return {
        "target_gap_amount": target_gap_amount,
        "raw_action_amount": target_gap_amount,
        "action_amount": target_gap_amount,
        "action_amount_label": _format_action_amount_label(direction, target_gap_amount),
        "action_amount_direction": direction,
        "action_amount_to_mid": action_amount_to_mid,
    }


def _linear_action_compatibility_fields():
    """Keep shared row consumers safe without exposing unused Linear triggers."""
    return {
        "trigger_price": None,
        "trigger_direction": None,
        "relevant_trigger_price": None,
        "relevant_trigger_type": None,
        "distance_to_trigger_percent": None,
        "distance_to_relevant_trigger_percent": None,
        "distance_to_relevant_trigger_label": None,
        "trigger_breakdown": None,
    }


def _linear_position_status(current_weight, target_low, target_high, target_mid):
    if target_mid <= 0 and current_weight > 0:
        return "ZERO_TARGET_OWNED"
    if current_weight < target_low:
        return "BELOW_TARGET"
    if current_weight > target_high:
        return "ABOVE_TARGET"
    return "INSIDE_TARGET"


def _linear_action_explanation(row):
    action = row.get("action") or "Re-evaluate"
    position_status = row.get("position_status")
    if action == "Watch / Rating Guardrail":
        return "The position is below its Linear target band, but the current rating prevents an Add action."
    if action == "Watch / Extended":
        return "The position is below its Linear target band, but the high Extension Risk guardrail prevents an Add action."
    if action == "Watch" and row.get("desired_action") == "Add":
        return "The position is below its Linear target band, but no executable Add is currently funded."
    if action == "Add":
        return "Current weight is below the Linear target band, so the position is eligible to add toward the target midpoint."
    if action == "Hold" and position_status == "INSIDE_TARGET":
        return "Current weight is inside the Linear target band, so no allocation change is required."
    if action == "Trim":
        return "Current weight is above the Linear target band, so the position is eligible to trim toward the target midpoint."
    if action == "Sell":
        if str(row.get("rating") or "").strip() in {"Sell", "Strong Sell"}:
            return "The current rating requires a full exit under the Linear Allocation sell rule."
        return "The final Linear target is zero while the position is owned, so the position is marked Sell."
    if position_status == "BELOW_TARGET":
        return "Current weight is below the Linear target band, but no executable allocation change is currently available."
    if position_status == "ABOVE_TARGET":
        return "Current weight is above the Linear target band, but no executable allocation change is currently available."
    return "The final action is the executable result produced by the current Linear Allocation calculation."


def _linear_detail_diagnostics(row):
    cap_amount = safe_number(row.get("linear_cap_applied")) or 0.0
    return {
        "linear_explanation": _linear_action_explanation(row),
        "linear_target_breakdown": {
            "linear_score": row.get("linear_allocation_score"),
            "target_before_caps": row.get("linear_target_mid_before_caps"),
            "cap_applied": cap_amount > 1e-9,
            "cap_amount": cap_amount,
            "cap_reason": row.get("linear_cap_reason") if cap_amount > 1e-9 else "—",
            "target_after_cap_low": row.get("pre_reserve_target_low"),
            "target_after_cap_mid": row.get("pre_reserve_target_mid"),
            "target_after_cap_high": row.get("pre_reserve_target_high"),
            "reserve_scale_factor": row.get("reserve_scale_factor"),
            "final_target_low": row.get("final_target_low"),
            "final_target_mid": row.get("final_target_mid"),
            "final_target_high": row.get("final_target_high"),
            "bearish_confidence": row.get("bearish_confidence"),
            "bearish_cap_progress": row.get("bearish_cap_progress"),
            "bearish_cap_applied": row.get("bearish_cap_applied"),
        },
        "linear_score_breakdown": {
            "expected_cagr_score": row.get("linear_expected_cagr_score"),
            "upside_score": row.get("linear_upside_score"),
            "core_net_score": row.get("linear_core_net_score"),
            "potential_net_score": row.get("linear_potential_net_score"),
            "confidence_quality_score": row.get("linear_confidence_quality_score"),
            "weights_used": row.get("linear_weights_used"),
            "linear_score_before_penalty": row.get("linear_score_before_penalty"),
            "linear_score_after_penalty": row.get("linear_score_after_penalty"),
            "penalty_factor": row.get("linear_penalty_factor"),
            "penalties_applied": row.get("linear_penalties_applied"),
            "rating_bonus_factor": row.get("linear_rating_bonus_factor"),
            "rating_bonus_reason": row.get("linear_rating_bonus_reason"),
            "linear_score_before_min_threshold": row.get("linear_score_before_min_threshold"),
            "linear_min_score_threshold": row.get("linear_min_score_threshold"),
            "linear_min_score_threshold_applied": row.get("linear_min_score_threshold_applied"),
            "linear_min_score_threshold_reason": row.get("linear_min_score_threshold_reason"),
            "linear_score_before_frontier_boost": row.get("linear_score_before_frontier_boost"),
            "frontier_optionality_score": row.get("frontier_optionality_score"),
            "frontier_optionality_boost_factor": row.get("frontier_optionality_boost_factor"),
            "frontier_optionality_applied": row.get("frontier_optionality_applied"),
            "frontier_optionality_applied_reason": row.get("frontier_optionality_applied_reason"),
            "final_linear_score": row.get("final_linear_score"),
            "linear_score": row.get("linear_allocation_score"),
        },
        "guardrails": {
            "rating": "Triggered" if row.get("rating_guardrail_applied") else "Not triggered",
            "extension_risk": "Triggered" if row.get("extension_guardrail_applied") else "Not triggered",
            "minimum_executable_trade": "Triggered" if row.get("minimum_trade_size_blocked_by_configured_minimum") else "Not triggered",
            "whole_share_minimum": "Triggered" if row.get("minimum_trade_size_blocked") and not row.get("minimum_trade_size_blocked_by_configured_minimum") else "Not triggered",
        },
    }


def _linear_action_decision_path(row, action):
    path = [{"status": "pass", "text": f"Rating is {row.get('rating') or 'Hold'}."}]
    current_weight = safe_number(row.get("current_position_weight")) or 0.0
    target_low = safe_number(row.get("target_weight_low")) or 0.0
    target_high = safe_number(row.get("target_weight_high")) or 0.0
    target_mid = safe_number(row.get("target_weight_mid")) or 0.0
    if target_mid <= 0 and current_weight > 0:
        path.append({"status": "pass", "text": "Final target is zero while the position is owned."})
    elif current_weight < target_low:
        path.append({"status": "pass", "text": "Current position is below the target band."})
    elif current_weight > target_high:
        path.append({"status": "pass", "text": "Current position is above the target band."})
    else:
        path.append({"status": "pass", "text": "Current position is inside the target band."})
    if action == "Watch / Rating Guardrail":
        path.append({"status": "warning", "text": "Rating guardrail blocks the buy-side action."})
    elif action == "Watch / Extended":
        extension_risk = safe_number(row.get("extension_risk"))
        threshold = safe_number(row.get("extension_guardrail_threshold"))
        if extension_risk is not None and threshold is not None:
            path.append({"status": "warning", "text": f"Extension Risk is {extension_risk:.1f}/5, at or above the configured threshold of {threshold:.1f}."})
    path.append({"status": "result", "text": f"Action = {action}."})
    return path


def _linear_stock_penalty_factor(item, core_net, potential_net, upside, rating, settings):
    factor = 1.0
    penalties = []

    def apply_penalty(setting_key, label):
        nonlocal factor
        penalty = _clamp(safe_number(settings.get(setting_key)) or 0.0, 0.0, 1.0)
        if penalty > 0:
            factor *= (1.0 - penalty)
            penalties.append({"key": setting_key, "label": label, "penalty": penalty})

    core_threshold = safe_number(settings.get("core_confidence_penalty_threshold"))
    if core_threshold is not None and core_net < core_threshold:
        apply_penalty("core_confidence_penalty", "Core confidence below threshold")

    upside_threshold = safe_number(settings.get("upside_penalty_threshold"))
    if upside_threshold is not None and upside is not None and upside < upside_threshold:
        apply_penalty("upside_penalty", "Upside below threshold")

    potential_threshold = safe_number(settings.get("potential_confidence_penalty_threshold"))
    if potential_threshold is not None and potential_net < potential_threshold:
        apply_penalty("potential_confidence_penalty", "Potential confidence below threshold")

    if settings.get("hold_rating_penalty_enabled", True) and str(rating or "").strip().lower() == "hold":
        apply_penalty("hold_rating_penalty", "Hold rating")

    return _clamp(factor, 0.0, 1.0), penalties


def _linear_rating_bonus_factor(rating, settings):
    if not settings.get("linear_rating_bonus_enabled", True):
        return 1.0, "Rating bonus disabled"
    normalized_rating = str(rating or "").strip().lower()
    if normalized_rating == "strong buy":
        bonus = _clamp(safe_number(settings.get("linear_strong_buy_rating_bonus")) or 0.0, 0.0, 1.0)
        return 1.0 + bonus, "Strong Buy rating bonus" if bonus > 0 else "No rating bonus"
    if normalized_rating == "buy":
        bonus = _clamp(safe_number(settings.get("linear_buy_rating_bonus")) or 0.0, 0.0, 1.0)
        return 1.0 + bonus, "Buy rating bonus" if bonus > 0 else "No rating bonus"
    return 1.0, "No rating bonus"


def is_linear_buy_action_allowed_for_rating(rating, settings):
    if not settings.get("linear_block_buy_actions_for_hold_rating", True):
        return True
    normalized_rating = str(rating or "").strip().casefold()
    return normalized_rating in {"strong buy", "buy", "speculative buy"}


def _linear_frontier_optionality_boost(score_before_boost, item, rating, settings):
    frontier_score = normalize_frontier_optionality_score(item.get("frontier_optionality_score"))
    score_before_boost = _clamp(safe_number(score_before_boost) or 0.0, 0.0, 1.0)
    max_boost_pct = _clamp(safe_number(settings.get("linear_frontier_optionality_max_boost_pct")) or 0.0, 0.0, 20.0)
    diagnostics = {
        "linear_score_before_frontier_boost": score_before_boost,
        "frontier_optionality_score": frontier_score,
        "frontier_optionality_boost_factor": 1.0,
        "frontier_optionality_applied": False,
        "frontier_optionality_applied_reason": "No Frontier Score",
    }
    if frontier_score <= 0.0:
        return score_before_boost, diagnostics
    if score_before_boost <= 0.0:
        diagnostics["frontier_optionality_applied_reason"] = "Linear Score before boost is zero"
        return score_before_boost, diagnostics
    if str(rating or "").strip().casefold() in {"sell", "strong sell"}:
        diagnostics["frontier_optionality_applied_reason"] = f"{rating} rating"
        return score_before_boost, diagnostics
    expected_cagr = safe_number(item.get("expected_cagr"))
    if expected_cagr is None or expected_cagr <= 0.0:
        diagnostics["frontier_optionality_applied_reason"] = "Expected CAGR is not positive"
        return score_before_boost, diagnostics
    upside = safe_number(item.get("upside"))
    if upside is None or upside <= 0.0:
        diagnostics["frontier_optionality_applied_reason"] = "Upside is not positive"
        return score_before_boost, diagnostics
    if item.get("final_scenario_stale"):
        diagnostics["frontier_optionality_applied_reason"] = "Final Scenario overlay is stale"
        return score_before_boost, diagnostics
    if max_boost_pct <= 0.0:
        diagnostics["frontier_optionality_applied_reason"] = "Configured max boost is zero"
        return score_before_boost, diagnostics

    boost_factor = 1.0 + (max_boost_pct / 100.0) * (frontier_score / 5.0)
    final_score = _clamp(score_before_boost * boost_factor, 0.0, 1.0)
    diagnostics.update({
        "frontier_optionality_boost_factor": boost_factor,
        "frontier_optionality_applied": final_score > score_before_boost,
        "frontier_optionality_applied_reason": "Applied" if final_score > score_before_boost else "Clamped at maximum Linear Score",
    })
    return final_score, diagnostics


def _linear_release_date_warning_details(release_date, warning_days, today=None):
    """Return display-only release-date warning metadata using the server's local date."""
    safe_warning_days = safe_number(warning_days)
    if safe_warning_days is None or safe_warning_days <= 0:
        return {"release_date_warning": False, "release_date_warning_days": 0, "release_date_days_until": None, "release_date_warning_reason": None}
    normalized_date = str(release_date or "").strip()
    try:
        parsed_date = date.fromisoformat(normalized_date)
    except (TypeError, ValueError):
        return {"release_date_warning": False, "release_date_warning_days": int(safe_warning_days), "release_date_days_until": None, "release_date_warning_reason": None}
    if parsed_date.isoformat() != normalized_date:
        return {"release_date_warning": False, "release_date_warning_days": int(safe_warning_days), "release_date_days_until": None, "release_date_warning_reason": None}
    days_until = (parsed_date - (today or date.today())).days
    is_near = 0 <= days_until <= safe_warning_days
    return {
        "release_date_warning": is_near,
        "release_date_warning_days": int(safe_warning_days),
        "release_date_days_until": days_until,
        "release_date_warning_reason": "Release date is within the configured warning window" if is_near else None,
    }


def compute_linear_action_plan(candidates, total_portfolio_value, cash_like_available, settings):
    target_total = safe_number(settings.get("linear_allocated_target_total_pct")) or 0.0
    weight_keys = ["linear_expected_cagr_weight", "linear_upside_weight", "linear_core_confidence_weight", "linear_potential_confidence_weight", "linear_confidence_quality_weight"]
    weight_total = sum(safe_number(settings.get(key)) or 0.0 for key in weight_keys)
    weights = {key: ((safe_number(settings.get(key)) or 0.0) / weight_total if weight_total > 0 else 0.0) for key in weight_keys}
    rows = []
    for item in candidates:
        expected_cagr = safe_number(item.get("expected_cagr"))
        upside = safe_number(item.get("upside"))
        core_net = safe_number(item.get("core_confidence_diff")) or 0.0
        potential_net = safe_number(item.get("potential_confidence_diff")) or 0.0
        expected_cagr_score = _linear_score_range(expected_cagr, settings["linear_min_expected_cagr"], settings["linear_full_expected_cagr"])
        upside_score = _linear_score_range(upside, settings["linear_min_upside"], settings["linear_full_upside"])
        core_net_score = _linear_score_range(core_net, settings["linear_min_core_net"], settings["linear_full_core_net"])
        potential_net_score = _linear_score_range(potential_net, settings["linear_min_potential_net"], settings["linear_full_potential_net"])
        confidence_quality_score = _linear_confidence_quality_score(item.get("core_bullish_confidence"), item.get("core_bearish_confidence"), item.get("potential_bullish_confidence"), item.get("potential_bearish_confidence"))
        score = (
            weights["linear_expected_cagr_weight"] * expected_cagr_score
            + weights["linear_upside_weight"] * upside_score
            + weights["linear_core_confidence_weight"] * core_net_score
            + weights["linear_potential_confidence_weight"] * potential_net_score
            + weights["linear_confidence_quality_weight"] * confidence_quality_score
        )
        score_before_penalty = score
        rating = item.get("rating") or item.get("bucket") or "Hold"
        penalty_factor, penalties_applied = _linear_stock_penalty_factor(item, core_net, potential_net, upside, rating, settings)
        score *= penalty_factor
        score_after_penalty = score
        rating_bonus_factor, rating_bonus_reason = _linear_rating_bonus_factor(rating, settings)
        score *= rating_bonus_factor
        score_before_min_threshold = score
        min_score_threshold = safe_number(settings.get("linear_min_score_threshold")) or 0.0
        min_score_threshold_applied = False
        min_score_threshold_reason = None
        if settings.get("linear_zero_target_if_expected_cagr_negative", True) and expected_cagr is not None and expected_cagr < 0:
            score = 0.0
            min_score_threshold_reason = "Negative expected CAGR guardrail"
        if settings.get("linear_zero_target_if_upside_negative", True) and upside is not None and upside < 0:
            score = 0.0
            min_score_threshold_reason = (
                "Negative expected CAGR and negative upside guardrails"
                if min_score_threshold_reason
                else "Negative upside guardrail"
            )
        if score < min_score_threshold:
            if score > 0.0:
                min_score_threshold_applied = True
                min_score_threshold_reason = "Score below configured minimum threshold"
            score = 0.0
        score_before_frontier_boost = _clamp(score, 0.0, 1.0)
        final_score, frontier_diagnostics = _linear_frontier_optionality_boost(
            score_before_frontier_boost,
            item,
            rating,
            settings,
        )
        row = {
            "mode": "linear",
            "symbol": item.get("symbol"),
            "company_name": item.get("company_name"),
            "rating": rating,
            "current_price": item.get("current_price"),
            "expected_price": item.get("expected_price"),
            "expected_cagr": expected_cagr,
            "effective_scenarios": item.get("effective_scenarios"),
            "effective_scenario_source": item.get("effective_scenario_source"),
            "uses_final_scenario_overlay": item.get("uses_final_scenario_overlay"),
            "final_scenario_stale": item.get("final_scenario_stale"),
            "upside": upside,
            "core_confidence_diff": core_net,
            "core_bullish_confidence": item.get("core_bullish_confidence"),
            "core_bearish_confidence": item.get("core_bearish_confidence"),
            "potential_confidence_diff": potential_net,
            "potential_bullish_confidence": item.get("potential_bullish_confidence"),
            "potential_bearish_confidence": item.get("potential_bearish_confidence"),
            "current_position_weight": item.get("current_position_weight") or 0.0,
            "current_position_market_value": item.get("current_position_market_value") or 0.0,
            "owned_share_quantity": item.get("owned_share_quantity"),
            "total_portfolio_value": total_portfolio_value,
            "linear_expected_cagr_score": expected_cagr_score,
            "linear_upside_score": upside_score,
            "linear_core_net_score": core_net_score,
            "linear_potential_net_score": potential_net_score,
            "linear_confidence_quality_score": confidence_quality_score,
            "linear_score_before_penalty": score_before_penalty,
            "linear_score_after_penalty": score_after_penalty,
            "linear_penalty_factor": penalty_factor,
            "linear_penalties_applied": penalties_applied,
            "linear_rating_bonus_factor": rating_bonus_factor,
            "linear_rating_bonus_reason": rating_bonus_reason,
            "linear_score_before_min_threshold": score_before_min_threshold,
            "linear_min_score_threshold": min_score_threshold,
            "linear_min_score_threshold_applied": min_score_threshold_applied,
            "linear_min_score_threshold_reason": min_score_threshold_reason,
            **frontier_diagnostics,
            "final_linear_score": final_score,
            "linear_allocation_score": final_score,
            "linear_weights_used": weights,
            "momentum_score": item.get("momentum_score"),
            "momentum_label": item.get("momentum_label"),
            "extension_risk": item.get("extension_risk"),
            "extension_label": item.get("extension_label"),
            "momentum_updated_at": item.get("momentum_updated_at"),
            "release_date": item.get("release_date"),
            "release_timing": item.get("release_timing"),
        }
        row.update(_linear_release_date_warning_details(
            row["release_date"], settings.get("linear_release_date_warning_days"),
        ))
        cap, cap_reason = _linear_cap_details(row, settings)
        row["linear_effective_cap"] = cap
        row["linear_effective_cap_reason"] = cap_reason
        rows.append(row)
    allocated_total = _apply_linear_caps_and_redistribute(rows, target_total, settings)
    add_tolerance = (safe_number(settings.get("linear_add_band_tolerance_pct")) or 0.0) / 100.0
    trim_tolerance = (safe_number(settings.get("linear_trim_band_tolerance_pct")) or 0.0) / 100.0
    for row in rows:
        pre_reserve_mid = safe_number(row.get("linear_target_mid")) or 0.0
        pre_reserve_low = pre_reserve_mid * max(0.0, 1.0 - add_tolerance) if pre_reserve_mid > 0 else 0.0
        pre_reserve_high = pre_reserve_mid * (1.0 + trim_tolerance) if pre_reserve_mid > 0 else 0.0
        row.update({
            "pre_reserve_target_low": pre_reserve_low,
            "pre_reserve_target_mid": pre_reserve_mid,
            "pre_reserve_target_high": pre_reserve_high,
            "linear_add_band_tolerance_pct": add_tolerance * 100.0,
            "linear_trim_band_tolerance_pct": trim_tolerance * 100.0,
        })
    reserve_details = _apply_linear_dynamic_reserve(rows, settings)
    allocated_total = reserve_details["final_total_target_mid"]
    for row in rows:
        target_mid = safe_number(row.get("linear_target_mid")) or 0.0
        target_low = target_mid * max(0.0, 1.0 - add_tolerance) if target_mid > 0 else 0.0
        target_high = target_mid * (1.0 + trim_tolerance) if target_mid > 0 else 0.0
        uncapped_target_mid = safe_number(row.get("linear_target_mid_before_caps")) or 0.0
        uncapped_target_low = uncapped_target_mid * max(0.0, 1.0 - add_tolerance) if uncapped_target_mid > 0 else 0.0
        uncapped_target_high = uncapped_target_mid * (1.0 + trim_tolerance) if uncapped_target_mid > 0 else 0.0
        row.update({
            "target_weight_mid": target_mid,
            "target_weight_low": target_low,
            "target_weight_high": target_high,
            "linear_target_weight_mid": target_mid,
            "linear_target_weight_low": target_low,
            "linear_target_weight_high": target_high,
            "position_gap_to_mid": target_mid - (safe_number(row.get("current_position_weight")) or 0.0),
            "cap_applied": row.get("linear_cap_applied"),
            "cap_reason": row.get("linear_cap_reason"),
            "uncapped_target_low": uncapped_target_low,
            "uncapped_target_mid": uncapped_target_mid,
            "uncapped_target_high": uncapped_target_high,
            "adjusted_target_low": target_low,
            "adjusted_target_mid": target_mid,
            "adjusted_target_high": target_high,
            "linear_add_band_tolerance_pct": add_tolerance * 100.0,
            "linear_trim_band_tolerance_pct": trim_tolerance * 100.0,
        })
        current_weight = safe_number(row.get("current_position_weight")) or 0.0
        rating_label = str(row.get("rating") or "").strip()
        extension_risk = safe_number(row.get("extension_risk"))
        extension_guardrail_applied = False
        extension_guardrail_reason = None
        extension_guardrail_diagnostic = None
        extension_guardrail_threshold = safe_number(settings.get("linear_high_extension_risk_threshold"))
        position_status = _linear_position_status(current_weight, target_low, target_high, target_mid)
        if (rating_label in {"Sell", "Strong Sell"} or target_mid <= 0) and current_weight > 0:
            action = "Sell"
            sizing_action = action
        elif current_weight < target_low:
            action = "Add"
            sizing_action = "Add"
            if action in {"Strong Add", "Add", "Starter Buy"} and not is_linear_buy_action_allowed_for_rating(rating_label, settings):
                action = "Watch / Rating Guardrail"
        elif current_weight > target_high:
            action = "Trim"
            sizing_action = "Trim"
        else:
            action = "Hold"
            sizing_action = action
        amount_fields = _linear_action_amount_fields(sizing_action, target_mid, target_high, total_portfolio_value, row.get("current_position_market_value"))
        desired_action = "Add" if action == "Watch / Rating Guardrail" else action
        rating_guardrail_applied = action == "Watch / Rating Guardrail"
        if (
            action in {"Strong Add", "Add", "Starter Buy"}
            and settings.get("linear_high_extension_guardrail_enabled", True)
            and extension_risk is not None
            and extension_guardrail_threshold is not None
            and extension_risk >= extension_guardrail_threshold
        ):
            action = "Watch / Extended"
            extension_guardrail_applied = True
            extension_guardrail_reason = "Target Band indicates Add, but Extension Risk is high. Add is deferred to avoid chasing an extended move."
        elif action in {"Strong Add", "Add", "Starter Buy"} and extension_risk is None:
            extension_guardrail_diagnostic = "Extension Risk unavailable; guardrail not applied."
        if action in {"Watch / Rating Guardrail", "Watch / Extended"}:
            amount_fields["action_amount"] = 0.0
            amount_fields["action_amount_label"] = "—"
            amount_fields["action_amount_direction"] = "none"
        reason = "Linear Allocation compares current weight with the final target band. Add is suggested below Target Low, Hold inside the band, and Trim above Target High. Target Bands already reflect valuation, confidence, caps, Dynamic Reserve, and other Linear Allocation inputs."
        rating_guardrail_reason = None
        if rating_guardrail_applied:
            rating_guardrail_reason = "Hold rating blocks buy-side action."
            reason = rating_guardrail_reason
        elif extension_guardrail_applied:
            reason = extension_guardrail_reason
        row.update({
            "action": action,
            "base_linear_action": sizing_action,
            "position_status": position_status,
            "desired_action": desired_action,
            "executable_action": action,
            "action_priority": ACTION_PLAN_ACTION_PRIORITY.get(action, 99),
            "reason": reason,
            "rating_guardrail_applied": rating_guardrail_applied,
            "rating_guardrail_reason": rating_guardrail_reason,
            "extension_guardrail_applied": extension_guardrail_applied,
            "extension_guardrail_reason": extension_guardrail_reason,
            "extension_guardrail_diagnostic": extension_guardrail_diagnostic,
            "extension_guardrail_threshold": extension_guardrail_threshold,
            **amount_fields,
        })
        row.update(_linear_action_compatibility_fields())
    execution = _apply_linear_cash_constrained_execution_layer(
        rows,
        total_portfolio_value,
        cash_like_available,
        settings,
        dynamic_reserve_pct=reserve_details["dynamic_reserve_pct"],
    )
    for row in rows:
        row["decision_path"] = _linear_action_decision_path(row, row.get("action") or "Hold")
        row.update(_linear_detail_diagnostics(row))
    rows.sort(key=lambda row: (-(safe_number(row.get("linear_action_priority")) or 0.0), -(safe_number(row.get("linear_allocation_score")) or 0.0), row.get("symbol") or ""))
    summary = {
        "mode_label": "Linear Allocation",
        "linear_allocated_target_total": allocated_total,
        "linear_configured_target_total": target_total,
        "current_equity_allocation": sum(safe_number(row.get("current_position_weight")) or 0.0 for row in rows),
        "cash_like_available": cash_like_available,
        "eligible_stock_count": len(rows),
        "capped_stock_count": sum(1 for row in rows if (safe_number(row.get("linear_cap_applied")) or 0.0) > 1e-9),
        **reserve_details,
        **execution,
        "execution_warning": "Linear add demand exceeds available funding. Action amounts have been cash-constrained and prioritized." if execution["total_add_demand"] > execution["available_buy_budget"] + 1e-6 else None,
    }
    return {"rows": rows, "summary": summary}

def build_action_plan(conn):
    settings = get_action_plan_settings(conn)
    dynamic_mode = bool(settings.get("action_use_dynamic_bucket_sizing", True))
    weighted_count_enabled = bool(settings.get("action_use_weighted_eligible_count", True))
    analysis_items = list_analysis_symbols(conn)
    positions = load_positions_cache(conn)
    positions_by_symbol = {normalize_symbol(row.get("symbol")): row for row in positions if normalize_symbol(row.get("symbol"))}
    portfolio_cash_summary = build_portfolio_cash_summary(conn, positions, settings)
    total_portfolio_value = portfolio_cash_summary["portfolio_value_used"]
    portfolio_value_source = portfolio_cash_summary["portfolio_value_source"]
    portfolio_value_warning = portfolio_cash_summary["portfolio_value_warning"]
    actual_cash = portfolio_cash_summary["actual_cash"]
    actual_cash_source = portfolio_cash_summary["actual_cash_source"]
    cash_equivalent_symbols = portfolio_cash_summary["cash_equivalent_symbols"]
    cash_equivalent_value = portfolio_cash_summary["cash_equivalent_value"]
    cash_equivalent_positions = portfolio_cash_summary["cash_equivalent_positions"]
    cash_like_available = portfolio_cash_summary["cash_like_available"]
    treat_cash_equivalents = bool(settings.get("action_treat_cash_equivalents_as_cash", True))

    symbols = sorted({normalize_symbol(item.get("symbol")) for item in analysis_items if normalize_symbol(item.get("symbol"))} | set(positions_by_symbol.keys()))
    if treat_cash_equivalents:
        symbols = [symbol for symbol in symbols if symbol not in set(cash_equivalent_symbols)]
    analysis_by_symbol = {normalize_symbol(item.get("symbol")): item for item in analysis_items if normalize_symbol(item.get("symbol"))}

    candidates = []
    for symbol in symbols:
        analysis = analysis_by_symbol.get(symbol)
        if not analysis:
            continue
        position = positions_by_symbol.get(symbol)
        market_value = abs(safe_number(position.get("marketValue")) or 0.0) if position else 0.0
        current_position_weight = (market_value / total_portfolio_value * 100.0) if total_portfolio_value > 0 else 0.0
        owned = market_value > 0
        if not _is_action_plan_eligible(analysis, owned, settings):
            continue
        rating = analysis.get("rating") or "Hold"
        upside = safe_number(analysis.get("upside"))
        core_diff = safe_number(analysis.get("core_confidence_diff")) or 0.0
        core_bearish = safe_number(analysis.get("core_bearish_confidence")) or 0.0
        potential_diff = safe_number(analysis.get("potential_confidence_diff"))
        potential_bull = safe_number(analysis.get("potential_bullish_confidence"))
        upside_score = _score_range(upside or 0.0, settings["action_upside_zero_score"], settings["action_upside_full_score"])
        core_conviction_score = _score_range(core_diff, settings["action_core_diff_zero_score"], settings["action_core_diff_full_score"])
        penalty_start = settings["action_core_bearish_penalty_start"]
        penalty_full = settings["action_core_bearish_penalty_full"]
        if core_bearish <= penalty_start:
            core_risk_modifier = 1.0
        elif core_bearish >= penalty_full:
            core_risk_modifier = 0.5
        else:
            core_risk_modifier = 1.0 - ((core_bearish - penalty_start) / (penalty_full - penalty_start)) * 0.5
        core_score = max(0.0, upside_score * core_conviction_score * core_risk_modifier)
        potential_conviction = 0.0
        potential_score_component = 0.0
        legacy_potential_bonus_weight = 0.0
        if (
            upside is not None
            and potential_diff is not None
            and potential_bull is not None
            and upside >= settings["action_potential_bonus_upside_minimum"]
            and potential_bull >= settings["action_potential_bullish_confidence_minimum"]
            and potential_diff >= settings["action_potential_diff_minimum"]
        ):
            potential_conviction = _score_range(potential_diff, settings["action_potential_diff_minimum"], settings["action_potential_diff_full_score"])
            potential_score_component = potential_conviction * settings["action_max_potential_score_contribution"]
            legacy_potential_bonus_weight = min(settings["action_max_potential_bonus_weight"], settings["action_max_potential_bonus_weight"] * upside_score * potential_conviction)
        allocation_weight_total = sum(settings[key] for key in (
            "action_allocation_upside_weight",
            "action_allocation_core_weight",
            "action_allocation_potential_weight",
        ))
        normalized_allocation_weights = {
            "upside": settings["action_allocation_upside_weight"] / allocation_weight_total,
            "core": settings["action_allocation_core_weight"] / allocation_weight_total,
            "potential": settings["action_allocation_potential_weight"] / allocation_weight_total,
        } if allocation_weight_total > 0 else {"upside": 0.6, "core": 0.3, "potential": 0.1}
        allocation_risk_modifier = 1.0 - ((1.0 - core_risk_modifier) * settings["action_allocation_risk_penalty_strength"])
        allocation_score = _clamp((
            normalized_allocation_weights["upside"] * upside_score
            + normalized_allocation_weights["core"] * core_conviction_score
            + normalized_allocation_weights["potential"] * potential_conviction
        ) * allocation_risk_modifier, 0.0, 1.0)
        fixed_bucket_score = core_score
        if fixed_bucket_score <= 0 and legacy_potential_bonus_weight > 0:
            fixed_bucket_score = 0.05
        bucket_sizing_weight_total = sum(settings[key] for key in (
            "action_bucket_sizing_upside_weight",
            "action_bucket_sizing_core_weight",
            "action_bucket_sizing_potential_weight",
        ))
        normalized_bucket_sizing_weights = {
            "upside": settings["action_bucket_sizing_upside_weight"] / bucket_sizing_weight_total,
            "core": settings["action_bucket_sizing_core_weight"] / bucket_sizing_weight_total,
            "potential": settings["action_bucket_sizing_potential_weight"] / bucket_sizing_weight_total,
        } if bucket_sizing_weight_total > 0 else {"upside": 0.5, "core": 0.4, "potential": 0.1}
        bucket_sizing_risk_modifier = 1.0 - ((1.0 - core_risk_modifier) * settings["action_bucket_sizing_risk_penalty_strength"])
        bucket_sizing_score = _clamp((
            normalized_bucket_sizing_weights["upside"] * upside_score
            + normalized_bucket_sizing_weights["core"] * core_conviction_score
            + normalized_bucket_sizing_weights["potential"] * potential_conviction
        ) * bucket_sizing_risk_modifier, 0.0, 1.0)
        weighted_count = 0.0
        if weighted_count_enabled and rating not in {"Sell", "Strong Sell"}:
            weighted_count = _clamp(
                (bucket_sizing_score - settings["action_weighted_count_min_score"]) / (settings["action_weighted_count_full_score"] - settings["action_weighted_count_min_score"]),
                0.0,
                settings["action_weighted_count_max_contribution"],
            )
        elif rating not in {"Sell", "Strong Sell"} and bucket_sizing_score > 0:
            weighted_count = 1.0
        candidates.append({
            **analysis,
            "symbol": symbol,
            "current_position_weight": current_position_weight,
            "company_bucket_score": allocation_score if dynamic_mode else fixed_bucket_score,
            "company_allocation_score": allocation_score,
            "allocation_score": allocation_score,
            "allocation_upside_weight_used": normalized_allocation_weights["upside"],
            "allocation_core_weight_used": normalized_allocation_weights["core"],
            "allocation_potential_weight_used": normalized_allocation_weights["potential"],
            "allocation_risk_penalty_strength": settings["action_allocation_risk_penalty_strength"],
            "allocation_risk_modifier": allocation_risk_modifier,
            "bucket_sizing_score": bucket_sizing_score,
            "bucket_sizing_risk_modifier": bucket_sizing_risk_modifier,
            "weighted_count": weighted_count,
            "upside_score": upside_score,
            "core_conviction_score": core_conviction_score,
            "core_risk_modifier": core_risk_modifier,
            "core_score": core_score,
            "potential_bonus_weight": 0.0 if dynamic_mode else legacy_potential_bonus_weight,
            "potential_conviction_score": potential_conviction,
            "potential_score_component": potential_score_component,
            "current_position_market_value": market_value,
            "owned_share_quantity": position.get("position") if position else None,
            "bucket": rating,
        })

    equity_buckets = ["Strong Buy", "Buy", "Speculative Buy", "Hold"]
    bucket_counts = {bucket: 0 for bucket in ACTION_PLAN_BUCKET_KEYS}
    bucket_score_totals = {bucket: 0.0 for bucket in ACTION_PLAN_BUCKET_KEYS}
    bucket_weighted_counts = {bucket: 0.0 for bucket in ACTION_PLAN_BUCKET_KEYS}
    for item in candidates:
        bucket = item["bucket"]
        bucket_counts[bucket] = bucket_counts.get(bucket, 0) + 1
        bucket_score_totals[bucket] = bucket_score_totals.get(bucket, 0.0) + max(0.0, item["company_bucket_score"])
        bucket_weighted_counts[bucket] = bucket_weighted_counts.get(bucket, 0.0) + max(0.0, item["weighted_count"])

    bucket_sizing_details = {}
    if dynamic_mode:
        raw_bucket_targets = {bucket: 0.0 for bucket in ACTION_PLAN_BUCKET_KEYS}
        for bucket in equity_buckets:
            details = _action_plan_bucket_sizing_details(bucket, bucket_weighted_counts.get(bucket, 0.0), 0.0, settings, dynamic_mode=True)
            bucket_sizing_details[bucket] = details
            raw_bucket_targets[bucket] = details["raw_bucket_target"]
        for bucket in ACTION_PLAN_BUCKET_KEYS:
            bucket_sizing_details.setdefault(bucket, _action_plan_bucket_sizing_details(bucket, bucket_weighted_counts.get(bucket, 0.0), raw_bucket_targets.get(bucket, 0.0), settings, dynamic_mode=True))
        effective_bucket_targets, bucket_compression, compression_applied = _compress_action_plan_bucket_targets(raw_bucket_targets, settings)
        bucket_cash_target = 100.0 - sum(effective_bucket_targets.values())
    else:
        raw_bucket_targets = {bucket: settings[key] for bucket, key in ACTION_PLAN_BUCKET_KEYS.items()}
        bucket_sizing_details = {
            bucket: _action_plan_bucket_sizing_details(bucket, bucket_weighted_counts.get(bucket, 0.0), raw_target, settings, dynamic_mode=False)
            for bucket, raw_target in raw_bucket_targets.items()
        }
        effective_bucket_targets = dict(raw_bucket_targets)
        bucket_compression = {bucket: 0.0 for bucket in ACTION_PLAN_BUCKET_KEYS}
        compression_applied = 0.0
        bucket_cash_target = settings["action_bucket_cash_target"]

    rows = []
    bucket_allocated = {bucket: 0.0 for bucket in ACTION_PLAN_BUCKET_KEYS}
    bucket_allocated_before_caps = {bucket: 0.0 for bucket in ACTION_PLAN_BUCKET_KEYS}
    bucket_cap_applied = {bucket: 0.0 for bucket in ACTION_PLAN_BUCKET_KEYS}
    for item in candidates:
        rating = item["bucket"]
        bucket_target = effective_bucket_targets.get(rating, 0.0)
        bucket_raw_target = raw_bucket_targets.get(rating, 0.0)
        sizing_detail = bucket_sizing_details.get(rating) or _action_plan_bucket_sizing_details(rating, bucket_weighted_counts.get(rating, 0.0), bucket_raw_target, settings, dynamic_mode)
        bucket_weight_per_effective_stock = sizing_detail.get("bucket_weight_per_effective_stock")
        max_effective_count = sizing_detail.get("max_effective_count")
        max_bucket_target = sizing_detail.get("max_bucket_target")
        bucket_max_target = sizing_detail.get("bucket_max_target")
        weighted_eligible_count_in_bucket = sizing_detail.get("weighted_eligible_count", 0.0)
        weighted_count_used = sizing_detail.get("weighted_count_used", weighted_eligible_count_in_bucket)
        effective_weighted_count_used = sizing_detail.get("effective_weighted_count_used", weighted_count_used)
        uncapped_bucket_target = sizing_detail.get("uncapped_bucket_target")
        score_total = bucket_score_totals.get(rating, 0.0)
        bucket_share = (item["company_bucket_score"] / score_total * 100.0) if score_total > 0 else 0.0
        raw_target = bucket_target * item["company_bucket_score"] / score_total if score_total > 0 else 0.0
        target_before_caps = raw_target + (0.0 if dynamic_mode else item["potential_bonus_weight"])
        cap, cap_reason_text = _action_plan_cap_details(rating, safe_number(item.get("core_confidence_diff")) or 0.0, settings)
        target_mid = min(target_before_caps, cap)
        cap_applied = max(0.0, target_before_caps - target_mid)
        cap_reason = cap_reason_text if cap_applied > 1e-9 else "—"
        target_low, target_high = _target_band(target_mid, rating, settings)
        row = {
            "symbol": item["symbol"],
            "company_name": item.get("company_name"),
            "rating": rating,
            "current_price": item.get("current_price"),
            "expected_price": item.get("expected_price"),
            "expected_cagr": item.get("expected_cagr"),
            "upside": item.get("upside"),
            "core_confidence_diff": item.get("core_confidence_diff"),
            "core_bullish_confidence": item.get("core_bullish_confidence"),
            "core_bearish_confidence": item.get("core_bearish_confidence"),
            "potential_confidence_diff": item.get("potential_confidence_diff"),
            "potential_bullish_confidence": item.get("potential_bullish_confidence"),
            "potential_bearish_confidence": item.get("potential_bearish_confidence"),
            "current_position_weight": item["current_position_weight"],
            "current_position_market_value": item.get("current_position_market_value"),
            "owned_share_quantity": item.get("owned_share_quantity"),
            "total_portfolio_value": total_portfolio_value,
            "target_weight_mid": target_mid,
            "target_weight_low": target_low,
            "target_weight_high": target_high,
            "target_mid_before_caps": target_before_caps,
            "target_mid_after_caps": target_mid,
            "cap_applied": cap_applied,
            "cap_reason": cap_reason,
            "position_gap_to_mid": target_mid - item["current_position_weight"],
            "bucket": rating,
            "bucket_target_percent": bucket_target,
            "bucket_raw_target": bucket_raw_target,
            "bucket_effective_target": bucket_target,
            "upside_score": item["upside_score"],
            "core_conviction_score": item["core_conviction_score"],
            "core_risk_modifier": item["core_risk_modifier"],
            "core_score": item["core_score"],
            "potential_conviction_score": item["potential_conviction_score"],
            "potential_score_component": item["potential_score_component"],
            "potential_bonus_weight": item["potential_bonus_weight"],
            "company_allocation_score": item["company_allocation_score"],
            "allocation_score": item["allocation_score"],
            "allocation_upside_weight_used": item["allocation_upside_weight_used"],
            "allocation_core_weight_used": item["allocation_core_weight_used"],
            "allocation_potential_weight_used": item["allocation_potential_weight_used"],
            "allocation_risk_penalty_strength": item["allocation_risk_penalty_strength"],
            "allocation_risk_modifier": item["allocation_risk_modifier"],
            "company_bucket_score": item["company_bucket_score"],
            "bucket_sizing_score": item["bucket_sizing_score"],
            "bucket_sizing_risk_modifier": item["bucket_sizing_risk_modifier"],
            "weighted_count": item["weighted_count"],
            "weighted_eligible_count": item["weighted_count"],
            "weighted_count_contribution": item["weighted_count"],
            "score_breakdown": {
                "upside_score": item["upside_score"],
                "core_conviction_score": item["core_conviction_score"],
                "core_risk_modifier": item["core_risk_modifier"],
                "core_score": item["core_score"],
                "potential_conviction_score": item["potential_conviction_score"],
                "potential_score_component": item["potential_score_component"],
                "potential_bonus_weight": item["potential_bonus_weight"],
                "company_allocation_score": item["company_allocation_score"],
                "allocation_score": item["allocation_score"],
                "allocation_upside_weight_used": item["allocation_upside_weight_used"],
                "allocation_core_weight_used": item["allocation_core_weight_used"],
                "allocation_potential_weight_used": item["allocation_potential_weight_used"],
                "allocation_risk_penalty_strength": item["allocation_risk_penalty_strength"],
                "allocation_risk_modifier": item["allocation_risk_modifier"],
                "company_bucket_score": item["company_bucket_score"],
                "bucket_sizing_score": item["bucket_sizing_score"],
                "bucket_sizing_risk_modifier": item["bucket_sizing_risk_modifier"],
                "weighted_count": item["weighted_count"],
            },
            "target_weight_breakdown": {
                "rating_bucket": rating,
                "bucket_target_percent": bucket_target,
                "bucket_raw_target": bucket_raw_target,
                "bucket_effective_target": bucket_target,
                "bucket_weight_per_effective_stock": bucket_weight_per_effective_stock,
                "max_effective_count": max_effective_count,
                "weighted_count_used": weighted_count_used,
                "effective_weighted_count_used": effective_weighted_count_used,
                "uncapped_bucket_target": uncapped_bucket_target,
                "bucket_max_target": bucket_max_target,
                "max_bucket_target": max_bucket_target,
                "eligible_count_in_bucket": bucket_counts.get(rating, 0),
                "weighted_eligible_count_in_bucket": weighted_eligible_count_in_bucket,
                "company_allocation_score": item["company_allocation_score"],
                "allocation_score": item["allocation_score"],
                "allocation_upside_weight_used": item["allocation_upside_weight_used"],
                "allocation_core_weight_used": item["allocation_core_weight_used"],
                "allocation_potential_weight_used": item["allocation_potential_weight_used"],
                "allocation_risk_penalty_strength": item["allocation_risk_penalty_strength"],
                "allocation_risk_modifier": item["allocation_risk_modifier"],
                "company_bucket_score": item["company_bucket_score"],
                "bucket_sizing_score": item["bucket_sizing_score"],
                "bucket_sizing_risk_modifier": item["bucket_sizing_risk_modifier"],
                "weighted_count": item["weighted_count"],
                "total_bucket_allocation_score": score_total,
                "total_bucket_score": score_total,
                "weighted_count_contribution": item["weighted_count"],
                "bucket_share_percent": bucket_share,
                "raw_target_weight": raw_target,
                "target_before_caps": target_before_caps,
                "target_mid_before_caps": target_before_caps,
                "potential_bonus_weight": item["potential_bonus_weight"],
                "cap_applied": cap_applied,
                "cap_reason": cap_reason,
                "target_weight_mid": target_mid,
                "target_mid_after_caps": target_mid,
                "target_weight_low": target_low,
                "target_weight_high": target_high,
            },
            "uses_final_scenario_overlay": item.get("uses_final_scenario_overlay"),
            "final_scenario_stale": item.get("final_scenario_stale"),
            "momentum_score": item.get("momentum_score"),
            "momentum_label": item.get("momentum_label"),
            "extension_risk": item.get("extension_risk"),
            "extension_label": item.get("extension_label"),
            "momentum_updated_at": item.get("momentum_updated_at"),
        }
        action, trigger_price, trigger_direction, distance, reason = _choose_action_plan_decision(row, settings)
        amount_fields = _action_amount_fields(action, item["current_position_weight"], target_mid, total_portfolio_value, item.get("current_position_market_value"))
        trigger_type_by_action = {
            "Strong Add": "strong_add",
            "Add": "add",
            "Starter Buy": "starter_buy",
            "Trim": "trim",
            "Strong Trim": "trim",
            "Sell": "sell",
            "Watch": "starter_buy" if rating == "Speculative Buy" else "add",
        }
        row.update({
            "action": action,
            "trigger_price": trigger_price,
            "trigger_direction": trigger_direction,
            "distance_to_trigger_percent": distance,
            "reason": reason if score_total > 0 or action in {"Sell", "Re-evaluate"} else "No positive attractiveness/conviction score.",
            "action_priority": ACTION_PLAN_ACTION_PRIORITY.get(action, 99),
            **amount_fields,
            "cash_like_available": cash_like_available,
            "action_amount_cash_covered": None,
            "action_amount_cash_shortfall": None,
            "action_amount_cash_note": None,
            "trigger_breakdown": _action_plan_trigger_breakdown(row),
        })
        row["decision_path"] = _action_plan_decision_path(row, action)
        bucket_allocated[rating] = bucket_allocated.get(rating, 0.0) + target_mid
        bucket_allocated_before_caps[rating] = bucket_allocated_before_caps.get(rating, 0.0) + target_before_caps
        bucket_cap_applied[rating] = bucket_cap_applied.get(rating, 0.0) + cap_applied
        rows.append(row)

    linear_payload = compute_linear_action_plan(candidates, total_portfolio_value, cash_like_available, settings)
    execution_summary = _apply_cash_constrained_execution_layer(rows, total_portfolio_value, cash_like_available, settings)
    rows.sort(key=lambda row: (row["action_priority"], -abs(row.get("position_gap_to_mid") or 0.0), row["symbol"]))
    bucket_summary = []
    for bucket, key in ACTION_PLAN_BUCKET_KEYS.items():
        raw_target = raw_bucket_targets.get(bucket, 0.0)
        effective_target = effective_bucket_targets.get(bucket, 0.0)
        allocated = bucket_allocated.get(bucket, 0.0)
        allocated_before_caps = bucket_allocated_before_caps.get(bucket, 0.0)
        post_cap_unallocated = bucket_cap_applied.get(bucket, 0.0)
        eligible_count = bucket_counts.get(bucket, 0)
        status = "Normal"
        if raw_target <= 0 and effective_target <= 0:
            status = "Zero target"
        elif eligible_count <= 0:
            status = "Empty"
        elif bucket_compression.get(bucket, 0.0) > 1e-9:
            status = "Compressed"
        elif post_cap_unallocated > 1e-9:
            status = "Capped"
        elif effective_target - allocated > 1e-9:
            status = "Underallocated"
        sizing_detail = bucket_sizing_details.get(bucket) or _action_plan_bucket_sizing_details(bucket, bucket_weighted_counts.get(bucket, 0.0), raw_target, settings, dynamic_mode)
        bucket_summary.append({
            "bucket": bucket,
            "bucket_target_percent": effective_target,
            "eligible_count": eligible_count,
            "weighted_eligible_count": sizing_detail.get("weighted_eligible_count", bucket_weighted_counts.get(bucket, 0.0)),
            "max_effective_count": sizing_detail.get("max_effective_count"),
            "weighted_count_used": sizing_detail.get("weighted_count_used"),
            "effective_weighted_count_used": sizing_detail.get("effective_weighted_count_used"),
            "bucket_weight_per_effective_stock": sizing_detail.get("bucket_weight_per_effective_stock"),
            "uncapped_bucket_target": sizing_detail.get("uncapped_bucket_target"),
            "raw_bucket_target": sizing_detail.get("raw_bucket_target", raw_target),
            "bucket_max_target": sizing_detail.get("bucket_max_target"),
            "max_bucket_target": sizing_detail.get("max_bucket_target"),
            "raw_target": raw_target,
            "effective_target": effective_target,
            "compression_amount": bucket_compression.get(bucket, 0.0),
            "allocated_before_caps": allocated_before_caps,
            "allocated_after_caps": allocated,
            "allocated_target_percent": allocated,
            "post_cap_unallocated": post_cap_unallocated,
            "unallocated_due_to_caps_percent": post_cap_unallocated,
            "status": status,
        })
    raw_equity_target = sum(raw_bucket_targets.values())
    effective_equity_target = sum(effective_bucket_targets.values())
    allocated_total = sum(bucket_allocated.values())
    post_cap_unallocated_total = sum(bucket_cap_applied.values())
    total_effective_bucket_target = effective_equity_target + bucket_cash_target
    rounding_adjustment = 100.0 - total_effective_bucket_target
    return {
        "action_plan": rows,
        "linear_action_plan": linear_payload["rows"],
        "settings": settings,
        "summary": {
            "total_portfolio_value": total_portfolio_value,
            "portfolio_value_used": total_portfolio_value,
            "portfolio_value_source": portfolio_value_source,
            "portfolio_value_warning": portfolio_value_warning,
            "actual_cash": actual_cash,
            "actual_cash_source": actual_cash_source,
            "cash_equivalent_symbols": cash_equivalent_symbols,
            "cash_equivalent_value": cash_equivalent_value,
            "cash_like_available": cash_like_available,
            "cash_like_available_percent": (cash_like_available / total_portfolio_value * 100.0) if total_portfolio_value > 0 else None,
            **execution_summary,
            "execution_warning": "Add demand exceeds available funding. Action amounts have been cash-constrained and prioritized." if execution_summary["total_add_demand"] > execution_summary["available_buy_budget"] + 1e-6 else None,
            "configured_cash_target_percent": bucket_cash_target,
            "cash_like_vs_target_gap_percent": ((cash_like_available / total_portfolio_value * 100.0) - bucket_cash_target) if total_portfolio_value > 0 else None,
            "raw_equity_target": raw_equity_target,
            "effective_equity_target": effective_equity_target,
            "cash_unallocated_target": bucket_cash_target,
            "post_cap_unallocated": post_cap_unallocated_total,
            "final_allocated_stock_target": allocated_total,
            "total_effective_bucket_target": total_effective_bucket_target,
            "rounding_adjustment": rounding_adjustment,
            "compression_applied": compression_applied,
            "unallocated_due_to_underfilled_buckets": max(0.0, effective_equity_target - allocated_total),
            "dynamic_bucket_sizing_enabled": dynamic_mode,
            "weighted_eligible_count_enabled": weighted_count_enabled,
            "configured_bucket_total": total_effective_bucket_target,
            "allocated_target_total": allocated_total,
            "unallocated_target_capacity": max(0.0, 100.0 - allocated_total),
            "unallocated_target_total": max(0.0, 100.0 - allocated_total),
            "cash_equivalent_positions": cash_equivalent_positions,
            "bucket_summary": bucket_summary,
            "linear_summary": linear_payload["summary"],
        },
    }

def build_linear_action_plan_detail(payload, symbol, variables=None):
    normalized = normalize_symbol(symbol)
    row = next(
        (
            item for item in payload.get("linear_action_plan", [])
            if normalize_symbol(item.get("symbol")) == normalized
        ),
        None,
    )
    if not row:
        return None
    row = dict(row)
    for obsolete_key in (
        "trigger_price",
        "trigger_direction",
        "relevant_trigger_price",
        "relevant_trigger_type",
        "distance_to_trigger_percent",
        "distance_to_relevant_trigger_percent",
        "distance_to_relevant_trigger_label",
        "trigger_breakdown",
    ):
        row.pop(obsolete_key, None)
    row["detail_source"] = "linear_action_plan"
    row["action_relevant_key_variables"] = sorted(
        variables or [],
        key=lambda item: (safe_number(item.get("importance")) or 0.0, safe_number(item.get("confidence")) or 0.0),
        reverse=True,
    )[:10]
    row["summary"] = payload.get("summary", {}).get("linear_summary", {})
    return row


def get_action_plan_detail(conn, symbol):
    normalized = normalize_symbol(symbol)
    payload = build_action_plan(conn)
    detail = get_analysis_detail(conn, normalized)
    variables = []
    if detail and detail.get("version"):
        variables = detail["version"].get("key_variables") or []
    return build_linear_action_plan_detail(payload, normalized, variables)


def overlay_cached_market_fields(live_rows, cached_rows):
    cached_by_symbol = {
        normalize_symbol(item.get("symbol")): item
        for item in (cached_rows or [])
        if normalize_symbol(item.get("symbol"))
    }
    merged = []
    for row in live_rows or []:
        combined = dict(row)
        symbol = normalize_symbol(combined.get("symbol"))
        cached = cached_by_symbol.get(symbol)
        if cached:
            for field in ("price", "changePercent", "marketValue", "unrealizedPnL", "unrealizedPnLPercent", "dailyPnL", "currency"):
                if combined.get(field) is None and cached.get(field) is not None:
                    combined[field] = cached.get(field)
        merged.append(combined)
    return merged


def build_positions_payload(conn, positions, data_source, warning=None):
    normalized_positions = []
    for row in positions or []:
        normalized_row = dict(row)
        if abs(safe_number(normalized_row.get("position")) or 0.0) <= 0:
            continue
        normalized_row["unrealizedPnLPercent"] = compute_unrealized_pnl_percent(normalized_row)
        normalized_row["costBasis"] = compute_cost_basis(normalized_row)
        normalized_positions.append(normalized_row)

    analysis_items = list_analysis_symbols(conn)
    payload = {
        "positions": merge_positions_with_latest_analysis(normalized_positions, analysis_items),
        "data_source": data_source,
        "portfolio_summary": build_portfolio_cash_summary(conn, normalized_positions),
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
        SELECT variable_text, variable_type, COALESCE(driver_category, 'Core Driver') AS driver_category, confidence, importance
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
                "driver_category": normalized_driver_category(item["driver_category"]),
                "confidence": item["confidence"],
                "importance": item["importance"],
            }
            for item in key_variables
        ],
    }


def _normalize_watchpoint_text(value):
    text = str(value or "").strip()
    return text if text else None


def _normalize_earnings_watchpoint_item(raw_item):
    if not isinstance(raw_item, dict):
        return None
    key_variable = _normalize_watchpoint_text(raw_item.get("key_variable"))
    if not key_variable:
        return None
    raw_watchpoints = raw_item.get("watchpoints")
    if not isinstance(raw_watchpoints, list):
        return None
    cleaned = []
    seen = set()
    for raw_watchpoint in raw_watchpoints:
        normalized = _normalize_watchpoint_text(raw_watchpoint)
        if not normalized:
            continue
        dedupe_key = normalized.lower()
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        cleaned.append(normalized)
    if not cleaned:
        return None
    return {
        "key_variable": key_variable,
        "type": str(raw_item.get("type") or "").strip(),
        "watchpoints": cleaned,
    }


def _build_earnings_watchpoints_schema():
    return {
        "name": "earnings_watchpoints",
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "watchpoints_by_variable": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "key_variable": {"type": "string"},
                            "type": {"type": "string"},
                            "watchpoints": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["key_variable", "type", "watchpoints"],
                    },
                }
            },
            "required": ["watchpoints_by_variable"],
        },
    }


def _build_earnings_watchpoint_analysis_schema():
    return {
        "name": "earnings_watchpoint_analysis",
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "watchpoint_results": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "watchpoint_id": {"type": "string"},
                            "key_variable": {"type": "string"},
                            "watchpoint": {"type": "string"},
                            "status": {"type": "string"},
                            "result_text": {"type": "string"},
                        },
                        "required": ["watchpoint_id", "key_variable", "watchpoint", "status", "result_text"],
                    },
                }
            },
            "required": ["watchpoint_results"],
        },
    }


def _read_earnings_document_text(storage_path):
    file_path = Path(storage_path)
    if not file_path.is_absolute():
        file_path = BASE_DIR / file_path
    if not file_path.exists():
        return ""
    suffix = file_path.suffix.lower()
    try:
        if suffix in {".txt", ".csv", ".html"}:
            return file_path.read_text(encoding="utf-8", errors="replace")
        if suffix == ".docx":
            with zipfile.ZipFile(file_path) as archive:
                xml_text = archive.read("word/document.xml").decode("utf-8", errors="replace")
            text = re.sub(r"<[^>]+>", " ", xml_text)
            return unescape(re.sub(r"\s+", " ", text)).strip()
        if suffix == ".xlsx":
            with zipfile.ZipFile(file_path) as archive:
                parts = []
                for name in archive.namelist():
                    if name.startswith("xl/worksheets/") and name.endswith(".xml"):
                        parts.append(archive.read(name).decode("utf-8", errors="replace"))
                    if name == "xl/sharedStrings.xml":
                        parts.append(archive.read(name).decode("utf-8", errors="replace"))
            text = " ".join(parts)
            text = re.sub(r"<[^>]+>", " ", text)
            return unescape(re.sub(r"\s+", " ", text)).strip()
        if suffix == ".pdf":
            try:
                from pypdf import PdfReader  # type: ignore

                reader = PdfReader(str(file_path))
                texts = [(page.extract_text() or "") for page in reader.pages]
                return "\n".join(texts).strip()
            except Exception:
                raw = file_path.read_bytes()
                fragments = re.findall(rb"\(([^()]*)\)", raw)
                decoded = []
                for fragment in fragments:
                    text = fragment.decode("latin-1", errors="ignore")
                    text = re.sub(r"\\[nrt]", " ", text)
                    text = text.replace("\\(", "(").replace("\\)", ")").replace("\\\\", "\\")
                    decoded.append(text)
                return re.sub(r"\s+", " ", " ".join(decoded)).strip()
    except Exception:
        return ""
    return ""


def _is_meaningful_extracted_text(text):
    normalized = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(normalized) < 40:
        return False
    letters = re.sub(r"[^A-Za-z0-9]", "", normalized)
    return len(letters) >= 30


def _format_earnings_watchpoints_for_prompt(watchpoints_by_variable):
    lines = []
    for group in watchpoints_by_variable or []:
        key_variable = str(group.get("key_variable") or "").strip() or "Unknown variable"
        group_type = str(group.get("type") or "").strip()
        lines.append(f"Key Variable: {key_variable}{f' ({group_type})' if group_type else ''}")
        for watchpoint in group.get("watchpoints") or []:
            lines.append(f"- {watchpoint}")
    return "\n".join(lines)


def chunk_watchpoints(items, batch_size):
    effective_size = max(1, int(batch_size or 1))
    return [items[idx: idx + effective_size] for idx in range(0, len(items), effective_size)]


def _format_earnings_watchpoint_batch_for_prompt(batch_items):
    lines = []
    grouped = {}
    for item in batch_items:
        key = item["key_variable"]
        grouped.setdefault(key, {"type": item.get("type") or "", "items": []})
        grouped[key]["items"].append(item)
    for key_variable, payload in grouped.items():
        group_type = payload.get("type") or ""
        lines.append(f"Key Variable: {key_variable}{f' ({group_type})' if group_type else ''}")
        for item in payload["items"]:
            lines.append(f"- watchpoint_id={item['watchpoint_id']} | watchpoint={item['watchpoint']}")
    return "\n".join(lines)


def _format_earnings_documents_for_prompt(document_rows):
    blocks = []
    readable_count = 0
    diagnostics = []
    for row in document_rows or []:
        text = _read_earnings_document_text(row["storage_path"])
        meaningful = _is_meaningful_extracted_text(text)
        diagnostics.append(
            {
                "file_name": row.get("original_file_name"),
                "document_type": row.get("document_type"),
                "extracted_chars": len(text or ""),
                "readable": meaningful,
            }
        )
        if not meaningful:
            continue
        readable_count += 1
        text = re.sub(r"\s+", " ", text).strip()[:12000]
        blocks.append(
            "\n".join(
                [
                    f"Document: {row['original_file_name']}",
                    f"Type: {row.get('document_type') or 'Other'}",
                    f"Content:\n{text}",
                ]
            )
        )
    return "\n\n---\n\n".join(blocks), readable_count, diagnostics

def _parse_release_date(value):
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.strptime(text, "%Y-%m-%d")
        return parsed.strftime("%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("release_date must be in YYYY-MM-DD format") from exc


def _validate_fiscal_quarter(value):
    quarter = str(value or "").strip().upper()
    if quarter not in {"Q1", "Q2", "Q3", "Q4"}:
        raise ValueError("fiscal_quarter must be one of: Q1, Q2, Q3, Q4")
    return quarter


def _build_earnings_review_thesis_snapshot(conn, symbol):
    detail = get_analysis_detail(conn, symbol)
    if not detail:
        raise ValueError(f"Analysis for symbol {symbol} not found")
    version = detail.get("version") or {}
    raw_key_variables = version.get("key_variables") or []
    normalized_key_variables = []
    for item in raw_key_variables:
        if not isinstance(item, dict):
            continue
        variable_text = (
            item.get("variable")
            or item.get("variable_text")
            or item.get("key_variable")
            or item.get("text")
            or ""
        )
        variable_type = (
            item.get("type")
            or item.get("variable_type")
            or item.get("polarity")
            or ""
        )
        normalized_key_variables.append(
            {
                "variable": str(variable_text).strip(),
                "type": str(variable_type).strip(),
                "driver_category": safe_driver_category(item.get("driver_category")),
                "confidence": safe_number(item.get("confidence")),
                "importance": safe_number(item.get("importance")),
            }
        )
    return {
        "symbol": symbol,
        "company_name": version.get("company_name") or symbol,
        "rating": version.get("rating"),
        "current_price": version.get("current_price"),
        "expected_price": version.get("expected_price"),
        "expected_cagr": version.get("expected_cagr"),
        "upside": version.get("upside"),
        "business_model": version.get("business_model") or "",
        "business_summary": version.get("business_summary") or "",
        "key_variables": normalized_key_variables,
        "scenarios": version.get("scenarios") or [],
        "analysis_version_id": version.get("id"),
        "analysis_version_created_at": version.get("created_at"),
    }


def get_earnings_review_watchpoints(conn, earnings_review_id):
    rows = conn.execute(
        """
        SELECT id, key_variable_text, key_variable_type, watchpoints_json, generated_at, display_order
        FROM earnings_review_watchpoints
        WHERE earnings_review_id = ?
        ORDER BY display_order ASC, id ASC
        """,
        (earnings_review_id,),
    ).fetchall()
    items = []
    for row in rows:
        try:
            parsed = json.loads(row["watchpoints_json"] or "[]")
            watchpoints = [str(item).strip() for item in parsed if str(item).strip()]
        except Exception:
            watchpoints = []
        items.append(
            {
                "id": row["id"],
                "key_variable": row["key_variable_text"],
                "type": row["key_variable_type"] or "",
                "watchpoints": watchpoints,
                "watchpoint_ids": [f"{row['id']}:{idx}" for idx, _ in enumerate(watchpoints)],
                "generated_at": row["generated_at"],
            }
        )
    return items


def _replace_earnings_review_watchpoints(conn, earnings_review_id, watchpoints_by_variable):
    now = utc_now_iso()
    conn.execute("DELETE FROM earnings_review_watchpoints WHERE earnings_review_id = ?", (earnings_review_id,))
    for idx, item in enumerate(watchpoints_by_variable):
        conn.execute(
            """
            INSERT INTO earnings_review_watchpoints (
              earnings_review_id, key_variable_text, key_variable_type, watchpoints_json,
              display_order, generated_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                earnings_review_id,
                item["key_variable"],
                item.get("type") or "",
                json.dumps(item.get("watchpoints") or [], ensure_ascii=False),
                idx,
                now,
                now,
                now,
            ),
        )


def _safe_upload_filename(filename):
    candidate = Path(filename or "").name.strip()
    if not candidate:
        candidate = "document"
    return "".join(ch if (ch.isalnum() or ch in {"-", "_", "."}) else "_" for ch in candidate)


def _ensure_earnings_review_record(conn, symbol, review_id):
    row = conn.execute(
        "SELECT id, symbol FROM earnings_reviews WHERE id = ? AND symbol = ?",
        (review_id, symbol),
    ).fetchone()
    if not row:
        raise ValueError(f"Earnings review record {review_id} not found for symbol {symbol}")
    return row


def list_earnings_review_documents(conn, symbol, review_id):
    _ensure_earnings_review_record(conn, symbol, review_id)
    rows = conn.execute(
        """
        SELECT id, original_file_name, document_type, mime_type, file_size, uploaded_at, created_at, updated_at
        FROM earnings_review_documents
        WHERE earnings_review_id = ?
        ORDER BY uploaded_at DESC, id DESC
        """,
        (review_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def _list_earnings_review_documents_with_storage(conn, review_id):
    rows = conn.execute(
        """
        SELECT id, original_file_name, storage_path, document_type, mime_type, file_size, uploaded_at
        FROM earnings_review_documents
        WHERE earnings_review_id = ?
        ORDER BY uploaded_at DESC, id DESC
        """,
        (review_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def list_earnings_review_watchpoint_results(conn, review_id):
    rows = conn.execute(
        """
        SELECT key_variable_text, watchpoint_text, status, result_text, analysed_at, updated_at
        FROM earnings_review_watchpoint_results
        WHERE earnings_review_id = ?
        ORDER BY id ASC
        """,
        (review_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def clear_earnings_review_watchpoint_results(conn, review_id):
    conn.execute("DELETE FROM earnings_review_watchpoint_results WHERE earnings_review_id = ?", (review_id,))
    conn.commit()


def recalculate_earnings_review_status(conn, review_id):
    documents_count = conn.execute(
        "SELECT COUNT(*) AS c FROM earnings_review_documents WHERE earnings_review_id = ?",
        (review_id,),
    ).fetchone()["c"]
    if int(documents_count or 0) > 0:
        new_status = EARNINGS_REVIEW_STATUS_DOCUMENTS_UPLOADED
    else:
        watchpoints_count = conn.execute(
            "SELECT COUNT(*) AS c FROM earnings_review_watchpoints WHERE earnings_review_id = ?",
            (review_id,),
        ).fetchone()["c"]
        new_status = (
            EARNINGS_REVIEW_STATUS_WATCHPOINTS_GENERATED
            if int(watchpoints_count or 0) > 0
            else EARNINGS_REVIEW_STATUS_DRAFT
        )
    conn.execute(
        "UPDATE earnings_reviews SET status = ?, updated_at = ? WHERE id = ?",
        (new_status, utc_now_iso(), review_id),
    )
    conn.commit()
    return new_status


def save_earnings_review_document(
    conn,
    symbol,
    review_id,
    document_type,
    original_file_name,
    payload,
    mime_type=None,
):
    _ensure_earnings_review_record(conn, symbol, review_id)
    if document_type not in EARNINGS_REVIEW_ALLOWED_DOCUMENT_TYPES:
        raise ValueError("Invalid document type.")
    safe_original_name = _safe_upload_filename(original_file_name)
    extension = Path(safe_original_name).suffix.lower()
    if extension not in EARNINGS_REVIEW_ALLOWED_FILE_EXTENSIONS:
        raise ValueError("Unsupported file type. Allowed: pdf, txt, docx, csv, xlsx, html.")
    if payload is None or len(payload) <= 0:
        raise ValueError("A file is required.")
    if len(payload) > EARNINGS_REVIEW_MAX_DOCUMENT_BYTES:
        raise ValueError("File is too large. Maximum size is 15 MB.")

    review_dir = UPLOADS_DIR / "earnings_reviews" / str(review_id)
    review_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}{extension}"
    storage_path = review_dir / stored_name
    storage_path.write_bytes(payload)
    now = utc_now_iso()
    cursor = conn.execute(
        """
        INSERT INTO earnings_review_documents (
          earnings_review_id, original_file_name, storage_path, document_type,
          mime_type, file_size, uploaded_at, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            review_id,
            safe_original_name,
            str(storage_path),
            document_type,
            (mime_type or "").strip() or None,
            len(payload),
            now,
            now,
            now,
        ),
    )
    conn.commit()
    recalculate_earnings_review_status(conn, review_id)
    row = conn.execute(
        """
        SELECT id, original_file_name, document_type, mime_type, file_size, uploaded_at, created_at, updated_at
        FROM earnings_review_documents
        WHERE id = ?
        """,
        (cursor.lastrowid,),
    ).fetchone()
    return dict(row)


def delete_earnings_review_document(conn, symbol, review_id, document_id):
    _ensure_earnings_review_record(conn, symbol, review_id)
    row = conn.execute(
        """
        SELECT id, storage_path
        FROM earnings_review_documents
        WHERE id = ? AND earnings_review_id = ?
        """,
        (document_id, review_id),
    ).fetchone()
    if not row:
        raise ValueError("Document not found.")
    storage_path = Path(row["storage_path"])
    if not storage_path.is_absolute():
        storage_path = BASE_DIR / storage_path
    conn.execute("DELETE FROM earnings_review_documents WHERE id = ? AND earnings_review_id = ?", (document_id, review_id))
    conn.commit()
    try:
        if storage_path.exists():
            storage_path.unlink()
    except OSError:
        logger.warning("Unable to remove earnings review document file %s", storage_path)
    recalculate_earnings_review_status(conn, review_id)


def get_earnings_review_document_download(conn, symbol, review_id, document_id):
    _ensure_earnings_review_record(conn, symbol, review_id)
    row = conn.execute(
        """
        SELECT id, original_file_name, storage_path, mime_type
        FROM earnings_review_documents
        WHERE id = ? AND earnings_review_id = ?
        """,
        (document_id, review_id),
    ).fetchone()
    if not row:
        raise ValueError("Document not found.")
    file_path = Path(row["storage_path"])
    if not file_path.is_absolute():
        file_path = BASE_DIR / file_path
    if not file_path.exists():
        raise ValueError("Document file is missing.")
    return dict(row), file_path


def list_earnings_review_symbols(conn):
    rows = conn.execute(
        """
        SELECT symbol
        FROM earnings_review_symbols
        ORDER BY symbol ASC
        """
    ).fetchall()
    analysis_by_symbol = {row["symbol"]: row for row in list_analysis_symbols(conn)}
    position_symbols = {
        normalize_symbol(item.get("symbol"))
        for item in load_positions_cache(conn)
        if abs(safe_number(item.get("position")) or 0.0) > 0
    }
    items = []
    for row in rows:
        symbol = row["symbol"]
        analysis = analysis_by_symbol.get(symbol) or {}
        latest_status_row = conn.execute(
            """
            SELECT fiscal_year, fiscal_quarter, status
            FROM earnings_reviews
            WHERE symbol = ?
            ORDER BY fiscal_year DESC,
                     CASE fiscal_quarter WHEN 'Q4' THEN 4 WHEN 'Q3' THEN 3 WHEN 'Q2' THEN 2 ELSE 1 END DESC,
                     id DESC
            LIMIT 1
            """,
            (symbol,),
        ).fetchone()
        latest_quarter = None
        if latest_status_row:
            latest_quarter = f"FY{latest_status_row['fiscal_year']} {latest_status_row['fiscal_quarter']}"
        items.append(
            {
                "symbol": symbol,
                "in_portfolio": symbol in position_symbols,
                "rating": analysis.get("rating"),
                "latest_quarter": latest_quarter,
                "latest_review_status": latest_status_row["status"] if latest_status_row else None,
            }
        )
    return items


def add_earnings_review_symbol(conn, symbol):
    normalized = normalize_symbol(symbol)
    if not normalized:
        raise ValueError("Symbol is required.")
    exists = conn.execute("SELECT 1 FROM analysis_roots WHERE symbol = ?", (normalized,)).fetchone()
    if not exists:
        raise ValueError("Symbol not found in Analysis.")
    duplicate = conn.execute("SELECT 1 FROM earnings_review_symbols WHERE symbol = ?", (normalized,)).fetchone()
    if duplicate:
        raise ValueError("Symbol already exists in Earnings Review.")
    now = utc_now_iso()
    conn.execute(
        "INSERT INTO earnings_review_symbols (symbol, created_at, updated_at) VALUES (?, ?, ?)",
        (normalized, now, now),
    )
    conn.commit()
    return normalized


def get_earnings_review_symbol_history(conn, symbol):
    analysis_context = get_latest_analysis_context(conn, symbol)
    reviews = conn.execute(
        """
        SELECT id, fiscal_year, fiscal_quarter, release_date, status, watchpoints_generated_at, created_at, updated_at
        FROM earnings_reviews
        WHERE symbol = ?
        ORDER BY fiscal_year DESC, fiscal_quarter DESC, id DESC
        """,
        (symbol,),
    ).fetchall()
    records = []
    for row in reviews:
        count_row = conn.execute(
            "SELECT COUNT(*) AS count FROM earnings_review_watchpoints WHERE earnings_review_id = ?",
            (row["id"],),
        ).fetchone()
        records.append(
            {
                "id": row["id"],
                "fiscal_year": row["fiscal_year"],
                "fiscal_quarter": row["fiscal_quarter"],
                "release_date": row["release_date"],
                "status": row["status"],
                "watchpoints_generated_at": row["watchpoints_generated_at"],
                "watchpoints_count": int(count_row["count"] or 0),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        )

    return {
        "symbol": symbol,
        "company_name": analysis_context.get("company_name") or symbol,
        "records": records,
    }


def create_earnings_review_record(conn, symbol, fiscal_year, fiscal_quarter, release_date=None):
    now = utc_now_iso()
    normalized_quarter = _validate_fiscal_quarter(fiscal_quarter)
    try:
        year = int(fiscal_year)
    except (TypeError, ValueError) as exc:
        raise ValueError("fiscal_year must be a valid integer") from exc
    if year < 1900 or year > 2200:
        raise ValueError("fiscal_year must be between 1900 and 2200")
    normalized_release_date = _parse_release_date(release_date)
    snapshot = _build_earnings_review_thesis_snapshot(conn, symbol)

    try:
        conn.execute(
            """
            INSERT INTO earnings_reviews (
              symbol, company_name_snapshot, fiscal_year, fiscal_quarter, release_date,
              status, thesis_snapshot_json, watchpoints_generated_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)
            """,
            (
                symbol,
                snapshot.get("company_name") or symbol,
                year,
                normalized_quarter,
                normalized_release_date,
                EARNINGS_REVIEW_STATUS_DRAFT,
                json.dumps(snapshot, ensure_ascii=False),
                now,
                now,
            ),
        )
    except sqlite3.IntegrityError as exc:
        raise ValueError(f"Earnings review already exists for {symbol} {year} {normalized_quarter}") from exc

    review_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
    conn.commit()
    return get_earnings_review_record_detail(conn, symbol, review_id)


def get_earnings_review_record_detail(conn, symbol, review_id):
    row = conn.execute(
        """
        SELECT id, symbol, company_name_snapshot, fiscal_year, fiscal_quarter, release_date,
               status, thesis_snapshot_json, watchpoints_generated_at, created_at, updated_at
        FROM earnings_reviews
        WHERE id = ? AND symbol = ?
        """,
        (review_id, symbol),
    ).fetchone()
    if not row:
        raise ValueError(f"Earnings review record not found for symbol={symbol} id={review_id}")
    try:
        snapshot = json.loads(row["thesis_snapshot_json"] or "{}")
        if not isinstance(snapshot, dict):
            snapshot = {}
    except Exception:
        snapshot = {}
    watchpoints = get_earnings_review_watchpoints(conn, row["id"])
    documents = list_earnings_review_documents(conn, symbol, row["id"])
    watchpoint_results = list_earnings_review_watchpoint_results(conn, row["id"])
    normalized_snapshot_key_variables = []
    for item in snapshot.get("key_variables") or []:
        if not isinstance(item, dict):
            continue
        normalized_snapshot_key_variables.append(
            {
                "variable": str(
                    item.get("variable")
                    or item.get("variable_text")
                    or item.get("key_variable")
                    or item.get("text")
                    or ""
                ).strip(),
                "type": str(
                    item.get("type")
                    or item.get("variable_type")
                    or item.get("polarity")
                    or ""
                ).strip(),
                "driver_category": safe_driver_category(item.get("driver_category")),
                "confidence": safe_number(item.get("confidence")),
                "importance": safe_number(item.get("importance")),
            }
        )
    return {
        "id": row["id"],
        "symbol": row["symbol"],
        "company_name_snapshot": row["company_name_snapshot"] or snapshot.get("company_name") or row["symbol"],
        "fiscal_year": row["fiscal_year"],
        "fiscal_quarter": row["fiscal_quarter"],
        "release_date": row["release_date"],
        "status": row["status"],
        "watchpoints_generated_at": row["watchpoints_generated_at"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "thesis_snapshot": snapshot,
        "key_variables_snapshot": normalized_snapshot_key_variables,
        "watchpoints_by_variable": watchpoints,
        "watchpoint_results": watchpoint_results,
        "documents": documents,
    }


def generate_earnings_watchpoints_for_review(conn, symbol, review_id):
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is required for earnings watchpoint generation")

    detail = get_earnings_review_record_detail(conn, symbol, review_id)
    snapshot = detail.get("thesis_snapshot") or {}
    templates, sources = get_prompt_templates_for_keys(
        conn,
        EARNINGS_REVIEW_WORKFLOW_PROMPT_KEYS,
        purpose="earnings_watchpoints",
    )
    template = templates[ANALYSIS_PROMPT_SETTING_KEY_EARNINGS_WATCHPOINTS]
    template_source = sources[ANALYSIS_PROMPT_SETTING_KEY_EARNINGS_WATCHPOINTS]
    prompt_context = build_prompt_context(
        symbol=snapshot.get("symbol") or symbol,
        price=snapshot.get("current_price"),
        company_name=snapshot.get("company_name") or detail.get("company_name_snapshot") or symbol,
        business_model=snapshot.get("business_model") or "",
        business_summary=snapshot.get("business_summary") or "",
        key_variables=snapshot.get("key_variables") or [],
    )
    prompt_text = render_prompt_template(template, prompt_context)
    response = request_ai_step("earnings_watchpoints", prompt_text, _build_earnings_watchpoints_schema())
    raw_items = response.get("watchpoints_by_variable") if isinstance(response, dict) else None
    if not isinstance(raw_items, list):
        raise AnalysisValidationError("earnings_watchpoints.watchpoints_by_variable must be an array")
    normalized_items = [item for item in (_normalize_earnings_watchpoint_item(raw) for raw in raw_items) if item]
    if not normalized_items:
        raise AnalysisValidationError("No valid watchpoints_by_variable entries were returned by AI")
    _replace_earnings_review_watchpoints(conn=conn, earnings_review_id=review_id, watchpoints_by_variable=normalized_items)
    clear_earnings_review_watchpoint_results(conn, review_id)
    now = utc_now_iso()
    conn.execute(
        """
        UPDATE earnings_reviews
        SET watchpoints_generated_at = ?, updated_at = ?
        WHERE id = ? AND symbol = ?
        """,
        (
            now,
            now,
            review_id,
            symbol,
        ),
    )
    logger.info(
        "Generated earnings watchpoints review_id=%s symbol=%s prompt_source=%s groups=%s",
        review_id,
        symbol,
        template_source,
        len(normalized_items),
    )
    conn.commit()
    recalculate_earnings_review_status(conn, review_id)
    return get_earnings_review_record_detail(conn, symbol, review_id)


def analyze_earnings_watchpoints_for_review(conn, symbol, review_id):
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is required for earnings watchpoint analysis")
    detail = get_earnings_review_record_detail(conn, symbol, review_id)
    watchpoints_by_variable = detail.get("watchpoints_by_variable") or []
    if not watchpoints_by_variable:
        raise ValueError("Generate earnings watchpoints before analysing them.")
    documents = _list_earnings_review_documents_with_storage(conn, review_id)
    if not documents:
        raise ValueError("Upload at least one earnings document before analysing watchpoints.")

    watchpoint_items = []
    for group in watchpoints_by_variable:
        key_variable = str(group.get("key_variable") or "").strip()
        group_type = str(group.get("type") or "").strip()
        group_id = str(group.get("id") or "").strip()
        group_watchpoint_ids = group.get("watchpoint_ids") or []
        if not key_variable:
            continue
        for idx, watchpoint in enumerate(group.get("watchpoints") or []):
            normalized_watchpoint = str(watchpoint).strip()
            if not normalized_watchpoint:
                continue
            watchpoint_id = str(group_watchpoint_ids[idx] if idx < len(group_watchpoint_ids) else "").strip()
            if not watchpoint_id:
                watchpoint_id = f"{group_id or key_variable}:{idx}"
            watchpoint_items.append(
                {
                    "watchpoint_id": watchpoint_id,
                    "key_variable": key_variable,
                    "type": group_type,
                    "watchpoint": normalized_watchpoint,
                }
            )
    if not watchpoint_items:
        raise ValueError("Generate earnings watchpoints before analysing them.")

    snapshot = detail.get("thesis_snapshot") or {}
    templates, sources = get_prompt_templates_for_keys(
        conn,
        EARNINGS_REVIEW_WORKFLOW_PROMPT_KEYS,
        purpose="earnings_watchpoint_analysis",
    )
    template = templates[ANALYSIS_PROMPT_SETTING_KEY_EARNINGS_WATCHPOINT_ANALYSIS]
    template_source = sources[ANALYSIS_PROMPT_SETTING_KEY_EARNINGS_WATCHPOINT_ANALYSIS]
    documents_text, readable_count, diagnostics = _format_earnings_documents_for_prompt(documents)
    logger.info(
        "Earnings document extraction summary review_id=%s symbol=%s total=%s readable=%s diagnostics=%s",
        review_id,
        symbol,
        len(documents),
        readable_count,
        diagnostics,
    )
    if readable_count <= 0 or not documents_text.strip():
        raise ValueError("Analysis could not run because no readable text could be extracted from the uploaded documents.")

    all_results_by_id = {}
    batches = chunk_watchpoints(watchpoint_items, batch_size=4)
    for batch_index, batch in enumerate(batches, start=1):
        batch_by_id = {item["watchpoint_id"]: item for item in batch}
        expected_ids = set(batch_by_id.keys())
        prompt_context = build_prompt_context(
            symbol=snapshot.get("symbol") or symbol,
            company_name=snapshot.get("company_name") or detail.get("company_name_snapshot") or symbol,
            business_model=snapshot.get("business_model") or "",
            business_summary=snapshot.get("business_summary") or "",
            key_variables=snapshot.get("key_variables") or [],
            earnings_watchpoints=_format_earnings_watchpoint_batch_for_prompt(batch),
            earnings_documents=documents_text,
        )
        prompt_text = render_prompt_template(template, prompt_context)
        def _run_batch_request(batch_prompt_text):
            attempts = (1, 2)
            response_payload = None
            last_timeout_exc = None
            for attempt in attempts:
                timeout_seconds = get_ai_step_timeout("earnings_watchpoint_analysis", attempt=attempt)
                logger.info(
                    "Earnings watchpoint analysis attempt symbol=%s review_id=%s batch=%s/%s attempt=%s watchpoints=%s documents=%s extracted_chars=%s prompt_chars=%s timeout=%.1f",
                    symbol,
                    review_id,
                    batch_index,
                    len(batches),
                    attempt,
                    len(batch),
                    len(documents),
                    len(documents_text),
                    len(batch_prompt_text),
                    timeout_seconds,
                )
                try:
                    response_payload = request_ai_step(
                        "earnings_watchpoint_analysis",
                        batch_prompt_text,
                        _build_earnings_watchpoint_analysis_schema(),
                        attempt=attempt,
                    )
                    break
                except RuntimeError as exc:
                    is_timeout = "timed out on step earnings_watchpoint_analysis" in str(exc).lower()
                    if is_timeout and attempt == 1:
                        last_timeout_exc = exc
                        logger.warning(
                            "Earnings watchpoint analysis timeout on batch %s/%s. Retrying once with longer timeout.",
                            batch_index,
                            len(batches),
                        )
                        continue
                    if is_timeout:
                        last_timeout_exc = exc
                    logger.exception(
                        "Earnings watchpoint analysis failed on batch %s/%s attempt %s",
                        batch_index,
                        len(batches),
                        attempt,
                    )
                    raise ValueError(
                        f"Earnings watchpoint analysis failed on batch {batch_index}/{len(batches)}."
                    ) from exc
            if response_payload is None and last_timeout_exc is not None:
                raise RuntimeError(
                    f"Earnings watchpoint analysis timed out on batch {batch_index}/{len(batches)} after retry."
                ) from last_timeout_exc
            return response_payload

        def _validate_batch_response(response_payload):
            raw_items = response_payload.get("watchpoint_results") if isinstance(response_payload, dict) else None
            if not isinstance(raw_items, list):
                raise AnalysisValidationError(
                    f"earnings_watchpoint_analysis.watchpoint_results must be an array for batch {batch_index}/{len(batches)}"
                )
            returned_ids = []
            duplicates = set()
            batch_results = {}
            for raw in raw_items:
                if not isinstance(raw, dict):
                    continue
                watchpoint_id = str(raw.get("watchpoint_id") or "").strip()
                key_variable = str(raw.get("key_variable") or "").strip()
                watchpoint = str(raw.get("watchpoint") or "").strip()
                status = str(raw.get("status") or "").strip()
                result_text = str(raw.get("result_text") or "").strip()
                if not watchpoint_id:
                    continue
                if watchpoint_id in returned_ids:
                    duplicates.add(watchpoint_id)
                returned_ids.append(watchpoint_id)
                if watchpoint_id not in expected_ids:
                    continue
                if status not in EARNINGS_WATCHPOINT_ANALYSIS_ALLOWED_STATUSES or not result_text:
                    continue
                batch_results[watchpoint_id] = (key_variable, watchpoint, status, result_text)

            returned_ids_set = set(returned_ids)
            missing_ids = sorted(expected_ids - returned_ids_set)
            extra_ids = sorted(returned_ids_set - expected_ids)
            duplicate_ids = sorted(duplicates)
            logger.info(
                "Earnings watchpoint batch validation review_id=%s symbol=%s batch=%s/%s expected_ids=%s returned_ids=%s missing_ids=%s duplicate_ids=%s extra_ids=%s",
                review_id,
                symbol,
                batch_index,
                len(batches),
                sorted(expected_ids),
                sorted(returned_ids_set),
                missing_ids,
                duplicate_ids,
                extra_ids,
            )
            is_valid = not missing_ids and not duplicate_ids and not extra_ids and len(batch_results) == len(expected_ids)
            return is_valid, batch_results, missing_ids, duplicate_ids, extra_ids

        response = _run_batch_request(prompt_text)
        is_valid, batch_results, missing_ids, duplicate_ids, extra_ids = _validate_batch_response(response)
        if not is_valid:
            repair_prompt = (
                f"{prompt_text}\n\nSTRICT RETRY INSTRUCTIONS:\n"
                "- Return exactly one item for every watchpoint_id in this batch.\n"
                "- Preserve each watchpoint_id exactly.\n"
                "- Do not add any extra watchpoint_id.\n"
                "- If evidence is insufficient, still return that watchpoint_id with status Unclear.\n"
                "- Output must be valid JSON matching schema."
            )
            logger.warning(
                "Retrying batch %s/%s due to incomplete/invalid ID mapping. missing=%s duplicate=%s extra=%s",
                batch_index,
                len(batches),
                missing_ids,
                duplicate_ids,
                extra_ids,
            )
            response = _run_batch_request(repair_prompt)
            is_valid, batch_results, missing_ids, duplicate_ids, extra_ids = _validate_batch_response(response)
            if not is_valid:
                raise AnalysisValidationError(
                    f"AI output did not return valid analysis for every watchpoint_id in batch {batch_index}/{len(batches)}."
                )

        all_results_by_id.update(batch_results)

    normalized_results = [
        (
            item["key_variable"],
            item["watchpoint"],
            all_results_by_id[item["watchpoint_id"]][2],
            all_results_by_id[item["watchpoint_id"]][3],
        )
        for item in watchpoint_items
        if item["watchpoint_id"] in all_results_by_id
    ]
    if len(normalized_results) != len(watchpoint_items):
        raise AnalysisValidationError("AI output did not return valid analysis for every watchpoint.")

    now = utc_now_iso()
    conn.execute("DELETE FROM earnings_review_watchpoint_results WHERE earnings_review_id = ?", (review_id,))
    for key_variable, watchpoint, status, result_text in normalized_results:
        conn.execute(
            """
            INSERT INTO earnings_review_watchpoint_results (
              earnings_review_id, key_variable_text, watchpoint_text, status, result_text,
              analysed_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (review_id, key_variable, watchpoint, status, result_text, now, now, now),
        )
    conn.execute(
        "UPDATE earnings_reviews SET status = ?, updated_at = ? WHERE id = ? AND symbol = ?",
        (EARNINGS_REVIEW_STATUS_WATCHPOINTS_ANALYSED, now, review_id, symbol),
    )
    logger.info(
        "Analysed earnings watchpoints review_id=%s symbol=%s prompt_source=%s results=%s",
        review_id,
        symbol,
        template_source,
        len(normalized_results),
    )
    conn.commit()
    return get_earnings_review_record_detail(conn, symbol, review_id)


def generate_earnings_watchpoints(conn, symbol):
    """Backward-compatible helper: generate for the latest review record of a symbol."""
    latest = conn.execute(
        """
        SELECT id
        FROM earnings_reviews
        WHERE symbol = ?
        ORDER BY fiscal_year DESC, fiscal_quarter DESC, id DESC
        LIMIT 1
        """,
        (symbol,),
    ).fetchone()
    if not latest:
        raise ValueError(f"No earnings review record exists for symbol {symbol}")
    return generate_earnings_watchpoints_for_review(conn, symbol, int(latest["id"]))


def _parse_iso_datetime(value):
    text = str(value or "").strip()
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        return None


def _normalize_event_sources(value):
    if not isinstance(value, list):
        return []
    dedupe = set()
    normalized = []
    for raw in value:
        if not isinstance(raw, dict):
            continue
        title = str(raw.get("title", "")).strip()
        url = str(raw.get("url", "")).strip()
        source_name = str(raw.get("source_name", "")).strip()
        published_at = str(raw.get("published_at", "")).strip()
        if not (title or url or source_name):
            continue
        key = (title.lower(), url.lower(), source_name.lower(), published_at)
        if key in dedupe:
            continue
        dedupe.add(key)
        normalized.append(
            {
                "title": title,
                "url": url,
                "source_name": source_name,
                "published_at": published_at,
            }
        )
    return normalized


def _choose_alert_event_date(raw_event_date, event_sources):
    dated_sources = [src for src in event_sources if _parse_iso_datetime(src.get("published_at"))]
    if dated_sources:
        # Deterministic rule: use earliest reliable source date to anchor first known event publication.
        dated_sources.sort(key=lambda src: _parse_iso_datetime(src.get("published_at")))
        return dated_sources[0].get("published_at")
    return str(raw_event_date or "").strip() or None


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
    event_sources = _normalize_event_sources(item.get("event_sources"))
    event_date = _choose_alert_event_date(item.get("event_date"), event_sources)
    return {
        "alert_type": alert_type,
        "event_date": event_date,
        "event_summary": event_summary,
        "impact_summary": impact_summary,
        "affected_variables": affected_variables,
        "event_sources": event_sources,
        "suggested_action": str(item.get("suggested_action", "")).strip(),
    }


def get_latest_scenario_build_timestamp(conn, symbol):
    row = conn.execute(
        """
        SELECT MAX(v.created_at) AS latest_created_at
        FROM analysis_roots r
        JOIN analysis_versions v ON v.analysis_root_id = r.id
        WHERE r.symbol = ?
        """,
        (symbol,),
    ).fetchone()
    return row["latest_created_at"] if row else None


def get_last_recent_event_check_timestamp(conn, symbol):
    row = conn.execute(
        "SELECT MAX(checked_at) AS last_checked_at FROM recent_event_checks WHERE symbol = ?",
        (symbol,),
    ).fetchone()
    return row["last_checked_at"] if row else None


def get_recent_event_search_cutoff(conn, symbol):
    last_check = _parse_iso_datetime(get_last_recent_event_check_timestamp(conn, symbol))
    latest_scenario = _parse_iso_datetime(get_latest_scenario_build_timestamp(conn, symbol))
    candidates = [dt for dt in (last_check, latest_scenario) if dt]
    if not candidates:
        return None
    return max(candidates).isoformat()


def _is_alert_after_cutoff(alert, cutoff_iso):
    if not cutoff_iso:
        return True
    cutoff_dt = _parse_iso_datetime(cutoff_iso)
    event_dt = _parse_iso_datetime(alert.get("event_date"))
    if not cutoff_dt or not event_dt:
        return False
    return event_dt > cutoff_dt


def record_recent_event_check(conn, symbol, cutoff_used, alerts_created_count, events_found_count):
    conn.execute(
        """
        INSERT INTO recent_event_checks (symbol, checked_at, cutoff_used, alerts_created_count, events_found_count)
        VALUES (?, ?, ?, ?, ?)
        """,
        (symbol, utc_now_iso(), cutoff_used, int(alerts_created_count), int(events_found_count)),
    )


def insert_recent_event_alert(conn, context, alert, prompt_used, raw_response, search_cutoff_used=None):
    now = utc_now_iso()
    # Deterministic dedupe: keep exactly one alert per
    # (symbol, alert_type, event_summary, impact_summary) regardless of status.
    try:
        conn.execute(
            """
            INSERT INTO thesis_review_alerts (
              symbol, company_name, alert_type, status, event_date, event_summary,
              impact_summary, affected_variables_json, event_sources_json, search_cutoff_used,
              suggested_action, prompt_used, raw_response_json, created_at, updated_at
            ) VALUES (?, ?, ?, 'New', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                context["symbol"],
                context["company_name"],
                alert["alert_type"],
                alert.get("event_date"),
                alert["event_summary"],
                alert["impact_summary"],
                json.dumps(alert["affected_variables"], ensure_ascii=False),
                json.dumps(alert.get("event_sources", []), ensure_ascii=False),
                search_cutoff_used,
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


def _merge_alert_items_by_event(items):
    merged = {}
    for alert in items:
        key = (alert["alert_type"], alert["event_summary"], alert["impact_summary"])
        if key not in merged:
            merged[key] = dict(alert)
            continue
        existing = merged[key]
        existing_sources = _normalize_event_sources((existing.get("event_sources") or []) + (alert.get("event_sources") or []))
        existing["event_sources"] = existing_sources
        existing_date = _parse_iso_datetime(existing.get("event_date"))
        incoming_date = _parse_iso_datetime(alert.get("event_date"))
        if incoming_date and (not existing_date or incoming_date < existing_date):
            existing["event_date"] = alert.get("event_date")
    return list(merged.values())


def _normalize_recent_event_candidate(item):
    if not isinstance(item, dict):
        return None
    event_title = str(item.get("event_title", "")).strip()
    event_summary = str(item.get("event_summary", "")).strip()
    event_sources = _normalize_event_sources(item.get("event_sources"))
    event_date = _choose_alert_event_date(item.get("event_date"), event_sources)
    if not event_title and not event_summary:
        return None
    if not event_summary:
        event_summary = event_title
    if not event_title:
        event_title = event_summary
    return {
        "event_title": event_title,
        "event_summary": event_summary,
        "event_date": event_date,
        "event_sources": event_sources,
    }


def _is_candidate_after_cutoff(candidate, cutoff_iso):
    if not cutoff_iso:
        return True
    cutoff_dt = _parse_iso_datetime(cutoff_iso)
    event_dt = _parse_iso_datetime(candidate.get("event_date"))
    if not cutoff_dt or not event_dt:
        return False
    return event_dt > cutoff_dt


def _merge_candidate_events(items):
    merged = {}
    for candidate in items:
        key = ((candidate.get("event_title") or "").lower(), (candidate.get("event_summary") or "").lower())
        if key not in merged:
            merged[key] = dict(candidate)
            continue
        existing = merged[key]
        existing["event_sources"] = _normalize_event_sources((existing.get("event_sources") or []) + (candidate.get("event_sources") or []))
        existing_date = _parse_iso_datetime(existing.get("event_date"))
        incoming_date = _parse_iso_datetime(candidate.get("event_date"))
        if incoming_date and (not existing_date or incoming_date < existing_date):
            existing["event_date"] = candidate.get("event_date")
    return list(merged.values())


def _build_recent_event_candidate_schema():
    return {
        "name": "analysis_recent_event_candidates",
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "symbol": {"type": "string"},
                "event_candidates": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "event_title": {"type": "string"},
                            "event_summary": {"type": "string"},
                            "event_date": {"type": "string"},
                            "event_sources": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "properties": {
                                        "title": {"type": "string"},
                                        "url": {"type": "string"},
                                        "source_name": {"type": "string"},
                                        "published_at": {"type": "string"},
                                    },
                                    "required": ["title", "url", "source_name", "published_at"],
                                },
                            },
                        },
                        "required": ["event_title", "event_summary", "event_date", "event_sources"],
                    },
                },
            },
            "required": ["symbol", "event_candidates"],
        },
    }


def _build_recent_event_check_schema():
    return {
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
                            "event_date": {"type": "string"},
                            "event_summary": {"type": "string"},
                            "impact_summary": {"type": "string"},
                            "affected_variables": {"type": "array", "items": {"type": "string"}},
                            "suggested_action": {"type": "string"},
                            "event_sources": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "properties": {
                                        "title": {"type": "string"},
                                        "url": {"type": "string"},
                                        "source_name": {"type": "string"},
                                        "published_at": {"type": "string"},
                                    },
                                    "required": ["title", "url", "source_name", "published_at"],
                                },
                            },
                        },
                        "required": [
                            "alert_type",
                            "event_date",
                            "event_summary",
                            "impact_summary",
                            "affected_variables",
                            "suggested_action",
                            "event_sources",
                        ],
                    },
                },
            },
            "required": ["symbol", "alerts"],
        },
    }


def run_recent_event_check(conn, symbols):
    templates, _sources = get_prompt_templates_for_keys(
        conn,
        RECENT_EVENT_WORKFLOW_PROMPT_KEYS,
        purpose="recent_event_check",
    )
    candidate_template = templates[ANALYSIS_PROMPT_SETTING_KEY_RECENT_EVENT_CANDIDATE]
    check_template = templates[ANALYSIS_PROMPT_SETTING_KEY_RECENT_EVENT_CHECK]

    summary = {
        "symbols_checked": 0,
        "alerts_created": 0,
        "no_material_impact_count": 0,
        "errors_count": 0,
        "errors": [],
    }

    for symbol in symbols:
        summary["symbols_checked"] += 1
        cutoff_used = get_recent_event_search_cutoff(conn, symbol)
        try:
            context = get_latest_analysis_context(conn, symbol)

            # Step 2: discover post-cutoff candidate events.
            candidate_prompt = render_recent_event_prompt(
                candidate_template,
                build_prompt_context(
                    symbol=context["symbol"],
                    price=context["current_price"],
                    company_name=context["company_name"],
                    business_model=context["business_model"],
                    business_summary=context["business_summary"],
                    key_variables=context["key_variables"],
                    event_search_cutoff=cutoff_used or "none",
                ),
            )
            candidate_response = request_ai_step("recent_event_candidates", candidate_prompt, _build_recent_event_candidate_schema())
            raw_candidates = candidate_response.get("event_candidates") if isinstance(candidate_response, dict) else None
            raw_candidates = raw_candidates if isinstance(raw_candidates, list) else []
            normalized_candidates = [item for item in (_normalize_recent_event_candidate(raw) for raw in raw_candidates) if item]
            normalized_candidates = _merge_candidate_events(normalized_candidates)
            post_cutoff_candidates = [item for item in normalized_candidates if _is_candidate_after_cutoff(item, cutoff_used)]

            logger.info(
                "Recent-event candidates symbol=%s cutoff=%s raw=%d normalized=%d post_cutoff=%d",
                symbol,
                cutoff_used,
                len(raw_candidates),
                len(normalized_candidates),
                len(post_cutoff_candidates),
            )

            if not post_cutoff_candidates:
                summary["no_material_impact_count"] += 1
                record_recent_event_check(conn, symbol, cutoff_used, alerts_created_count=0, events_found_count=0)
                continue

            event_candidates_text = json.dumps(post_cutoff_candidates, separators=(",", ":"), ensure_ascii=False)

            # Step 4/5: evaluate candidate events for material thesis impact.
            check_prompt = render_recent_event_prompt(
                check_template,
                build_prompt_context(
                    symbol=context["symbol"],
                    price=context["current_price"],
                    company_name=context["company_name"],
                    business_model=context["business_model"],
                    business_summary=context["business_summary"],
                    key_variables=context["key_variables"],
                    event_candidates=event_candidates_text,
                ),
            )
            check_response = request_ai_step("recent_event_check", check_prompt, _build_recent_event_check_schema())
            alerts = check_response.get("alerts") if isinstance(check_response, dict) else None
            if not isinstance(alerts, list) or not alerts:
                summary["no_material_impact_count"] += 1
                record_recent_event_check(conn, symbol, cutoff_used, alerts_created_count=0, events_found_count=len(post_cutoff_candidates))
                continue

            normalized_alerts = [item for item in (_normalize_recent_event_alert(raw_alert) for raw_alert in alerts) if item]
            normalized_alerts = _merge_alert_items_by_event(normalized_alerts)
            # Defensive filter: ensure only post-cutoff alerts persist even if model returns stale candidates.
            filtered_alerts = [item for item in normalized_alerts if _is_alert_after_cutoff(item, cutoff_used)]

            created_for_symbol = 0
            raw_response = {
                "candidate_prompt": candidate_prompt,
                "candidate_response": candidate_response,
                "candidate_events_used": post_cutoff_candidates,
                "evaluation_prompt": check_prompt,
                "evaluation_response": check_response,
            }
            for normalized in filtered_alerts:
                created = insert_recent_event_alert(conn, context, normalized, check_prompt, raw_response, cutoff_used)
                if created:
                    summary["alerts_created"] += 1
                    created_for_symbol += 1

            if not filtered_alerts:
                summary["no_material_impact_count"] += 1

            record_recent_event_check(
                conn,
                symbol,
                cutoff_used,
                alerts_created_count=created_for_symbol,
                events_found_count=len(post_cutoff_candidates),
            )
        except Exception as exc:
            summary["errors_count"] += 1
            summary["errors"].append({"symbol": symbol, "error": str(exc)})
            logger.exception("Recent-event check failed for %s", symbol)
            record_recent_event_check(conn, symbol, cutoff_used, alerts_created_count=0, events_found_count=0)
    conn.commit()
    return summary


def _deserialize_json_list(value):
    try:
        parsed = json.loads(value or "[]")
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []


def _serialize_alert_row(row):
    return {
        "id": row["id"],
        "symbol": row["symbol"],
        "company_name": row["company_name"],
        "alert_type": row["alert_type"],
        "status": row["status"],
        "event_date": row["event_date"],
        "event_summary": row["event_summary"],
        "impact_summary": row["impact_summary"],
        "affected_variables": _deserialize_json_list(row["affected_variables_json"]),
        "event_sources": _deserialize_json_list(row["event_sources_json"]),
        "search_cutoff_used": row["search_cutoff_used"],
        "suggested_action": row["suggested_action"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def get_alerts(conn):
    rows = conn.execute(
        """
        SELECT id, symbol, company_name, alert_type, status, event_date, event_summary,
               impact_summary, affected_variables_json, event_sources_json, search_cutoff_used,
               suggested_action, created_at, updated_at
        FROM thesis_review_alerts
        ORDER BY COALESCE(event_date, created_at) DESC, id DESC
        """
    ).fetchall()
    return [_serialize_alert_row(row) for row in rows]


def get_alert_by_id(conn, alert_id):
    row = conn.execute(
        """
        SELECT id, symbol, company_name, alert_type, status, event_date, event_summary,
               impact_summary, affected_variables_json, event_sources_json, search_cutoff_used,
               suggested_action, created_at, updated_at
        FROM thesis_review_alerts
        WHERE id = ?
        """,
        (alert_id,),
    ).fetchone()
    return _serialize_alert_row(row) if row else None



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

    def _read_multipart_form(self):
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type.lower():
            return None
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return None
        if length <= 0:
            return None
        body = self.rfile.read(length)
        from email.parser import BytesParser
        from email.policy import default

        message = BytesParser(policy=default).parsebytes(
            f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8") + body
        )
        if not message.is_multipart():
            return None
        fields = {}
        files = {}
        for part in message.iter_parts():
            disposition = part.get("Content-Disposition", "")
            if "form-data" not in disposition:
                continue
            name = part.get_param("name", header="content-disposition")
            if not name:
                continue
            filename = part.get_filename()
            payload = part.get_payload(decode=True) or b""
            if filename is None:
                charset = part.get_content_charset() or "utf-8"
                fields[name] = payload.decode(charset, errors="replace")
                continue
            files.setdefault(name, []).append(
                {
                    "filename": filename,
                    "content": payload,
                    "content_type": part.get_content_type(),
                }
            )
        return {"fields": fields, "files": files}

    def _send_file(self, file_path, download_name):
        with open(file_path, "rb") as handle:
            payload = handle.read()
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Disposition", f'attachment; filename="{download_name}"')
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path

        if path == "/api/positions":
            query = parse_qs(parsed_url.query or "")
            refresh = str(query.get("refresh", ["0"])[0]).strip().lower() in {"1", "true", "yes", "on"}
            return self.handle_positions_api(refresh=refresh)
        if path == "/api/analysis":
            return self.handle_analysis_get()
        if path == "/api/earnings-review":
            return self.handle_earnings_review_get()
        if path == "/api/earnings-review/calendar":
            return self.handle_earnings_review_calendar_get()
        if path.startswith("/api/earnings-review/"):
            suffix = path[len("/api/earnings-review/") :]
            parts = [item for item in suffix.split("/") if item]
            if len(parts) == 1:
                symbol = normalize_symbol(parts[0])
                if not symbol:
                    return self._send_json({"error": "Invalid symbol"}, status=400)
                return self.handle_earnings_review_symbol_get(symbol)
            if len(parts) == 2:
                symbol = normalize_symbol(parts[0])
                if not symbol or not parts[1].isdigit():
                    return self._send_json({"error": "Invalid earnings review path"}, status=400)
                return self.handle_earnings_review_record_get(symbol, int(parts[1]))
            if len(parts) == 3 and parts[2] == "documents":
                symbol = normalize_symbol(parts[0])
                if not symbol or not parts[1].isdigit():
                    return self._send_json({"error": "Invalid earnings review documents path"}, status=400)
                return self.handle_earnings_review_documents_get(symbol, int(parts[1]))
            if len(parts) == 5 and parts[2] == "documents" and parts[4] == "download":
                symbol = normalize_symbol(parts[0])
                if not symbol or not parts[1].isdigit() or not parts[3].isdigit():
                    return self._send_json({"error": "Invalid earnings review document download path"}, status=400)
                return self.handle_earnings_review_document_download(symbol, int(parts[1]), int(parts[3]))
        if path.startswith("/api/analysis/versions/"):
            parts = [item for item in path[len("/api/analysis/versions/") :].split("/") if item]
            if len(parts) == 2 and parts[0].isdigit() and parts[1] == "external-scenarios":
                return self.handle_external_scenarios_get(int(parts[0]))
            return self._send_json({"error": "Invalid analysis version external scenario path"}, status=400)
        if path.startswith("/api/action-plan/"):
            symbol = normalize_symbol(path[len("/api/action-plan/") :])
            if not symbol:
                return self._send_json({"error": "Invalid action plan symbol"}, status=400)
            return self.handle_action_plan_detail_get(symbol)
        if path == "/api/action-plan":
            return self.handle_action_plan_get()
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
        if path == "/api/backup/export":
            query = parse_qs(parsed_url.query or "")
            include_env = str(query.get("include_env", ["1"])[0]).strip().lower() in {"1", "true", "yes", "on"}
            return self.handle_backup_export(include_env=include_env)
        if path.startswith("/api/alerts/"):
            alert_id = path[len("/api/alerts/"):]
            if alert_id.isdigit():
                return self.handle_alert_detail_get(alert_id)

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
        if path == "/api/analysis/momentum/update":
            return self.handle_analysis_momentum_update()
        if path.startswith("/api/analysis/versions/"):
            parts = [item for item in path[len("/api/analysis/versions/") :].split("/") if item]
            if len(parts) == 2 and parts[0].isdigit() and parts[1] == "external-scenarios":
                return self.handle_external_scenario_create(int(parts[0]))
            if len(parts) == 3 and parts[0].isdigit() and parts[1] == "final-scenario" and parts[2] == "recalculate":
                return self.handle_final_scenario_recalculate(int(parts[0]))
            return self._send_json({"error": "Invalid analysis version external scenario path"}, status=400)
        if path.startswith("/api/analysis/") and path.endswith("/key-variables/import"):
            symbol = normalize_symbol(path[len("/api/analysis/") : -len("/key-variables/import")])
            if not symbol:
                return self._send_json({"error": "Invalid symbol"}, status=400)
            return self.handle_analysis_key_variables_import(symbol)
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
        if path.startswith("/api/analysis/") and path.endswith("/frontier-optionality"):
            symbol = normalize_symbol(path[len("/api/analysis/") : -len("/frontier-optionality")])
            if not symbol:
                return self._send_json({"error": "Invalid symbol"}, status=400)
            return self.handle_analysis_frontier_optionality_save(symbol)
        if path.startswith("/api/analysis/") and path.endswith("/rerun-scenarios"):
            symbol = normalize_symbol(path[len("/api/analysis/") : -len("/rerun-scenarios")])
            if not symbol:
                return self._send_json({"error": "Invalid symbol"}, status=400)
            return self.handle_analysis_rerun_scenarios(symbol)
        if path == "/api/analysis/import-from-positions":
            return self.handle_analysis_import_positions()
        if path == "/api/earnings-review/symbols":
            return self.handle_earnings_review_symbol_add()
        if path == "/api/earnings-review/calendar":
            return self.handle_earnings_review_calendar_create()
        if path.startswith("/api/earnings-review/calendar/"):
            entry_id = path[len("/api/earnings-review/calendar/"):].strip()
            if not entry_id.isdigit():
                return self._send_json({"error": "Invalid earnings calendar entry id"}, status=400)
            return self.handle_earnings_review_calendar_save(int(entry_id))
        if path.startswith("/api/earnings-review/"):
            suffix = path[len("/api/earnings-review/") :]
            parts = [item for item in suffix.split("/") if item]
            if len(parts) == 1:
                symbol = normalize_symbol(parts[0])
                if not symbol:
                    return self._send_json({"error": "Invalid symbol"}, status=400)
                return self.handle_earnings_review_create(symbol)
            if len(parts) == 3 and parts[2] == "generate-watchpoints":
                symbol = normalize_symbol(parts[0])
                if not symbol or not parts[1].isdigit():
                    return self._send_json({"error": "Invalid earnings review generate path"}, status=400)
                return self.handle_earnings_review_generate_watchpoints(symbol, int(parts[1]))
            if len(parts) == 3 and parts[2] == "analyse-watchpoints":
                symbol = normalize_symbol(parts[0])
                if not symbol or not parts[1].isdigit():
                    return self._send_json({"error": "Invalid earnings review analyse path"}, status=400)
                return self.handle_earnings_review_analyse_watchpoints(symbol, int(parts[1]))
            if len(parts) == 3 and parts[2] == "documents":
                symbol = normalize_symbol(parts[0])
                if not symbol or not parts[1].isdigit():
                    return self._send_json({"error": "Invalid earnings review documents upload path"}, status=400)
                return self.handle_earnings_review_document_upload(symbol, int(parts[1]))
        if path == "/api/configuration/prompts/preview":
            return self.handle_configuration_prompts_preview()
        if path == "/api/configuration/prompts/reset":
            return self.handle_configuration_prompts_reset()
        if path == "/api/alerts/check-recent-events":
            return self.handle_alerts_check_recent_events()
        if path == "/api/backup/import":
            return self.handle_backup_import()

        self.send_error(404, "Not Found")

    def do_PUT(self):
        path = urlparse(self.path).path
        if path == "/api/configuration/prompts":
            return self.handle_configuration_prompts_put()
        if path == "/api/configuration/general":
            return self.handle_configuration_general_put()
        if path.startswith("/api/analysis/versions/"):
            parts = [item for item in path[len("/api/analysis/versions/") :].split("/") if item]
            if len(parts) == 3 and parts[0].isdigit() and parts[1] == "external-scenarios" and parts[2].isdigit():
                return self.handle_external_scenario_update(int(parts[0]), int(parts[2]))
            return self._send_json({"error": "Invalid analysis version external scenario path"}, status=400)
        if path.startswith("/api/alerts/") and path.endswith("/status"):
            alert_id = path[len("/api/alerts/") : -len("/status")]
            return self.handle_alerts_status_put(alert_id)
        if path.startswith("/api/earnings-review/calendar/"):
            entry_id = path[len("/api/earnings-review/calendar/"):].strip()
            if not entry_id.isdigit():
                return self._send_json({"error": "Invalid earnings calendar entry id"}, status=400)
            return self.handle_earnings_review_calendar_save(int(entry_id))

        self.send_error(404, "Not Found")

    def do_DELETE(self):
        path = urlparse(self.path).path
        if path.startswith("/api/analysis/versions/"):
            parts = [item for item in path[len("/api/analysis/versions/") :].split("/") if item]
            if len(parts) == 3 and parts[0].isdigit() and parts[1] == "external-scenarios" and parts[2].isdigit():
                return self.handle_external_scenario_delete(int(parts[0]), int(parts[2]))
            return self._send_json({"error": "Invalid analysis version external scenario path"}, status=400)
        if path.startswith("/api/earnings-review/calendar/"):
            entry_id = path[len("/api/earnings-review/calendar/"):].strip()
            if not entry_id.isdigit():
                return self._send_json({"error": "Invalid earnings calendar entry id"}, status=400)
            return self.handle_earnings_review_calendar_remove(int(entry_id))
        if path.startswith("/api/earnings-review/"):
            suffix = path[len("/api/earnings-review/") :]
            parts = [item for item in suffix.split("/") if item]
            if len(parts) == 2:
                symbol = normalize_symbol(parts[0])
                if not symbol or not parts[1].isdigit():
                    return self._send_json({"error": "Invalid earnings review delete path"}, status=400)
                return self.handle_earnings_review_delete(symbol, int(parts[1]))
            if len(parts) == 4 and parts[2] == "documents":
                symbol = normalize_symbol(parts[0])
                if not symbol or not parts[1].isdigit() or not parts[3].isdigit():
                    return self._send_json({"error": "Invalid earnings review document delete path"}, status=400)
                return self.handle_earnings_review_document_delete(symbol, int(parts[1]), int(parts[3]))
            return self._send_json({"error": "Invalid earnings review delete path"}, status=400)

        analysis_prefix = "/api/analysis/"
        if path.startswith(analysis_prefix):
            symbol = normalize_symbol(path[len(analysis_prefix) :])
            if not symbol:
                return self._send_json({"error": "Invalid symbol"}, status=400)
            return self.handle_analysis_delete(symbol)

        self.send_error(404, "Not Found")

    def handle_earnings_review_delete(self, symbol, review_id):
        conn = get_db_connection()
        try:
            row = conn.execute(
                "SELECT id FROM earnings_reviews WHERE id = ? AND symbol = ?",
                (review_id, symbol),
            ).fetchone()
            if not row:
                return self._send_json({"error": "Earnings review record not found"}, status=404)
            conn.execute("DELETE FROM earnings_reviews WHERE id = ? AND symbol = ?", (review_id, symbol))
            conn.commit()
            review_dir = UPLOADS_DIR / "earnings_reviews" / str(review_id)
            if review_dir.exists():
                shutil.rmtree(review_dir, ignore_errors=True)
            self._send_json({"ok": True, "deleted_review_id": review_id, "symbol": symbol})
        except Exception as exc:
            self._send_json(
                {"error": "Unable to delete earnings review record.", "details": str(exc)},
                status=500,
            )
        finally:
            conn.close()

    def handle_earnings_review_documents_get(self, symbol, review_id):
        conn = get_db_connection()
        try:
            self._send_json({"items": list_earnings_review_documents(conn, symbol, review_id)})
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=404)
        except Exception as exc:
            self._send_json(
                {"error": "Unable to load earnings review documents.", "details": str(exc)},
                status=500,
            )
        finally:
            conn.close()

    def handle_earnings_review_document_upload(self, symbol, review_id):
        conn = get_db_connection()
        try:
            form = self._read_multipart_form()
            if form is None:
                raise ValueError("Expected multipart/form-data.")
            document_type = (form.get("fields", {}).get("document_type") or "").strip()
            file_item = (form.get("files", {}).get("file") or [None])[0]
            if file_item is None:
                raise ValueError("A file is required.")
            item = save_earnings_review_document(
                conn=conn,
                symbol=symbol,
                review_id=review_id,
                document_type=document_type,
                original_file_name=file_item.get("filename") or "document",
                payload=file_item.get("content"),
                mime_type=file_item.get("content_type"),
            )
            self._send_json({"item": item}, status=201)
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=400)
        except Exception as exc:
            logger.exception("Unable to upload earnings review document")
            self._send_json(
                {"error": "Unable to upload earnings document.", "details": str(exc)},
                status=500,
            )
        finally:
            conn.close()

    def handle_earnings_review_document_download(self, symbol, review_id, document_id):
        conn = get_db_connection()
        try:
            item, file_path = get_earnings_review_document_download(conn, symbol, review_id, document_id)
            self.send_response(200)
            self.send_header("Content-Type", item.get("mime_type") or "application/octet-stream")
            self.send_header("Content-Disposition", f'attachment; filename="{item["original_file_name"]}"')
            self.send_header("Content-Length", str(file_path.stat().st_size))
            self.end_headers()
            with open(file_path, "rb") as handle:
                self.wfile.write(handle.read())
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=404)
        except Exception as exc:
            self._send_json(
                {"error": "Unable to download earnings document.", "details": str(exc)},
                status=500,
            )
        finally:
            conn.close()

    def handle_earnings_review_document_delete(self, symbol, review_id, document_id):
        conn = get_db_connection()
        try:
            delete_earnings_review_document(conn, symbol, review_id, document_id)
            self._send_json({"ok": True})
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=404)
        except Exception as exc:
            self._send_json(
                {"error": "Unable to delete earnings document.", "details": str(exc)},
                status=500,
            )
        finally:
            conn.close()

    def handle_positions_api(self, refresh=False):
        if not refresh:
            conn = get_db_connection()
            try:
                cached_positions = load_positions_cache(conn)
                payload = build_positions_payload(
                    conn,
                    cached_positions,
                    data_source="cached" if cached_positions else "empty",
                    warning=None if cached_positions else "No saved positions available. Click Refresh to load positions from TWS.",
                )
                logger.info(
                    "Positions API returning stored rows=%s sample_symbols=%s",
                    len(payload["positions"]),
                    [item.get("symbol") for item in payload["positions"][:5]],
                )
                self._send_json(payload)
            finally:
                conn.close()
            return

        try:
            ensure_event_loop()
            ib = get_ib_connection()
            positions = ib.positions()
            account_summary = None
            account_summary_warning = None
            try:
                account_summary = fetch_ib_portfolio_summary(ib)
            except Exception as exc:
                logger.warning("Unable to fetch IBKR account summary during positions refresh: %s", exc)
                account_summary_warning = "IBKR account summary/cash could not be updated."
            logger.info("Positions API using live IBKR path positions_count=%s", len(positions))
            contracts = [p.contract for p in positions if p.contract]
            tickers_by_conid = {}
            tws_data_enabled = is_tws_data_enabled()

            if contracts and tws_data_enabled:
                qualified = ib.qualifyContracts(*contracts)
                if qualified:
                    tickers, _diagnostics = request_ib_tickers_batched(
                        ib,
                        qualified,
                        purpose="positions_api",
                    )
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
                effective_data = data
                warning_message = None
                if tws_data_enabled:
                    save_positions_cache(conn, effective_data)
                    if account_summary:
                        save_portfolio_summary_cache(conn, account_summary)
                else:
                    cached_rows = load_positions_cache(conn)
                    effective_data = overlay_cached_market_fields(data, cached_rows)
                    if cached_rows:
                        save_positions_cache(conn, effective_data)
                    warning_message = "Data from TWS is disabled. Showing latest cached market values when available."
                if account_summary_warning:
                    warning_message = " ".join([part for part in [warning_message, account_summary_warning] if part])
                payload = build_positions_payload(
                    conn,
                    effective_data,
                    data_source="live",
                    warning=warning_message,
                )
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

    def handle_backup_export(self, include_env=True):
        temp_db_snapshot_path = None
        try:
            BACKUP_DIR.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".db", dir=str(BACKUP_DIR)) as temp_handle:
                temp_db_snapshot_path = temp_handle.name
            _create_db_backup_snapshot(str(DB_PATH), temp_db_snapshot_path)

            include_env_in_package = bool(include_env and ENV_PATH.exists())
            manifest = _build_backup_manifest(include_env_in_package)

            package_bytes = BytesIO()
            with zipfile.ZipFile(package_bytes, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.write(temp_db_snapshot_path, BACKUP_PACKAGE_DB_FILENAME)
                if include_env_in_package:
                    archive.write(ENV_PATH, BACKUP_PACKAGE_ENV_FILENAME)
                archive.writestr(BACKUP_PACKAGE_MANIFEST_FILENAME, json.dumps(manifest, indent=2))

            payload = package_bytes.getvalue()
            filename = f"{BACKUP_EXPORT_FILENAME_PREFIX}-{datetime.now().strftime('%Y-%m-%d-%H%M')}.zip"
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except Exception as exc:
            logger.exception("Backup export failed")
            self._send_json({"error": f"Unable to export backup: {exc}"}, status=500)
        finally:
            if temp_db_snapshot_path and os.path.exists(temp_db_snapshot_path):
                os.remove(temp_db_snapshot_path)

    def handle_backup_import(self):
        temp_upload_zip_path = None
        temp_import_db_path = None
        temp_import_env_path = None
        safety_backup_db_path = None
        safety_backup_env_path = None
        restored_env = False
        try:
            try:
                content_length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                return self._send_json({"error": "Invalid upload content length"}, status=400)

            if content_length <= 0:
                return self._send_json({"error": "No backup file uploaded"}, status=400)
            if content_length > BACKUP_IMPORT_MAX_BYTES:
                return self._send_json({"error": "Backup file too large"}, status=413)

            body = self.rfile.read(content_length)
            if len(body) != content_length:
                return self._send_json({"error": "Backup upload was incomplete"}, status=400)

            content_type = str(self.headers.get("Content-Type", "")).lower()
            if "application/zip" not in content_type and "application/octet-stream" not in content_type:
                return self._send_json({"error": "Backup upload must be a .zip package"}, status=400)

            parsed_url = urlparse(self.path)
            query = parse_qs(parsed_url.query or "")
            restore_env_requested = str(query.get("restore_env", ["0"])[0]).strip().lower() in {"1", "true", "yes", "on"}

            BACKUP_DIR.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".zip", dir=str(BACKUP_DIR)) as temp_handle:
                temp_handle.write(body)
                temp_upload_zip_path = temp_handle.name

            with zipfile.ZipFile(temp_upload_zip_path, "r") as archive:
                names = set(archive.namelist())
                if BACKUP_PACKAGE_DB_FILENAME not in names:
                    return self._send_json({"error": "Backup package is missing bakingmoney.db"}, status=400)

                with tempfile.NamedTemporaryFile(delete=False, suffix=".db", dir=str(BACKUP_DIR)) as db_handle:
                    db_handle.write(archive.read(BACKUP_PACKAGE_DB_FILENAME))
                    temp_import_db_path = db_handle.name

                if BACKUP_PACKAGE_MANIFEST_FILENAME in names:
                    try:
                        json.loads(archive.read(BACKUP_PACKAGE_MANIFEST_FILENAME).decode("utf-8"))
                    except Exception as exc:
                        return self._send_json({"error": f"Backup package manifest is invalid: {exc}"}, status=400)

                if restore_env_requested and BACKUP_PACKAGE_ENV_FILENAME in names:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".env", dir=str(BACKUP_DIR)) as env_handle:
                        env_handle.write(archive.read(BACKUP_PACKAGE_ENV_FILENAME))
                        temp_import_env_path = env_handle.name

            _validate_backup_db_file(temp_import_db_path)

            timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
            safety_backup_db_path = str(BACKUP_DIR / f"pre-restore-db-{timestamp}.db")
            _create_db_backup_snapshot(str(DB_PATH), safety_backup_db_path)
            if ENV_PATH.exists():
                safety_backup_env_path = str(BACKUP_DIR / f"pre-restore-env-{timestamp}.env")
                shutil.copy2(ENV_PATH, safety_backup_env_path)

            os.replace(temp_import_db_path, DB_PATH)
            temp_import_db_path = None
            if restore_env_requested and temp_import_env_path:
                os.replace(temp_import_env_path, ENV_PATH)
                temp_import_env_path = None
                restored_env = True

            conn = None
            try:
                conn = get_db_connection()
                conn.execute("SELECT 1").fetchone()
                conn.close()
                conn = None
                init_db()
            except Exception as exc:
                if safety_backup_db_path and os.path.exists(safety_backup_db_path):
                    shutil.copy2(safety_backup_db_path, DB_PATH)
                if safety_backup_env_path and os.path.exists(safety_backup_env_path):
                    shutil.copy2(safety_backup_env_path, ENV_PATH)
                raise RuntimeError(f"Restore verification failed and original DB was recovered: {exc}") from exc
            finally:
                try:
                    conn.close()
                except Exception:
                    pass

            return self._send_json(
                {
                    "success": True,
                    "message": "Backup restored successfully",
                    "restored_env": restored_env,
                }
            )
        except ValueError as exc:
            return self._send_json({"error": str(exc)}, status=400)
        except zipfile.BadZipFile:
            return self._send_json({"error": "Uploaded file is not a valid backup .zip package"}, status=400)
        except Exception as exc:
            logger.exception("Backup import failed")
            return self._send_json({"error": f"Unable to restore backup: {exc}"}, status=500)
        finally:
            if temp_upload_zip_path and os.path.exists(temp_upload_zip_path):
                os.remove(temp_upload_zip_path)
            if temp_import_db_path and os.path.exists(temp_import_db_path):
                os.remove(temp_import_db_path)
            if temp_import_env_path and os.path.exists(temp_import_env_path):
                os.remove(temp_import_env_path)

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

    def handle_earnings_review_get(self):
        conn = get_db_connection()
        try:
            items = list_earnings_review_symbols(conn)
            self._send_json({"items": items})
        except Exception as exc:
            self._send_json(
                {"error": "Unable to load earnings review symbols.", "details": str(exc)},
                status=500,
            )
        finally:
            conn.close()

    def handle_earnings_review_calendar_get(self):
        conn = get_db_connection()
        try:
            items = list_earnings_release_calendar(conn)
            self._send_json({"items": items})
        except Exception as exc:
            self._send_json(
                {"error": "Unable to load earnings calendar.", "details": str(exc)},
                status=500,
            )
        finally:
            conn.close()

    def handle_earnings_review_calendar_create(self):
        payload = self._read_json_body() or {}
        conn = get_db_connection()
        try:
            item = create_earnings_calendar_entry(
                conn=conn,
                symbol=payload.get("symbol"),
                fiscal_year=payload.get("fiscal_year"),
                fiscal_quarter=payload.get("fiscal_quarter"),
                release_date=payload.get("release_date"),
                release_timing=payload.get("release_timing"),
            )
            self._send_json({"ok": True, "item": item}, status=201)
        except ValueError as exc:
            status = 409 if "already exists" in str(exc).lower() else 400
            self._send_json({"error": str(exc)}, status=status)
        except Exception as exc:
            logger.exception("Unable to create earnings calendar row")
            self._send_json(
                {"error": "Unable to create earnings calendar row.", "details": str(exc)},
                status=500,
            )
        finally:
            conn.close()

    def handle_earnings_review_calendar_save(self, entry_id):
        payload = self._read_json_body() or {}
        conn = get_db_connection()
        try:
            item = update_earnings_calendar_entry(
                conn=conn,
                entry_id=entry_id,
                fiscal_year=payload.get("fiscal_year"),
                fiscal_quarter=payload.get("fiscal_quarter"),
                release_date=payload.get("release_date"),
                release_timing=payload.get("release_timing"),
            )
            self._send_json({"ok": True, "item": item})
        except ValueError as exc:
            status = 409 if "already exists" in str(exc).lower() else 400
            self._send_json({"error": str(exc)}, status=status)
        except Exception as exc:
            logger.exception("Unable to save earnings calendar row %s", entry_id)
            self._send_json(
                {"error": "Unable to save earnings calendar row.", "details": str(exc)},
                status=500,
            )
        finally:
            conn.close()

    def handle_earnings_review_calendar_remove(self, entry_id):
        conn = get_db_connection()
        try:
            result = delete_earnings_calendar_entry(conn, entry_id)
            self._send_json({"ok": True, "item": result})
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=400)
        except Exception as exc:
            logger.exception("Unable to remove earnings calendar row %s", entry_id)
            self._send_json(
                {"error": "Unable to remove earnings calendar row.", "details": str(exc)},
                status=500,
            )
        finally:
            conn.close()

    def handle_earnings_review_symbol_add(self):
        payload = self._read_json_body() or {}
        conn = get_db_connection()
        try:
            symbol = add_earnings_review_symbol(conn, payload.get("symbol"))
            self._send_json({"symbol": symbol}, status=201)
        except ValueError as exc:
            status = 409 if "already exists" in str(exc).lower() else 400
            self._send_json({"error": str(exc)}, status=status)
        except Exception as exc:
            logger.exception("Unable to add earnings review symbol")
            self._send_json(
                {"error": "Unable to add earnings review symbol.", "details": str(exc)},
                status=500,
            )
        finally:
            conn.close()

    def handle_earnings_review_symbol_get(self, symbol):
        conn = get_db_connection()
        try:
            self._send_json({"item": get_earnings_review_symbol_history(conn, symbol)})
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=404)
        except Exception as exc:
            self._send_json(
                {"error": "Unable to load earnings review symbol history.", "details": str(exc)},
                status=500,
            )
        finally:
            conn.close()

    def handle_earnings_review_create(self, symbol):
        payload = self._read_json_body() or {}
        conn = get_db_connection()
        try:
            detail = create_earnings_review_record(
                conn=conn,
                symbol=symbol,
                fiscal_year=payload.get("fiscal_year"),
                fiscal_quarter=payload.get("fiscal_quarter"),
                release_date=payload.get("release_date"),
            )
            self._send_json({"ok": True, "item": detail}, status=201)
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=400)
        except Exception as exc:
            logger.exception("Unable to create earnings review for symbol %s", symbol)
            self._send_json(
                {"error": "Unable to create earnings review.", "details": str(exc)},
                status=500,
            )
        finally:
            conn.close()

    def handle_earnings_review_record_get(self, symbol, review_id):
        conn = get_db_connection()
        try:
            self._send_json({"item": get_earnings_review_record_detail(conn, symbol, review_id)})
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=404)
        except Exception as exc:
            self._send_json(
                {"error": "Unable to load earnings review record detail.", "details": str(exc)},
                status=500,
            )
        finally:
            conn.close()

    def handle_earnings_review_generate_watchpoints(self, symbol, review_id):
        conn = get_db_connection()
        try:
            detail = generate_earnings_watchpoints_for_review(conn, symbol, review_id)
            self._send_json({"ok": True, "item": detail}, status=201)
        except AnalysisValidationError as exc:
            self._send_json({"error": "AI response validation failed.", "details": str(exc)}, status=422)
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=404)
        except Exception as exc:
            logger.exception("Unable to generate earnings watchpoints for symbol %s", symbol)
            self._send_json(
                {"error": "Unable to generate earnings watchpoints.", "details": str(exc)},
                status=500,
            )
        finally:
            conn.close()

    def handle_earnings_review_analyse_watchpoints(self, symbol, review_id):
        conn = get_db_connection()
        try:
            detail = analyze_earnings_watchpoints_for_review(conn, symbol, review_id)
            self._send_json({"ok": True, "item": detail}, status=201)
        except AnalysisValidationError as exc:
            self._send_json({"error": "AI response validation failed.", "details": str(exc)}, status=422)
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=400)
        except RuntimeError as exc:
            self._send_json(
                {"error": "Earnings watchpoint analysis timed out. Please try again.", "details": str(exc)},
                status=503,
            )
        except Exception as exc:
            logger.exception("Unable to analyse earnings watchpoints for symbol %s", symbol)
            self._send_json(
                {"error": "Unable to analyse earnings watchpoints.", "details": str(exc)},
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


    def handle_analysis_momentum_update(self):
        payload = self._read_json_body() or {}
        requested_symbols = payload.get("symbols")
        benchmark = normalize_symbol(payload.get("benchmark") or MOMENTUM_DEFAULT_BENCHMARK) or MOMENTUM_DEFAULT_BENCHMARK
        duration = str(payload.get("duration") or MOMENTUM_DEFAULT_DURATION).strip() or MOMENTUM_DEFAULT_DURATION
        conn = get_db_connection()
        try:
            if isinstance(requested_symbols, list) and requested_symbols:
                symbols = []
                seen = set()
                for item in requested_symbols:
                    symbol = normalize_symbol(item)
                    if symbol and symbol not in seen:
                        seen.add(symbol)
                        symbols.append(symbol)
            else:
                symbols = [normalize_symbol(row["symbol"]) for row in conn.execute("SELECT symbol FROM analysis_roots ORDER BY symbol ASC").fetchall()]
            if not symbols:
                self._send_json({"benchmark": benchmark, "duration": duration, "updated": [], "errors": []})
                return

            updated = []
            errors = []
            try:
                benchmark_rows = fetch_historical_daily_bars(benchmark, duration=duration)
            except Exception as exc:
                logger.exception("Unable to fetch momentum benchmark bars for %s", benchmark)
                self._send_json({"error": f"Unable to fetch benchmark {benchmark} historical bars.", "details": str(exc)}, status=502)
                return

            for symbol in symbols:
                try:
                    symbol_rows = fetch_historical_daily_bars(symbol, duration=duration)
                    snapshot = calculate_momentum_snapshot(symbol_rows, benchmark_rows)
                    updated_at = save_momentum_snapshot(conn, symbol, benchmark, duration, snapshot)
                    conn.commit()
                    updated.append(summarize_momentum_snapshot(symbol, snapshot, updated_at))
                except Exception as exc:
                    logger.exception("Unable to update momentum for %s", symbol)
                    errors.append({"symbol": symbol, "error": str(exc)})
            status = 207 if errors else 200
            self._send_json({"benchmark": benchmark, "duration": duration, "updated": updated, "errors": errors}, status=status)
        finally:
            conn.close()

    def handle_external_scenarios_get(self, version_id):
        conn = get_db_connection()
        try:
            self._send_json(_external_overlay_summary(conn, version_id))
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=404)
        except Exception as exc:
            logger.exception("Unable to load external scenarios for version %s", version_id)
            self._send_json({"error": "Unable to load external scenarios.", "details": str(exc)}, status=500)
        finally:
            conn.close()

    def handle_external_scenario_create(self, version_id):
        payload = self._read_json_body() or {}
        conn = get_db_connection()
        try:
            item = create_external_scenario(conn, version_id, payload)
            self._send_json({"ok": True, "item": item, **_external_overlay_summary(conn, version_id)}, status=201)
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=400)
        except Exception as exc:
            logger.exception("Unable to create external scenario for version %s", version_id)
            self._send_json({"error": "Unable to create external scenario.", "details": str(exc)}, status=500)
        finally:
            conn.close()

    def handle_external_scenario_update(self, version_id, external_id):
        payload = self._read_json_body() or {}
        conn = get_db_connection()
        try:
            item = update_external_scenario(conn, version_id, external_id, payload)
            self._send_json({"ok": True, "item": item, **_external_overlay_summary(conn, version_id)})
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=400)
        except Exception as exc:
            logger.exception("Unable to update external scenario %s for version %s", external_id, version_id)
            self._send_json({"error": "Unable to update external scenario.", "details": str(exc)}, status=500)
        finally:
            conn.close()

    def handle_external_scenario_delete(self, version_id, external_id):
        conn = get_db_connection()
        try:
            item = delete_external_scenario(conn, version_id, external_id)
            self._send_json({"ok": True, "item": item, **_external_overlay_summary(conn, version_id)})
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=400)
        except Exception as exc:
            logger.exception("Unable to delete external scenario %s for version %s", external_id, version_id)
            self._send_json({"error": "Unable to delete external scenario.", "details": str(exc)}, status=500)
        finally:
            conn.close()

    def handle_final_scenario_recalculate(self, version_id):
        conn = get_db_connection()
        try:
            overlay = recalculate_final_scenario_overlay(conn, version_id)
            self._send_json({"ok": True, "final_scenario_overlay": overlay, **_external_overlay_summary(conn, version_id)})
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=400)
        except Exception as exc:
            logger.exception("Unable to recalculate final scenario for version %s", version_id)
            self._send_json({"error": "Unable to recalculate final scenario.", "details": str(exc)}, status=500)
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

    def handle_analysis_key_variables_import(self, symbol):
        payload = self._read_json_body() or {}
        version_id = payload.get("version_id")
        if version_id is None:
            return self._send_json({"error": "version_id is required"}, status=400)

        conn = get_db_connection()
        try:
            detail = import_key_variable_edits(conn, symbol, int(version_id), payload)
            self._send_json({"ok": True, "analysis": detail})
        except AnalysisValidationError as exc:
            self._send_json({"error": str(exc)}, status=400)
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=404)
        except Exception as exc:
            logger.exception("Unable to import key variable edits for symbol %s", symbol)
            self._send_json({"error": "Unable to import key variables.", "details": str(exc)}, status=500)
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

    def handle_analysis_frontier_optionality_save(self, symbol):
        payload = self._read_json_body() or {}
        conn = get_db_connection()
        try:
            detail = save_frontier_optionality(
                conn,
                symbol,
                payload.get("frontier_optionality_score"),
                payload.get("frontier_optionality_notes") if "frontier_optionality_notes" in payload else None,
            )
            self._send_json({"ok": True, "analysis": detail})
        except ValueError as exc:
            message = str(exc)
            status = 404 if "not found" in message.lower() else 400
            self._send_json({"error": message}, status=status)
        except Exception as exc:
            logger.exception("Unable to save Frontier Optionality for symbol %s", symbol)
            self._send_json({"error": "Unable to save Frontier Optionality.", "details": str(exc)}, status=500)
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
            templates, sources = get_all_prompt_templates(conn, purpose="prompt_configuration_ui")
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
            templates, sources = get_all_prompt_templates(conn, purpose="prompt_configuration_ui_reset")
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

    def handle_action_plan_get(self):
        try:
            conn = get_db_connection()
            try:
                self._send_json(build_action_plan(conn))
            finally:
                conn.close()
        except Exception as exc:
            logger.exception("Unable to build Action Plan")
            self._send_json({"error": "Unable to build Action Plan.", "details": str(exc)}, status=500)

    def handle_action_plan_detail_get(self, symbol):
        try:
            conn = get_db_connection()
            try:
                detail = get_action_plan_detail(conn, symbol)
                if not detail:
                    return self._send_json({"error": "Action Plan symbol not found"}, status=404)
                self._send_json({"action_detail": detail})
            finally:
                conn.close()
        except Exception as exc:
            logger.exception("Unable to build Action Plan detail")
            self._send_json({"error": "Unable to build Action Plan detail.", "details": str(exc)}, status=500)

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
            templates, _sources = get_all_prompt_templates(conn, purpose="prompt_configuration_preview")
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

    def handle_alert_detail_get(self, raw_alert_id):
        try:
            alert_id = int(raw_alert_id)
        except Exception:
            return self._send_json({"error": "Invalid alert id"}, status=400)

        conn = get_db_connection()
        try:
            alert = get_alert_by_id(conn, alert_id)
            if not alert:
                return self._send_json({"error": "Alert not found"}, status=404)
            self._send_json({"alert": alert})
        except Exception as exc:
            self._send_json({"error": "Unable to load alert detail.", "details": str(exc)}, status=500)
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
    configure_bakingmoney_logging(force=True)

    if not STATIC_DIR.exists():
        raise FileNotFoundError("Missing static directory. Expected: ./static")

    init_db()
    server = HTTPServer((HOST, PORT), BakingMoneyHandler)
    print(f"Server running at http://{HOST}:{PORT}")
    server.serve_forever()
