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
import uuid
import zipfile
from html import unescape
from datetime import datetime, timezone
from http.server import HTTPServer, SimpleHTTPRequestHandler
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse
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
    "app_settings",
    "positions_cache",
    "thesis_review_alerts",
    "recent_event_checks",
)

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
OPENAI_STEP_TIMEOUT_OVERRIDES = {
    "earnings_watchpoint_analysis": {1: 120.0, 2: 180.0},
}
NO_PRICE_WARNING = "No live API market data (delayed/unavailable)"
ANALYSIS_PROMPT_SETTING_KEY_BUSINESS_MODEL = "analysis_prompt_business_model"
ANALYSIS_PROMPT_SETTING_KEY_KEY_VARIABLES = "analysis_prompt_key_variables"
ANALYSIS_PROMPT_SETTING_KEY_SCENARIOS = "analysis_prompt_scenarios"
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
ANALYSIS_SETTING_USE_TWS_DATA = "use_tws_data"

DEFAULT_SCENARIO_MULTI_PASS_ENABLED = False
DEFAULT_SCENARIO_PASS_COUNT = 1
DEFAULT_SCENARIO_OUTLIER_FILTER_ENABLED = True
DEFAULT_IB_PRICE_WAIT_SECONDS = 5
DEFAULT_IB_MARKET_DATA_BATCH_SIZE = 25

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
- Avoid overlap between variables, if two candidate variables describe the same mechanism, keep only the stronger one
- Keep each variable text concise. Prefer a short phrase or one short sentence, not a full explanation. Do not explicitly include “mechanism:” or “financial consequence:” in the variable text.
- confidence must be an integer from 0 to 10.
- importance must be an integer from 0 to 10.
- Use score discipline: reserve the highest scores for only the most central and well-supported variables.
- JSON only.
- No markdown.
- No commentary outside JSON."""

DEFAULT_PROMPT_SCENARIOS = """You are an equity analyst building a disciplined 5-year stock scenario analysis.

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
- The Base case must reflect the most likely balance of the variable set and must not simply be a softened Bull case.
- Probabilities must sum to 100.

Fresh-information rule:
Before building scenarios, review the latest company earnings release and guidance, and consider only recent news or analyst commentary that materially changes the company’s key variables, current expectations, or scenario probabilities. Prioritize primary sources and factual updates over sentiment or low-signal market commentary.

The key variables are the primary foundation for the scenario analysis. Build the Bear, Base, and Bull scenarios mainly from the highest-importance and highest-confidence key variables, and ensure that the scenario assumptions, price ranges, and probabilities are directly driven by how those variables could evolve over the next 5 years.

Valuation discipline:
- A strong business does not automatically imply high stock upside.
- Current valuation, company size, and already-priced expectations must materially constrain scenario outputs.
- Do not assume extreme 5-year upside unless clearly supported by multiple high-confidence, high-importance bullish variables and limited material bearish constraints.
- High-importance bullish and bearish variables must materially affect price ranges and probabilities, not just the written assumptions.
- If the stock is not obviously expensive relative to its risk, growth profile, and business quality, allow meaningful upside when justified by the variables.

Scenario realism:
- Use realistic price ranges that reflect both business performance and valuation constraints.
- Do not let optionality, speculative new products, or long-shot TAM expansion dominate the scenarios unless strongly supported by current evidence.
- Avoid ultra-optimistic outcomes that require near-perfect execution across multiple variables unless such outcomes are assigned a clearly low probability.
- Keep Bull plausible, not aspirational.
- Keep Bear pessimistic, not catastrophic unless the variable set truly supports that.
- The wider and more uncertain the path, the lower the probability should be.
- Use latest earnings release / shareholder letter / earnings call guidance and extract only facts that materially affect the 5-year thesis and current scenario framing.
- Use latest earnings release to understand current company valuation.

