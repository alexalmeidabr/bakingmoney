# PR #52 Price Freshness and Contract Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make newly evidenced streaming prices compete fairly with timestamped observations and make unowned Action Plan pricing use a safe, persistent qualified contract identity.

**Architecture:** Extend the existing quote-event collector to record source-specific acquisition evidence, persist that evidence alongside observations, and use one provenance-aware rank in both resolution and upsert decisions. Add an account/symbol contract-selection table written only at the successful IBKR qualification boundary; the shared resolver consumes it for both real and simulated plans and rejects unresolved ambiguity.

**Tech Stack:** Python 3, SQLite, `ib_insync`, `unittest`, Node test runner, existing synthetic browser smoke.

**Spec:** `docs/superpowers/specs/2026-11-22-pr52-price-freshness-contract-selection-design.md`

## Global Constraints

- Update existing PR #52 on `codex/persistent-action-plan-simulator`, keep base `codex/action-plan-view-parity`, and do not create or merge another PR.
- Only genuine current-acquisition price tick evidence may create `streaming_live` or `streaming_delayed`; request success, ticker population, and feed type alone are insufficient.
- Never assign retrieval time to `market_observed_at`; frozen, closing, delayed-frozen, cached, and legacy observations receive no retrieval-time freshness proxy.
- Preserve old usable prices without a five-minute eligibility deadline, shared real/simulation calculations, account isolation, observation history, migrations, backup/restore, trigger serialization, and PR #51 UI behavior.
- No polling, CI configuration, trading, simulated-price adjustments, allocation-method changes, UI redesign, or unrelated refactoring.

## Review Focus

- A populated live ticker with no current tick event remains usable but cannot outrank a newer reliable market timestamp by retrieval time.
- A current close tick or frozen/delayed-frozen event never becomes streaming evidence even when received during the request.
- A selected contract with no usable observation falls back safely instead of borrowing another contract's newer quote.
- A failed or ambiguous requalification leaves the previous account-scoped selection unchanged; a successful transition changes only that account/symbol mapping and retains both histories.
- A sole inferred candidate validates stock/symbol/currency metadata and is visibly labeled inferred; conflicting candidates never become trigger-eligible through recency.

---

### Task 1: Record genuine acquisition evidence and unify freshness ranking

**Files:**
- Modify: `web_server.py`
- Modify: `action_plan_prices.py`
- Modify: `test_manual_quote_observation.py`
- Modify: `test_action_plan_latest_prices.py`
- Modify: `test_action_plan_simulations.py`

**Interfaces:**
- Produces `_ManualQuoteObservations.acquisition_kind(ticker, contract_key, price_source, diagnostic) -> str | None`, based on current registered tick packets only.
- Produces normalized observation fields `security_type`, `currency`, and `acquisition_kind`, whose values are `streaming_live`, `streaming_delayed`, `snapshot`, or `None`.
- Produces one `_rank(observation)` used unchanged by `resolve_price()` and `persist_observation()`.

- [ ] Add packet-level failing tests proving current live/delayed bid, ask, or last ticks can establish streaming evidence, while pre-populated tickers, close ticks, wrong contracts, frozen/delayed-frozen feeds, and requests without events cannot.
- [ ] Run `python -m unittest test_manual_quote_observation` and confirm the new acquisition-evidence tests fail because no evidence API exists.
- [ ] Implement source-matched tick evidence collection without changing the existing coherent bid/ask proof rules.
- [ ] Add failing resolver/persistence tests for: old known $100 versus current evidenced live $120; old known versus newly retrieved close; newer known delayed versus older live; new live versus persisted live; newer known market time versus earlier live retrieval; two unknown-time evidenced live observations; frozen/delayed-frozen; failed/non-finite updates; restart; warnings; and identical resolver/upsert ordering.
- [ ] Run `python -m unittest test_action_plan_latest_prices test_action_plan_simulations` and confirm failures demonstrate known-time dominance and missing persisted acquisition metadata.
- [ ] Add nullable `security_type`, `currency`, and `acquisition_kind` schema migration, carry contract metadata/evidence from position and explicit-refresh acquisition, separate market-feed classification from persisted/cache state, and implement effective freshness time (`market_observed_at`, otherwise evidenced streaming `retrieved_at`).
- [ ] Re-run `python -m unittest test_manual_quote_observation test_action_plan_latest_prices test_action_plan_simulations` and confirm all focused freshness, provenance, restart, trigger, sizing, and parity cases pass.
- [ ] Commit the task.

