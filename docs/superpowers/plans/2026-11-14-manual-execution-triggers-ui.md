# Manual Execution Triggers UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Complete account-scoped manual trigger editing, plan comparison, and explicit live verification for analyzed unowned stocks.

**Architecture:** Extend the merged backend with a transient explicit quote store and an account-scoped POST endpoint. Use the existing dual-mode Action Plan response for immediate frontend mode switching. Render manual execution from backend amounts and statuses.

**Tech Stack:** Python `unittest`, `ib_insync`, SQLite, browser JavaScript, Node test runner.

**Spec:** `docs/superpowers/specs/2026-11-14-manual-execution-triggers-ui.md` and the attached user prompt.

## Global Constraints

- Start from merged `origin/main` in an isolated worktree.
- Keep baseline Linear Allocation, investment methodology, My Positions, and analysis prices unchanged.
- No automatic TWS requests in Action Plan GET, polling, subscriptions after request, or trading.
- Five-minute verified bid/ask freshness; reject delayed, frozen, partial, and wrong-contract quotes.
- Full Python and Node test suites; draft PR against main; do not merge.

## Review Focus

- A quote refresh for one account must not make another account's trigger eligible.
- A failed refresh must remove old proof for its requested symbols.
- A response from an earlier account selection must not overwrite the current UI.
- An eligible but unfunded Buy must not be described as ready.
- A stale explicit quote must return price confirmation required.

## Task 1: Explicit quote verification backend

Files: `web_server.py`, `test_manual_execution_api.py`, `test_manual_execution_engine.py`.

- [x] Write failing tests for validated/bounded symbols, account isolation, successful unowned live bid/ask, offline/partial/delayed/wrong-contract failure, invalidation, and expiration.
- [x] Run focused tests and confirm failures describe missing behavior.
- [x] Add `POST /api/manual-execution-quotes/refresh`, transient proof storage, and unowned manual evaluation/sizing. Preserve owned and baseline paths.
- [x] Run focused tests and confirm they pass.

## Task 2: Action Plan mode and table

Files: `static/index.html`, `static/app.js`, `static/styles.css`, Action Plan Node tests.

- [x] Write failing tests for default baseline, cached mode switch, recommendation filter, manual statuses, shares/amounts, summary, account race.
- [x] Run focused Node tests and confirm failures.
- [x] Add switch, explicit quote refresh button, manual columns, manual summary, and request state guards.
- [x] Run focused Node tests and confirm they pass.

## Task 3: Detail editor and explanation

Files: `static/index.html`, `static/app.js`, `static/styles.css`, Action Plan Node tests.

- [x] Write failing tests for full replacement save, reload, clear, price/percentage validation, reservation display, blocked Sell warning, and account changes.
- [x] Run focused tests and confirm failures.
- [x] Implement editor and explanatory detail using existing CRUD and dual-mode detail response.
- [x] Run focused tests and confirm they pass.

## Task 4: Validation and delivery

Files: workflow documentation, screenshots, PR body.

- [x] Run full `python -m unittest discover` and Node `node --test (Get-ChildItem -Name 'test_*.js' | Sort-Object)`.
- [x] Run `python -m py_compile web_server.py analysis_service.py`, `node --check static/app.js`, and `git diff --check`.
- [x] Capture both list modes and editor, document API/workflow/limits, inspect diff, commit and push.
- [x] Create draft PR against `main`, report actual verification counts and failures, leave PR unmerged.
