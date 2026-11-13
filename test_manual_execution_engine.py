import unittest
from datetime import datetime, timezone

import web_server


NOW = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)


def verified_row(**overrides):
    row = {
        "symbol": "NVDA",
        "action": "Add",
        "current_price": 100.0,
        "owned_share_quantity": 50,
        "position_price_status": "tws_received",
        "price_source": "marketPrice",
        "price_sizing_source": "position_quote",
        "price_last_successful_at": "2026-01-01T09:59:00+00:00",
        "target_weight_mid": 10.0,
        "manual_trigger_status": "waiting",
    }
    row.update(overrides)
    return row


class ManualExecutionEvaluationTests(unittest.TestCase):
    def test_buy_threshold_is_inclusive_and_rechecked_at_current_price(self):
        preference = {"buy_trigger_price": 80}
        self.assertEqual(web_server.evaluate_manual_execution_trigger(verified_row(), preference, NOW)["status"], "waiting")
        for price in (80, 75):
            with self.subTest(price=price):
                result = web_server.evaluate_manual_execution_trigger(verified_row(current_price=price), preference, NOW)
                self.assertEqual(result["status"], "eligible")
                self.assertEqual(result["verified_price"], price)

    def test_sell_and_trim_share_one_threshold_and_direction(self):
        above = {"sell_trigger_price": 120, "sell_trigger_direction": "at_or_above"}
        below = {"sell_trigger_price": 90, "sell_trigger_direction": "at_or_below"}
        for action in ("Trim", "Strong Trim", "Sell", "Strong Sell"):
            with self.subTest(action=action):
                self.assertEqual(web_server.evaluate_manual_execution_trigger(verified_row(action=action), above, NOW)["status"], "waiting")
                self.assertEqual(web_server.evaluate_manual_execution_trigger(verified_row(action=action, current_price=125), above, NOW)["status"], "eligible")
                self.assertEqual(web_server.evaluate_manual_execution_trigger(verified_row(action=action, current_price=85), below, NOW)["status"], "eligible")

    def test_no_relevant_trigger_keeps_existing_execution(self):
        self.assertEqual(web_server.evaluate_manual_execution_trigger(verified_row(), {}, NOW)["status"], "no_manual_trigger")
        self.assertEqual(web_server.evaluate_manual_execution_trigger(verified_row(action="Hold"), {"buy_trigger_price": 80}, NOW)["status"], "no_manual_trigger")
        self.assertEqual(web_server.evaluate_manual_execution_trigger(verified_row(action="Sell"), {"buy_trigger_price": 80}, NOW)["status"], "no_manual_trigger")

    def test_stale_cached_delayed_and_unowned_prices_require_confirmation(self):
        preference = {"buy_trigger_price": 120}
        cases = (
            {"position_price_status": "cached_stale"},
            {"price_sizing_source": "analysis_price_fallback"},
            {"price_source": "close"},
            {"price_source": "delayed_market_data"},
            {"price_last_successful_at": "2026-01-01T09:54:00+00:00"},
            {"price_last_successful_at": None},
            {"owned_share_quantity": 0},
        )
        for changes in cases:
            with self.subTest(changes=changes):
                result = web_server.evaluate_manual_execution_trigger(verified_row(**changes), preference, NOW)
                self.assertEqual(result["status"], "price_confirmation_required")
                self.assertIsNone(result["verified_price"])

    def test_reservation_uses_additional_whole_shares_at_trigger_price(self):
        preference = {"buy_trigger_price": 80, "reserve_enabled": True, "reserve_percentage": 60}
        result = web_server.calculate_manual_reservation(verified_row(), preference, 100_000, 0)
        self.assertEqual(result["planned_purchase_shares_at_trigger"], 75)
        self.assertEqual(result["planned_purchase_amount_at_trigger"], 6_000)
        self.assertEqual(result["requested_reservation"], 3_600)
        full = web_server.calculate_manual_reservation(verified_row(), {**preference, "reserve_percentage": 100}, 100_000, 0)
        self.assertEqual(full["requested_reservation"], 6_000)

    def test_reservation_is_inactive_when_disabled_satisfied_or_not_a_buy(self):
        preference = {"buy_trigger_price": 80, "reserve_enabled": True, "reserve_percentage": 60}
        cases = (
            (verified_row(manual_trigger_status="eligible"), preference),
            (verified_row(action="Sell"), preference),
            (verified_row(), {**preference, "reserve_enabled": False}),
            (verified_row(), {**preference, "reserve_percentage": 0}),
            (verified_row(), {**preference, "buy_trigger_price": None}),
        )
        for row, settings in cases:
            with self.subTest(row=row, settings=settings):
                self.assertEqual(web_server.calculate_manual_reservation(row, settings, 100_000, 0)["requested_reservation"], 0)
        self.assertEqual(web_server.calculate_manual_reservation(verified_row(), preference, 100_000, 6_001)["requested_reservation"], 0)


if __name__ == "__main__":
    unittest.main()
