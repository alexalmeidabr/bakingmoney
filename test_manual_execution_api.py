import os
import tempfile
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest import mock

import web_server
from test_manual_execution_engine import linear_settings
from test_multi_account_portfolio_db import FakeIB, FakePosition, FakeSummaryItem
from test_manual_quote_observation import PacketIB


class ManualExecutionApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db_path = os.path.join(self.temp.name, "manual-api.db")
        patch = mock.patch.object(web_server, "DB_PATH", self.db_path)
        patch.start()
        self.addCleanup(patch.stop)
        web_server.init_db()
        self.conn = web_server.get_db_connection()
        self.addCleanup(lambda: self.conn.close())
        web_server.save_action_plan_settings(self.conn, linear_settings())
        for account, quantity, total, cash in (
            ("U_ACCOUNT_A", 1, 100_000, 20_000),
            ("U_ACCOUNT_B", 2, 200_000, 30_000),
        ):
            timestamp = web_server.utc_now_iso()
            web_server.save_positions_cache(self.conn, [{
                "symbol": "AAA", "position": quantity, "price": 100.0,
                "avgCost": 80.0, "marketValue": quantity * 100.0,
                "contract_key": f"test:{account}:AAA", "price_status": "tws_received",
                "price_source": "marketPrice", "price_last_successful_at": timestamp,
            }], account_id=account)
            web_server._session_received_quotes[(self.db_path, account)] = {
                "AAA": (f"test:{account}:AAA", timestamp),
            }
            self.addCleanup(web_server._session_received_quotes.pop, (self.db_path, account), None)
            web_server._session_manual_verified_quotes[(self.db_path, account)] = {
                "AAA": {
                    "source": "live_bid_ask", "contract_key": f"test:{account}:AAA",
                    "bid": 99.0, "ask": 100.0,
                    "bid_tick_at": timestamp, "ask_tick_at": timestamp, "refresh_at": timestamp,
                },
            }
            self.addCleanup(web_server._session_manual_verified_quotes.pop, (self.db_path, account), None)
            web_server.save_portfolio_summary_cache(self.conn, {
                "base_currency": "USD", "net_liquidation": total, "actual_cash": cash,
            }, account_id=account)
        self.analysis_items = [
            {
                "symbol": symbol, "company_name": symbol,
                "rating": "Buy", "current_price": 100.0, "expected_price": 160.0,
                "expected_cagr": 18.0, "upside": 60.0,
                "core_confidence_diff": 6.0, "core_bullish_confidence": 8.0,
                "core_bearish_confidence": 2.0,
                "potential_confidence_diff": 4.0, "potential_bullish_confidence": 7.0,
                "potential_bearish_confidence": 1.0, "extension_risk": 1.0,
            }
            for symbol in ("AAA", "BBB")
        ]

    def build(self, account, both=False):
        with mock.patch.object(web_server, "list_analysis_symbols", return_value=self.analysis_items):
            return web_server.build_action_plan(self.conn, account_id=account, include_manual_execution=both)

    def test_opt_in_keeps_default_payload_exact_and_reuses_one_analysis_list(self):
        web_server.save_manual_execution_trigger(self.conn, "U_ACCOUNT_A", "AAA", {
            "buy_trigger_price": 80, "reserve_enabled": True, "reserve_percentage": 60,
        })
        with mock.patch.object(web_server, "list_analysis_symbols", return_value=self.analysis_items) as analysis_list:
            default = web_server.build_action_plan(self.conn, account_id="U_ACCOUNT_A")
            self.assertEqual(analysis_list.call_count, 1)
            both = web_server.build_action_plan(self.conn, account_id="U_ACCOUNT_A", include_manual_execution=True)
            self.assertEqual(analysis_list.call_count, 2)
        self.assertEqual({key: value for key, value in both.items() if key != "manual_execution"}, default)
        self.assertNotIn("manual_execution", default)
        base = {row["symbol"]: row for row in both["linear_action_plan"]}
        manual = {row["symbol"]: row for row in both["manual_execution"]["linear_action_plan"]}
        self.assertEqual(manual["AAA"]["manual_trigger_status"], "waiting")
        self.assertEqual(manual["AAA"]["recommended_action"], base["AAA"]["desired_action"])
        for field in ("rating", "expected_cagr", "upside", "target_weight_low", "target_weight_mid", "target_weight_high", "linear_allocation_score"):
            self.assertEqual(manual["AAA"][field], base["AAA"][field], field)
        self.assertEqual(manual["AAA"]["executable_action_amount"], 0)

    def test_same_symbol_preferences_and_reservations_stay_in_selected_account(self):
        web_server.save_manual_execution_trigger(self.conn, "U_ACCOUNT_A", "AAA", {
            "buy_trigger_price": 80, "reserve_enabled": True, "reserve_percentage": 60,
        })
        web_server.save_manual_execution_trigger(self.conn, "U_ACCOUNT_B", "AAA", {
            "buy_trigger_price": 120, "reserve_enabled": True, "reserve_percentage": 100,
        })
        a = self.build("U_ACCOUNT_A", both=True)["manual_execution"]
        b = self.build("U_ACCOUNT_B", both=True)["manual_execution"]
        a_row = next(row for row in a["linear_action_plan"] if row["symbol"] == "AAA")
        b_row = next(row for row in b["linear_action_plan"] if row["symbol"] == "AAA")
        self.assertEqual(a_row["owned_share_quantity"], 1)
        self.assertEqual(b_row["owned_share_quantity"], 2)
        self.assertEqual(a_row["manual_trigger_status"], "waiting")
        self.assertEqual(b_row["manual_trigger_status"], "eligible")
        self.assertGreater(a_row["requested_reservation"], 0)
        self.assertEqual(b_row["requested_reservation"], 0)

    def test_unowned_analysis_price_requires_confirmation_without_tws_request(self):
        web_server.save_manual_execution_trigger(self.conn, "U_ACCOUNT_A", "BBB", {
            "buy_trigger_price": 120, "reserve_enabled": True, "reserve_percentage": 50,
        })
        with mock.patch.object(web_server, "fetch_ib_prices", side_effect=AssertionError("Action Plan GET must not fetch TWS")), \
             mock.patch.object(web_server, "get_ib_connection", side_effect=AssertionError("Action Plan GET must not connect")):
            payload = self.build("U_ACCOUNT_A", both=True)
        row = next(row for row in payload["manual_execution"]["linear_action_plan"] if row["symbol"] == "BBB")
        self.assertEqual(row["manual_trigger_status"], "price_confirmation_required")
        self.assertIsNone(row["manual_verified_price"])
        self.assertEqual(row["executable_action_amount"], 0)
        self.assertGreater(row["requested_reservation"], 0)
        self.assertIn("BBB", payload["manual_execution"]["price_verification"]["confirmation_required_symbols"])

    def test_opt_in_with_no_account_keeps_empty_baseline(self):
        empty_path = os.path.join(self.temp.name, "empty.db")
        with mock.patch.object(web_server, "DB_PATH", empty_path):
            web_server.init_db()
            conn = web_server.get_db_connection()
            try:
                with mock.patch.object(web_server, "list_analysis_symbols", return_value=[]):
                    default = web_server.build_action_plan(conn)
                    both = web_server.build_action_plan(conn, include_manual_execution=True)
            finally:
                conn.close()
        self.assertEqual({key: value for key, value in both.items() if key != "manual_execution"}, default)
        self.assertEqual(both["manual_execution"]["linear_action_plan"], [])

    def test_positions_refresh_records_account_scoped_live_tick_proof(self):
        position = FakePosition("U_ACCOUNT_A", "AAA", 1, 80, 1)
        tick_at = datetime.now(timezone.utc)
        market = PacketIB(position.contract, [
            ("bid", 99.0, 10, tick_at), ("ask", 101.0, 10, tick_at),
        ])
        ib = FakeIB(
            positions=[position], managed_accounts=["U_ACCOUNT_A"],
            summary_items=[FakeSummaryItem("U_ACCOUNT_A", "NetLiquidation", "100000"),
                           FakeSummaryItem("U_ACCOUNT_A", "CashBalance", "20000")],
        )
        for name in ("pendingTickersEvent", "errorEvent", "reqMktData", "sleep", "cancelMktData"):
            setattr(ib, name, getattr(market, name))
        handler = SimpleNamespace()
        handler._send_json = lambda payload, status=200: setattr(handler, "response", (status, payload))
        with mock.patch.object(web_server, "ensure_event_loop", return_value=None), \
             mock.patch.object(web_server, "get_ib_connection", return_value=ib), \
             mock.patch.object(web_server, "get_ib_price_wait_seconds", return_value=0.05), \
             mock.patch.object(web_server, "list_analysis_symbols", return_value=[]):
            web_server.BakingMoneyHandler.handle_positions_api(handler, refresh=True, account_id="U_ACCOUNT_A")
        self.assertEqual(handler.response[0], 200)
        self.assertEqual(market.ticker.ticks, [])
        self.assertEqual(len(market.pendingTickersEvent.handlers), 0)
        proof = web_server._session_manual_verified_quotes[(self.db_path, "U_ACCOUNT_A")]["AAA"]
        self.assertEqual((proof["bid"], proof["ask"]), (99, 101))
        self.assertEqual(web_server._session_manual_verified_quotes[(self.db_path, "U_ACCOUNT_B")]["AAA"]["ask"], 100)
        web_server.save_manual_execution_trigger(self.conn, "U_ACCOUNT_A", "AAA", {"buy_trigger_price": 102})
        row = next(item for item in self.build("U_ACCOUNT_A", both=True)["manual_execution"]["linear_action_plan"]
                   if item["symbol"] == "AAA")
        self.assertEqual(row["manual_trigger_status"], "eligible")
        self.assertEqual(row["manual_verified_price"], 101)
        with mock.patch.object(web_server, "ensure_event_loop", return_value=None), \
             mock.patch.object(web_server, "get_ib_connection", side_effect=RuntimeError("TWS offline")), \
             mock.patch.object(web_server, "list_analysis_symbols", return_value=[]):
            web_server.BakingMoneyHandler.handle_positions_api(handler, refresh=True, account_id="U_ACCOUNT_A")
        self.assertNotIn((self.db_path, "U_ACCOUNT_A"), web_server._session_manual_verified_quotes)
        self.assertIn("AAA", web_server._session_manual_verified_quotes[(self.db_path, "U_ACCOUNT_B")])

    def test_trigger_aware_details_match_list_and_unavailable_account_is_rejected(self):
        web_server.save_manual_execution_trigger(self.conn, "U_ACCOUNT_A", "AAA", {"buy_trigger_price": 80})
        with mock.patch.object(web_server, "list_analysis_symbols", return_value=self.analysis_items) as analysis_list, \
             mock.patch.object(web_server, "get_analysis_detail", return_value=None):
            details = web_server.get_manual_action_plan_details(self.conn, "AAA", account_id="U_ACCOUNT_A")
            self.assertEqual(analysis_list.call_count, 1)
        self.assertEqual(details["action_detail"]["symbol"], "AAA")
        self.assertEqual(details["manual_execution_detail"]["manual_trigger_status"], "waiting")
        web_server.upsert_ib_account(self.conn, "U_UNAVAILABLE")
        self.conn.commit()
        with self.assertRaises(web_server.PortfolioDataUnavailableError):
            self.build("U_UNAVAILABLE", both=True)

    def test_action_plan_handlers_expose_both_only_when_opted_in(self):
        class Capture(web_server.BakingMoneyHandler):
            def _send_json(self, payload, status=200):
                self.payload = payload
                self.status = status

        handler = Capture.__new__(Capture)
        with mock.patch.object(web_server, "list_analysis_symbols", return_value=self.analysis_items), \
             mock.patch.object(web_server, "get_analysis_detail", return_value=None):
            web_server.BakingMoneyHandler.handle_action_plan_get(handler, account_id="U_ACCOUNT_A")
            self.assertNotIn("manual_execution", handler.payload)
            web_server.BakingMoneyHandler.handle_action_plan_get(handler, account_id="U_ACCOUNT_A", execution_modes="both")
            self.assertIn("manual_execution", handler.payload)
            web_server.BakingMoneyHandler.handle_action_plan_detail_get(handler, "AAA", account_id="U_ACCOUNT_A", execution_modes="both")
            self.assertIn("manual_execution_detail", handler.payload)
            web_server.BakingMoneyHandler.handle_action_plan_get(handler, account_id="U_ACCOUNT_A", execution_modes="invalid")
            self.assertEqual(handler.status, 400)

    def test_get_put_and_delete_routes_forward_selected_account_and_execution_mode(self):
        class Capture(web_server.BakingMoneyHandler):
            def handle_action_plan_get(self, account_id=None, execution_modes=None):
                self.called = ("plan", account_id, execution_modes)

            def handle_action_plan_detail_get(self, symbol, account_id=None, execution_modes=None):
                self.called = ("detail", symbol, account_id, execution_modes)

            def handle_manual_execution_triggers_get(self, account_id=None):
                self.called = ("list", account_id)

            def handle_manual_execution_trigger_get(self, symbol, account_id=None):
                self.called = ("get", symbol, account_id)

            def handle_manual_execution_trigger_put(self, symbol, account_id=None):
                self.called = ("put", symbol, account_id)

            def handle_manual_execution_trigger_delete(self, symbol, account_id=None):
                self.called = ("delete", symbol, account_id)

        handler = Capture.__new__(Capture)
        for method, path, expected in (
            ("do_GET", "/api/action-plan?execution_modes=both&account_id=U_ACCOUNT_A", ("plan", "U_ACCOUNT_A", "both")),
            ("do_GET", "/api/action-plan/AAA?execution_modes=both&account_id=U_ACCOUNT_A", ("detail", "AAA", "U_ACCOUNT_A", "both")),
            ("do_GET", "/api/manual-execution-triggers?account_id=U_ACCOUNT_A", ("list", "U_ACCOUNT_A")),
            ("do_GET", "/api/manual-execution-triggers/AAA?account_id=U_ACCOUNT_A", ("get", "AAA", "U_ACCOUNT_A")),
            ("do_PUT", "/api/manual-execution-triggers/AAA?account_id=U_ACCOUNT_A", ("put", "AAA", "U_ACCOUNT_A")),
            ("do_DELETE", "/api/manual-execution-triggers/AAA?account_id=U_ACCOUNT_A", ("delete", "AAA", "U_ACCOUNT_A")),
        ):
            with self.subTest(method=method, path=path):
                handler.path = path
                getattr(web_server.BakingMoneyHandler, method)(handler)
                self.assertEqual(handler.called, expected)


if __name__ == "__main__":
    unittest.main()