Interpretation rules:
- Distinguish clearly between business quality and stock attractiveness.
- A company can be excellent while the stock has limited upside.
- If current price is known, use it as an anchor, but do not force the Base case close to current price when the variable set clearly justifies deviation.
- Scenario probabilities must reflect the weighted balance of key variables using both importance and confidence.
- Avoid generic default probability splits unless the evidence is truly balanced.
- assumptions should be concise and reflect the business model and most important key variables.
- If the symbol is an ETF, reflect the performance drivers and risks of its top holdings.

JSON only.
No markdown.
No commentary outside JSON."""

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
        "required_vars": ["$Symbol", "$CompanyName", "$BusinessModel", "$KeyVariables"],
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


def request_ib_tickers_batched(ib, qualified_contracts, purpose):
    if not qualified_contracts:
        return []

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
    for batch_idx, batch in enumerate(batches, start=1):
        logger.info(
            "IBKR market data batch purpose=%s index=%s/%s size=%s",
            purpose,
            batch_idx,
            len(batches),
            len(batch),
        )
        batch_tickers = ib.reqTickers(*batch)
        ib.sleep(get_ib_price_wait_seconds())
        tickers.extend(batch_tickers or [])
        for contract in batch:
            try:
                ib.cancelMktData(contract)
                logger.debug(
                    "Cancelled IBKR market data purpose=%s conid=%s symbol=%s",
                    purpose,
                    getattr(contract, "conId", None),
                    getattr(contract, "symbol", None),
                )
            except Exception:
                continue
    return tickers


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
    supported_placeholders = ("$Symbol", "$CompanyName", "$Price", "$BusinessModel", "$KeyVariables", "$EventSearchCutoff", "$EventCandidates")
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
):

    symbol_value = symbol or "unknown"
    price_value = f"{price:.2f}" if isinstance(price, (int, float)) and math.isfinite(price) else "unknown"
    company_name_value = company_name or "unknown"
    business_value = build_business_model_prompt_value(business_model=business_model, business_summary=business_summary)
    key_vars_value = format_key_variables_for_prompt(key_variables or [])
    event_candidates_value = event_candidates
    if not isinstance(event_candidates_value, str):
        event_candidates_value = json.dumps(event_candidates_value or [], separators=(",", ":"), ensure_ascii=False)
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
        ensure_column_exists(conn, "analysis_scenarios", "price_mid", "REAL")
        ensure_column_exists(conn, "analysis_scenarios", "cagr_mid", "REAL")
        ensure_column_exists(conn, "analysis_version_scenarios", "price_mid", "REAL")
        ensure_column_exists(conn, "analysis_version_scenarios", "cagr_mid", "REAL")

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
    if not is_tws_data_enabled():
        logger.info("Skipping IBKR price fetch because use_tws_data is disabled symbols=%s", len(symbols))
        for symbol in symbols:
            warnings[symbol] = NO_PRICE_WARNING
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
            tickers = request_ib_tickers_batched(
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
                if price is None:
                    raw_market_price = safe_number(ticker.marketPrice()) if hasattr(ticker, "marketPrice") else None
                    raw_last = safe_number(getattr(ticker, "last", None))
                    raw_close = safe_number(getattr(ticker, "close", None))
                    for invalid_candidate in (raw_market_price, raw_last, raw_close):
                        if invalid_candidate is not None and invalid_candidate <= 0:
                            logger.info("Ignoring invalid TWS price symbol=%s price=%s", symbol, invalid_candidate)
                    logger.info("Keeping previous valid price for symbol=%s", symbol)
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


def request_ai_step(step_name, prompt_text, json_schema, attempt=1):
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
    request_timeout_seconds = get_ai_step_timeout(step_name, attempt=attempt)

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
                f"OpenAI request timed out on step {step_name} attempt {attempt} after {request_timeout_seconds:.1f}s"
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
                    "confidence": item["confidence"],
                    "importance": item["importance"],
                }
            )
        else:
            normalized_key_variables.append(
                {
                    "variable_text": item["variable"],
                    "variable_type": item["type"],
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
        current_price=effective_price,
    )
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


def calculate_expected_cagr(scenarios):
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
            validation = validate_scenario_output(payload, symbol, current_price=current_price)
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


def list_analysis_symbols(conn):
    rating_settings = get_rating_settings(conn)
    rows = conn.execute(
        """
        SELECT r.symbol, v.current_price, v.expected_price, v.expected_cagr, v.upside, v.confidence_level AS overall_confidence,
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
               (
                   SELECT MAX(rc.checked_at)
                   FROM recent_event_checks rc
                   WHERE rc.symbol = r.symbol
               ) AS last_recent_event_check_at,
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
        scenario_updated = _parse_iso_datetime(item.get("updated_at"))
        event_checked = _parse_iso_datetime(item.get("last_recent_event_check_at"))
        activity_candidates = [dt for dt in (scenario_updated, event_checked) if dt is not None]
        item["last_activity_at"] = max(activity_candidates).isoformat() if activity_candidates else None
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
        SELECT scenario_name, price_low, price_mid, price_high, cagr_low, cagr_mid, cagr_high, probability
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
        "expected_cagr": version_row["expected_cagr"],
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

    scenarios_with_cagr = enrich_scenarios_with_midpoints(scenarios, current_price=current_price)
    expected_price = calculate_expected_price(scenarios_with_cagr)
    expected_cagr = calculate_expected_cagr(scenarios_with_cagr)
    upside = calculate_upside(expected_price, current_price)
    confidence = calculate_overall_confidence(key_variables)

    conn.execute(
        """
        INSERT INTO analysis_versions (
            analysis_root_id, version_number, symbol, company_name, current_price, expected_price,
            expected_cagr, upside, confidence_level, assumptions_text, business_model_text, business_summary_text,
            raw_ai_response, source_trigger, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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

    templates, _sources = get_prompt_templates_for_keys(
        conn,
        (ANALYSIS_PROMPT_SETTING_KEY_SCENARIOS,),
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
        current_price=base_version["current_price"],
    )
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

    templates, _sources = get_prompt_templates_for_keys(
        conn,
        (ANALYSIS_PROMPT_SETTING_KEY_SCENARIOS,),
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
        current_price=base_version["current_price"],
    )
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
        row["expected_cagr"] = analysis.get("expected_cagr") if analysis else None
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
        normalized_row["unrealizedPnLPercent"] = compute_unrealized_pnl_percent(normalized_row)
        normalized_row["costBasis"] = compute_cost_basis(normalized_row)
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
            return self.handle_positions_api()
        if path == "/api/analysis":
            return self.handle_analysis_get()
        if path == "/api/earnings-review":
            return self.handle_earnings_review_get()
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
        if path == "/api/earnings-review/symbols":
            return self.handle_earnings_review_symbol_add()
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
        if path.startswith("/api/alerts/") and path.endswith("/status"):
            alert_id = path[len("/api/alerts/") : -len("/status")]
            return self.handle_alerts_status_put(alert_id)

        self.send_error(404, "Not Found")

    def do_DELETE(self):
        path = urlparse(self.path).path
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

    def handle_positions_api(self):
        try:
            ensure_event_loop()
            ib = get_ib_connection()
            positions = ib.positions()
            logger.info("Positions API using live IBKR path positions_count=%s", len(positions))
            contracts = [p.contract for p in positions if p.contract]
            tickers_by_conid = {}
            tws_data_enabled = is_tws_data_enabled()

            if contracts and tws_data_enabled:
                qualified = ib.qualifyContracts(*contracts)
                if qualified:
                    tickers = request_ib_tickers_batched(
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
                else:
                    cached_rows = load_positions_cache(conn)
                    effective_data = overlay_cached_market_fields(data, cached_rows)
                    if cached_rows:
                        save_positions_cache(conn, effective_data)
                    warning_message = "Data from TWS is disabled. Showing latest cached market values when available."
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
            refresh_latest_analysis_market_prices(conn)
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
