# PR #52 Remaining Review Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate trigger mutation races, isolate persisted prices by IBKR contract, and correct position-cache legacy timestamp fallback.

**Architecture:** Add a context-keyed frontend mutation lock shared by Save and Clear. Rebuild the observation table transactionally around a composite contract key and return grouped observations to the shared resolver. Keep timestamp compatibility at the cache boundary without promoting legacy metadata when an explicit market observation exists.

**Tech Stack:** Python 3, SQLite, vanilla JavaScript, `unittest`, `node:test`, headless Microsoft Edge.

**Spec:** `docs/superpowers/specs/2026-11-22-pr52-remaining-review-fixes-design.md`

## Global Constraints

- Update existing PR #52 on `codex/persistent-action-plan-simulator`; keep base `codex/action-plan-view-parity` and do not merge or create a PR.
- Preserve current timestamp/source precedence, trigger eligibility, simulation calculations, account isolation, backup/restore, and PR #51 UI behavior.
- No unrelated refactoring, CI configuration, simulated prices, investment-methodology changes, or trading behavior.

## Review Focus

- A request completing after navigation must release its old lock without enabling or rewriting the new editor.
- Save and Clear must share one context lock so neither operation can pass the other at the backend.
- Unknown legacy contract identity must never match an owned position, but must remain explicitly usable for an unowned symbol when no known identity exists.
- Two contract rows surviving migration must remain independently ranked after restart and backup/restore.
- An explicit market timestamp with no retrieval timestamp must round-trip without receiving a fabricated legacy retrieval time.

---

### Task 1: Serialize trigger mutations by editor context

**Files:**
- Modify: `static/app.js`
- Modify: `test_action_plan_simulator_ui.js`
- Modify: `test_manual_execution_ui.js`

**Interfaces:**
- Produces a context-keyed in-flight mutation registry shared by `saveManualTrigger(symbol)` and `clearManualTrigger(symbol)`.
- Mutation controls are disabled per active context; trigger fields remain editable; captured successful payloads update the baseline only in the same editor context.

- [ ] Add failing tests for double Save, Save→Clear, Clear→Save, editable inputs during Save, newer edits on success/failure, navigation/account/simulation/symbol changes, correct same-context recalculation, and real Action Plan isolation.
- [ ] Run `node --test test_action_plan_simulator_ui.js test_manual_execution_ui.js` and confirm failures are caused by concurrent requests or stale UI effects.
- [ ] Implement the minimal context lock, control-state helper, captured context/payload checks, and `finally` release logic in `static/app.js`.
- [ ] Re-run the two focused JavaScript files and confirm all mutation-race tests pass.
- [ ] Commit the task.

### Task 2: Persist observations by account, symbol, and contract

**Files:**
- Modify: `action_plan_prices.py`
- Modify: `web_server.py`
- Modify: `test_action_plan_latest_prices.py`
- Modify: `test_action_plan_simulations.py`
- Modify: `test_backup_restore.py`

**Interfaces:**
- `init_schema(conn)` migrates to `PRIMARY KEY(account_id, symbol, contract_key)` with a non-null unknown-identity sentinel.
- `persist_observation(...)` compares/replaces only the same contract identity.
- `load_observations(conn, account_id)` returns `dict[str, list[dict]]`; `build_action_plan(...)` consumes the complete list for each symbol.

- [ ] Add failing tests for distinct contracts in one account, same contract across accounts, older/newer same-contract writes, unknown identity, exact owned selection, unowned selection, contract transitions, restart, original-schema migration, and backup/restore.
- [ ] Run the focused Python tests and confirm the old `(account_id, symbol)` overwrite and singular loader fail them.
- [ ] Implement the transactional count-checked schema rebuild, per-contract upsert, grouped loader, resolver handling for unknown identity, and `build_action_plan` integration.
- [ ] Re-run focused price, simulation, migration, and backup tests; retain all existing timestamp/source-precedence cases.
- [ ] Commit the task.

### Task 3: Correct position-cache retrieval fallback and deliver

**Files:**
- Modify: `web_server.py`
- Modify: `test_multi_account_portfolio_db.py`
- Modify: `docs/manual-execution-triggers.md`
- Modify: `docs/action-plan-simulator.md`
- Modify: PR #52 description

**Interfaces:**
- `save_positions_cache(...)` persists explicit retrieval metadata first and uses legacy `price_last_successful_at` only when `market_observed_at` is absent.

- [ ] Add failing save/load and restart cases for explicit market+retrieval, market-only, retrieval-only, legacy-only, and no timestamps.
- [ ] Run the focused cache test and confirm market-only input currently receives the legacy timestamp as retrieval metadata.
- [ ] Implement the minimal conditional fallback and update documentation for mutation serialization, composite contract identity, migration, and legacy timestamp meaning.
- [ ] Run focused tests for all three tasks.
- [ ] Run `python -m unittest discover`, every root `test_*.js`, `node tools/smoke_action_plan_simulator.cjs`, and `git diff --check`.
- [ ] Review the full diff against the supplied findings, commit, push without force, and update existing PR #52 with actual results and limitations.
