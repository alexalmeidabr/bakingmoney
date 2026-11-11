import math
import os
import tempfile
import unittest
from unittest import mock

import web_server


class Contract:
    def __init__(self, symbol, con_id=None, sec_type="STK", currency="USD", exchange="SMART"):
        self.symbol = symbol
        self.conId = con_id
        self.secType = sec_type
        self.currency = currency
        self.exchange = exchange


class ResilientIbkrMarketDataRefreshTests(unittest.TestCase):
    def test_deduplicates_same_conid_without_merging_distinct_symbol_only_contracts(self):
        nvda_a = Contract("NVDA", 265598)
        nvda_b = Contract("NVDA", 265598)
        us_listing = Contract("ABC", None, exchange="SMART")
        foreign_listing = Contract("ABC", None, exchange="LSE")

        unique = web_server.unique_market_data_contracts([nvda_a, nvda_b, us_listing, foreign_listing])

        self.assertEqual(unique, [nvda_a, us_listing, foreign_listing])

    def test_cached_price_recalculates_live_position_metrics_and_marks_stale(self):
        live = [{
            "symbol": "UBER", "contract_key": "conid:118", "position": 162, "avgCost": 72.46,
            "price": None, "marketValue": None, "unrealizedPnL": None, "dailyPnL": 99,
            "changePercent": 1.2, "currency": "USD", "price_status": "unavailable",
        }]
        cached = [{
            "symbol": "UBER", "contract_key": "conid:118", "position": 150, "avgCost": 70,
            "price": 73, "marketValue": 10950, "unrealizedPnL": 450, "dailyPnL": 12,
            "changePercent": 1, "currency": "USD", "price_status": "tws_received",
            "price_source": "last", "price_last_successful_at": "2026-11-10T10:00:00+00:00",
        }]

        row = web_server.overlay_cached_market_fields(live, cached)[0]

        self.assertEqual(row["price"], 73)
        self.assertEqual(row["price_status"], "cached_stale")
        self.assertEqual(row["price_source"], "cached")
        self.assertEqual(row["price_last_successful_at"], "2026-11-10T10:00:00+00:00")
        self.assertEqual(row["marketValue"], 162 * 73)
        self.assertAlmostEqual(row["unrealizedPnL"], (73 - 72.46) * 162)
        self.assertIsNone(row["dailyPnL"])
        self.assertIsNone(row["changePercent"])

    def test_cached_price_never_crosses_contract_identity(self):
        live = [{"symbol": "ABC", "contract_key": "conid:1", "position": 10, "avgCost": 10, "price": None, "price_status": "unavailable"}]
        cached = [{"symbol": "ABC", "contract_key": "conid:2", "price": 99, "price_status": "tws_received"}]

        row = web_server.overlay_cached_market_fields(live, cached)[0]

        self.assertIsNone(row["price"])
        self.assertEqual(row["price_status"], "unavailable")

    def test_invalid_prices_are_not_market_prices(self):
        for value in (0, -1, float("nan"), float("inf"), -float("inf")):
            with self.subTest(value=value):
                self.assertFalse(web_server.is_valid_market_price(value))

    def test_retries_only_unresolved_contracts_once(self):
        class Ticker:
            def __init__(self, contract, price):
                self.contract = contract
                self.last = price
                self.close = None
                self.prevClose = None

            def marketPrice(self):
                return self.last

        resolved = Contract("NVDA", 1)
        missing = Contract("UBER", 2)
        with mock.patch.object(
            web_server,
            "request_ib_tickers_batched",
            side_effect=[([Ticker(resolved, 100), Ticker(missing, None)], {}), ([Ticker(missing, 73)], {})],
        ) as request:
            tickers, _diagnostics, refresh = web_server.request_ib_tickers_with_retry(object(), [resolved, missing], "positions_api")

        self.assertEqual(request.call_count, 2)
        self.assertEqual(request.call_args_list[1].args[1], [missing])
        self.assertEqual(web_server.extract_price(tickers[web_server.market_data_contract_key(missing)]), 73)
        self.assertEqual(refresh["initial_quotes_received"], 1)
        self.assertEqual(refresh["retry_contracts"], 1)
        self.assertEqual(refresh["retry_quotes_recovered"], 1)

    def test_price_freshness_metadata_survives_cache_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "positions.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    web_server.save_positions_cache(conn, [{
                        "symbol": "NVDA", "contract_key": "conid:1", "position": 10, "price": 100,
                        "avgCost": 90, "price_status": "tws_received", "price_source": "last",
                        "price_last_successful_at": "2026-11-11T10:00:00+00:00", "price_warning": None,
                    }], account_id="U1111111")
                    row = web_server.load_positions_cache(conn, "U1111111")[0]
                finally:
                    conn.close()

        self.assertEqual(row["contract_key"], "conid:1")
        self.assertEqual(row["price_status"], "tws_received")
        self.assertEqual(row["price_source"], "last")
        self.assertEqual(row["price_last_successful_at"], "2026-11-11T10:00:00+00:00")

    def test_live_rows_record_current_quote_provenance_by_contract_identity(self):
        class Position:
            def __init__(self, contract):
                self.contract = contract
                self.position = 12
                self.avgCost = 80

        class Ticker:
            def __init__(self, contract):
                self.contract = contract
                self.last = 100
                self.close = 98
                self.prevClose = 97

            def marketPrice(self):
                return self.last

        contract = Contract("NVDA", 1)
        rows = web_server._build_live_position_rows(
            [Position(contract)],
            {web_server.market_data_contract_key(contract): Ticker(contract)},
            quote_success_at="2026-11-11T10:00:00+00:00",
        )

        self.assertEqual(rows[0]["contract_key"], "conid:1")
        self.assertEqual(rows[0]["price_status"], "tws_received")
        self.assertEqual(rows[0]["price_source"], "marketPrice")
        self.assertEqual(rows[0]["price_last_successful_at"], "2026-11-11T10:00:00+00:00")

    def test_stale_quote_blocks_execution_but_preserves_theoretical_sell_intent(self):
        row = {
            "symbol": "UBER", "position_price_status": "cached_stale", "owned_share_quantity": 10,
            "action": "Sell", "desired_action": "Sell", "action_amount_direction": "sell",
            "suggested_share_count": 10, "action_amount": 730, "executable_action_amount": 730,
        }

        web_server.block_stale_price_execution([row])

        self.assertEqual(row["desired_action"], "Sell")
        self.assertEqual(row["action"], "Watch / Price Refresh")
        self.assertEqual(row["executable_action"], "Watch / Price Refresh")
        self.assertEqual(row["suggested_share_count"], 0)
        self.assertEqual(row["executable_action_amount"], 0)
        self.assertIn("cached price requires refresh", row["price_refresh_diagnostic"])


if __name__ == "__main__":
    unittest.main()
