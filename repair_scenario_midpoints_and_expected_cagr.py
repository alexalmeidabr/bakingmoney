#!/usr/bin/env python3
"""One-time repair utility for scenario midpoint and expected CAGR backfill."""

from __future__ import annotations

import argparse
import math
import shutil
import sqlite3
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = BASE_DIR / "bakingmoney.db"
BACKUP_DIR = BASE_DIR / "backups"
YEARS = 5
TOLERANCE = 0.0001
SAMPLE_LIMIT = 5


@dataclass
class ScenarioSummary:
    name: str
    scanned: int = 0
    updated_price_mid: int = 0
    updated_cagr_mid: int = 0
    skipped: int = 0
    unchanged: int = 0
    skip_reasons: Counter = field(default_factory=Counter)
    samples: list[tuple] = field(default_factory=list)


@dataclass
class ExpectedSummary:
    name: str
    scanned: int = 0
    updated_expected_cagr: int = 0
    skipped: int = 0
    unchanged: int = 0
    skip_reasons: Counter = field(default_factory=Counter)
    samples: list[tuple] = field(default_factory=list)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill scenario price_mid, cagr_mid, and expected_cagr")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH), help=f"SQLite DB path (default: {DEFAULT_DB_PATH})")
    parser.add_argument("--dry-run", action="store_true", help="Calculate and report changes without writing")
    return parser.parse_args()


def finite_number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def positive_number(value):
    number = finite_number(value)
    if number is None or number <= 0:
        return None
    return number


def compute_price_mid(price_low, price_high):
    low = positive_number(price_low)
    high = positive_number(price_high)
    if low is None or high is None:
        return None
    return (low + high) / 2.0


def compute_cagr_mid(price_mid, current_price, years=YEARS):
    mid = positive_number(price_mid)
    current = positive_number(current_price)
    if mid is None or current is None:
        return None
    return ((mid / current) ** (1 / years) - 1) * 100


def materially_differs(current, computed, tolerance=TOLERANCE):
    cur = finite_number(current)
    cmp_value = finite_number(computed)
    if cur is None and cmp_value is None:
        return False
    if cur is None or cmp_value is None:
        return True
    return abs(cur - cmp_value) > tolerance


def create_backup(db_path: Path) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup_path = BACKUP_DIR / f"bakingmoney-midpoint-expected-cagr-repair-{ts}.db"
    shutil.copy2(db_path, backup_path)
    return backup_path


def repair_scenario_table(conn, table_name, select_sql, update_sql, dry_run):
    summary = ScenarioSummary(name=table_name)
    rows = conn.execute(select_sql).fetchall()
    summary.scanned = len(rows)

    for row in rows:
        row_id = row["id"]
        computed_price_mid = compute_price_mid(row["price_low"], row["price_high"])
        if computed_price_mid is None:
            summary.skipped += 1
            summary.skip_reasons["invalid_price_bounds"] += 1
            continue

        computed_cagr_mid = compute_cagr_mid(computed_price_mid, row["current_price"])
        if computed_cagr_mid is None:
            summary.skipped += 1
            summary.skip_reasons["invalid_current_price"] += 1
            continue

        price_changed = materially_differs(row["price_mid"], computed_price_mid)
        cagr_changed = materially_differs(row["cagr_mid"], computed_cagr_mid)

        if not price_changed and not cagr_changed:
            summary.unchanged += 1
            continue

        if price_changed:
            summary.updated_price_mid += 1
        if cagr_changed:
            summary.updated_cagr_mid += 1

        if len(summary.samples) < SAMPLE_LIMIT:
            summary.samples.append(
                (
                    row_id,
                    row["price_mid"],
                    computed_price_mid,
                    row["cagr_mid"],
                    computed_cagr_mid,
                )
            )

        if not dry_run:
            conn.execute(update_sql, (computed_price_mid, computed_cagr_mid, row_id))

    return summary


def compute_expected_cagr_from_rows(rows):
    weighted_sum = 0.0
    probability_sum = 0.0
    valid_points = 0

    for row in rows:
        probability = finite_number(row["probability"])
        cagr_mid = finite_number(row["cagr_mid"])
        if probability is None or cagr_mid is None:
            continue
        weighted_sum += probability * cagr_mid
        probability_sum += probability
        valid_points += 1

    if valid_points == 0 or probability_sum <= 0:
        return None
    return weighted_sum / probability_sum


