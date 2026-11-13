# PR #49 Live Quote Verification Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Retain live bid and ask observations from separate IBKR packets without accepting unverified prices.

**Architecture:** Observe `pendingTickersEvent` during the existing batched positions market-data request. Register only tickers returned by that request, retain the latest qualifying bid and ask independently by contract, and remove the event handler in `finally`. Build transient account-scoped proof from those observations after refresh; keep baseline Action Plan and funding formulas unchanged.

**Tech Stack:** Python 3.12, `ib_insync`, SQLite, `unittest`, Node tests.

**Spec:** User attachment `dba7d9d5-852c-46b0-ba9f-1f206efa34e1/Pasted text.txt`.

## Global Constraints

- Update draft PR #49 on `codex/manual-execution-triggers-backend`; do not merge.
- Keep five-minute freshness based on actual tick timestamps, live market-data type, positive quote prices and sizes, contract/account identity, and no extra TWS requests.
- Do not change investment scoring, targets, Dynamic Reserve, reservation math, baseline Action Plan, UI, or unowned quote behavior.

## Review Focus

- Separate bid and ask packets must survive transient tick-list clearing.
- One-sided, stale, delayed, frozen, or unmatched-contract observations must not verify a trigger.
- Failed requests and repeated refreshes must remove handlers and stale proof.
- Eligible Buy and Sell/Trim must update funding and projected proceeds correctly.
- Account A observations must not validate Account B.

---

### Task 1: Observe market-data packets

**Files:** `web_server.py`, `test_manual_quote_observation.py`.

- [x] Write failing tests for separate packets, one-sided/stale/delayed/frozen/unmatched events, and handler cleanup.
- [x] Run focused tests and confirm expected failures.
- [x] Capture qualifying bid/ask ticks through a temporary `pendingTickersEvent` subscription in the existing batch request and pass observations through its retry wrapper.
- [x] Run focused tests and confirm they pass.

### Task 2: Integrate proof and funding

**Files:** `web_server.py`, `test_manual_execution_api.py`, `test_manual_execution_engine.py`, `docs/superpowers/specs/2026-11-13-manual-execution-triggers-backend-design.md`.

- [x] Update endpoint tests for packet separation, account/contract isolation, failed-refresh invalidation, and Buy/Sell funding effects.
- [x] Run focused tests; confirm final-tick-only fixtures fail after the proof path changes.
- [x] Build proof from captured observations rather than final `ticker.ticks`; document PR 2's explicit refresh need.
- [x] Run focused tests and confirm they pass.

### Task 3: Verify and update PR

- [x] Run full Python and Node suites, syntax checks, and `git diff --check`.
- [ ] Commit and push corrections to the existing branch.
- [ ] Update draft PR #49 with the revised quote lifecycle and actual test counts; leave unmerged.
