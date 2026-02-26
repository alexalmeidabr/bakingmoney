from pydantic import BaseModel, Field, field_validator, model_validator

from .scenarios import SCENARIO_TYPES


class WatchlistIn(BaseModel):
    ticker: str = Field(min_length=1, max_length=16)


class ScenarioInput(BaseModel):
    scenario_type: str
    horizon_years: int = 5
    price_low: float
    price_high: float
    cagr_low: float
    cagr_high: float
    probability: float
    assumptions_risks: str = ""
    what_to_look_for: str = ""

    @field_validator("scenario_type")
    @classmethod
    def validate_scenario_type(cls, value: str):
        lower = value.lower()
        if lower not in SCENARIO_TYPES:
            raise ValueError("scenario_type must be bear|base|bull|extreme")
        return lower

    @field_validator("probability")
    @classmethod
    def validate_probability(cls, value: float):
        if value < 0 or value > 1:
            raise ValueError("probability must be between 0 and 1")
        return value


class ScenarioUpsertRequest(BaseModel):
    scenarios: list[ScenarioInput]

    @model_validator(mode="after")
    def validate_scenarios(self):
        if len(self.scenarios) != 4:
            raise ValueError("Exactly 4 scenarios are required")
        types = {s.scenario_type for s in self.scenarios}
        if types != set(SCENARIO_TYPES):
            raise ValueError("Scenarios must include bear, base, bull, and extreme")
        total_prob = sum(s.probability for s in self.scenarios)
        if abs(total_prob - 1.0) > 1e-6:
            raise ValueError("Scenario probabilities must sum to 1")
        return self
