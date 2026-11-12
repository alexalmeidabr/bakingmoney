# Speculative Buy Criteria and Linear Allocation Penalty Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Require configured Potential confidence and breadth for Speculative Buy, and apply a configurable Linear Allocation penalty to that rating.

**Architecture:** The confidence breakdown remains the single source for weighted confidence and gains a count of qualifying effective variables. Rating settings validation and the configuration UI extend established mappings. Linear Allocation applies the new rating-specific factor within its existing multiplicative penalty pipeline.

**Tech Stack:** Python standard-library `unittest`, SQLite-backed settings, vanilla JavaScript/HTML.

**Spec:** `docs/superpowers/specs/2026-11-12-speculative-buy-criteria-and-penalty-design.md`

## Global Constraints

- Preserve rating order and all non-Speculative Buy eligibility.
- Potential confidence stays importance-weighted; count only `Potential Driver` + `Bullish` effective Key Variable records.
- Minimum count rejects fractional/invalid input; confidence and penalty ranges are 0–10 and 0–1 respectively.
- No schema migration or unrelated allocation/scenario/portfolio changes.

## Review Focus

- Missing potential confidence must fail even when the core confidence path is otherwise sufficient.
- Equal-to-threshold values must qualify (`>=`).
- Core and potential-bearish records must not inflate the count.
- List and detail must use the same effective analysis version and rating.
- Multiple Linear penalties must remain multiplicative and the new penalty appear once in diagnostics.

---

### Task 1: Confidence context and Speculative Buy eligibility

**Files:**
- Modify: `analysis_service.py`
- Modify: `web_server.py`
- Test: `test_analysis_service.py`
- Test: `test_web_server_openai_tools.py` or an existing web-server unit test module

**Interfaces:**
- Produces `calculate_confidence_breakdown(...)["bullish_potential_driver_count"]`.
- Consumes this field in `calculate_rating(..., confidence_context=...)`.

- [ ] Write failing tests for qualifying-count filtering, weighted-confidence threshold, count threshold, equality, missing confidence, existing core path, Hold fallback, and unchanged non-Speculative ratings.
- [ ] Run the targeted tests and verify they fail due to missing count criteria.
- [ ] Add the count to `calculate_confidence_breakdown` and require the two new settings in the existing Speculative Buy branch of `calculate_rating`.
- [ ] Run targeted tests and verify they pass.
- [ ] Commit the task.

### Task 2: Persisted settings, effective-version rating callers, and configuration UI

**Files:**
- Modify: `web_server.py`
- Modify: `static/index.html`
- Modify: `static/app.js`
- Test: existing configuration, backup/restore, and list/detail tests

**Interfaces:**
- Produces Rating Settings keys `speculative_buy_min_potential_bullish_confidence` and `speculative_buy_min_bullish_potential_drivers` with defaults `5.0` and `2`.
- Passes the effective Key Variable count through list/detail rating contexts.

- [ ] Write failing tests for defaults, persistence, invalid fractional/out-of-range values, backup compatibility, and list/detail consistency.
- [ ] Run those tests and verify expected failures.
- [ ] Add settings constants/defaults/validation, count derivation in effective list data, UI controls/help, and client save/load/validation wiring.
- [ ] Run focused Python and JavaScript tests and verify they pass.
- [ ] Commit the task.

### Task 3: Linear Allocation Speculative Buy penalty

**Files:**
- Modify: `web_server.py`
- Modify: `static/index.html`
- Modify: `static/app.js`
- Test: `test_linear_dynamic_reserve.py` and existing Linear Allocation diagnostics tests

**Interfaces:**
- Produces Action Plan setting `speculative_buy_rating_penalty` defaulting to `0.15`.
- `_linear_stock_penalty_factor(...)` emits `Speculative Buy rating` diagnostics when applicable.

- [ ] Write failing tests for default 15%, zero/100%, non-Speculative ratings, one-time application, multiplicative combination, and diagnostics.
- [ ] Run targeted tests and verify expected failures.
- [ ] Add settings validation/UI wiring and the one penalty-hook condition.
- [ ] Run focused tests and verify they pass.
- [ ] Commit the task.

### Task 4: Full regression verification and draft PR

**Files:**
- Verify all modified files and tests.

- [ ] Run `python -m unittest discover`, frontend tests, syntax checks, and `git diff --check`.
- [ ] Inspect the final diff against the design and scope constraints.
- [ ] Commit the complete implementation, push `codex/speculative-buy-criteria-and-penalty`, and create a draft PR to `main`.
