# Manual Execution Triggers Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add account-scoped manual execution price gates and cash reservations to an opt-in Action Plan variant without changing the default Action Plan.

**Architecture:** Persist preferences independently of analysis versions. Reuse one Linear target calculation, copy its pre-funding rows, and run baseline and trigger-aware funding independently through the existing execution machinery.

**Tech Stack:** Python, SQLite, `http.server`, `unittest`, Node test runner.

**Spec:** [Backend design](../specs/2026-11-13-manual-execution-triggers-backend-design.md) and the user-provided PR 1 prompt.

## Global Constraints

- The default Action Plan payload and investment methodology remain unchanged.
- Trigger-aware results require `execution_modes=both`; no automatic TWS request on Action Plan GET.
- Manual preferences are scoped to an existing portfolio account and symbol.
- Dynamic Reserve precedes manual reservations; blocked sells yield no proceeds; blocked buys cannot reach Bootstrap.
- Existing and restored old databases remain compatible; no `.env` or user database changes.
- Draft PR only; do not merge.

## Review Focus

- An unowned symbol with a saved analysis price on the eligible side remains unverified.
- A TWS quote from the current session but older than five minutes cannot satisfy a trigger.
- A Sell/Trim recommendation changing between variants keeps one shared preference and produces no blocked proceeds.
- A blocked Buy that qualifies for Bootstrap cannot re-enter execution through that path.
- Two accounts with the same symbol cannot see or spend each other's reservations.

### Task 1: Persistence and account-scoped CRUD

**Files:** Modify `web_server.py`; create `test_manual_execution_persistence.py`.

**Interfaces:** `list_manual_execution_triggers(conn, account_id)`, `get_manual_execution_trigger(conn, account_id, symbol)`, `save_manual_execution_trigger(conn, account_id, symbol, payload)`, and `delete_manual_execution_trigger(conn, account_id, symbol)`.

- [x] Write failing tests for initialization, idempotence, existing-data upgrade, CRUD, invalid values, account ambiguity/isolation, and backup/restore.
- [x] Run `python -m unittest test_manual_execution_persistence -v` and confirm expected failures.
- [x] Add table and validators; add GET/PUT/DELETE routing and handlers with account resolution.
- [x] Run the focused tests and commit the working task.

### Task 2: Trigger evaluation and reservation arithmetic

**Files:** Modify `web_server.py`; create `test_manual_execution_engine.py`.

**Interfaces:** `evaluate_manual_execution_trigger(row, preference, now=None)` returns status and quote diagnostics; `calculate_manual_reservation(row, preference, portfolio_value, minimum_trade_amount)` returns planned shares/amount and requested reservation.

- [x] Write failing threshold, no-trigger, stale/analysis-price/unowned, rounding, existing-holdings, zero/disabled, and minimum-trade tests.
- [x] Run `python -m unittest test_manual_execution_engine -v` and confirm expected failures.
- [x] Implement the pure evaluation and arithmetic helpers.
- [x] Run focused tests and commit the working task.

### Task 3: Independent trigger-aware funding

**Files:** Modify `web_server.py`; extend `test_manual_execution_engine.py`.

**Interfaces:** `compute_linear_action_plan(..., manual_triggers=None)` returns original `rows`/`summary`, plus `manual_execution` only when requested; `_apply_linear_cash_constrained_execution_layer(..., manual_execution=False)` preserves default behavior.

- [x] Write failing tests for unchanged baseline, blocked Buy/Sell, eligible Sell proceeds, Dynamic Reserve precedence, partial priority allocation, eligible Buy reallocation, Bootstrap exclusion, and no cash double counting.
- [x] Run focused tests and confirm expected failures.
- [x] Copy pre-funding rows and add manual statuses before independent execution passes; integrate reservations into the existing funding budget.
- [x] Run focused and existing Linear tests; commit the working task.

### Task 4: Action Plan API and full integration

**Files:** Modify `web_server.py`; create `test_manual_execution_api.py`; update the backend design if a verified-price limitation changes.

**Interfaces:** `build_action_plan(conn, account_id=None, include_manual_execution=False)`; opt-in list and detail handlers expose `manual_execution` and `manual_execution_detail` without changing default JSON.

- [x] Write failing tests for default/opt-in payload equivalence, detail consistency, account isolation, unowned confirmation, selected account errors, and shared-analysis call count.
- [x] Run focused tests and confirm expected failures.
- [x] Wire preferences and independent execution results into list/detail API routes.
- [x] Run focused tests, full Python and Node suites, syntax checks, and `git diff --check`; commit and push.
- [x] Open a draft PR against `main` with architecture, contracts, formulas, price freshness, baseline evidence, test counts, and PR 2 limitations; do not merge.
