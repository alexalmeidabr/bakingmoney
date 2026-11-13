# PR #49 Bounded Live Quote Wait Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep the existing positions market-data request open long enough to observe live bid and ask after an earlier last or close price, within a bounded batch wait.

**Architecture:** Add a readiness check to the transient quote collector using the same validation as final proof. With quote observations supplied, the batch loop waits until both general price and required live quote evidence are complete or the configured batch deadline expires. The positions refresh scopes the readiness wait to symbols with saved manual triggers. Existing general-price retry remains the only retry, so incomplete manual proof does not create duplicate subscriptions.

**Tech Stack:** Python 3.12, `ib_insync`, SQLite, `unittest`, Node tests.

**Spec:** User attachment `3671cd68-f9f4-4a5d-b563-50104b06acd1/Pasted text.txt`.

## Global Constraints

- Update existing draft PR #49 on `codex/manual-execution-triggers-backend`; do not merge.
- Keep the existing configurable base price wait (default 5 seconds) as a per-batch ceiling; do not add per-symbol waits or extra manual retries.
- Preserve default callers, cached-price fallback, quote freshness, investment calculations, reservations, account isolation, and UI.

## Review Focus

- Last or close arrives before bid and ask: the collector must continue until live proof is ready.
- One-sided, stale, delayed, frozen, or failed subscriptions must stop by the batch deadline and remain unverified.
- Multiple contracts share one deadline, and completion exits early when all required contracts are ready.
- No saved triggers must preserve the existing prompt Positions refresh path.
- Retry still depends on general price availability, without duplicating subscriptions solely for manual evidence.

---

### Task 1: Tests and readiness

**Files:** `test_manual_quote_observation.py`, `web_server.py`.

- [x] Add deterministic packet-order, timeout, multi-contract, retry, and no-observation tests.
- [x] Run focused tests and confirm the early-exit failures.
- [x] Add a reusable readiness check based on actual live bid/ask observations and final ticker identity.
- [x] Update the batch loop to wait within its existing deadline only for required manual proof.
- [x] Run focused market-data tests.

### Task 2: Positions scoping and documentation

**Files:** `web_server.py`, `test_manual_execution_api.py`, backend design document.

- [x] Test that saved triggers opt into waiting while accounts without them retain existing refresh timing.
- [x] Scope required contract keys from account-specific saved triggers without adding subscriptions.
- [x] Document timeout, retry, and PR 2 limitations.
- [x] Run focused endpoint and funding tests.

### Task 3: Verify and update PR

- [x] Run full Python and Node suites, syntax checks, and `git diff --check`.
- [x] Commit and push to the existing branch.
- [x] Update draft PR #49 description with the timeout/retry strategy and actual test counts; leave unmerged.
