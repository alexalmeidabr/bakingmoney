import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import action_plan_prices as prices


OLD = "2024-01-02T10:00:00+00:00"
NEW = "2024-01-03T10:00:00+00:00"
LATER_RETRIEVAL = "2024-01-04T10:00:00+00:00"
POSITION = dict(symbol="ABC", contract_key="1", price=20, price_status="cached_stale",
                price_source="last", market_observed_at=OLD, retrieved_at=OLD)
QUOTE = dict(symbol="ABC", contract_key="1", bid=19, ask=21, source="live_bid_ask",
             refresh_at=OLD, bid_tick_at=OLD, ask_tick_at=OLD)
DELAYED = dict(symbol="ABC", contract_key="1", price=22, price_source="delayed_last",
               market_observed_at=NEW, retrieved_at=NEW)


class PriceResolution(unittest.TestCase):
    def test_persistence_isolated_by_contract_and_account(self):
        with sqlite3.connect(":memory:") as conn:
            prices.init_schema(conn)
            self.assertTrue(prices.persist_observation(conn, "A", "ABC", {
                "symbol": "ABC", "contract_key": "conid:111", "price": 100,
                "price_source": "last", "market_observed_at": OLD,
            }))
            self.assertTrue(prices.persist_observation(conn, "A", "ABC", {
                "symbol": "ABC", "contract_key": "conid:222", "price": 105,
                "price_source": "last", "market_observed_at": NEW,
            }))
            self.assertTrue(prices.persist_observation(conn, "B", "ABC", {
                "symbol": "ABC", "contract_key": "conid:111", "price": 200,
                "price_source": "last", "market_observed_at": NEW,
            }))
            self.assertFalse(prices.persist_observation(conn, "A", "ABC", {
                "symbol": "ABC", "contract_key": "conid:111", "price": 90,
                "price_source": "last", "market_observed_at": "2024-01-01T10:00:00+00:00",
            }))
            self.assertTrue(prices.persist_observation(conn, "A", "ABC", {
                "symbol": "ABC", "contract_key": "conid:111", "price": 110,
                "price_source": "last", "market_observed_at": LATER_RETRIEVAL,
            }))
            self.assertTrue(prices.persist_observation(conn, "A", "ABC", {
                "symbol": "ABC", "price": 80, "price_source": "cached",
                "retrieved_at": LATER_RETRIEVAL,
            }))
            account_a = prices.load_observations(conn, "A")["ABC"]
            account_b = prices.load_observations(conn, "B")["ABC"]
        self.assertEqual({None, "conid:111", "conid:222"}, {row["contract_key"] for row in account_a})
        self.assertEqual({110, 105, 80}, {row["price"] for row in account_a})
        self.assertEqual([(200, "conid:111")], [(row["price"], row["contract_key"]) for row in account_b])

    def test_owned_resolution_uses_exact_contract_and_unowned_prefers_known_identity(self):
        observations = [
            dict(POSITION, contract_key="conid:111", price=100, market_observed_at=OLD),
            dict(POSITION, contract_key="conid:222", price=105, market_observed_at=NEW),
            dict(POSITION, contract_key=None, price=999, market_observed_at=LATER_RETRIEVAL, persisted=True),
        ]
        owned = prices.resolve_price({"symbol": "ABC", "contract_key": "conid:111"}, {}, observations)
        unowned = prices.resolve_price({}, {"symbol": "ABC"}, observations)
        legacy = prices.resolve_price({}, {"symbol": "ABC"}, [observations[-1]])
        self.assertEqual((100, "conid:111"), (owned["price"], owned["contract_key"]))
        self.assertEqual((105, "conid:222"), (unowned["price"], unowned["contract_key"]))
        self.assertEqual(999, legacy["price"])
        self.assertIn("contract identity is unknown", legacy["price_warning"].lower())

    def test_newer_live_observation_beats_older_close_retrieved_later(self):
        live = dict(POSITION, price=100, market_observed_at=NEW, retrieved_at=NEW)
        close = dict(POSITION, price=95, price_source="close", market_observed_at=OLD,
                     retrieved_at=LATER_RETRIEVAL)
        selected = prices.resolve_price(live, {}, [close])
        self.assertEqual((100, NEW, NEW, "market_observation"), (
            selected["price"], selected["market_observed_at"], selected["retrieved_at"],
            selected["price_timestamp_kind"],
        ))

    def test_newer_delayed_price_beats_older_live_sides(self):
        for items in ([QUOTE, DELAYED], [DELAYED, QUOTE]):
            selected = prices.resolve_price(POSITION, {}, items)
            self.assertEqual((22, "delayed_last", NEW), (selected["price"], selected["price_source"],
                             selected["price_last_successful_at"]))
            self.assertIsNone(selected.get("manual_quote_proof"))
            self.assertTrue(selected["price_warning"])

    def test_equal_market_times_use_documented_source_quality(self):
        cases = [
            (dict(POSITION, price=100, price_source="last", price_status="tws_received"),
             dict(POSITION, price=101, price_source="delayed_last", price_status="tws_received"), 100, "last"),
            (dict(POSITION, price=100, price_source="delayed_last", delayed=True, price_status="tws_received"),
             dict(POSITION, price=101, price_source="frozen_last", price_status="tws_received"), 100, "delayed_last"),
            (dict(POSITION, price=100, price_source="frozen_last", price_status="tws_received"),
             dict(POSITION, price=101, price_source="delayed_frozen_last", delayed=True,
                  price_status="tws_received"), 100, "frozen_last"),
        ]
        for first, second, expected_price, expected_source in cases:
            with self.subTest(first=first["price_source"], second=second["price_source"]):
                selected = prices.resolve_price({}, {}, [second, first])
                self.assertEqual((expected_price, expected_source),
                                 (selected["price"], selected["price_source"]))

    def test_unknown_time_uses_source_quality_before_retrieval_time(self):
        frozen = dict(symbol="ABC", contract_key="1", price=95, price_source="frozen_close",
                      retrieved_at=LATER_RETRIEVAL)
        live = dict(symbol="ABC", contract_key="1", price=100, price_source="last",
                    retrieved_at=OLD)
        selected = prices.resolve_price({}, {}, [frozen, live])
        self.assertEqual((100, "last", None, OLD, "retrieval"), (
            selected["price"], selected["price_source"], selected["market_observed_at"],
            selected["retrieved_at"], selected["price_timestamp_kind"],
        ))

    def test_cached_known_time_beats_refreshed_unknown_time(self):
        cached = dict(POSITION, persisted=True, price=100, market_observed_at=NEW,
                      retrieved_at=NEW)
        refreshed = dict(POSITION, price=105, price_source="last", market_observed_at=None,
                         retrieved_at=LATER_RETRIEVAL)
        selected = prices.resolve_price({}, {}, [refreshed, cached])
        self.assertEqual((100, NEW, "market_observation"), (
            selected["price"], selected["market_observed_at"], selected["price_timestamp_kind"],
        ))

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
        unknown = dict(POSITION, market_observed_at=None, retrieved_at=None)
        resolved_unknown = prices.resolve_price(unknown, {})
        self.assertIsNone(resolved_unknown["price_last_successful_at"])
        self.assertEqual("unknown", resolved_unknown["price_timestamp_kind"])
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
                   market_observed_at=NEW, retrieved_at=NEW, manual_quote_proof=QUOTE)
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
                    self.assertEqual(expected, prices.resolve_price({}, {}, saved)["price"])
                self.assertFalse(prices.load_observations(backup, "C"))
            reopened.close()

    def test_legacy_timestamp_migrates_as_retrieval_not_market_observation(self):
        with sqlite3.connect(":memory:") as conn:
            conn.execute("""
                CREATE TABLE action_plan_price_observations (
                    account_id TEXT NOT NULL, symbol TEXT NOT NULL, contract_key TEXT,
                    price REAL NOT NULL, price_source TEXT NOT NULL,
                    price_last_successful_at TEXT, bid REAL, ask REAL,
                    bid_tick_at TEXT, ask_tick_at TEXT, delayed INTEGER NOT NULL,
                    price_warning TEXT, PRIMARY KEY(account_id, symbol)
                )
            """)
            conn.execute("""
                INSERT INTO action_plan_price_observations
                VALUES ('A','ABC','1',95,'close',?,NULL,NULL,NULL,NULL,0,NULL)
            """, (LATER_RETRIEVAL,))
            conn.execute("""
                INSERT INTO action_plan_price_observations
                VALUES ('A','DEF',NULL,85,'close',?,NULL,NULL,NULL,NULL,0,NULL)
            """, (LATER_RETRIEVAL,))
            prices.init_schema(conn)
            saved = prices.load_observations(conn, "A")["ABC"][0]
            unknown_identity = prices.load_observations(conn, "A")["DEF"][0]
            selected = prices.resolve_price({}, {}, [saved])
            columns = {row[1] for row in conn.execute("PRAGMA table_info(action_plan_price_observations)")}
            primary_key = [row[1] for row in sorted(
                conn.execute("PRAGMA table_info(action_plan_price_observations)"), key=lambda row: row[5]
            ) if row[5]]
        self.assertTrue({"market_observed_at", "retrieved_at", "persisted_at"}.issubset(columns))
        self.assertEqual(["account_id", "symbol", "contract_key"], primary_key)
        self.assertIsNone(unknown_identity["contract_key"])
        self.assertEqual((None, LATER_RETRIEVAL, "retrieval"), (
            selected["market_observed_at"], selected["retrieved_at"], selected["price_timestamp_kind"],
        ))

    def test_failed_or_unknown_refresh_does_not_replace_known_saved_observation(self):
        with sqlite3.connect(":memory:") as conn:
            prices.init_schema(conn)
            self.assertTrue(prices.persist_observation(conn, "A", "ABC", DELAYED))
            self.assertFalse(prices.persist_observation(conn, "A", "ABC", {
                "symbol": "ABC", "contract_key": "1", "price": 30,
                "price_source": "last", "retrieved_at": LATER_RETRIEVAL,
            }))
            self.assertFalse(prices.persist_observation(conn, "A", "ABC", {
                "symbol": "ABC", "contract_key": "1", "price": float("nan"),
                "price_source": "last", "retrieved_at": LATER_RETRIEVAL,
            }))
            selected = prices.resolve_price({}, {}, prices.load_observations(conn, "A")["ABC"])
        self.assertEqual((22, NEW), (selected["price"], selected["market_observed_at"]))
