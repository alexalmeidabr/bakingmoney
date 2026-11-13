# Automatic TWS Market-Data Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automatically use TWS market data for existing refresh actions without a user-controlled enable/disable setting.

**Architecture:** Remove configuration gating at the frontend and backend boundaries while retaining current IBKR request helpers and cached fallback behavior. Tests exercise the endpoints/helpers through fakes so legacy persisted settings cannot suppress live requests.

**Tech Stack:** Python `unittest`, `ib_insync` fakes, vanilla JavaScript Node tests.

**Spec:** `docs/superpowers/specs/2026-11-13-remove-tws-data-toggle-design.md`

## Global Constraints

- Do not modify the analysis methodology, ratings, Speculative Buy criteria/penalty, Linear Allocation, Dynamic Reserve, scenario calculations, multi-account architecture, retry/cache algorithms, or backup format.
- Do not add background polling, subscriptions, or a new market-data provider.
- Keep legacy database rows compatible; an obsolete setting may remain stored but cannot disable requests.
- Preserve PR #46 cached-price Action Plan behavior.

## Review Focus

- Legacy `use_tws_data = 0` must still request and save a connected TWS quote (Task 1).
- Connection failure must preserve cached prices and a later explicit refresh must recover without restart (Task 1).
- Partial quotes must retain per-contract cached fallback and diagnostics (Task 1).
- Two-account refreshes must remain account-scoped (Task 1).
- The UI and API configuration responses must expose no user switch or disabled wording (Task 2).

---

### Task 1: Remove backend market-data gating

**Files:**
- Modify: `web_server.py: general configuration, fetch_ib_prices, fetch_latest_historical_close, positions refresh`
- Test: `test_ibkr_market_data_refresh.py`, `test_multi_account_portfolio_db.py`

**Interfaces:**
- Consumes: existing `get_ib_connection`, quote request/retry helpers, position cache helpers.
- Produces: refresh behavior based on connection/request outcome rather than `use_tws_data`.

- [ ] **Step 1: Write failing backend regression tests**

Cover legacy-disabled live prices, analysis price fetch, disconnect/reconnect, partial quotes, and selected-account isolation.

- [ ] **Step 2: Run focused tests to verify they fail because the setting still gates requests**

Run: `python -m unittest test_ibkr_market_data_refresh test_multi_account_portfolio_db -v`

- [ ] **Step 3: Remove `use_tws_data` gating and user-configurable persistence**

Ignore old submitted values and use only the actual IBKR connection/request result for live quote attempts and diagnostics.

- [ ] **Step 4: Run focused backend tests**

Run: `python -m unittest test_ibkr_market_data_refresh test_multi_account_portfolio_db -v`

### Task 2: Remove the TWS switch UI and API contract

**Files:**
- Modify: `static/index.html`, `static/app.js`, `web_server.py`
- Test: `test_alerts_feature.py`, `test_positions_price_freshness.js` or a dedicated Node test

**Interfaces:**
- Consumes: general configuration endpoint and existing portfolio account controls.
- Produces: no DOM IDs, event handlers, requests, or returned settings for `use_tws_data`.

- [ ] **Step 1: Write failing UI/configuration contract tests**

Assert the removed control identifiers and disabled wording are absent and that configuration does not advertise `use_tws_data`.

- [ ] **Step 2: Run those tests to verify the old UI/API still exposes the switch**

Run: `node --test test_tws_data_toggle_removal.js` and the focused Python test.

- [ ] **Step 3: Remove markup, client state/handlers, and configuration payload field**

Keep the portfolio account selector layout and all unrelated configuration inputs unchanged.

- [ ] **Step 4: Run focused UI/configuration tests**

Run: `node --test test_tws_data_toggle_removal.js` and focused Python tests.

### Task 3: Verify integrated refresh and cached-price behavior

**Files:**
- Test: existing market-data, multi-account, and Action Plan test modules

**Interfaces:**
- Consumes: Tasks 1-2 changes and merged PR #46 Action Plan behavior.
- Produces: validated release candidate.

- [ ] **Step 1: Run required full verification**

Run: `python -m unittest discover`, `node --test (Get-ChildItem -Name 'test_*.js' | Sort-Object)`, `python -m py_compile web_server.py analysis_service.py`, `node --check static/app.js`, and `git diff --check`.

- [ ] **Step 2: Commit, push, and open a new draft PR against `main`**

Do not modify the old PR branch or merge the PR.