### Task 2: Persist qualified contract selection and reject unowned ambiguity

**Files:**
- Modify: `action_plan_prices.py`
- Modify: `web_server.py`
- Modify: `test_action_plan_latest_prices.py`
- Modify: `test_manual_execution_api.py`
- Modify: `test_action_plan_simulations.py`
- Modify: `test_backup_restore.py`

**Interfaces:**
- Produces table `action_plan_contract_selections(account_id, symbol, contract_key, security_type, currency, qualified_at)` with primary key `(account_id, symbol)`.
- Produces `save_contract_selection(conn, account_id, symbol, contract_key, qualified_at) -> bool` and `load_contract_selections(conn, account_id) -> dict[str, dict]`.
- Extends `resolve_price(position, analysis, observations=(), selected_contract=None)` and `resolve_action_plan_price(...)` with the persisted selection metadata.

- [ ] Add failing unit tests for exact owned matching, selected unowned matching, a newer wrong-contract quote, sole metadata-compatible inferred stock candidate with warning, incompatible/unknown candidate fallback, conflicting contracts, contract transition, legacy unknown identity, and account isolation.
- [ ] Run `python -m unittest test_action_plan_latest_prices` and confirm current unowned resolution still selects a conflicting contract by rank.
- [ ] Create the selection table during initialization, add validated save/load helpers, include it in legacy account reconciliation, and filter resolver candidates by owned or selected contract before ranking. Validate sole inferred candidates using available `sec_type`, `currency`, and symbol metadata; return an explicit ambiguity/inference warning rather than silently choosing.
- [ ] Add failing API tests proving exactly-one successful IBKR stock qualification persists selection even if quote acquisition later fails, failed/ambiguous qualification preserves the previous selection, and successful requalification updates it without deleting old observations.
- [ ] Implement selection writes at the qualification boundary before quote persistence; do not write selection for failed or ambiguous qualification.
- [ ] Add end-to-end Action Plan/Simulator tests proving an unrelated same-symbol contract cannot make an unowned Buy trigger eligible or change whole-share sizing, while the selected contract produces identical real/simulated results.
- [ ] Add restart/backup tests for selection, observations, account isolation, and restored-database initialization.
- [ ] Run `python -m unittest test_action_plan_latest_prices test_manual_execution_api test_action_plan_simulations test_backup_restore` and confirm all contract, trigger, sizing, transition, restart, and backup cases pass.
- [ ] Commit the task.

### Task 3: Document, review, validate, and update PR #52

**Files:**
- Modify: `docs/manual-execution-triggers.md`
- Modify: `docs/action-plan-simulator.md`
- Modify: PR #52 description

**Interfaces:**
- Documents the exact effective-freshness ordering, acquisition-evidence requirement, inferred versus verified contract identity, safe ambiguity fallback, and migration behavior.

- [ ] Update user/developer documentation without claiming retrieval time is an exchange timestamp or an inferred contract is verified.
- [ ] Run the focused tests from Tasks 1 and 2 together.
- [ ] Run `python -m unittest discover` and record the actual pass/fail count.
- [ ] Run every root `test_*.js` with `node --test` and record the actual pass/fail/skip count.
- [ ] Run `node tools/smoke_action_plan_simulator.cjs` and `git diff --check`.
- [ ] Review `affcab19e727af451cea819629ca9cb4ed15a1a7..HEAD` for freshness, timestamp meaning, evidence spoofing, ambiguity, cross-account contamination, trigger/sizing parity, migration, and backup compatibility; fix any Critical/Important findings with RED→GREEN tests.
- [ ] Commit remaining documentation/review fixes, push without force to `codex/persistent-action-plan-simulator`, and update existing PR #52 with the policy, metadata/schema changes, tests, actual results, and limitations. Do not merge.
