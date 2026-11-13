# Action Plan Cached-Price Restoration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make valid cached prices usable for Action Plan valuation, sizing, and funding while retaining nonblocking freshness warnings.

**Architecture:** `web_server.py` will select an Action Plan sizing price independently of analysis valuation. Both execution layers and the final unavailable-price guard will rely on price availability rather than the cached/fresh status label.

**Tech Stack:** Python standard-library `unittest`, SQLite cache, vanilla JavaScript.

**Spec:** `docs/superpowers/specs/2026-11-12-action-plan-cached-price-design.md`

## Global Constraints

- Valid cached TWS quotes must produce normal Add/Hold/Trim/Sell sizing and funding.
- Only a genuinely unusable price blocks price-dependent execution; no fabricated market value, weight, amount, or shares.
- Preserve TWS cache metadata, account isolation, Dynamic Reserve, bootstrap behavior, and PR #45 rating behavior.

## Review Focus

- Restarted-process cache must work without `_session_received_quotes`.
- Analysis-price fallback must be labelled and must not mutate analysis metrics.
- Insufficient cash must remain an unfunded/reserve result, not a price-refresh result.
- Cached positions in different accounts must remain independently valued and sized.
- Sell intent without a usable price must remain visible but unsized.

---

### Task 1: Reproduce cached-price Action Plan regression

**Files:**
- Modify: `test_ibkr_market_data_refresh.py`
- Modify: `test_multi_account_action_plan.py`

- [ ] Write failing restart/cached-price tests covering Add, Hold, Trim/Sell, funding, and account isolation.
- [ ] Run focused tests and verify they fail because cached prices are converted to refresh blockers.

### Task 2: Separate sizing-price availability from freshness

**Files:**
- Modify: `web_server.py`
- Test: `test_ibkr_market_data_refresh.py`, `test_multi_account_action_plan.py`, `test_linear_dynamic_reserve.py`

- [ ] Add a minimal Action Plan price-resolution helper and thread its source/warning metadata into candidates and Linear rows.
- [ ] Make both cash-constrained execution layers and unavailable-price guard block only rows without a usable sizing price.
- [ ] Run focused regression tests and verify they pass.

### Task 3: Verify UI-facing warning and full regression suite

**Files:**
- Modify only if the existing warning/detail rendering cannot expose the retained metadata.
- Test: existing frontend freshness and Action Plan tests.

- [ ] Verify cached warnings are nonblocking and unavailable-price diagnostics remain clear.
- [ ] Run the Python suite, Node suite, syntax checks, and `git diff --check`.
- [ ] Commit, push, and open a draft PR against `main`.
