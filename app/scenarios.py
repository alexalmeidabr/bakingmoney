SCENARIO_TYPES = ("bear", "base", "bull", "extreme")


def default_scenarios_from_price(ticker: str, current_price: float | None, horizon_years: int = 5):
    price = current_price if current_price and current_price > 0 else 100.0

    multipliers = {
        "bear": (0.90, 1.20, -0.02, 0.04, 0.20),
        "base": (1.30, 1.70, 0.06, 0.10, 0.50),
        "bull": (1.90, 2.40, 0.12, 0.18, 0.20),
        "extreme": (0.60, 1.00, -0.10, 0.00, 0.10),
    }

    scenarios = []
    for scenario_type in SCENARIO_TYPES:
        pl, ph, cl, ch, prob = multipliers[scenario_type]
        scenarios.append(
            {
                "ticker": ticker,
                "scenario_type": scenario_type,
                "horizon_years": horizon_years,
                "price_low": round(price * pl, 2),
                "price_high": round(price * ph, 2),
                "cagr_low": cl,
                "cagr_high": ch,
                "probability": prob,
                "assumptions_risks": "TODO: replace with analyst assumptions and key risks.",
                "what_to_look_for": "TODO: define leading indicators, earnings events, and macro triggers.",
            }
        )
    return scenarios
