import json
import math
from typing import Any, Dict, List, Optional

SCENARIO_ORDER = ["Bear", "Base", "Bull"]
SCENARIO_SET = set(SCENARIO_ORDER)
VARIABLE_TYPES = {"Bullish", "Bearish"}
MIN_KEY_VARIABLES = 6
MAX_KEY_VARIABLES = 10


class AnalysisValidationError(ValueError):
    pass


def _safe_float(value: Any, name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise AnalysisValidationError(f"{name} must be a valid number")

    if not math.isfinite(number):
        raise AnalysisValidationError(f"{name} must be a finite number")

    return number


def _safe_int_0_10(value: Any, name: str) -> int:
    number = _safe_float(value, name)
    rounded = round(number)
    if not math.isclose(number, rounded, abs_tol=1e-9):
        raise AnalysisValidationError(f"{name} must be an integer")
    integer = int(rounded)
    if integer < 0 or integer > 10:
        raise AnalysisValidationError(f"{name} must be in [0, 10]")
    return integer


def _normalize_probability(value: float) -> float:
    return value / 100.0 if value > 1 else value


def extract_json_payload(text: str) -> Dict[str, Any]:
    if not isinstance(text, str) or not text.strip():
        raise AnalysisValidationError("AI response was empty")

    stripped = text.strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start == -1 or end == -1 or start >= end:
            raise AnalysisValidationError("AI response did not contain valid JSON")
        try:
            return json.loads(stripped[start : end + 1])
        except json.JSONDecodeError as exc:
            raise AnalysisValidationError(f"Unable to parse AI JSON response: {exc}")


def parse_analysis_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise AnalysisValidationError("AI payload must be a JSON object")

    symbol = payload.get("symbol")
    if not isinstance(symbol, str) or not symbol.strip():
        raise AnalysisValidationError("symbol is required")
    symbol = symbol.strip().upper()

    assumptions = payload.get("assumptions", "")
    if assumptions is None:
        assumptions = ""
    if not isinstance(assumptions, str):
        raise AnalysisValidationError("assumptions must be text")

    raw_scenarios = payload.get("scenarios")
    if not isinstance(raw_scenarios, list):
        raise AnalysisValidationError("scenarios must be an array")
    if len(raw_scenarios) != 3:
        raise AnalysisValidationError("scenarios must include exactly 3 items")

    scenarios = []
    seen_names = set()
    total_probability = 0.0

    for item in raw_scenarios:
        if not isinstance(item, dict):
            raise AnalysisValidationError("each scenario must be an object")

        scenario_name = item.get("name")
        if scenario_name not in SCENARIO_SET:
            raise AnalysisValidationError("scenario name must be Bear, Base, or Bull")
        if scenario_name in seen_names:
            raise AnalysisValidationError("duplicate scenario names are not allowed")

        price_low = _safe_float(item.get("price_low"), f"{scenario_name}.price_low")
        price_high = _safe_float(item.get("price_high"), f"{scenario_name}.price_high")
        cagr_low = _safe_float(item.get("cagr_low"), f"{scenario_name}.cagr_low")
        cagr_high = _safe_float(item.get("cagr_high"), f"{scenario_name}.cagr_high")
        probability = _safe_float(item.get("probability"), f"{scenario_name}.probability")

        if price_low > price_high:
            raise AnalysisValidationError(f"{scenario_name} price_low cannot exceed price_high")
        if cagr_low > cagr_high:
            raise AnalysisValidationError(f"{scenario_name} cagr_low cannot exceed cagr_high")

        probability_normalized = _normalize_probability(probability)
        if probability_normalized < 0:
            raise AnalysisValidationError(f"{scenario_name} probability cannot be negative")

        scenarios.append(
            {
                "scenario_name": scenario_name,
                "price_low": price_low,
                "price_high": price_high,
                "cagr_low": cagr_low,
                "cagr_high": cagr_high,
                "probability": probability_normalized,
            }
        )
        total_probability += probability_normalized
        seen_names.add(scenario_name)

    if seen_names != SCENARIO_SET:
        raise AnalysisValidationError("scenarios must include exactly one Bear, Base, and Bull")

    if abs(total_probability - 1.0) > 0.02:
        raise AnalysisValidationError("scenario probabilities must sum to 100%")

    raw_variables = payload.get("key_variables")
    if not isinstance(raw_variables, list):
        raise AnalysisValidationError("key_variables must be an array")
    if len(raw_variables) < MIN_KEY_VARIABLES or len(raw_variables) > MAX_KEY_VARIABLES:
        raise AnalysisValidationError(
            f"key_variables must contain between {MIN_KEY_VARIABLES} and {MAX_KEY_VARIABLES} items"
        )

    key_variables = []
    for index, item in enumerate(raw_variables):
        if not isinstance(item, dict):
            raise AnalysisValidationError("each key variable must be an object")

        variable_text = item.get("variable")
        if not isinstance(variable_text, str) or not variable_text.strip():
            raise AnalysisValidationError(f"key_variables[{index}].variable is required")

        variable_type = item.get("type")
        if variable_type not in VARIABLE_TYPES:
            raise AnalysisValidationError(f"key_variables[{index}].type must be Bullish or Bearish")

        confidence = _safe_int_0_10(item.get("confidence"), f"key_variables[{index}].confidence")
        importance = _safe_int_0_10(item.get("importance"), f"key_variables[{index}].importance")

        key_variables.append(
            {
                "variable_text": variable_text.strip(),
                "variable_type": variable_type,
                "confidence": confidence,
                "importance": importance,
            }
        )

    return {
        "symbol": symbol,
        "assumptions": assumptions.strip(),
        "scenarios": sorted(
            scenarios,
            key=lambda s: SCENARIO_ORDER.index(s["scenario_name"]),
        ),
        "key_variables": key_variables,
    }


def calculate_expected_price(scenarios: List[Dict[str, Any]]) -> float:
    expected = 0.0
    for scenario in scenarios:
        midpoint = (scenario["price_low"] + scenario["price_high"]) / 2.0
        expected += midpoint * scenario["probability"]
    return expected


def calculate_upside(expected_price: float, current_price: Optional[float]) -> Optional[float]:
    if current_price is None or current_price == 0:
        return None
    return ((expected_price / current_price) - 1.0) * 100.0


def calculate_overall_confidence(key_variables: List[Dict[str, Any]]) -> Optional[float]:
    if not key_variables:
        return None

    weight_total = sum(item["importance"] for item in key_variables)
    if weight_total <= 0:
        return None

    weighted_confidence = sum(item["confidence"] * item["importance"] for item in key_variables)
    return weighted_confidence / weight_total
