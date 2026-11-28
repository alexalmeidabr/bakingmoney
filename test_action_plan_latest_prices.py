import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import action_plan_prices as prices


OLD = "2024-01-02T10:00:00+00:00"
NEW = "2024-01-03T10:00:00+00:00"
LATER_RETRIEVAL = "2024-01-04T10:00:00+00:00"
LATEST = "2024-01-05T10:00:00+00:00"
POSITION = dict(symbol="ABC", contract_key="1", price=20, price_status="cached_stale",
                price_source="last", market_observed_at=OLD, retrieved_at=OLD)
QUOTE = dict(symbol="ABC", contract_key="1", bid=19, ask=21, source="live_bid_ask",
             refresh_at=OLD, bid_tick_at=OLD, ask_tick_at=OLD)
DELAYED = dict(symbol="ABC", contract_key="1", price=22, price_source="delayed_last",
               market_observed_at=NEW, retrieved_at=NEW)


class PriceResolution(unittest.TestCase):
    def test_last_with_older_sides_uses_streaming_receipt_and_survives_restart(self):
        side_time = "2024-01-03T10:00:00+00:00"
        saved_time = "2024-01-03T10:01:00+00:00"
        receipt = "2024-01-03T10:02:00+00:00"
        saved = dict(POSITION, price=115, price_source="last", market_observed_at=saved_time)
        last = dict(POSITION, price=120, price_source="last", acquisition_kind="streaming_live",
                    market_observed_at=None, retrieved_at=receipt, bid=119, ask=121,
                    bid_tick_at=side_time, ask_tick_at=side_time)
        selected = prices.resolve_price({}, {}, [saved, last])
        self.assertEqual((120, None, receipt, "retrieval"),
                         (selected["price"], selected["market_observed_at"],
                          selected["retrieved_at"], selected["price_timestamp_kind"]))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "prices.db"
            with sqlite3.connect(path) as conn:
                prices.init_schema(conn)
                self.assertTrue(prices.persist_observation(conn, "A", "ABC", saved))
                self.assertTrue(prices.persist_observation(conn, "A", "ABC", last))
                self.assertFalse(prices.persist_observation(conn, "A", "ABC", saved))
            conn.close()
            with sqlite3.connect(path) as conn:
                reopened = prices.resolve_price({}, {}, prices.load_observations(conn, "A")["ABC"])
            conn.close()
        self.assertEqual((120, None, "streaming_live"),
                         (reopened["price"], reopened["market_observed_at"], reopened["acquisition_kind"]))

    def test_midpoint_and_last_same_value_keep_distinct_timestamp_sources(self):
        side_time = "2024-01-03T10:00:00+00:00"
        fields = dict(symbol="ABC", contract_key="1", price=120, bid=119, ask=121,
                      bid_tick_at=side_time, ask_tick_at=side_time,
                      retrieved_at="2024-01-03T10:02:00+00:00")
        midpoint = prices.resolve_price({}, {}, [dict(fields, price_source="marketPrice")])
        last = prices.resolve_price({}, {}, [dict(fields, price_source="last",
                                                    acquisition_kind="streaming_live")])
        self.assertEqual(side_time, midpoint["market_observed_at"])
        self.assertIsNone(last["market_observed_at"])
        self.assertEqual(fields["retrieved_at"], last["retrieved_at"])
        reliable_last = prices.resolve_price({}, {}, [dict(fields, price_source="last",
                                                             market_observed_at="2024-01-03T10:01:00+00:00")])
        self.assertEqual("2024-01-03T10:01:00+00:00", reliable_last["market_observed_at"])
        evaluated = prices.evaluate_trigger(
            dict(reliable_last, current_price=120, action="Add"), {"buy_trigger_price": 120.5},
        )
        self.assertEqual((120, "eligible", "last"),
                         (evaluated["verified_price"], evaluated["status"], evaluated["price_source"]))
        explicit_source = prices.resolve_price({}, {}, [dict(fields, price_source="last",
                                                               market_data_source="live")])
        self.assertIsNone(explicit_source["market_observed_at"])

    def test_older_sides_do_not_replace_newer_last_for_trigger(self):
        sides = "2024-01-03T10:00:00+00:00"
        last = dict(symbol="ABC", contract_key="1", price=120, price_source="last",
                    bid=119, ask=121, bid_tick_at=sides, ask_tick_at=sides,
                    retrieved_at="2024-01-03T10:02:00+00:00", acquisition_kind="streaming_live")
        reference = prices.resolve_price({}, {}, [last])
        for action, preference in (("Add", {"buy_trigger_price": 120.5}),
                                   ("Trim", {"sell_trigger_price": 119.5})):
            with self.subTest(action=action):
                evaluated = prices.evaluate_trigger(dict(reference, current_price=120, action=action), preference)
                self.assertEqual((120, "eligible", "last"),
                                 (evaluated["verified_price"], evaluated["status"],
                                  evaluated["price_source"]))

    def test_current_sides_can_still_supply_executable_prices_with_last_reference(self):
        last = dict(symbol="ABC", contract_key="1", price=120, price_source="last",
                    bid=119, ask=121, bid_tick_at="2024-01-03T10:02:00+00:00",
                    ask_tick_at="2024-01-03T10:02:00+00:00",
                    retrieved_at="2024-01-03T10:02:00.500000+00:00",
                    acquisition_kind="streaming_live")
        reference = prices.resolve_price({}, {}, [last])
        for action, preference, expected_price, expected_source in (
                ("Add", {"buy_trigger_price": 121}, 121, "last (ask)"),
                ("Trim", {"sell_trigger_price": 119}, 119, "last (bid)")):
            with self.subTest(action=action):
                evaluated = prices.evaluate_trigger(dict(reference, current_price=120, action=action), preference)
                self.assertEqual((expected_price, "eligible", expected_source),
                                 (evaluated["verified_price"], evaluated["status"],
                                  evaluated["price_source"]))

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
        owned = prices.resolve_price({
            "symbol": "ABC", "position": 1, "contract_key": "conid:111",
        }, {}, observations)
        unowned = prices.resolve_price({}, {"symbol": "ABC", "current_price": 90}, observations)
        legacy = prices.resolve_price({}, {"symbol": "ABC"}, [observations[-1]])
        self.assertEqual((100, "conid:111"), (owned["price"], owned["contract_key"]))
        self.assertEqual((90, "analysis_fallback"), (unowned["price"], unowned["price_source"]))
        self.assertIn("multiple contract", unowned["price_warning"].lower())
        self.assertEqual(999, legacy["price"])
        self.assertIn("contract identity is unknown", legacy["price_warning"].lower())

    def test_unowned_resolution_uses_selected_or_inferred_contract_safely(self):
        observations = [
            dict(POSITION, contract_key="conid:111", price=100, market_observed_at=OLD,
                 security_type="STK", currency="USD"),
            dict(POSITION, contract_key="conid:222", price=150, market_observed_at=NEW,
                 security_type="STK", currency="USD"),
        ]
        selected = prices.resolve_price(
            {}, {"symbol": "ABC", "current_price": 90}, observations,
            selected_contract={"contract_key": "conid:111", "security_type": "STK", "currency": "USD"},
        )
        self.assertEqual((100, "conid:111"), (selected["price"], selected["contract_key"]))
        self.assertNotIn("inferred", (selected["price_warning"] or "").lower())

        inferred = prices.resolve_price({}, {"symbol": "ABC", "current_price": 90}, [observations[0]])
        self.assertEqual((100, "conid:111"), (inferred["price"], inferred["contract_key"]))
        self.assertIn("inferred, not verified", inferred["price_warning"].lower())

        for incompatible in (
            dict(observations[0], security_type="OPT"),
            dict(observations[0], currency="EUR"),
        ):
            with self.subTest(incompatible=incompatible):
                fallback = prices.resolve_price(
                    {}, {"symbol": "ABC", "current_price": 90, "currency": "USD"}, [incompatible]
                )
                self.assertEqual((90, "analysis_fallback"),
                                 (fallback["price"], fallback["price_source"]))
                self.assertIn("instrument metadata", fallback["price_warning"].lower())

        missing_selected = prices.resolve_price(
            {}, {"symbol": "ABC", "current_price": 90}, [observations[1]],
            selected_contract={"contract_key": "conid:111", "security_type": "STK", "currency": "USD"},
        )
        self.assertEqual((90, "analysis_fallback"),
                         (missing_selected["price"], missing_selected["price_source"]))
        self.assertIn("qualified contract", missing_selected["price_warning"].lower())

    def test_contract_authority_requires_finite_nonzero_ownership(self):
        position = dict(
            POSITION, contract_key="conid:111", price=95,
            market_observed_at=OLD, security_type="STK", currency="USD",
        )
        selected_observation = dict(
            POSITION, contract_key="conid:222", price=110,
            market_observed_at=NEW, security_type="STK", currency="USD",
        )
        selection = {
            "contract_key": "conid:222", "security_type": "STK", "currency": "USD",
        }

        for quantity in (0, 0.0, -0.0, None, False, True, "invalid", float("nan"), float("inf")):
            with self.subTest(quantity=quantity):
                resolved = prices.resolve_price(
                    dict(position, position=quantity), {"symbol": "ABC", "current_price": 90},
                    [selected_observation], selected_contract=selection,
                )
                self.assertEqual((110, "conid:222"),
                                 (resolved["price"], resolved["contract_key"]))

        for quantity in (1, -1):
            with self.subTest(quantity=quantity):
                resolved = prices.resolve_price(
                    dict(position, position=quantity), {"symbol": "ABC", "current_price": 90},
                    [selected_observation], selected_contract=selection,
                )
                self.assertEqual((95, "conid:111"),
                                 (resolved["price"], resolved["contract_key"]))

        missing_selected = prices.resolve_price(
            dict(position, position=0), {"symbol": "ABC", "current_price": 90}, [],
            selected_contract=selection,
        )
        self.assertEqual((90, "analysis_fallback"),
                         (missing_selected["price"], missing_selected["price_source"]))

        ambiguous = prices.resolve_price(
            dict(position, position=0), {"symbol": "ABC", "current_price": 90},
            [selected_observation],
        )
        self.assertEqual((90, "analysis_fallback"),
                         (ambiguous["price"], ambiguous["price_source"]))
        self.assertIn("multiple contract", ambiguous["price_warning"].lower())

    def test_contract_selection_persists_transitions_and_account_isolation(self):
        with sqlite3.connect(":memory:") as conn:
            prices.init_schema(conn)
            self.assertTrue(prices.save_contract_selection(
                conn, "A", "ABC", "conid:111", "STK", "USD", OLD,
            ))
            self.assertTrue(prices.save_contract_selection(
                conn, "B", "ABC", "conid:222", "STK", "USD", NEW,
            ))
            self.assertTrue(prices.save_contract_selection(
                conn, "A", "ABC", "conid:333", "STK", "USD", LATER_RETRIEVAL,
            ))
            account_a = prices.load_contract_selections(conn, "A")
            account_b = prices.load_contract_selections(conn, "B")
            tables = {row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )}
        self.assertIn("action_plan_contract_selections", tables)
        self.assertEqual("conid:333", account_a["ABC"]["contract_key"])
        self.assertEqual("conid:222", account_b["ABC"]["contract_key"])

    def test_owned_position_without_contract_does_not_use_contract_specific_observation(self):
        position = {
            "symbol": "ABC", "position": 10, "price": None,
            "contract_key": None, "price_status": "unavailable",
        }
        observations = [
            dict(POSITION, contract_key="conid:111", price=100, market_observed_at=OLD),
            dict(POSITION, contract_key="conid:222", price=105, market_observed_at=NEW),
        ]
        selected = prices.resolve_price(position, {"symbol": "ABC", "current_price": 90}, observations)
        self.assertEqual((90, "analysis_fallback"), (selected["price"], selected["price_source"]))

    def test_newer_live_observation_beats_older_close_retrieved_later(self):
        live = dict(POSITION, price=100, market_observed_at=NEW, retrieved_at=NEW)
        close = dict(POSITION, price=95, price_source="close", market_observed_at=OLD,
                     retrieved_at=LATER_RETRIEVAL)
        selected = prices.resolve_price(live, {}, [close])
        self.assertEqual((100, NEW, NEW, "market_observation"), (
            selected["price"], selected["market_observed_at"], selected["retrieved_at"],
            selected["price_timestamp_kind"],
        ))

    def test_evidenced_live_retrieval_beats_older_known_observation_and_persists(self):
        old_known = dict(POSITION, persisted=True, price=100, market_observed_at=NEW,
                         retrieved_at=NEW)
        current_live = dict(POSITION, price=120, market_observed_at=None,
                            retrieved_at=LATER_RETRIEVAL,
                            acquisition_kind="streaming_live")
        selected = prices.resolve_price({}, {}, [old_known, current_live])
        self.assertEqual((120, None, LATER_RETRIEVAL, "streaming_live"), (
            selected["price"], selected["market_observed_at"], selected["retrieved_at"],
            selected["acquisition_kind"],
        ))
        self.assertIn("exchange observation time is unknown", selected["price_warning"].lower())

        with sqlite3.connect(":memory:") as conn:
            prices.init_schema(conn)
            self.assertTrue(prices.persist_observation(conn, "A", "ABC", old_known))
            self.assertTrue(prices.persist_observation(conn, "A", "ABC", current_live))
            saved = prices.load_observations(conn, "A")["ABC"]
            reopened = prices.resolve_price({}, {}, saved)
            columns = {row[1] for row in conn.execute(
                "PRAGMA table_info(action_plan_price_observations)"
            )}
        self.assertIn("acquisition_kind", columns)
        self.assertEqual((120, "streaming_live"),
                         (reopened["price"], reopened["acquisition_kind"]))

    def test_retrieval_proxy_never_promotes_snapshots_or_unevidenced_prices(self):
        known = dict(POSITION, persisted=True, price=100, market_observed_at=NEW,
                     retrieved_at=NEW)
        snapshots = (
            dict(POSITION, price=95, price_source="close", market_observed_at=None,
                 retrieved_at=LATER_RETRIEVAL, acquisition_kind="snapshot"),
            dict(POSITION, price=96, price_source="frozen_last", market_observed_at=None,
                 retrieved_at=LATER_RETRIEVAL, acquisition_kind="snapshot"),
            dict(POSITION, price=97, price_source="delayed_frozen_last", market_observed_at=None,
                 retrieved_at=LATER_RETRIEVAL, acquisition_kind="snapshot"),
            dict(POSITION, price=120, price_source="last", market_observed_at=None,
                 retrieved_at=LATER_RETRIEVAL, acquisition_kind=None),
        )
        for incoming in snapshots:
            with self.subTest(source=incoming["price_source"]):
                self.assertEqual(100, prices.resolve_price({}, {}, [known, incoming])["price"])
                with sqlite3.connect(":memory:") as conn:
                    prices.init_schema(conn)
                    self.assertTrue(prices.persist_observation(conn, "A", "ABC", known))
                    self.assertFalse(prices.persist_observation(conn, "A", "ABC", incoming))

    def test_effective_freshness_orders_known_and_streaming_times_consistently(self):
        earlier_live = dict(POSITION, price=110, market_observed_at=None,
                            retrieved_at=LATER_RETRIEVAL, acquisition_kind="streaming_live")
        later_known = dict(POSITION, price=115, market_observed_at=LATEST,
                           retrieved_at=LATEST, price_source="delayed_last")
        later_live = dict(POSITION, price=120, market_observed_at=None,
                          retrieved_at=LATEST, acquisition_kind="streaming_live")
        earlier_delayed = dict(POSITION, price=105, market_observed_at=None,
                               retrieved_at=OLD, price_source="delayed_last",
                               acquisition_kind="streaming_delayed")
        self.assertEqual(115, prices.resolve_price({}, {}, [earlier_live, later_known])["price"])
        self.assertEqual(120, prices.resolve_price({}, {}, [earlier_live, later_live])["price"])
        self.assertEqual(110, prices.resolve_price({}, {}, [earlier_delayed, earlier_live])["price"])

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
            self.assertEqual(20, prices.resolve_price(dict(POSITION, position=1), {}, [mismatched])["price"])

    def test_unknown_contract_or_wrong_account_cannot_supply_owned_price(self):
        for raw in (dict(DELAYED, contract_key=None), dict(DELAYED, account_id="B")):
            self.assertEqual(20, prices.resolve_price(
                dict(POSITION, position=1, account_id="A"), {}, [raw],
            )["price"])

    def test_fresh_live_sides_display_source_and_warn_when_contract_is_inferred(self):
        now = datetime.now(timezone.utc)
        stamp = now.isoformat()
        quote = dict(QUOTE, refresh_at=stamp, bid_tick_at=stamp, ask_tick_at=stamp)
        selected = prices.resolve_price({}, {}, [quote])
        evaluation = prices.evaluate_trigger(dict(selected, action="Trim", current_price=selected["price"]),
                                              {"sell_trigger_price": 19}, now)
        self.assertEqual(("eligible", "live_bid_ask (bid)", stamp),
                         (evaluation["status"], evaluation["price_source"], evaluation["verified_quote_at"]))
        self.assertIn("inferred, not verified", evaluation["verification_reason"].lower())

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
