import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import action_plan_prices as prices


OLD = "2024-01-02T10:00:00+00:00"
NEW = "2024-01-03T10:00:00+00:00"
POSITION = dict(symbol="ABC", contract_key="1", price=20, price_status="cached_stale",
                price_source="last", price_last_successful_at=OLD)
QUOTE = dict(symbol="ABC", contract_key="1", bid=19, ask=21, source="live_bid_ask",
             refresh_at=OLD, bid_tick_at=OLD, ask_tick_at=OLD)
DELAYED = dict(symbol="ABC", contract_key="1", price=22, price_source="delayed_last",
               price_last_successful_at=NEW)


class PriceResolution(unittest.TestCase):
    def test_newer_delayed_price_beats_older_live_sides(self):
        for items in ([QUOTE, DELAYED], [DELAYED, QUOTE]):
            selected = prices.resolve_price(POSITION, {}, items)
            self.assertEqual((22, "delayed_last", NEW), (selected["price"], selected["price_source"],
                             selected["price_last_successful_at"]))
            self.assertIsNone(selected.get("manual_quote_proof"))
            self.assertTrue(selected["price_warning"])

    def test_side_prices_and_cached_price_conditions(self):
        for observations, action, threshold, expected_price, status in [
            ([QUOTE], "Add", 20, 21, "waiting"), ([QUOTE], "Trim", 19, 19, "eligible"),
            ([], "Starter Buy", 20, 20, "eligible"), ([], "Sell", 20, 20, "eligible"),
            ([], "Strong Add", 19, 20, "waiting"),
        ]:
            selected = prices.resolve_price(POSITION, {}, observations)
            row = dict(selected, current_price=selected["price"], action=action)
            evaluation = prices.evaluate_trigger(row, dict(buy_trigger_price=threshold, sell_trigger_price=threshold))
            self.assertEqual((status, expected_price, OLD, None), (
                evaluation["status"], evaluation["verified_price"], evaluation["verified_quote_at"],
                evaluation["verified_quote_expires_at"]))
            self.assertTrue(evaluation["verification_reason"])

    def test_no_price_and_analysis_and_missing_time(self):
        for invalid in (True, 0, -1, float("nan"), float("inf"), "bogus"):
            selected = prices.resolve_price({"price": invalid}, {"current_price": invalid})
            self.assertIsNone(selected["price"])
            self.assertEqual("price_unavailable", prices.evaluate_trigger(
                dict(action="Add", current_price=selected["price"]), {"buy_trigger_price": 1})["status"])
        selected = prices.resolve_price({}, {"current_price": 10})
        self.assertEqual(("analysis_fallback", 10), (selected["price_source"], selected["price"]))
        unknown = dict(POSITION, price_last_successful_at=None)
        self.assertIsNone(prices.resolve_price(unknown, {})["price_last_successful_at"])
        self.assertEqual(22, prices.resolve_price(unknown, {}, [DELAYED])["price"])

    def test_identity(self):
        for mismatched in (dict(DELAYED, contract_key="2"), dict(DELAYED, symbol="OTHER")):
            self.assertEqual(20, prices.resolve_price(POSITION, {}, [mismatched])["price"])

    def test_unknown_contract_or_wrong_account_cannot_supply_owned_price(self):
        for raw in (dict(DELAYED, contract_key=None), dict(DELAYED, account_id="B")):
            self.assertEqual(20, prices.resolve_price(dict(POSITION, account_id="A"), {}, [raw])["price"])

    def test_fresh_live_sides_display_source_and_do_not_warn(self):
        now = datetime.now(timezone.utc)
        stamp = now.isoformat()
        quote = dict(QUOTE, refresh_at=stamp, bid_tick_at=stamp, ask_tick_at=stamp)
        selected = prices.resolve_price({}, {}, [quote])
        evaluation = prices.evaluate_trigger(dict(selected, action="Trim", current_price=selected["price"]),
                                              {"sell_trigger_price": 19}, now)
        self.assertEqual(("eligible", "live_bid_ask (bid)", stamp, None),
                         (evaluation["status"], evaluation["price_source"], evaluation["verified_quote_at"],
                          evaluation["verification_reason"]))

    def test_direct_evaluator_discards_older_side_price(self):
        row = dict(action="Add", current_price=22, price_source="delayed_last",
                   price_last_successful_at=NEW, manual_quote_proof=QUOTE)
        result = prices.evaluate_trigger(row, {"buy_trigger_price": 21})
        self.assertEqual(("waiting", 22, NEW), (result["status"], result["verified_price"], result["verified_quote_at"]))

    def test_restart_backup_failed_and_out_of_order_refresh(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "prices.db"
            with sqlite3.connect(path) as conn:
                prices.init_schema(conn)
                prices.persist_observation(conn, "A", "ABC", DELAYED)
                prices.persist_observation(conn, "B", "ABC", QUOTE)
                prices.persist_observation(conn, "A", "ABC", QUOTE)
                prices.persist_observation(conn, "A", "ABC", {"price": 0})
            conn.close()
            with sqlite3.connect(path) as reopened, sqlite3.connect(":memory:") as backup:
                reopened.backup(backup)
                for account, expected in (("A", 22), ("B", 20)):
                    saved = prices.load_observations(backup, account)["ABC"]
                    self.assertEqual(expected, prices.resolve_price({}, {}, [saved])["price"])
                self.assertFalse(prices.load_observations(backup, "C"))
            reopened.close()
