"""Repeatable synthetic, read-only-to-production Stage 1 benchmark.

Run in either the baseline or optimized worktree with identical arguments.
"""

import argparse
import inspect
import json
import os
import statistics
import tempfile
import time
from unittest import mock

import web_server


def seed(conn, symbols, versions):
    now = "2026-01-01T00:00:00+00:00"
    for index in range(symbols):
        symbol = f"S{index:05d}"
        cursor = conn.execute("INSERT INTO analysis_roots (symbol, created_at, updated_at) VALUES (?, ?, ?)", (symbol, now, now))
        root_id = cursor.lastrowid
        for version in range(versions):
            cursor = conn.execute(
                "INSERT INTO analysis_versions (analysis_root_id, version_number, symbol, current_price, expected_price, expected_cagr, upside, confidence_level, created_at) VALUES (?, ?, ?, 100, 150, 10, 50, 6, ?)",
                (root_id, version + 1, symbol, now),
            )
            version_id = cursor.lastrowid
            for kind in ("Bullish", "Bearish"):
                for category in ("Core Driver", "Potential Driver"):
                    conn.execute("INSERT INTO analysis_version_key_variables (analysis_version_id, variable_text, variable_type, driver_category, confidence, importance, created_at) VALUES (?, 'x', ?, ?, 6, 5, ?)", (version_id, kind, category, now))
            conn.execute("INSERT INTO analysis_version_scenario_passes (analysis_version_id, pass_index, validation_status, created_at) VALUES (?, 1, 'valid', ?)", (version_id, now))
        conn.execute("INSERT INTO recent_event_checks (symbol, checked_at) VALUES (?, ?)", (symbol, now))
    conn.commit()
    positions = [
        {"symbol": f"S{index:05d}", "position": index + 1, "avgCost": 90, "price": 100, "marketValue": (index + 1) * 100}
        for index in range(min(symbols, 10))
    ]
    if positions:
        web_server.save_positions_cache(conn, positions, account_id="U_BENCHMARK")
        web_server.save_portfolio_summary_cache(conn, {"net_liquidation": 100000, "actual_cash": 90000}, account_id="U_BENCHMARK")


def median_ms(fn, iterations):
    durations = []
    for _ in range(iterations):
        start = time.perf_counter()
        fn()
        durations.append((time.perf_counter() - start) * 1000)
    return round(statistics.median(durations), 3)


def run(symbols=40, versions=4, iterations=3):
    with tempfile.TemporaryDirectory(prefix="bakingmoney-stage1-") as directory:
        db_path = os.path.join(directory, "synthetic.db")
        with mock.patch.object(web_server, "DB_PATH", db_path):
            web_server.init_db()
            conn = web_server.get_db_connection()
            try:
                seed(conn, symbols, versions)
                results = {}
                cached_positions = web_server.load_positions_cache(conn, account_id="U_BENCHMARK")
                results["analysis_list_ms"] = median_ms(lambda: web_server.list_analysis_symbols(conn), iterations)
                results["positions_payload_ms"] = median_ms(lambda: web_server.build_positions_payload(conn, cached_positions, "cached", account_id="U_BENCHMARK"), iterations)
                results["positions_cache_ms"] = median_ms(lambda: web_server.load_positions_cache(conn, account_id="U_BENCHMARK"), iterations)
                class Capture:
                    def _send_json(self, payload, status=200):
                        json.dumps(payload)

                capture = Capture()
                results["analysis_endpoint_ms"] = median_ms(lambda: web_server.BakingMoneyHandler.handle_analysis_get(capture), iterations)
                results["positions_endpoint_ms"] = median_ms(lambda: web_server.BakingMoneyHandler.handle_positions_api(capture), iterations)
                ownership_supported = "ownership_only" in inspect.signature(web_server.BakingMoneyHandler.handle_positions_api).parameters
                def analysis_screen():
                    web_server.BakingMoneyHandler.handle_analysis_get(capture)
                    web_server.BakingMoneyHandler.handle_positions_api(capture, **({"ownership_only": True} if ownership_supported else {}))
                def positions_screen():
                    web_server.BakingMoneyHandler.handle_positions_api(capture)
                    if not ownership_supported:
                        web_server.BakingMoneyHandler.handle_analysis_get(capture)
                results["analysis_screen_backend_ms"] = median_ms(analysis_screen, iterations)
                results["positions_screen_backend_ms"] = median_ms(positions_screen, iterations)
                data = web_server.list_analysis_symbols(conn)
                results["json_serialization_ms"] = median_ms(lambda: json.dumps({"analysis": data}), iterations)
                query = "SELECT MAX(checked_at) FROM recent_event_checks WHERE symbol = ?"
                results["event_confidence_query_ms"] = median_ms(lambda: conn.execute(query, ("S00000",)).fetchone(), iterations)
                results["event_query_plan"] = [tuple(row) for row in conn.execute("EXPLAIN QUERY PLAN " + query, ("S00000",))]
                results["counts"] = {table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in ("analysis_roots", "analysis_versions", "analysis_version_key_variables", "analysis_version_scenario_passes", "recent_event_checks", "positions_cache")}
                return results
            finally:
                conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", type=int, default=40)
    parser.add_argument("--versions", type=int, default=4)
    parser.add_argument("--iterations", type=int, default=3)
    arguments = parser.parse_args()
    print(json.dumps(run(arguments.symbols, arguments.versions, arguments.iterations), indent=2))
