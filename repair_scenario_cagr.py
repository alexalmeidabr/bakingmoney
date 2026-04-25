#!/usr/bin/env python3
"""One-time repair utility for scenario CAGR values stored in SQLite.

This script recalculates CAGR values for both versioned and legacy scenario tables
using a 5-year horizon and current-price values from their parent rows.

Safety features:
- Preflight check that blocks execution until backend CAGR computation appears fixed.
- Timestamped DB backup before any write.
- Transactional updates with rollback on failure.
- Dry-run support.
"""

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
from typing import Iterable

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = BASE_DIR / "bakingmoney.db"
BACKUP_DIR = BASE_DIR / "backups"
YEARS = 5
TOLERANCE = 0.0001
SAMPLE_LIMIT = 5


@dataclass
class RowRepairResult:
    row_id: int
    before_low: float
    before_high: float
    after_low: float
    after_high: float


@dataclass
class TableSummary:
    name: str
    scanned: int = 0
    updated: int = 0
    skipped: int = 0
    unchanged: int = 0
    sample_changes: list[RowRepairResult] | None = None
    skip_reasons: Counter | None = None

    def __post_init__(self) -> None:
        if self.sample_changes is None:
            self.sample_changes = []
        if self.skip_reasons is None:
            self.skip_reasons = Counter()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Repair stored CAGR values in analysis scenario tables.",
    )
    parser.add_argument(
        "--db-path",
        default=str(DEFAULT_DB_PATH),
        help=f"Path to SQLite database (default: {DEFAULT_DB_PATH})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute and print proposed changes without writing to the database.",
    )
    return parser.parse_args()


def is_valid_positive_number(value: object) -> bool:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(numeric) and numeric > 0


def compute_cagr(price: float, current_price: float) -> float:
    return ((price / current_price) ** (1 / YEARS) - 1) * 100


def materially_differs(stored: float, computed: float, tolerance: float = TOLERANCE) -> bool:
    return abs(stored - computed) > tolerance


def create_backup(db_path: Path) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup_path = BACKUP_DIR / f"bakingmoney-cagr-repair-{timestamp}.db"
    shutil.copy2(db_path, backup_path)
    return backup_path


def confirm_backend_cagr_is_computed_in_code(base_dir: Path) -> tuple[bool, list[str]]:
    """Block repair unless backend code appears to own CAGR computation.

    This check intentionally errs on the safe side because this script is intended
    to run only after scenario generation no longer depends on AI-provided CAGR.
    """

    web_server_path = base_dir / "web_server.py"
    if not web_server_path.exists():
        return False, [f"Missing required file: {web_server_path}"]

    text = web_server_path.read_text(encoding="utf-8")
    blockers: list[str] = []

    blocker_patterns = {
        "Scenario prompt still includes AI CAGR fields": '"cagr_low": 0, "cagr_high": 0',
        "Scenario schema still requires AI CAGR fields": '"required": ["name", "price_low", "price_high", "cagr_low", "cagr_high", "probability"]',
        "Scenario validation still parses AI CAGR fields": 'float(item.get("cagr_low"))',
        "Scenario aggregation still computes median from AI CAGR": 'statistics.median([v["cagr_low"] for v in scenario_values])',
        "Scenario persistence still stores cagr_low from scenario payload": 'scenario["cagr_low"]',
    }
    for reason, pattern in blocker_patterns.items():
        if pattern in text:
            blockers.append(reason)

    if "** (1 / 5)" not in text and "* 100" not in text:
        blockers.append("Could not detect backend CAGR formula implementation in web_server.py")

    return (len(blockers) == 0), blockers


