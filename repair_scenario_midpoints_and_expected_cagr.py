#!/usr/bin/env python3
"""One-time repair utility for scenario midpoints and expected CAGR fields."""

from __future__ import annotations

import argparse
import math
import shutil
import sqlite3
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = BASE_DIR / "bakingmoney.db"
BACKUP_DIR = BASE_DIR / "backups"
YEARS = 5
TOLERANCE = 0.0001
SAMPLE_LIMIT = 5


@dataclass
class Summary:
    name: str
    scanned: int = 0
    updated: int = 0
    skipped: int = 0
    unchanged: int = 0
    skip_reasons: Counter | None = None

    def __post_init__(self):
        if self.skip_reasons is None:
            self.skip_reasons = Counter()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Repair scenario price_mid/cagr_mid and expected_cagr values.")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH), help=f"SQLite path (default: {DEFAULT_DB_PATH})")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    return parser.parse_args()


def finite_number(value):
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(num):
        return None
    return num


def positive_number(value):
    num = finite_number(value)
    if num is None or num <= 0:
        return None
    return num


def compute_price_mid(price_low, price_high):
    low = positive_number(price_low)
    high = positive_number(price_high)
    if low is None or high is None:
        return None
    return (low + high) / 2.0


def compute_cagr(price_target, current_price, years=YEARS):
    price = positive_number(price_target)
    current = positive_number(current_price)
    if price is None or current is None:
        return None
    return ((price / current) ** (1 / years) - 1) * 100


def materially_differs(current, computed, tol=TOLERANCE):
    cur = finite_number(current)
    cmp_v = finite_number(computed)
    if cur is None and cmp_v is None:
        return False
    if cur is None or cmp_v is None:
        return True
    return abs(cur - cmp_v) > tol


def create_backup(db_path: Path) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    dst = BACKUP_DIR / f"bakingmoney-midpoint-cagr-repair-{ts}.db"
    shutil.copy2(db_path, dst)
    return dst


def repair_scenario_table(conn, table_name, select_sql, update_sql, dry_run):
    summary = Summary(table_name)
    samples = []
    rows = conn.execute(select_sql).fetchall()
    summary.scanned = len(rows)

    for row in rows:
        row_id = row["id"]
        price_mid = compute_price_mid(row["price_low"], row["price_high"])
        cagr_mid = compute_cagr(price_mid, row["current_price"]) if price_mid is not None else None

        if price_mid is None:
            summary.skipped += 1
            summary.skip_reasons["invalid_price_range"] += 1
            continue

        if cagr_mid is None:
            summary.skip_reasons["invalid_current_price_for_cagr"] += 1
            cagr_mid = 0.0

        needs = materially_differs(row["price_mid"], price_mid) or materially_differs(row["cagr_mid"], cagr_mid)
        if not needs:
            summary.unchanged += 1
            continue

        summary.updated += 1
        if len(samples) < SAMPLE_LIMIT:
            samples.append((row_id, row["price_mid"], price_mid, row["cagr_mid"], cagr_mid))
        if not dry_run:
            conn.execute(update_sql, (price_mid, cagr_mid, row_id))

    return summary, samples


def calculate_expected_cagr_for_parent(conn, table, id_col, expected_table, expected_id_col):
    rows = conn.execute(
        f"""
        SELECT {id_col} AS parent_id, probability, cagr_mid
        FROM {table}
        ORDER BY {id_col} ASC
        """
    ).fetchall()

    grouped = {}
    for row in rows:
        grouped.setdefault(row["parent_id"], []).append(row)

    updates = []
    for parent_id, scenario_rows in grouped.items():
        total = 0.0
        weighted = 0.0
        valid = False
        for s in scenario_rows:
            p = finite_number(s["probability"])
            c = finite_number(s["cagr_mid"])
            if p is None or c is None:
                continue
            total += p
            weighted += p * c
            valid = True
        if not valid or total <= 0:
            value = None
        else:
            value = weighted / total
        updates.append((parent_id, value))

    return updates


def repair_expected_cagr(conn, table_name, id_col, scenario_table, scenario_fk, dry_run):
    summary = Summary(f"{table_name}.expected_cagr")
    samples = []
    target_rows = conn.execute(f"SELECT {id_col} AS id, expected_cagr FROM {table_name}").fetchall()
    summary.scanned = len(target_rows)
    by_id = {row["id"]: row["expected_cagr"] for row in target_rows}

    computed_updates = calculate_expected_cagr_for_parent(conn, scenario_table, scenario_fk, table_name, id_col)

    for parent_id, computed in computed_updates:
        current = by_id.get(parent_id)
        if not materially_differs(current, computed):
            summary.unchanged += 1
            continue
        summary.updated += 1
        if len(samples) < SAMPLE_LIMIT:
            samples.append((parent_id, current, computed))
        if not dry_run:
            conn.execute(f"UPDATE {table_name} SET expected_cagr = ? WHERE {id_col} = ?", (computed, parent_id))

    return summary, samples


def print_summary(backup_path, dry_run, summaries_with_samples):
    print("\n=== Midpoint/CAGR Repair Summary ===")
    print(f"Mode: {'DRY RUN' if dry_run else 'WRITE'}")
    print(f"Backup: {backup_path if backup_path else '(not created in dry-run mode)'}")
    for summary, samples in summaries_with_samples:
        print(f"\n{summary.name}")
        print(f"  scanned: {summary.scanned}")
        print(f"  updated: {summary.updated}")
        print(f"  skipped: {summary.skipped}")
        print(f"  unchanged: {summary.unchanged}")
        if summary.skip_reasons:
            print("  skip_reasons: " + ", ".join(f"{k}={v}" for k, v in sorted(summary.skip_reasons.items())))
        if samples:
            print("  sample_changes:")
            for sample in samples:
                print(f"    {sample}")


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
            print(f"Error: failed to create backup, aborting: {exc}", file=sys.stderr)
            return 2

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        if not args.dry_run:
            conn.execute("BEGIN")

        summaries = []
        summaries.append(
            repair_scenario_table(
                conn,
                "analysis_version_scenarios",
                """
                SELECT s.id, s.price_low, s.price_high, s.price_mid, s.cagr_mid, v.current_price
                FROM analysis_version_scenarios s
                JOIN analysis_versions v ON v.id = s.analysis_version_id
                """,
                "UPDATE analysis_version_scenarios SET price_mid = ?, cagr_mid = ? WHERE id = ?",
                args.dry_run,
            )
        )
        summaries.append(
            repair_scenario_table(
                conn,
                "analysis_scenarios",
                """
                SELECT s.id, s.price_low, s.price_high, s.price_mid, s.cagr_mid, a.current_price
                FROM analysis_scenarios s
                JOIN analysis_symbols a ON a.id = s.analysis_symbol_id
                """,
                "UPDATE analysis_scenarios SET price_mid = ?, cagr_mid = ? WHERE id = ?",
                args.dry_run,
            )
        )

        summaries.append(
            repair_expected_cagr(
                conn,
                table_name="analysis_versions",
                id_col="id",
                scenario_table="analysis_version_scenarios",
                scenario_fk="analysis_version_id",
                dry_run=args.dry_run,
            )
        )
        summaries.append(
            repair_expected_cagr(
                conn,
                table_name="analysis_symbols",
                id_col="id",
                scenario_table="analysis_scenarios",
                scenario_fk="analysis_symbol_id",
                dry_run=args.dry_run,
            )
        )

        if not args.dry_run:
            conn.commit()
    except Exception:
        if not args.dry_run:
            conn.rollback()
        raise
    finally:
        conn.close()

    print_summary(backup_path, args.dry_run, summaries)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
