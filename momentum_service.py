"""Deterministic momentum and extension-risk calculations.

This module intentionally has no TWS, database, pandas, or OpenAI dependency so the
web app and the standalone TWS smoke-test script can share identical formulas.
"""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any, Sequence


def safe_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def clamp(value: Any, min_value: float, max_value: float) -> float:
    number = safe_number(value)
    if number is None:
        number = min_value
    return max(min_value, min(max_value, number))


def scale(value: Any, weak_level: float, strong_level: float) -> float:
    number = safe_number(value)
    if number is None or weak_level == strong_level:
        return 0.5
    if strong_level < weak_level:
        weak_level, strong_level = strong_level, weak_level
    if number <= weak_level:
        return 0.0
    if number >= strong_level:
        return 1.0
    return (number - weak_level) / (strong_level - weak_level)


def momentum_label(score: Any) -> str:
    value = safe_number(score)
    if value is None:
        return "Unknown"
    if value < 1.0:
        return "Very weak"
    if value < 2.0:
        return "Weak"
    if value < 3.0:
        return "Mixed / neutral"
    if value < 4.0:
        return "Positive"
    return "Strong"


def extension_label(score: Any) -> str:
    value = safe_number(score)
    if value is None:
        return "Unknown"
    if value < 1.0:
        return "Low extension"
    if value < 2.5:
        return "Normal"
    if value < 4.0:
        return "Extended"
    return "Very extended"


def _get(bar: Any, key: str) -> Any:
    if isinstance(bar, dict):
        return bar.get(key)
    if key == "date":
        return getattr(bar, "date", getattr(bar, "day", None))
    return getattr(bar, key, None)


def _date_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def _closes(bars: Sequence[Any]) -> list[float | None]:
    return [safe_number(_get(bar, "close")) for bar in bars]


def _pct_return_from_closes(closes: Sequence[float | None], days: int) -> float | None:
    if len(closes) <= days:
        return None
    latest = closes[-1]
    prior = closes[-1 - days]
    if latest is None or prior is None or prior <= 0:
        return None
    return (latest / prior - 1.0) * 100.0


def _sma(values: Sequence[float | None], window: int) -> float | None:
    valid = [value for value in values[-window:] if value is not None]
    if len(valid) < window:
        return None
    return sum(valid) / window


def _percent_above(value: Any, baseline: Any) -> float | None:
    value_num = safe_number(value)
    baseline_num = safe_number(baseline)
    if value_num is None or baseline_num is None or baseline_num <= 0:
        return None
    return (value_num / baseline_num - 1.0) * 100.0


def _ratio(numerator: Any, denominator: Any) -> float | None:
    num = safe_number(numerator)
    den = safe_number(denominator)
    if num is None or den is None or den == 0:
        return None
    return num / den


def _average(values: Sequence[float | None]) -> float | None:
    valid = [value for value in values if value is not None]
    if not valid:
        return None
    return sum(valid) / len(valid)


def _up_down_volume_ratio(bars: Sequence[Any]) -> float | None:
    if len(bars) < 2:
        return None
    recent = bars[-60:]
    up_volume = 0.0
    down_volume = 0.0
    for previous, current in zip(recent, recent[1:]):
        previous_close = safe_number(_get(previous, "close"))
        current_close = safe_number(_get(current, "close"))
        current_volume = safe_number(_get(current, "volume"))
        if previous_close is None or current_close is None or current_volume is None:
            continue
        if current_close > previous_close:
            up_volume += current_volume
        elif current_close < previous_close:
            down_volume += current_volume
    return _ratio(up_volume, down_volume)


def _atr_20(bars: Sequence[Any]) -> float | None:
    if len(bars) < 21:
        return None
    true_ranges: list[float | None] = []
    for previous, current in zip(bars, bars[1:]):
        high = safe_number(_get(current, "high"))
        low = safe_number(_get(current, "low"))
        previous_close = safe_number(_get(previous, "close"))
        if high is None or low is None:
            true_ranges.append(None)
            continue
        ranges = [high - low]
        if previous_close is not None:
            ranges.extend([abs(high - previous_close), abs(low - previous_close)])
        true_ranges.append(max(ranges))
    return _average(true_ranges[-20:])


