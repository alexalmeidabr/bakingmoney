import pytest
from pydantic import ValidationError

from app.schemas import ScenarioInput, ScenarioUpsertRequest


def test_scenario_default_horizon_is_five():
    scenario = ScenarioInput(
        scenario_type="base",
        price_low=100,
        price_high=150,
        cagr_low=0.06,
        cagr_high=0.1,
        probability=0.5,
    )
    assert scenario.horizon_years == 5


def test_probability_sum_must_equal_one():
    payload = {
        "scenarios": [
            {"scenario_type": "bear", "price_low": 80, "price_high": 110, "cagr_low": -0.02, "cagr_high": 0.04, "probability": 0.2},
            {"scenario_type": "base", "price_low": 120, "price_high": 160, "cagr_low": 0.06, "cagr_high": 0.1, "probability": 0.5},
            {"scenario_type": "bull", "price_low": 180, "price_high": 230, "cagr_low": 0.12, "cagr_high": 0.18, "probability": 0.2},
            {"scenario_type": "extreme", "price_low": 60, "price_high": 100, "cagr_low": -0.10, "cagr_high": 0.0, "probability": 0.05},
        ]
    }

    with pytest.raises(ValidationError):
        ScenarioUpsertRequest(**payload)


def test_valid_probability_sum_is_one():
    payload = {
        "scenarios": [
            {"scenario_type": "bear", "price_low": 80, "price_high": 110, "cagr_low": -0.02, "cagr_high": 0.04, "probability": 0.2},
            {"scenario_type": "base", "price_low": 120, "price_high": 160, "cagr_low": 0.06, "cagr_high": 0.1, "probability": 0.5},
            {"scenario_type": "bull", "price_low": 180, "price_high": 230, "cagr_low": 0.12, "cagr_high": 0.18, "probability": 0.2},
            {"scenario_type": "extreme", "price_low": 60, "price_high": 100, "cagr_low": -0.10, "cagr_high": 0.0, "probability": 0.1},
        ]
    }

    validated = ScenarioUpsertRequest(**payload)
    assert len(validated.scenarios) == 4
