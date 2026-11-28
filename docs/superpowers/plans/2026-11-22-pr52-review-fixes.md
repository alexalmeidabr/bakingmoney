# PR #52 Review Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correct PR #52's timestamp/quote-precedence defects and protect unsaved simulation trigger edits without changing established Simulator calculations or scope.

**Architecture:** Keep `action_plan_prices.py` as the shared resolver, but carry explicit UTC market-observation, retrieval, and persistence timestamps through SQLite, position refreshes, API rows, trigger evaluation, and UI labels. Extend the shared trigger editor with a normalized baseline and revision-aware simulator-only navigation guard.

**Tech Stack:** Python 3, SQLite, vanilla JavaScript, `unittest`, `node:test`, headless Chromium/Edge smoke test.

**Spec:** `docs/superpowers/specs/2026-11-22-pr52-review-fixes-design.md`

## Global Constraints

- Update existing PR #52 on `codex/persistent-action-plan-simulator`; keep base `codex/action-plan-view-parity` and do not merge or create a PR.
- Do not reinterpret historical retrieval timestamps as confirmed market observations.
- Preserve account/contract isolation, coherent quote snapshots, last-usable-price retention, analysis fallback ordering, and trigger eligibility without a five-minute gate.
- Preserve real Action Plan trigger persistence and every existing Simulator calculation and CRUD behavior.
- Use backward-compatible SQLite column migration and retain backup/restore compatibility.

## Review Focus

- A later retrieval of an older close must not outrank a known newer market observation.
- A type-4 delayed-frozen source must remain distinguishable from delayed and frozen data.
- Legacy database rows with only `price_last_successful_at` must load as unknown-market-time retrievals.
- A clear/save response arriving after another edit must leave the newer edit visible and dirty.
- Every simulator exit path must cancel cleanly when discard confirmation is rejected.

---

### Task 1: Explicit timestamp model and deterministic resolver

**Files:**
- Modify: `action_plan_prices.py`
- Modify: `test_action_plan_latest_prices.py`

**Interfaces:**
- Produces normalized observation fields `market_observed_at`, `retrieved_at`, `persisted_at`, `price_timestamp_kind`, and compatibility `price_last_successful_at`.
- Produces deterministic source classes and selection ordering: known market time, source quality, retrieval fallback, stable candidate identity.

- [ ] Write focused failing tests for newer live vs older later-retrieved close, newer delayed vs older live, equal live/delayed, equal delayed/frozen, unknown frozen, cached-known vs refreshed-unknown, all-missing time, invalid values, account/contract isolation, failed persistence, restart, and legacy migration semantics.
- [ ] Run `python -m unittest test_action_plan_latest_prices -v` and confirm failures identify conflated timestamps/precedence.
- [ ] Implement timestamp normalization, source classification, ranking, warnings, schema columns, and replacement logic without combining candidates.
- [ ] Run `python -m unittest test_action_plan_latest_prices -v` and confirm all focused cases pass.

### Task 2: Carry provenance through TWS, caches, API, and UI

**Files:**
- Modify: `web_server.py`
- Modify: `static/app.js`
- Modify: `test_manual_quote_observation.py`
- Modify: `test_positions_price_freshness.js`
- Modify: `test_manual_execution_ui.js`
- Modify: `test_backup_restore.py`

**Interfaces:**
- Consumes Task 1 timestamp fields and ranking.
- Produces position-cache columns, live-row retrieval metadata, delayed-frozen source labels, trigger evaluation timestamp-kind fields, and accurate market-observed/retrieved UI wording.

- [ ] Write failing pipeline, migration, restart, failed-refresh, delayed/frozen provenance, trigger-state, and UI-label tests.
- [ ] Run the named Python/JavaScript tests and confirm failures occur at the old conflated fields or labels.
- [ ] Add backward-compatible cache/observation migrations and propagate the explicit fields through `_build_live_position_rows`, position persistence/load, explicit quote refresh, `build_action_plan`, and trigger evaluation.
- [ ] Update UI provenance formatting so known market time, retrieval-only time, and unknown time have distinct labels.
- [ ] Run the targeted Python and JavaScript tests and confirm they pass.

### Task 3: Simulation trigger editor dirty-state protection

**Files:**
- Modify: `static/app.js`
- Modify: `test_action_plan_simulator_ui.js`
- Modify: `test_manual_execution_ui.js`

**Interfaces:**
- Produces normalized trigger baseline/revision state, `simulationTriggerDirty()`, combined discard protection, and stale-response-safe save/clear behavior.
- Leaves real Action Plan editor navigation semantics unchanged.

- [ ] Write failing JavaScript tests for every field, revert-to-clean, price refresh, simulation/account/view/detail/table/analysis/refresh/delete/duplicate/unload guards, save success/failure, clear success, stale async responses, and real Action Plan isolation.
- [ ] Run `node --test test_action_plan_simulator_ui.js test_manual_execution_ui.js` and confirm the new tests fail for missing trigger dirty tracking.
- [ ] Implement normalized baseline comparison, revision tracking, combined simulator guard, and success/failure handling using the existing shared editor and endpoints.
- [ ] Run the two targeted JavaScript files and confirm all cases pass.

### Task 4: Documentation, regression validation, delivery

**Files:**
- Modify: `docs/action-plan-simulator.md`
- Modify: `docs/manual-execution-triggers.md`
- Modify: PR #52 description

**Interfaces:**
- Documents the exact precedence and timestamp labels plus simulator loss protection.

- [ ] Update developer/user documentation with the explicit precedence, migration meaning, and dirty-state behavior.
- [ ] Run `python -m unittest discover` and record the complete count and status.
- [ ] Run `node --test (Get-ChildItem -File -Filter 'test_*.js' | ForEach-Object { $_.Name })` and record counts/status.
- [ ] Run `node tools/smoke_action_plan_simulator.cjs` and `git diff --check`; record any limitation rather than implying CI or live IBKR coverage.
- [ ] Review the diff against every finding, commit the fixes to `codex/persistent-action-plan-simulator`, push without force, and update PR #52's description while retaining its PR #51 dependency.
