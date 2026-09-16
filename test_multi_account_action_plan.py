import os
import tempfile
import unittest
from unittest import mock

import web_server


ACCOUNT_A = "U_TEST_A"
ACCOUNT_B = "U_TEST_B"


def position(symbol, quantity, market_value, price=100.0, avg_cost=50.0):
    return {
        "symbol": symbol,
        "position": quantity,
        "price": price,
        "avgCost": avg_cost,
        "marketValue": market_value,
        "currency": "USD",
    }


class MultiAccountActionPlanIsolationTests(unittest.TestCase):
    def open_conn(self, db_path):
        conn = web_server.sqlite3.connect(db_path)
        conn.row_factory = web_server.sqlite3.Row
        return conn

    def init_db(self, db_path):
        with mock.patch.object(web_server, "DB_PATH", db_path):
            web_server.init_db()

    def save_state(self, conn, account_id, *, positions, portfolio_value, actual_cash):
        web_server.save_positions_cache(conn, positions, account_id=account_id)
        web_server.save_portfolio_summary_cache(
            conn,
            {
                "base_currency": "USD",
                "net_liquidation": portfolio_value,
                "actual_cash": actual_cash,
            },
            account_id=account_id,
        )

    def save_settings(self, conn, **overrides):
        settings = {
            "linear_allocated_target_total_pct": 20.0,
            "linear_min_score_threshold": 0.0,
            "linear_score_allocation_power": 1.0,
            "linear_max_single_stock_pct": 100.0,
            "linear_enable_risk_caps": False,
            "linear_rating_bonus_enabled": False,
            "hold_rating_penalty_enabled": False,
            "core_confidence_penalty": 0.0,
            "upside_penalty": 0.0,
            "potential_confidence_penalty": 0.0,
            "action_min_cash_unallocated_target": 5.0,
            "linear_max_reserve_pct": 20.0,
            "linear_reserve_benchmark_yield_pct": 4.0,
            "linear_min_equity_excess_cagr_pct": 0.0,
            "linear_full_attractiveness_equity_excess_cagr_pct": 10.0,
            "linear_add_band_tolerance_pct": 0.0,
            "linear_trim_band_tolerance_pct": 0.0,
            "action_min_executable_trade_amount": 0.0,
            "linear_high_extension_guardrail_enabled": False,
            "action_treat_cash_equivalents_as_cash": True,
            "action_cash_equivalent_symbols": "SGOV",
        }
        settings.update(overrides)
        web_server.save_action_plan_settings(conn, settings)

    def analysis_items(self, symbols=("NVDA", "MSFT")):
        return [
            {
                "symbol": symbol,
                "company_name": f"{symbol} Corp",
                "rating": "Buy",
                "current_price": 100.0,
                "expected_price": 160.0,
                "expected_cagr": 18.0,
                "upside": 60.0,
                "confidence_diff": 6.0,
                "bullish_confidence": 8.0,
                "bearish_confidence": 2.0,
                "core_confidence_diff": 6.0,
                "core_bullish_confidence": 8.0,
                "core_bearish_confidence": 2.0,
                "potential_confidence_diff": 4.0,
                "potential_bullish_confidence": 7.0,
                "potential_bearish_confidence": 1.0,
                "frontier_optionality_score": 0.0,
                "extension_risk": 1.0,
            }
            for symbol in symbols
        ]

    def build_plan(self, db_path, account_id, analysis_items=None):
        with mock.patch.object(web_server, "DB_PATH", db_path), \
             mock.patch.object(web_server, "list_analysis_symbols", return_value=analysis_items or self.analysis_items()):
            conn = web_server.get_db_connection()
            try:
                return web_server.build_action_plan(conn, account_id=account_id)
            finally:
                conn.close()

    def detail(self, db_path, account_id, symbol, analysis_items=None):
        with mock.patch.object(web_server, "DB_PATH", db_path), \
             mock.patch.object(web_server, "list_analysis_symbols", return_value=analysis_items or self.analysis_items()), \
             mock.patch.object(web_server, "get_analysis_detail", return_value=None):
            conn = web_server.get_db_connection()
            try:
                return web_server.get_action_plan_detail(conn, symbol, account_id=account_id)
            finally:
                conn.close()

    def row(self, payload, symbol):
        return next(item for item in payload["linear_action_plan"] if item["symbol"] == symbol)

    def account_specific_snapshot(self, payload, symbol):
        row = self.row(payload, symbol)
        summary = payload["summary"]
        linear_summary = summary["linear_summary"]
        keys = (
            "owned_share_quantity",
            "current_position_weight",
            "current_position_market_value",
            "total_portfolio_value",
            "target_weight_low",
            "target_weight_mid",
            "target_weight_high",
            "position_gap_to_mid",
            "target_gap_amount",
            "action_amount",
            "executable_action_amount",
            "suggested_share_count",
            "funding_status",
            "action",
        )
        return {
            "row": {key: row.get(key) for key in keys},
            "portfolio_value_used": summary.get("portfolio_value_used"),
            "actual_cash": summary.get("actual_cash"),
            "cash_equivalent_value": summary.get("cash_equivalent_value"),
            "cash_like_available": summary.get("cash_like_available"),
            "linear_available_buy_budget": linear_summary.get("available_buy_budget"),
            "linear_current_cash_unallocated": linear_summary.get("current_cash_unallocated"),
            "linear_target_reserve_amount": linear_summary.get("target_reserve_amount"),
        }

    def test_same_global_analysis_produces_account_specific_execution_without_aggregation(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "account-plan-isolation.db")
            self.init_db(db_path)
            conn = self.open_conn(db_path)
            try:
                self.save_settings(conn)
                self.save_state(
                    conn,
                    ACCOUNT_A,
                    positions=[
                        position("NVDA", 100, 10_000),
                        position("MSFT", 20, 2_000),
                        position("SGOV", 100, 10_000),
                    ],
                    portfolio_value=100_000,
                    actual_cash=5_000,
                )
                self.save_state(
                    conn,
                    ACCOUNT_B,
                    positions=[
                        position("NVDA", 25, 2_500),
                    ],
                    portfolio_value=250_000,
                    actual_cash=50_000,
                )
            finally:
                conn.close()

            plan_a = self.build_plan(db_path, ACCOUNT_A)
            plan_b = self.build_plan(db_path, ACCOUNT_B)
            nvda_a = self.row(plan_a, "NVDA")
            nvda_b = self.row(plan_b, "NVDA")
            msft_a = self.row(plan_a, "MSFT")
            msft_b = self.row(plan_b, "MSFT")

            self.assertEqual(plan_a["summary"]["portfolio_value_used"], 100_000)
            self.assertEqual(plan_b["summary"]["portfolio_value_used"], 250_000)
            self.assertNotEqual(plan_a["summary"]["portfolio_value_used"], 350_000)
            self.assertEqual(plan_a["summary"]["actual_cash"], 5_000)
            self.assertEqual(plan_b["summary"]["actual_cash"], 50_000)
            self.assertNotEqual(plan_a["summary"]["actual_cash"], 55_000)

            self.assertEqual(plan_a["summary"]["cash_equivalent_value"], 10_000)
            self.assertEqual(plan_b["summary"]["cash_equivalent_value"], 0)
            self.assertEqual(plan_a["summary"]["cash_like_available"], 15_000)
            self.assertEqual(plan_b["summary"]["cash_like_available"], 50_000)
            self.assertEqual(plan_a["summary"]["cash_equivalent_positions"], [{"symbol": "SGOV", "market_value": 10_000, "position": 100, "price": 100.0}])
            self.assertEqual(plan_b["summary"]["cash_equivalent_positions"], [])

            self.assertEqual(nvda_a["owned_share_quantity"], 100)
            self.assertEqual(nvda_b["owned_share_quantity"], 25)
            self.assertAlmostEqual(nvda_a["current_position_weight"], 10.0)
            self.assertAlmostEqual(nvda_b["current_position_weight"], 1.0)
            self.assertEqual(nvda_a["current_position_market_value"], 10_000)
            self.assertEqual(nvda_b["current_position_market_value"], 2_500)
            self.assertNotEqual(nvda_a["current_position_market_value"], 12_500)

            self.assertEqual(msft_a["owned_share_quantity"], 20)
            self.assertEqual(msft_b["owned_share_quantity"], 0)
            self.assertEqual(msft_b["current_position_market_value"], 0.0)
            self.assertEqual(msft_b["current_position_weight"], 0.0)

            self.assertAlmostEqual(nvda_a["linear_allocation_score"], nvda_b["linear_allocation_score"])
            self.assertAlmostEqual(msft_a["linear_allocation_score"], msft_b["linear_allocation_score"])
            self.assertNotEqual(
                nvda_a["target_weight_mid"] / 100.0 * plan_a["summary"]["portfolio_value_used"],
                nvda_b["target_weight_mid"] / 100.0 * plan_b["summary"]["portfolio_value_used"],
            )
            self.assertNotEqual(nvda_a["target_gap_amount"], nvda_b["target_gap_amount"])
            self.assertNotEqual(nvda_a["action"], nvda_b["action"])
            self.assertNotEqual(plan_a["summary"]["linear_summary"]["current_cash_unallocated"], plan_b["summary"]["linear_summary"]["current_cash_unallocated"])
            self.assertNotEqual(plan_a["summary"]["linear_summary"]["target_reserve_amount"], plan_b["summary"]["linear_summary"]["target_reserve_amount"])
            self.assertNotEqual(plan_a["summary"]["linear_summary"]["total_add_demand"], plan_b["summary"]["linear_summary"]["total_add_demand"])

    def test_cross_account_mutation_does_not_change_other_account_action_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "account-plan-mutation.db")
            self.init_db(db_path)
            conn = self.open_conn(db_path)
            try:
                self.save_settings(conn)
                self.save_state(
                    conn,
                    ACCOUNT_A,
                    positions=[position("NVDA", 100, 10_000), position("SGOV", 100, 10_000)],
                    portfolio_value=100_000,
                    actual_cash=5_000,
                )
                self.save_state(
                    conn,
                    ACCOUNT_B,
                    positions=[position("NVDA", 25, 2_500)],
                    portfolio_value=250_000,
                    actual_cash=50_000,
                )
            finally:
                conn.close()

            before_a = self.account_specific_snapshot(self.build_plan(db_path, ACCOUNT_A), "NVDA")

            conn = self.open_conn(db_path)
            try:
                self.save_state(
                    conn,
                    ACCOUNT_B,
                    positions=[position("NVDA", 5_000, 500_000), position("SGOV", 8_000, 800_000)],
                    portfolio_value=2_000_000,
                    actual_cash=500_000,
                )
            finally:
                conn.close()

            after_a = self.account_specific_snapshot(self.build_plan(db_path, ACCOUNT_A), "NVDA")
            self.assertEqual(after_a, before_a)

            before_b = self.account_specific_snapshot(self.build_plan(db_path, ACCOUNT_B), "NVDA")
            conn = self.open_conn(db_path)
            try:
                self.save_state(
                    conn,
                    ACCOUNT_A,
                    positions=[position("NVDA", 1, 100), position("SGOV", 0, 0)],
                    portfolio_value=1_000,
                    actual_cash=10,
                )
            finally:
                conn.close()

            after_b = self.account_specific_snapshot(self.build_plan(db_path, ACCOUNT_B), "NVDA")
            self.assertEqual(after_b, before_b)

    def test_action_plan_detail_matches_selected_account_parent_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "account-plan-detail.db")
            self.init_db(db_path)
            conn = self.open_conn(db_path)
            try:
                self.save_settings(conn)
                self.save_state(conn, ACCOUNT_A, positions=[position("NVDA", 100, 10_000)], portfolio_value=100_000, actual_cash=5_000)
                self.save_state(conn, ACCOUNT_B, positions=[position("NVDA", 25, 2_500)], portfolio_value=250_000, actual_cash=50_000)
            finally:
                conn.close()

            for account_id in (ACCOUNT_A, ACCOUNT_B):
                with self.subTest(account_id=account_id):
                    plan = self.build_plan(db_path, account_id, analysis_items=self.analysis_items(("NVDA",)))
                    row = self.row(plan, "NVDA")
                    detail = self.detail(db_path, account_id, "NVDA", analysis_items=self.analysis_items(("NVDA",)))
                    self.assertIsNotNone(detail)
                    for key in (
                        "owned_share_quantity",
                        "current_position_weight",
                        "current_position_market_value",
                        "target_weight_low",
                        "target_weight_mid",
                        "target_weight_high",
                        "target_gap_amount",
                        "action",
                        "action_amount",
                        "executable_action_amount",
                        "suggested_share_count",
                        "funding_status",
                        "total_portfolio_value",
                    ):
                        self.assertEqual(detail[key], row[key])
                    self.assertEqual(detail["summary"], plan["summary"]["linear_summary"])

    def test_action_plan_detail_uses_selected_account_cash_funding_diagnostics(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "account-plan-detail-cash.db")
            self.init_db(db_path)
            conn = self.open_conn(db_path)
            try:
                self.save_settings(
                    conn,
                    action_min_cash_unallocated_target=0.0,
                    linear_max_reserve_pct=0.0,
                )
                self.save_state(
                    conn,
                    ACCOUNT_A,
                    positions=[position("NVDA", 100, 10_000), position("SGOV", 100, 10_000)],
                    portfolio_value=100_000,
                    actual_cash=5_000,
                )
                self.save_state(
                    conn,
                    ACCOUNT_B,
                    positions=[position("NVDA", 25, 2_500)],
                    portfolio_value=250_000,
                    actual_cash=50_000,
                )
            finally:
                conn.close()

            plan_a = self.build_plan(db_path, ACCOUNT_A, analysis_items=self.analysis_items(("NVDA",)))
            plan_b = self.build_plan(db_path, ACCOUNT_B, analysis_items=self.analysis_items(("NVDA",)))
            detail_a = self.detail(db_path, ACCOUNT_A, "NVDA", analysis_items=self.analysis_items(("NVDA",)))
            detail_b = self.detail(db_path, ACCOUNT_B, "NVDA", analysis_items=self.analysis_items(("NVDA",)))

            self.assertEqual(plan_a["summary"]["actual_cash"], 5_000)
            self.assertEqual(plan_b["summary"]["actual_cash"], 50_000)
            self.assertEqual(plan_a["summary"]["cash_equivalent_value"], 10_000)
            self.assertEqual(plan_b["summary"]["cash_equivalent_value"], 0)
            self.assertEqual(plan_a["summary"]["cash_equivalent_positions"], [{"symbol": "SGOV", "market_value": 10_000, "position": 100, "price": 100.0}])
            self.assertEqual(plan_b["summary"]["cash_equivalent_positions"], [])

            self.assertEqual(detail_a["summary"], plan_a["summary"]["linear_summary"])
            self.assertEqual(detail_b["summary"], plan_b["summary"]["linear_summary"])
            self.assertEqual(detail_a["summary"]["cash_like_available"], 15_000)
            self.assertEqual(detail_b["summary"]["cash_like_available"], 50_000)
            self.assertEqual(detail_a["summary"]["current_cash_unallocated"], 15_000)
            self.assertEqual(detail_b["summary"]["current_cash_unallocated"], 50_000)
            self.assertEqual(detail_a["summary"]["available_buy_budget"], 15_000)
            self.assertEqual(detail_b["summary"]["available_buy_budget"], 50_000)
            self.assertEqual(detail_a["summary"]["cash_available_for_linear_buys"], 15_000)
            self.assertEqual(detail_b["summary"]["cash_available_for_linear_buys"], 50_000)
            self.assertEqual(detail_a["summary"]["target_reserve_amount"], 0)
            self.assertEqual(detail_b["summary"]["target_reserve_amount"], 0)
            self.assertNotEqual(detail_a["summary"]["cash_like_available"], detail_b["summary"]["cash_like_available"])

    def test_same_symbol_can_trim_in_one_account_and_add_in_another(self):
        analysis_items = self.analysis_items(("NVDA",))
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "account-plan-trim-add.db")
            self.init_db(db_path)
            conn = self.open_conn(db_path)
            try:
                self.save_settings(
                    conn,
                    linear_allocated_target_total_pct=10.0,
                    action_min_cash_unallocated_target=0.0,
                    linear_max_reserve_pct=0.0,
                )
                self.save_state(conn, ACCOUNT_A, positions=[position("NVDA", 200, 20_000)], portfolio_value=100_000, actual_cash=5_000)
                self.save_state(conn, ACCOUNT_B, positions=[position("NVDA", 10, 1_000)], portfolio_value=100_000, actual_cash=50_000)
            finally:
                conn.close()

            row_a = self.row(self.build_plan(db_path, ACCOUNT_A, analysis_items=analysis_items), "NVDA")
            row_b = self.row(self.build_plan(db_path, ACCOUNT_B, analysis_items=analysis_items), "NVDA")

            self.assertEqual(row_a["action"], "Trim")
            self.assertEqual(row_a["action_amount_direction"], "trim")
            self.assertGreater(row_a["suggested_share_count"], 0)
            self.assertEqual(row_b["action"], "Add")
            self.assertEqual(row_b["action_amount_direction"], "add")
            self.assertGreater(row_b["suggested_share_count"], 0)
            self.assertNotEqual(row_b["suggested_share_count"], row_a["suggested_share_count"])

    def test_whole_share_sizing_uses_selected_account_exact_target_gap(self):
        analysis_items = self.analysis_items(("NVDA",))
        analysis_items[0]["current_price"] = 137.0
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "account-plan-whole-share-sizing.db")
            self.init_db(db_path)
            conn = self.open_conn(db_path)
            try:
                self.save_settings(
                    conn,
                    linear_allocated_target_total_pct=20.0,
                    action_min_cash_unallocated_target=0.0,
                    linear_max_reserve_pct=0.0,
                    linear_add_band_tolerance_pct=0.0,
                    linear_trim_band_tolerance_pct=0.0,
                )
                self.save_state(
                    conn,
                    ACCOUNT_A,
                    positions=[position("NVDA", 73, 10_000, price=137.0)],
                    portfolio_value=100_000,
                    actual_cash=50_000,
                )
            finally:
                conn.close()

            row = self.row(self.build_plan(db_path, ACCOUNT_A, analysis_items=analysis_items), "NVDA")

            self.assertEqual(row["action"], "Add")
            self.assertEqual(row["action_amount_direction"], "add")
            self.assertEqual(row["current_position_market_value"], 10_000)
            self.assertAlmostEqual(row["current_position_weight"], 10.0)
            self.assertAlmostEqual(row["target_weight_mid"], 20.0)
            self.assertAlmostEqual(row["target_gap_amount"], 10_000.0)
            self.assertEqual(row["suggested_share_count"], 72)
            self.assertAlmostEqual(row["executable_action_amount"], 9_864.0)
            self.assertEqual(row["funding_status"], "Fully funded")

    def test_build_action_plan_passes_selected_account_to_portfolio_loaders(self):
        original_load_positions = web_server.load_positions_cache
        original_cash_summary = web_server.build_portfolio_cash_summary
        original_load_summary = web_server.load_portfolio_summary_cache

        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "account-plan-loader-account-id.db")
            self.init_db(db_path)
            conn = self.open_conn(db_path)
            try:
                self.save_settings(conn)
                self.save_state(conn, ACCOUNT_A, positions=[position("NVDA", 100, 10_000)], portfolio_value=100_000, actual_cash=5_000)
                self.save_state(conn, ACCOUNT_B, positions=[position("NVDA", 25, 2_500)], portfolio_value=250_000, actual_cash=50_000)
            finally:
                conn.close()

            with mock.patch.object(web_server, "load_positions_cache", wraps=original_load_positions) as load_positions_mock, \
                 mock.patch.object(web_server, "build_portfolio_cash_summary", wraps=original_cash_summary) as cash_summary_mock, \
                 mock.patch.object(web_server, "load_portfolio_summary_cache", wraps=original_load_summary) as load_summary_mock:
                for account_id in (ACCOUNT_A, ACCOUNT_B):
                    with self.subTest(account_id=account_id):
                        self.build_plan(db_path, account_id, analysis_items=self.analysis_items(("NVDA",)))

                        for helper_mock in (load_positions_mock, cash_summary_mock, load_summary_mock):
                            self.assertGreaterEqual(helper_mock.call_count, 1)
                            self.assertTrue(
                                all(call.kwargs.get("account_id") == account_id for call in helper_mock.call_args_list),
                                helper_mock.call_args_list,
                            )

                        load_positions_mock.reset_mock()
                        cash_summary_mock.reset_mock()
                        load_summary_mock.reset_mock()


if __name__ == "__main__":
    unittest.main()