def calculate_basic_metrics(symbol_rows: Sequence[Any], benchmark_rows: Sequence[Any] | None = None) -> dict[str, Any]:
    bars = list(symbol_rows or [])
    benchmark_bars = list(benchmark_rows or [])
    closes = _closes(bars)
    benchmark_closes = _closes(benchmark_bars)
    volumes = [safe_number(_get(bar, "volume")) for bar in bars]
    latest_close = closes[-1] if closes else None
    has_volume = any(volume is not None and volume > 0 for volume in volumes)

    ret_20 = _pct_return_from_closes(closes, 20)
    ret_60 = _pct_return_from_closes(closes, 60)
    ret_120 = _pct_return_from_closes(closes, 120)
    b_ret_20 = _pct_return_from_closes(benchmark_closes, 20)
    b_ret_60 = _pct_return_from_closes(benchmark_closes, 60)
    b_ret_120 = _pct_return_from_closes(benchmark_closes, 120)

    sma_50 = _sma(closes, 50)
    sma_200 = _sma(closes, 200)
    prior_sma_50 = _sma(closes[:-20], 50) if len(closes) >= 70 else None
    highs = [safe_number(_get(bar, "high")) for bar in bars]
    high_52w = max((value for value in highs[-252:] if value is not None), default=None)
    high_3m = max((value for value in highs[-63:] if value is not None), default=None)
    avg_vol_20 = _sma(volumes, 20)
    avg_vol_60 = _sma(volumes, 60)
    atr_20 = _atr_20(bars)

    returns = [ret_20, ret_60, ret_120]
    available_returns = [value for value in returns if value is not None]
    return_consistency = (
        sum(1 for value in available_returns if value > 0) / len(available_returns)
        if available_returns
        else 0.5
    )

    return {
        "bars": len(bars),
        "first_date": _date_text(_get(bars[0], "date")) if bars else None,
        "last_date": _date_text(_get(bars[-1], "date")) if bars else None,
        "latest_close": latest_close,
        "has_volume": has_volume,
        "ret_20": ret_20,
        "ret_60": ret_60,
        "ret_120": ret_120,
        "rel_20": ret_20 - b_ret_20 if ret_20 is not None and b_ret_20 is not None else None,
        "rel_60": ret_60 - b_ret_60 if ret_60 is not None and b_ret_60 is not None else None,
        "rel_120": ret_120 - b_ret_120 if ret_120 is not None and b_ret_120 is not None else None,
        "sma_50": sma_50,
        "sma_200": sma_200,
        "price_vs_sma_50": _percent_above(latest_close, sma_50),
        "price_vs_sma_200": _percent_above(latest_close, sma_200),
        "sma_50_vs_sma_200": _percent_above(sma_50, sma_200),
        "sma_50_slope_20d": _percent_above(sma_50, prior_sma_50),
        "high_52w": high_52w,
        "high_3m": high_3m,
        "distance_from_52w_high": _percent_above(latest_close, high_52w),
        "distance_from_3m_high": _percent_above(latest_close, high_3m),
        "return_consistency": return_consistency,
        "avg_vol_20": avg_vol_20,
        "avg_vol_60": avg_vol_60,
        "volume_ratio_20_60": _ratio(avg_vol_20, avg_vol_60),
        "up_down_volume_ratio": _up_down_volume_ratio(bars),
        "atr_20": atr_20,
        "atr_20_pct": _percent_above((latest_close or 0) + atr_20, latest_close) if atr_20 is not None else None,
    }


def calculate_momentum_snapshot(symbol_rows: Sequence[Any], benchmark_rows: Sequence[Any] | None = None) -> dict[str, Any]:
    metrics = calculate_basic_metrics(symbol_rows, benchmark_rows)
    trend_score = (
        0.30 * scale(metrics.get("price_vs_sma_50"), -10, 10)
        + 0.25 * scale(metrics.get("price_vs_sma_200"), -20, 20)
        + 0.25 * scale(metrics.get("sma_50_vs_sma_200"), -10, 10)
        + 0.20 * scale(metrics.get("sma_50_slope_20d"), -5, 5)
    )
    relative_strength_score = (
        0.25 * scale(metrics.get("rel_20"), -10, 10)
        + 0.45 * scale(metrics.get("rel_60"), -15, 15)
        + 0.30 * scale(metrics.get("rel_120"), -20, 20)
    )
    warning = None
    if metrics.get("has_volume"):
        volume_score = (
            0.55 * scale(metrics.get("volume_ratio_20_60"), 0.75, 1.50)
            + 0.45 * scale(metrics.get("up_down_volume_ratio"), 0.70, 1.50)
        )
    else:
        volume_score = 0.5
        warning = "Volume data missing; neutral volume score used."

    price_structure_score = (
        0.50 * scale(metrics.get("distance_from_52w_high"), -50, 0)
        + 0.30 * scale(metrics.get("distance_from_3m_high"), -25, 0)
        + 0.20 * clamp(metrics.get("return_consistency"), 0, 1)
    )
    momentum_raw = (
        0.35 * trend_score
        + 0.25 * relative_strength_score
        + 0.20 * volume_score
        + 0.20 * price_structure_score
    )
    momentum_score = clamp(momentum_raw * 5.0, 0.0, 5.0)

    extension_raw = (
        0.40 * scale(metrics.get("price_vs_sma_50"), 10, 30)
        + 0.35 * scale(metrics.get("ret_20"), 15, 40)
        + 0.25 * scale(metrics.get("atr_20_pct"), 4, 12)
    )
    extension_risk = clamp(extension_raw * 5.0, 0.0, 5.0)

    close_values = [value for value in _closes(symbol_rows or []) if value is not None]
    if metrics.get("latest_close") is None or not close_values:
        status = "Error"
    elif metrics.get("bars", 0) >= 200:
        status = "OK"
    else:
        status = "Partial"

    components = {
        "trend_score": trend_score,
        "relative_strength_score": relative_strength_score,
        "volume_score": volume_score,
        "price_structure_score": price_structure_score,
        "momentum_raw": momentum_raw,
        "extension_raw": extension_raw,
    }
    return {
        "momentum_score": momentum_score,
        "momentum_label": momentum_label(momentum_score),
        "extension_risk": extension_risk,
        "extension_label": extension_label(extension_risk),
        "momentum_status": status,
        "warning": warning,
        "metrics": metrics,
        "components": components,
        **components,
    }
