#!/usr/bin/env python3
r"""Standalone IBKR/TWS historical daily bar smoke test for future Momentum Score inputs.

PowerShell example:
    cd C:\Users\alexa\Documents\bakingmoney
    .\.venv\Scripts\activate
    python test_tws_historical_momentum_data.py --symbols NVDA MSFT AMZN UBER RBRK GOOGL AVGO --benchmark QQQ --duration "1 Y" --save-csv
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import math
import os
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Sequence

from momentum_service import calculate_momentum_snapshot

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency
    load_dotenv = None

try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

try:
    from ib_insync import IB, Stock
except ImportError as exc:  # pragma: no cover - environment-dependent
    print("ERROR: ib_insync is required. Install it in your virtualenv before running this script.")
    raise SystemExit(1) from exc

DEFAULT_SYMBOLS = ["NVDA", "MSFT", "AMZN", "UBER"]
DEFAULT_BENCHMARK = "QQQ"
DEFAULT_DURATION = "1 Y"
OUTPUT_DIR = Path("tws_historical_test_output")


@dataclass(frozen=True)
class DailyBar:
    day: date | str
    open: float | None
    high: float | None
    low: float | None
    close: float | None
    volume: float | None


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Test whether TWS/IBKR can provide historical daily price/volume bars for momentum inputs."
    )
    parser.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS, help="Symbols to test. Default: NVDA MSFT AMZN UBER")
    parser.add_argument("--benchmark", default=DEFAULT_BENCHMARK, help="Benchmark symbol for relative strength. Default: QQQ")
    parser.add_argument("--duration", default=DEFAULT_DURATION, help='IBKR duration string. Default: "1 Y"')
    parser.add_argument("--save-csv", action="store_true", help="Save raw daily bars to tws_historical_test_output/*.csv")
    return parser.parse_args(argv)


def load_environment() -> None:
    if load_dotenv is not None:
        load_dotenv()


def env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or str(raw).strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        print(f"WARNING: {name}={raw!r} is not an integer; using {default}.")
        return default


def connect_ib() -> IB:
    host = os.getenv("IB_HOST", "127.0.0.1")
    port = env_int("IB_PORT", 7496)
    client_id = env_int("IB_CLIENT_ID", 10)
    ib = IB()

    def on_error(req_id, error_code, error_string, contract):
        contract_label = f" contract={contract}" if contract else ""
        print(f"TWS ERROR reqId={req_id} code={error_code}: {error_string}{contract_label}")

    ib.errorEvent += on_error
    print(f"Connecting to TWS/IBKR at {host}:{port} clientId={client_id} ...")
    ib.connect(host, port, clientId=client_id)
    return ib


def normalize_symbol(symbol: str) -> str:
    return str(symbol or "").strip().upper()


def request_daily_bars(ib: IB, symbol: str, duration: str) -> list[DailyBar]:
    contract = Stock(normalize_symbol(symbol), "SMART", "USD")
    bars = ib.reqHistoricalData(
        contract,
        endDateTime="",
        durationStr=duration,
        barSizeSetting="1 day",
        whatToShow="TRADES",
        useRTH=True,
        formatDate=1,
        keepUpToDate=False,
    )
    return [
        DailyBar(
            day=bar.date,
            open=safe_float(bar.open),
            high=safe_float(bar.high),
            low=safe_float(bar.low),
            close=safe_float(bar.close),
            volume=safe_float(bar.volume),
        )
        for bar in bars
    ]


def safe_float(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def calculate_metrics(symbol: str, bars: Sequence[DailyBar], benchmark_bars: Sequence[DailyBar]) -> dict[str, object]:
    snapshot = calculate_momentum_snapshot(bars, benchmark_bars)
    metrics = snapshot["metrics"]
    return {
        "symbol": symbol,
        "quality": snapshot["momentum_status"],
        "bars": metrics.get("bars"),
        "first_date": metrics.get("first_date"),
        "last_date": metrics.get("last_date"),
        "latest_close": metrics.get("latest_close"),
        "volume_available": metrics.get("has_volume"),
        "ret_20": metrics.get("ret_20"),
        "ret_60": metrics.get("ret_60"),
        "ret_120": metrics.get("ret_120"),
        "rel_20": metrics.get("rel_20"),
        "rel_60": metrics.get("rel_60"),
        "rel_120": metrics.get("rel_120"),
        "sma_50": metrics.get("sma_50"),
        "sma_200": metrics.get("sma_200"),
        "price_vs_50": metrics.get("price_vs_sma_50"),
        "price_vs_200": metrics.get("price_vs_sma_200"),
        "sma_50_slope_20": metrics.get("sma_50_slope_20d"),
        "high_52w": metrics.get("high_52w"),
        "distance_52w_high": metrics.get("distance_from_52w_high"),
        "avg_vol_20": metrics.get("avg_vol_20"),
        "avg_vol_60": metrics.get("avg_vol_60"),
        "vol_20_60_ratio": metrics.get("volume_ratio_20_60"),
        "up_down_vol_ratio_60": metrics.get("up_down_volume_ratio"),
        "momentum_score": snapshot.get("momentum_score"),
        "momentum_label": snapshot.get("momentum_label"),
        "extension_risk": snapshot.get("extension_risk"),
        "extension_label": snapshot.get("extension_label"),
    }

def save_bars_csv(symbol: str, bars: Sequence[DailyBar], output_dir: Path = OUTPUT_DIR) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{normalize_symbol(symbol)}_daily_bars.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["date", "open", "high", "low", "close", "volume"])
        for bar in bars:
            writer.writerow([bar.day, bar.open, bar.high, bar.low, bar.close, bar.volume])
    return path


def fmt_number(value: object, digits: int = 2) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, bool):
        return "Y" if value else "N"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            return "N/A"
        return f"{value:,.{digits}f}"
    return str(value)


def print_summary_table(metrics_rows: Sequence[dict[str, object]]) -> None:
    columns = [
        ("Symbol", "symbol", 8),
        ("Qual", "quality", 5),
        ("Bars", "bars", 5),
        ("First", "first_date", 10),
        ("Last", "last_date", 10),
        ("Close", "latest_close", 10),
        ("Vol?", "volume_available", 5),
        ("Mom", "momentum_score", 6),
        ("Mom Label", "momentum_label", 15),
        ("Ext", "extension_risk", 6),
        ("Ext Label", "extension_label", 14),
        ("20D%", "ret_20", 8),
        ("60D%", "ret_60", 8),
        ("120D%", "ret_120", 8),
        ("RS20%", "rel_20", 8),
        ("RS60%", "rel_60", 8),
        ("RS120%", "rel_120", 8),
        ("SMA50", "sma_50", 10),
        ("SMA200", "sma_200", 10),
        ("P/50%", "price_vs_50", 8),
        ("P/200%", "price_vs_200", 8),
        ("50Slope%", "sma_50_slope_20", 9),
        ("52W High", "high_52w", 10),
        ("FromHigh%", "distance_52w_high", 10),
        ("AvgVol20", "avg_vol_20", 12),
        ("AvgVol60", "avg_vol_60", 12),
        ("Vol20/60", "vol_20_60_ratio", 9),
        ("Up/DownVol", "up_down_vol_ratio_60", 10),
    ]
    header = " ".join(label.ljust(width) for label, _key, width in columns)
    print("\n" + header)
    print("-" * len(header))
    for row in metrics_rows:
        cells = []
        for _label, key, width in columns:
            digits = 0 if key in {"avg_vol_20", "avg_vol_60"} else 2
            cells.append(fmt_number(row.get(key), digits=digits).ljust(width))
        print(" ".join(cells))


def main(argv: Sequence[str]) -> int:
    args = parse_args(argv)
    load_environment()
    symbols = [normalize_symbol(symbol) for symbol in args.symbols if normalize_symbol(symbol)]
    benchmark = normalize_symbol(args.benchmark)
    if benchmark not in symbols:
        request_symbols = [benchmark, *symbols]
    else:
        request_symbols = symbols

    print("Historical momentum data smoke test")
    print("Suggested PowerShell run:")
    print(r'  cd C:\Users\alexa\Documents\bakingmoney')
    print(r'  .\.venv\Scripts\activate')
    print(r'  python test_tws_historical_momentum_data.py --symbols NVDA MSFT AMZN UBER RBRK GOOGL AVGO --benchmark QQQ --duration "1 Y" --save-csv')
    print(f"\nSymbols: {' '.join(symbols)} | Benchmark: {benchmark} | Duration: {args.duration}")

    ib = None
    bars_by_symbol: dict[str, list[DailyBar]] = {}
    try:
        ib = connect_ib()
        for symbol in request_symbols:
            try:
                print(f"Requesting {args.duration} daily TRADES bars for {symbol} ...")
                bars = request_daily_bars(ib, symbol, args.duration)
                bars_by_symbol[symbol] = bars
                print(f"  received {len(bars)} bars for {symbol}")
                if args.save_csv:
                    path = save_bars_csv(symbol, bars)
                    print(f"  saved {path}")
            except Exception as exc:  # keep going if one symbol fails
                print(f"ERROR: failed to retrieve {symbol}: {exc}")
    except Exception as exc:
        print(f"ERROR: could not connect to TWS/IBKR or complete requests: {exc}")
        return 1
    finally:
        if ib is not None and ib.isConnected():
            ib.disconnect()
            print("Disconnected from TWS/IBKR.")

    benchmark_bars = bars_by_symbol.get(benchmark, [])
    if not benchmark_bars:
        print(f"ERROR: benchmark {benchmark} did not return bars; relative-strength metrics will be N/A.")

    rows = []
    for symbol in symbols:
        bars = bars_by_symbol.get(symbol)
        if not bars:
            print(f"ERROR: no bars available for {symbol}; skipping metrics.")
            continue
        try:
            rows.append(calculate_metrics(symbol, bars, benchmark_bars))
        except Exception as exc:
            print(f"ERROR: failed to calculate metrics for {symbol}: {exc}")

    if rows:
        print_summary_table(rows)
    else:
        print("No symbol metrics to display.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
