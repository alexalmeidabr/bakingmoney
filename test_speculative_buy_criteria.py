import os
import tempfile
import unittest
from unittest import mock

import web_server
from web_server import ACTION_PLAN_DEFAULT_SETTINGS, DEFAULT_RATING_SETTINGS, _linear_stock_penalty_factor, calculate_rating


def rating_settings():
    settings = dict(DEFAULT_RATING_SETTINGS)
    settings.update({
        "strong_buy_min_upside": 200.0,
        "buy_min_upside": 200.0,
        "strong_sell_max_upside": -100.0,
        "sell_max_upside": -100.0,
    })
    return settings


def eligible_context(**overrides):
    context = {
        "core_bullish_confidence": 4.6,
        "core_bearish_confidence": 4.4,
        "potential_bullish_confidence": 5.0,
        "potential_bearish_confidence": 4.0,
        "bullish_potential_driver_count": 2,
    }
    context.update(overrides)
    return context


class SpeculativeBuyCriteriaTests(unittest.TestCase):
    def test_qualifies_when_weighted_potential_confidence_and_driver_count_meet_thresholds(self):
        rating, _ = calculate_rating(75.0, 5.0, 4.0, rating_settings(), eligible_context())
        self.assertEqual(rating, "Speculative Buy")

    def test_falls_through_to_hold_when_weighted_potential_confidence_is_below_threshold(self):
        rating, _ = calculate_rating(
            75.0, 5.0, 4.0, rating_settings(), eligible_context(potential_bullish_confidence=4.9)
        )
        self.assertEqual(rating, "Hold")

    def test_falls_through_to_hold_when_bullish_potential_driver_count_is_below_threshold(self):
        rating, _ = calculate_rating(
            75.0, 5.0, 4.0, rating_settings(), eligible_context(bullish_potential_driver_count=1)
        )
        self.assertEqual(rating, "Hold")

    def test_missing_potential_bullish_confidence_fails_even_on_core_confidence_path(self):
        rating, _ = calculate_rating(
            75.0,
            6.0,
            4.0,
            rating_settings(),
            eligible_context(core_bullish_confidence=6.0, core_bearish_confidence=4.0, potential_bullish_confidence=None),
        )
        self.assertEqual(rating, "Hold")

    def test_speculative_buy_linear_penalty_is_multiplicative_and_diagnostic(self):
        settings = dict(ACTION_PLAN_DEFAULT_SETTINGS)
        settings["core_confidence_penalty"] = 0.20
        settings["core_confidence_penalty_threshold"] = 1.0
        factor, penalties = _linear_stock_penalty_factor({}, 0.0, 1.0, 100.0, "Speculative Buy", settings)
        self.assertAlmostEqual(factor, 0.68)
        self.assertEqual(
            [(penalty["key"], penalty["label"], penalty["penalty"]) for penalty in penalties],
            [
                ("core_confidence_penalty", "Core confidence below threshold", 0.20),
                ("speculative_buy_rating_penalty", "Speculative Buy rating", 0.15),
            ],
        )

    def test_speculative_buy_penalty_does_not_apply_to_buy_or_zero_penalty(self):
        settings = dict(ACTION_PLAN_DEFAULT_SETTINGS)
        buy_factor, buy_penalties = _linear_stock_penalty_factor({}, 1.0, 1.0, 100.0, "Buy", settings)
        settings["speculative_buy_rating_penalty"] = 0.0
        zero_factor, zero_penalties = _linear_stock_penalty_factor({}, 1.0, 1.0, 100.0, "Speculative Buy", settings)
        self.assertEqual((buy_factor, buy_penalties), (1.0, []))
        self.assertEqual((zero_factor, zero_penalties), (1.0, []))

    def test_new_settings_default_persist_and_reject_fractional_driver_count(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "settings.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    self.assertEqual(web_server.get_rating_settings(conn)["speculative_buy_min_potential_bullish_confidence"], 5.0)
                    self.assertEqual(web_server.get_rating_settings(conn)["speculative_buy_min_bullish_potential_drivers"], 2.0)
                    self.assertEqual(web_server.get_action_plan_settings(conn)["speculative_buy_rating_penalty"], 0.15)
                    web_server.save_general_configuration(conn, {"rating_settings": {"speculative_buy_min_bullish_potential_drivers": 3}})
                    self.assertEqual(web_server.get_rating_settings(conn)["speculative_buy_min_bullish_potential_drivers"], 3.0)
                    with self.assertRaisesRegex(ValueError, "whole number"):
                        web_server.save_general_configuration(conn, {"rating_settings": {"speculative_buy_min_bullish_potential_drivers": 1.5}})
                finally:
                    conn.close()