def repair_table(
    conn: sqlite3.Connection,
    table_name: str,
    select_sql: str,
    update_sql: str,
    dry_run: bool,
) -> TableSummary:
    summary = TableSummary(name=table_name)

    rows = conn.execute(select_sql).fetchall()
    summary.scanned = len(rows)

    for row in rows:
        row_id = int(row["id"])
        current_price = row["current_price"]
        price_low = row["price_low"]
        price_high = row["price_high"]

        invalid_reasons: list[str] = []
        if not is_valid_positive_number(current_price):
            invalid_reasons.append("invalid_current_price")
        if not is_valid_positive_number(price_low):
            invalid_reasons.append("invalid_price_low")
        if not is_valid_positive_number(price_high):
            invalid_reasons.append("invalid_price_high")

        if invalid_reasons:
            summary.skipped += 1
            for reason in invalid_reasons:
                summary.skip_reasons[reason] += 1
            print(f"[{table_name}] skip id={row_id}: {', '.join(invalid_reasons)}")
            continue

        current_price_f = float(current_price)
        price_low_f = float(price_low)
        price_high_f = float(price_high)
        stored_low = float(row["cagr_low"])
        stored_high = float(row["cagr_high"])

        computed_low = compute_cagr(price_low_f, current_price_f)
        computed_high = compute_cagr(price_high_f, current_price_f)

        low_differs = materially_differs(stored_low, computed_low)
        high_differs = materially_differs(stored_high, computed_high)

        if not low_differs and not high_differs:
            summary.unchanged += 1
            continue

        summary.updated += 1
        if len(summary.sample_changes) < SAMPLE_LIMIT:
            summary.sample_changes.append(
                RowRepairResult(
                    row_id=row_id,
                    before_low=stored_low,
                    before_high=stored_high,
                    after_low=computed_low,
                    after_high=computed_high,
                )
            )

        if not dry_run:
            conn.execute(update_sql, (computed_low, computed_high, row_id))

    return summary


def print_summary(backup_path: Path | None, summaries: Iterable[TableSummary], dry_run: bool) -> None:
    print("\n=== CAGR Repair Summary ===")
    if dry_run:
        print("Mode: DRY RUN (no DB writes)")
    print(f"Backup: {backup_path if backup_path else '(not created in dry-run mode)'}")

    for summary in summaries:
        print(f"\nTable: {summary.name}")
        print(f"  scanned: {summary.scanned}")
        print(f"  updated: {summary.updated}")
        print(f"  skipped: {summary.skipped}")
        print(f"  unchanged: {summary.unchanged}")

        if summary.skip_reasons:
            reasons = ", ".join(f"{k}={v}" for k, v in sorted(summary.skip_reasons.items()))
            print(f"  skip_reasons: {reasons}")

        if summary.sample_changes:
            print("  sample_changes:")
            for change in summary.sample_changes:
                print(
                    "    "
                    f"id={change.row_id} "
                    f"cagr_low {change.before_low:.6f} -> {change.after_low:.6f}; "
                    f"cagr_high {change.before_high:.6f} -> {change.after_high:.6f}"
                )


def main() -> int:
    args = parse_args()
    db_path = Path(args.db_path).expanduser().resolve()

    if not db_path.exists():
        print(f"Error: database file does not exist: {db_path}", file=sys.stderr)
        return 1

    check_ok, blockers = confirm_backend_cagr_is_computed_in_code(BASE_DIR)
    if not check_ok:
        print("Error: refusing to run repair until backend CAGR generation is confirmed fixed.", file=sys.stderr)
        for blocker in blockers:
            print(f" - {blocker}", file=sys.stderr)
        return 2

    backup_path: Path | None = None

    try:
        if not args.dry_run:
            try:
                backup_path = create_backup(db_path)
            except Exception as exc:
                print(f"Error: failed to create backup; aborting without changes: {exc}", file=sys.stderr)
                return 3

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            if not args.dry_run:
                conn.execute("BEGIN")

            version_summary = repair_table(
                conn=conn,
                table_name="analysis_version_scenarios",
                select_sql="""
                    SELECT
                        s.id,
                        s.price_low,
                        s.price_high,
                        s.cagr_low,
                        s.cagr_high,
                        v.current_price
                    FROM analysis_version_scenarios s
                    JOIN analysis_versions v ON v.id = s.analysis_version_id
                """,
                update_sql="""
                    UPDATE analysis_version_scenarios
                    SET cagr_low = ?, cagr_high = ?
                    WHERE id = ?
                """,
                dry_run=args.dry_run,
            )

            legacy_summary = repair_table(
                conn=conn,
                table_name="analysis_scenarios",
                select_sql="""
                    SELECT
                        s.id,
                        s.price_low,
                        s.price_high,
                        s.cagr_low,
                        s.cagr_high,
                        a.current_price
                    FROM analysis_scenarios s
                    JOIN analysis_symbols a ON a.id = s.analysis_symbol_id
                """,
                update_sql="""
                    UPDATE analysis_scenarios
                    SET cagr_low = ?, cagr_high = ?
                    WHERE id = ?
                """,
                dry_run=args.dry_run,
            )

            if not args.dry_run:
                conn.commit()
        except Exception:
            if not args.dry_run:
                conn.rollback()
            raise
        finally:
            conn.close()

    except Exception as exc:
        print(f"Error: repair failed: {exc}", file=sys.stderr)
        return 4

    print_summary(backup_path, [version_summary, legacy_summary], dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