def repair_expected_cagr_table(conn, table_name, id_col, scenario_table, scenario_fk, dry_run):
    summary = ExpectedSummary(name=table_name)

    parent_rows = conn.execute(f"SELECT {id_col} AS id, expected_cagr FROM {table_name} ORDER BY {id_col} ASC").fetchall()
    summary.scanned = len(parent_rows)

    scenario_rows = conn.execute(
        f"SELECT {scenario_fk} AS parent_id, probability, cagr_mid FROM {scenario_table} ORDER BY {scenario_fk} ASC"
    ).fetchall()

    grouped = {}
    for row in scenario_rows:
        grouped.setdefault(row["parent_id"], []).append(row)

    for parent in parent_rows:
        parent_id = parent["id"]
        rows = grouped.get(parent_id, [])

        if not rows:
            summary.skipped += 1
            summary.skip_reasons["no_scenarios"] += 1
            continue

        computed_expected_cagr = compute_expected_cagr_from_rows(rows)
        if computed_expected_cagr is None:
            summary.skipped += 1
            summary.skip_reasons["invalid_scenario_inputs"] += 1
            continue

        if not materially_differs(parent["expected_cagr"], computed_expected_cagr):
            summary.unchanged += 1
            continue

        summary.updated_expected_cagr += 1
        if len(summary.samples) < SAMPLE_LIMIT:
            summary.samples.append((parent_id, parent["expected_cagr"], computed_expected_cagr))

        if not dry_run:
            conn.execute(
                f"UPDATE {table_name} SET expected_cagr = ? WHERE {id_col} = ?",
                (computed_expected_cagr, parent_id),
            )

    return summary


def print_scenario_summary(summary: ScenarioSummary):
    print(f"Table: {summary.name}")
    print(f"  scanned: {summary.scanned}")
    print(f"  updated_price_mid: {summary.updated_price_mid}")
    print(f"  updated_cagr_mid: {summary.updated_cagr_mid}")
    print(f"  skipped: {summary.skipped}")
    print(f"  unchanged: {summary.unchanged}")
    if summary.skip_reasons:
        reasons = ", ".join(f"{k}={v}" for k, v in sorted(summary.skip_reasons.items()))
        print(f"  skip_reasons: {reasons}")
    if summary.samples:
        print("  sample_changes:")
        for sample in summary.samples:
            print(
                "    "
                f"id={sample[0]} price_mid {sample[1]} -> {sample[2]}; "
                f"cagr_mid {sample[3]} -> {sample[4]}"
            )


def print_expected_summary(summary: ExpectedSummary):
    print(f"Table: {summary.name}")
    print(f"  scanned: {summary.scanned}")
    print(f"  updated_expected_cagr: {summary.updated_expected_cagr}")
    print(f"  skipped: {summary.skipped}")
    print(f"  unchanged: {summary.unchanged}")
    if summary.skip_reasons:
        reasons = ", ".join(f"{k}={v}" for k, v in sorted(summary.skip_reasons.items()))
        print(f"  skip_reasons: {reasons}")
    if summary.samples:
        print("  sample_changes:")
        for sample in summary.samples:
            print(f"    id={sample[0]} expected_cagr {sample[1]} -> {sample[2]}")


def main() -> int:
    args = parse_args()
    db_path = Path(args.db_path).expanduser().resolve()

    if not db_path.exists():
        print(f"Error: database file does not exist: {db_path}", file=sys.stderr)
        return 1

    backup_path = None
    if not args.dry_run:
        try:
            backup_path = create_backup(db_path)
        except Exception as exc:
            print(f"Error: failed to create backup; aborting without DB changes: {exc}", file=sys.stderr)
            return 2

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    try:
        if not args.dry_run:
            conn.execute("BEGIN")

        version_scenarios_summary = repair_scenario_table(
            conn=conn,
            table_name="analysis_version_scenarios",
            select_sql="""
                SELECT s.id, s.price_low, s.price_high, s.price_mid, s.cagr_mid, v.current_price
                FROM analysis_version_scenarios s
                JOIN analysis_versions v ON v.id = s.analysis_version_id
            """,
            update_sql="UPDATE analysis_version_scenarios SET price_mid = ?, cagr_mid = ? WHERE id = ?",
            dry_run=args.dry_run,
        )

        legacy_scenarios_summary = repair_scenario_table(
            conn=conn,
            table_name="analysis_scenarios",
            select_sql="""
                SELECT s.id, s.price_low, s.price_high, s.price_mid, s.cagr_mid, a.current_price
                FROM analysis_scenarios s
                JOIN analysis_symbols a ON a.id = s.analysis_symbol_id
            """,
            update_sql="UPDATE analysis_scenarios SET price_mid = ?, cagr_mid = ? WHERE id = ?",
            dry_run=args.dry_run,
        )

        versions_summary = repair_expected_cagr_table(
            conn=conn,
            table_name="analysis_versions",
            id_col="id",
            scenario_table="analysis_version_scenarios",
            scenario_fk="analysis_version_id",
            dry_run=args.dry_run,
        )

        symbols_summary = repair_expected_cagr_table(
            conn=conn,
            table_name="analysis_symbols",
            id_col="id",
            scenario_table="analysis_scenarios",
            scenario_fk="analysis_symbol_id",
            dry_run=args.dry_run,
        )

        if not args.dry_run:
            conn.commit()
    except Exception as exc:
        if not args.dry_run:
            conn.rollback()
        print(f"Error: repair failed: {exc}", file=sys.stderr)
        return 3
    finally:
        conn.close()

    print("\n=== Midpoint / Expected CAGR Repair Summary ===")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print(f"Backup: {backup_path if backup_path else '(not created in dry-run mode)'}")
    print()
    print_scenario_summary(version_scenarios_summary)
    print()
    print_scenario_summary(legacy_scenarios_summary)
    print()
    print_expected_summary(versions_summary)
    print()
    print_expected_summary(symbols_summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
