import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest import mock

import web_server
from test_manual_execution_engine import linear_candidate, linear_settings, verified_row


class FakeEvent:
    def __init__(self):
        self.handlers = []

    def __iadd__(self, handler):
        self.handlers.append(handler)
        return self

    def __isub__(self, handler):
        self.handlers.remove(handler)
        return self

    def emit(self, tickers):
        for handler in list(self.handlers):
            handler(tickers)


class PacketTicker:
    def __init__(self, contract, market_data_type=1):
        self.contract = contract
        self.marketDataType = market_data_type
        self.bid = self.ask = self.last = self.close = self.prevClose = None
        self.bidSize = self.askSize = 0
        self.ticks = []

    def marketPrice(self):
        if self.bid is not None and self.ask is not None:
            return (self.bid + self.ask) / 2
        return None


class PacketIB:
    def __init__(self, contract, packets, market_data_type=1, fail_request=False):
        self.contract = contract
        self.packets = list(packets)
        self.market_data_type = market_data_type
        self.fail_request = fail_request
        self.pendingTickersEvent = FakeEvent()
        self.errorEvent = FakeEvent()
        self.ticker = None
        self.tickers_by_key = {}
        self.cancelled = []
        self.requests = []
        self.clock = None

    def reqMktData(self, contract, *_args):
        self.requests.append(contract)
        if self.fail_request:
            raise RuntimeError("subscription failed")
        key = web_server.market_data_contract_key(contract)
        self.ticker = self.tickers_by_key.setdefault(key, PacketTicker(contract, self.market_data_type))
        return self.ticker

    def sleep(self, _seconds):
        if self.clock is not None:
            self.clock.value += _seconds
        if not self.packets:
            return
        packet = self.packets.pop(0)
        if len(packet) == 5:
            contract, side, price, size, timestamp = packet
            ticker = self.tickers_by_key[web_server.market_data_contract_key(contract)]
        else:
            side, price, size, timestamp = packet
            ticker = self.ticker
        if side == "bid":
            ticker.bid, ticker.bidSize, tick_type = price, size, 1
        elif side == "ask":
            ticker.ask, ticker.askSize, tick_type = price, size, 2
        elif side == "last":
            ticker.last, tick_type = price, 4
        elif side == "close":
            ticker.close = ticker.prevClose = price
            tick_type = 9
        else:
            raise ValueError(side)
        ticker.ticks = [SimpleNamespace(tickType=tick_type, price=price, size=size, time=timestamp)]
        self.pendingTickersEvent.emit([ticker])
        ticker.ticks = []

    def cancelMktData(self, contract):
        self.cancelled.append(contract)


class ManualQuoteObservationTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.contract = SimpleNamespace(symbol="NVDA", conId=101, secType="STK", currency="USD")
        self.key = web_server.market_data_contract_key(self.contract)

    def collect(self, packets, market_data_type=1, fail_request=False):
        ib = PacketIB(self.contract, packets, market_data_type, fail_request)
        observations = web_server._ManualQuoteObservations()
        with mock.patch.object(web_server, "get_ib_price_wait_seconds", return_value=0.02), \
             mock.patch.object(web_server, "get_ib_delayed_price_extra_wait_seconds", return_value=0):
            tickers, diagnostics = web_server.request_ib_tickers_batched(
                ib, [self.contract], "positions_api", quote_observations=observations,
            )
        return ib, tickers, diagnostics, observations

    def proof(self, ib, diagnostics, observations):
        return web_server._manual_quote_proof_from_ticker(
            ib.ticker, self.key, self.now.isoformat(), diagnostics.get("NVDA"),
            observations=observations, now=self.now,
        )

    def buy_status(self, proof):
        row = verified_row(
            price_last_successful_at=self.now.isoformat(), manual_quote_proof=proof,
        )
        return web_server.evaluate_manual_execution_trigger(row, {"buy_trigger_price": 80}, self.now)["status"]

    def test_separate_bid_and_ask_packets_survive_transient_tick_clearing(self):
        ib, tickers, diagnostics, observations = self.collect([
            ("bid", 78, 10, self.now), ("ask", 79, 10, self.now),
        ])
        self.assertEqual(tickers, [ib.ticker])
        self.assertEqual(ib.ticker.ticks, [])
        self.assertEqual(len(ib.pendingTickersEvent.handlers), 0)
        self.assertEqual(len(ib.errorEvent.handlers), 0)
        proof = self.proof(ib, diagnostics, observations)
        self.assertEqual((proof["bid"], proof["ask"]), (78, 79))
        self.assertEqual(proof["bid_tick_at"], self.now.isoformat())
        self.assertEqual(proof["ask_tick_at"], self.now.isoformat())

    def test_only_one_side_or_final_fields_without_events_cannot_verify(self):
        for packets in ([('bid', 78, 10, self.now)], [('ask', 79, 10, self.now)], []):
            with self.subTest(packets=packets):
                ib, _tickers, diagnostics, observations = self.collect(packets)
                if not packets:
                    ib.ticker.bid, ib.ticker.ask = 78, 79
                    ib.ticker.bidSize = ib.ticker.askSize = 10
                    ib.ticker.ticks = [
                        SimpleNamespace(tickType=1, price=78, size=10, time=self.now),
                        SimpleNamespace(tickType=2, price=79, size=10, time=self.now),
                    ]
                proof = self.proof(ib, diagnostics, observations)
                self.assertIsNone(proof)
                self.assertEqual(self.buy_status(proof), "price_confirmation_required")

    def test_stale_or_nonlive_side_cannot_verify(self):
        stale = self.now - timedelta(minutes=6)
        for packets, data_type in (
            ([("bid", 78, 10, stale), ("ask", 79, 10, self.now)], 1),
            ([("bid", 78, 10, self.now), ("ask", 79, 10, stale)], 1),
            ([("bid", 78, 10, self.now), ("ask", 79, 10, self.now)], 2),
            ([("bid", 78, 10, self.now), ("ask", 79, 10, self.now)], 3),
        ):
            with self.subTest(packets=packets, data_type=data_type):
                ib, _tickers, diagnostics, observations = self.collect(packets, data_type)
                proof = self.proof(ib, diagnostics, observations)
                self.assertIsNone(proof)
                self.assertEqual(self.buy_status(proof), "price_confirmation_required")

    def test_failed_requests_remove_handlers_and_do_not_accumulate(self):
        for _ in range(2):
            ib, tickers, diagnostics, observations = self.collect([], fail_request=True)
            self.assertEqual(tickers, [])
            self.assertEqual(len(ib.pendingTickersEvent.handlers), 0)
            self.assertEqual(len(ib.errorEvent.handlers), 0)
            self.assertIsNone(self.proof(ib, diagnostics, observations))

        ib = PacketIB(self.contract, [("bid", 78, 10, self.now)])
        observations = web_server._ManualQuoteObservations()
        with mock.patch.object(web_server, "get_ib_price_wait_seconds", return_value=0.02):
            web_server.request_ib_tickers_batched(ib, [self.contract], "positions_api", quote_observations=observations)
        self.assertEqual(len(ib.pendingTickersEvent.handlers), 0)
        ib.packets = [("bid", 78, 10, self.now), ("ask", 79, 10, self.now)]
        second = web_server._ManualQuoteObservations()
        with mock.patch.object(web_server, "get_ib_price_wait_seconds", return_value=0.02):
            web_server.request_ib_tickers_batched(ib, [self.contract], "positions_api", quote_observations=second)
        self.assertEqual(len(ib.pendingTickersEvent.handlers), 0)
        self.assertIsNotNone(self.proof(ib, {}, second))

    def test_event_handler_removed_when_market_data_wait_raises(self):
        ib = PacketIB(self.contract, [])
        ib.sleep = mock.Mock(side_effect=RuntimeError("market data failed"))
        observations = web_server._ManualQuoteObservations()
        with mock.patch.object(web_server, "get_ib_price_wait_seconds", return_value=1):
            with self.assertRaisesRegex(RuntimeError, "market data failed"):
                web_server.request_ib_tickers_batched(
                    ib, [self.contract], "positions_api", quote_observations=observations,
                )
        self.assertEqual(len(ib.pendingTickersEvent.handlers), 0)
        self.assertEqual(len(ib.errorEvent.handlers), 0)

    def test_unregistered_contract_event_cannot_supply_missing_side(self):
        ib = PacketIB(self.contract, [("bid", 78, 10, self.now)])
        foreign_contract = SimpleNamespace(symbol="NVDA", conId=202, secType="STK", currency="USD")
        foreign = PacketTicker(foreign_contract)
        original_sleep = ib.sleep

        def emit_foreign(seconds):
            original_sleep(seconds)
            foreign.ask, foreign.askSize = 79, 10
            foreign.ticks = [SimpleNamespace(tickType=2, price=79, size=10, time=self.now)]
            ib.pendingTickersEvent.emit([foreign])
            foreign.ticks = []

        ib.sleep = emit_foreign
        observations = web_server._ManualQuoteObservations()
        with mock.patch.object(web_server, "get_ib_price_wait_seconds", return_value=0.02):
            web_server.request_ib_tickers_batched(ib, [self.contract], "positions_api", quote_observations=observations)
        self.assertIsNone(self.proof(ib, {}, observations))
        self.assertIsNone(web_server._manual_quote_proof_from_ticker(
            ib.ticker, web_server.market_data_contract_key(foreign_contract), self.now.isoformat(), {},
            observations=observations, now=self.now,
        ))

    def test_latest_quote_field_must_still_match_observation(self):
        ib, _tickers, diagnostics, observations = self.collect([
            ("bid", 78, 10, self.now), ("ask", 79, 10, self.now),
        ])
        ib.ticker.bidSize = 0
        self.assertIsNone(self.proof(ib, diagnostics, observations))
        ib.ticker.bidSize = 10
        ib.ticker.ask = 81
        self.assertIsNone(self.proof(ib, diagnostics, observations))

    def test_side_specific_trigger_comparisons_use_observed_quote(self):
        cases = (
            ("Add", 78, 79, {"buy_trigger_price": 80}, "eligible"),
            ("Add", 80, 81, {"buy_trigger_price": 80}, "waiting"),
            ("Trim", 121, 122, {"sell_trigger_price": 120}, "eligible"),
            ("Sell", 119, 120, {"sell_trigger_price": 120}, "waiting"),
            ("Sell", 89, 90, {"sell_trigger_price": 90, "sell_trigger_direction": "at_or_below"}, "eligible"),
        )
        for action, bid, ask, preference, expected in cases:
            with self.subTest(action=action, bid=bid, ask=ask, preference=preference):
                ib, _tickers, diagnostics, observations = self.collect([
                    ("bid", bid, 10, self.now), ("ask", ask, 10, self.now),
                ])
                proof = self.proof(ib, diagnostics, observations)
                row = verified_row(
                    action=action, price_last_successful_at=self.now.isoformat(),
                    manual_quote_proof=proof,
                )
                result = web_server.evaluate_manual_execution_trigger(row, preference, self.now)
                self.assertEqual(result["status"], expected)
                self.assertEqual(result["verified_price"], ask if action == "Add" else bid)

    def test_observed_quote_controls_buy_and_sell_funding(self):
        ib, _tickers, diagnostics, observations = self.collect([
            ("last", 100, 1, self.now), ("bid", 78, 10, self.now), ("ask", 79, 10, self.now),
        ])
        proof = self.proof(ib, diagnostics, observations)
        candidate = linear_candidate(
            "NVDA", current_price=80, current_position_market_value=80,
            current_position_weight=0.08, price_last_successful_at=self.now.isoformat(),
            manual_quote_proof=proof,
        )
        preference = {"buy_trigger_price": 80, "reserve_enabled": True, "reserve_percentage": 100}
        blocked = web_server.compute_linear_action_plan(
            [dict(candidate, manual_quote_proof=None)], 100_000, 20_000,
            linear_settings(), manual_triggers={"NVDA": preference},
        )["manual_execution"]
        self.assertEqual(blocked["rows"][0]["manual_trigger_status"], "price_confirmation_required")
        self.assertGreater(blocked["rows"][0]["requested_reservation"], 0)
        self.assertEqual(blocked["rows"][0]["executable_action_amount"], 0)
        payload = web_server.compute_linear_action_plan(
            [candidate], 100_000, 20_000, linear_settings(), manual_triggers={"NVDA": preference},
        )["manual_execution"]
        row = payload["rows"][0]
        self.assertEqual(row["manual_trigger_status"], "eligible")
        self.assertEqual(row["manual_verified_price"], 79)
        self.assertEqual(row["requested_reservation"], 0)
        self.assertGreater(row["executable_action_amount"], 0)

        sell_ib, _tickers, sell_diagnostics, sell_observations = self.collect([
            ("last", 120, 1, self.now), ("bid", 121, 10, self.now), ("ask", 122, 10, self.now),
        ])
        sell_proof = self.proof(sell_ib, sell_diagnostics, sell_observations)
        sell_candidate = linear_candidate(
            "NVDA", rating="Sell", current_price=120, current_position_market_value=1_200,
            current_position_weight=1.2, owned_share_quantity=10,
            price_last_successful_at=self.now.isoformat(), manual_quote_proof=sell_proof,
        )
        blocked_sell = web_server.compute_linear_action_plan(
            [dict(sell_candidate, manual_quote_proof=None)], 100_000, 0,
            linear_settings(action_min_cash_unallocated_target=0, linear_max_reserve_pct=0),
            manual_triggers={"NVDA": {"sell_trigger_price": 120}},
        )["manual_execution"]
        self.assertEqual(blocked_sell["summary"]["executable_sell_trim_proceeds"], 0)
        sell_payload = web_server.compute_linear_action_plan(
            [sell_candidate], 100_000, 0,
            linear_settings(action_min_cash_unallocated_target=0, linear_max_reserve_pct=0),
            manual_triggers={"NVDA": {"sell_trigger_price": 120}},
        )["manual_execution"]
        self.assertEqual(sell_payload["rows"][0]["manual_trigger_status"], "eligible")
        self.assertEqual(sell_payload["summary"]["executable_sell_trim_proceeds"], 1_210)

    def test_last_price_does_not_end_collection_before_live_bid_and_ask(self):
        clock = SimpleNamespace(value=0.0)
        ib = PacketIB(self.contract, [
            ("last", 100, 1, self.now),
            ("bid", 99, 10, self.now),
            ("ask", 101, 10, self.now),
        ])
        ib.clock = clock
        observations = web_server._ManualQuoteObservations()
        with mock.patch.object(web_server.time, "monotonic", side_effect=lambda: clock.value), \
             mock.patch.object(web_server, "get_ib_price_wait_seconds", return_value=2):
            tickers, diagnostics = web_server.request_ib_tickers_batched(
                ib, [self.contract], "positions_api", quote_observations=observations,
            )
        self.assertEqual(tickers, [ib.ticker])
        self.assertEqual(ib.packets, [])
        self.assertLess(clock.value, 2)
        self.assertEqual(len(ib.requests), 1)
        self.assertEqual(ib.cancelled, [self.contract])
        self.assertEqual(len(ib.pendingTickersEvent.handlers), 0)
        self.assertEqual((self.proof(ib, diagnostics, observations)["bid"],
                          self.proof(ib, diagnostics, observations)["ask"]), (99, 101))

    def test_previous_close_does_not_end_collection_before_live_quote(self):
        clock = SimpleNamespace(value=0.0)
        ib = PacketIB(self.contract, [
            ("close", 100, 1, self.now),
            ("bid", 98, 10, self.now),
            ("ask", 99, 10, self.now),
        ])
        ib.clock = clock
        observations = web_server._ManualQuoteObservations()
        with mock.patch.object(web_server.time, "monotonic", side_effect=lambda: clock.value), \
             mock.patch.object(web_server, "get_ib_price_wait_seconds", return_value=2):
            web_server.request_ib_tickers_batched(
                ib, [self.contract], "positions_api", quote_observations=observations,
            )
        self.assertEqual(ib.packets, [])
        self.assertLess(clock.value, 2)
        self.assertEqual((self.proof(ib, {}, observations)["bid"],
                          self.proof(ib, {}, observations)["ask"]), (98, 99))

    def test_one_sided_quote_uses_one_batch_deadline_and_keeps_last_price(self):
        clock = SimpleNamespace(value=0.0)
        ib = PacketIB(self.contract, [
            ("last", 100, 1, self.now), ("bid", 99, 10, self.now),
        ])
        ib.clock = clock
        observations = web_server._ManualQuoteObservations()
        with mock.patch.object(web_server.time, "monotonic", side_effect=lambda: clock.value), \
             mock.patch.object(web_server, "get_ib_price_wait_seconds", return_value=1):
            tickers, diagnostics = web_server.request_ib_tickers_batched(
                ib, [self.contract], "positions_api", quote_observations=observations,
            )
        self.assertEqual(clock.value, 1)
        self.assertEqual(web_server.extract_price(tickers[0]), 100)
        self.assertIsNone(self.proof(ib, diagnostics, observations))
        self.assertEqual(self.buy_status(None), "price_confirmation_required")
        self.assertEqual(ib.cancelled, [self.contract])
        self.assertEqual(len(ib.pendingTickersEvent.handlers), 0)

    def test_nonlive_last_price_does_not_wait_for_impossible_proof(self):
        for market_data_type in (2, 3, 4):
            with self.subTest(market_data_type=market_data_type):
                clock = SimpleNamespace(value=0.0)
                ib = PacketIB(self.contract, [("last", 100, 1, self.now)], market_data_type)
                ib.clock = clock
                observations = web_server._ManualQuoteObservations()
                with mock.patch.object(web_server.time, "monotonic", side_effect=lambda: clock.value), \
                     mock.patch.object(web_server, "get_ib_price_wait_seconds", return_value=2):
                    tickers, diagnostics = web_server.request_ib_tickers_batched(
                        ib, [self.contract], "positions_api", quote_observations=observations,
                    )
                self.assertLess(clock.value, 2)
                self.assertEqual(web_server.extract_price(tickers[0]), 100)
                self.assertIsNone(self.proof(ib, diagnostics, observations))

    def test_multiple_contracts_share_one_bounded_verification_window(self):
        msft = SimpleNamespace(symbol="MSFT", conId=202, secType="STK", currency="USD")
        asml = SimpleNamespace(symbol="ASML", conId=303, secType="STK", currency="USD")
        clock = SimpleNamespace(value=0.0)
        ib = PacketIB(self.contract, [
            (self.contract, "bid", 99, 10, self.now),
            (msft, "last", 200, 1, self.now),
            (asml, "bid", 98, 10, self.now),
            (self.contract, "ask", 101, 10, self.now),
            (asml, "ask", 99, 10, self.now),
        ])
        ib.clock = clock
        observations = web_server._ManualQuoteObservations()
        with mock.patch.object(web_server.time, "monotonic", side_effect=lambda: clock.value), \
             mock.patch.object(web_server, "get_ib_price_wait_seconds", return_value=2):
            tickers, _diagnostics = web_server.request_ib_tickers_batched(
                ib, [self.contract, msft, asml], "positions_api", quote_observations=observations,
            )
        self.assertEqual(len(tickers), 3)
        self.assertEqual(len(ib.requests), 3)
        self.assertEqual(clock.value, 2)
        self.assertEqual(
            {web_server.market_data_contract_key(contract) for contract in ib.cancelled},
            {web_server.market_data_contract_key(contract) for contract in (self.contract, msft, asml)},
        )
        for contract in (self.contract, asml):
            key = web_server.market_data_contract_key(contract)
            proof = web_server._manual_quote_proof_from_ticker(
                ib.tickers_by_key[key], key, self.now.isoformat(), {}, observations=observations, now=self.now,
            )
            self.assertIsNotNone(proof)
        self.assertIsNone(web_server._manual_quote_proof_from_ticker(
            ib.tickers_by_key[web_server.market_data_contract_key(msft)],
            web_server.market_data_contract_key(msft), self.now.isoformat(), {},
            observations=observations, now=self.now,
        ))

    def test_incomplete_manual_quote_does_not_retry_usable_last_price(self):
        clock = SimpleNamespace(value=0.0)
        ib = PacketIB(self.contract, [("last", 100, 1, self.now), ("bid", 99, 10, self.now)])
        ib.clock = clock
        observations = web_server._ManualQuoteObservations()
        with mock.patch.object(web_server.time, "monotonic", side_effect=lambda: clock.value), \
             mock.patch.object(web_server, "get_ib_price_wait_seconds", return_value=1):
            tickers, diagnostics, refresh = web_server.request_ib_tickers_with_retry(
                ib, [self.contract], "positions_api", quote_observations=observations,
            )
        self.assertEqual(clock.value, 1)
        self.assertEqual(len(ib.requests), 1)
        self.assertEqual(refresh["retry_contracts"], 0)
        self.assertEqual(web_server.extract_price(tickers[self.key]), 100)
        self.assertIsNone(self.proof(ib, diagnostics, observations))

    def test_general_price_caller_still_stops_after_last_price(self):
        clock = SimpleNamespace(value=0.0)
        ib = PacketIB(self.contract, [
            ("last", 100, 1, self.now), ("bid", 99, 10, self.now), ("ask", 101, 10, self.now),
        ])
        ib.clock = clock
        with mock.patch.object(web_server.time, "monotonic", side_effect=lambda: clock.value), \
             mock.patch.object(web_server, "get_ib_price_wait_seconds", return_value=2):
            tickers, _diagnostics = web_server.request_ib_tickers_batched(ib, [self.contract], "price_fetch")
        self.assertEqual(clock.value, 0.25)
        self.assertEqual(web_server.extract_price(tickers[0]), 100)
        self.assertEqual(len(ib.packets), 2)


if __name__ == "__main__":
    unittest.main()
