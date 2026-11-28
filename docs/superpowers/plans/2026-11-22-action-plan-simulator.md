# Persistent Action Plan Simulator Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task, with isolated frontend work and a fresh final review.

**Goal:** Implement the user's persistent, account-scoped cash simulator and latest usable trigger prices, then create a dependent pull request without merging.

**Architecture:** Share build_action_plan with explicit cash and trigger inputs. Persist assumptions and independent trigger collections in SQLite. Share the current frontend renderers through isolated view contexts. Persist market observations separately from research and resolve by observation time.

**Tech Stack:** Python, SQLite, vanilla JavaScript, unittest, node:test.

**Spec:** User attachment `C:/Users/alexa/.codex/attachments/2d07d0a8-c7c6-4971-ac2a-ce877a8d29cf/Pasted text.txt`.

## Global Constraints

- Base branch: codex/action-plan-view-parity, PR #51 is open; preserve all its UI refinements and document dependency.
- Only additional_cash_usd is simulated; no snapshots, orders, research changes, or real cash/cache changes.
- Every endpoint and asynchronous UI response must respect account and simulation identity.
- Trigger collections have no fallback to real preferences after creation.
- Latest usable cached/delayed/analysis prices support planning without a five-minute eligibility gate.
- Run full Python and JavaScript suites and git diff --check; report actual counts.

## Review Focus

- Unknown or changing accounts and late requests must never leak settings or results.
- Empty trigger collections must stay empty through clear, duplicate, refresh, and restart.
- Additional cash must enter portfolio value and actual cash exactly once, preserving cash equivalents.
- Older quotes or failed refreshes must not replace or discard newer usable observations.
- Backup restoration must migrate older schemas without data loss.

### Task 1: Persistence, API, shared calculation context

**Files:** web_server.py, test_action_plan_simulations.py.
**Interfaces:** build_action_plan(..., additional_cash_usd=0, manual_trigger_preferences=None); simulation CRUD helpers and /api/action-plan-simulations REST routes, payloads {simulation}, {simulations}, {triggers}, {trigger}; calculations match existing Action Plan and detail payloads.

- [x] Add failing persistence, isolation, validation, restart/backup and calculation invariant tests.
- [x] Implement schema, transactional CRUD and shared trigger validation.
- [x] Inject additional cash and independent preferences into the existing engine; implement account-scoped endpoints.
- [x] Run focused tests and review boundary cases.

### Task 2: Latest usable price behavior

**Files:** web_server.py, existing price/manual tests, docs/manual-execution-triggers.md.
**Interfaces:** shared price resolution for regular and simulated plans, account-scoped persisted observations and current price provenance.

- [x] Add failing cached/delayed/missing-time/restart/refresh-failure/recency tests.
- [x] Replace five-minute trigger blocking with deterministic latest usable selection; persist explicit refresh results.
- [x] Keep bid/ask conventions consistent with displayed evaluation metadata and funding prices.
- [x] Update intentional old expectations and run focused tests.

### Task 3: Dedicated simulator UI sharing current renderers

**Files:** static/app.js, static/index.html, static/styles.css, test_action_plan_simulator_ui.js, existing UI tests.
**Interfaces:** REST endpoints from Task 1; financial edits only applied after PUT; simulation-scoped plan, detail, triggers, and request context; shared market refresh endpoint.

- [x] Add failing UI behavior tests.
- [x] Implement sidebar, selector, dialog, collapsed settings, CRUD, independent state and guarded asynchronous routing.
- [x] Share summaries, table, detail, triggers, filters and cached execution modes; remove expiry UI behavior.
- [x] Run all JS tests.

### Task 4: Documentation, integration review, validation and PR

**Files:** docs/action-plan-simulator.md, final regression tests as needed.

- [x] Document persistence, independent triggers, cash calculations and price provenance.
- [x] Review complete implementation for spec compliance and fix material findings with regression tests.
- [x] Run python -m unittest discover, all test_*.js via node --test, git diff --check.
- [x] Prepare delivery on the new feature branch with a PR against codex/action-plan-view-parity and explicit #51 dependency. Do not merge.

## Execution ledger

- Baseline: checkout clean at 42bdda4, equal to origin/codex/action-plan-view-parity; origin/main 84778ea. PR #51 open, sole open PR. JavaScript baseline 155 passed.
- Decision: The attached implementation specification already authorizes building and a PR; proceed without additional design approval. Work on a new branch in the current clean checkout, preserving pr-51.
- Task 1 complete: persistent account-scoped CRUD, independent triggers, transactional duplication/deletion, shared calculation injection, zero-cash parity, fallback cash accounting and backup/restart regressions.
- Task 2 complete: latest usable observations, persisted explicit and positions-associated bid/ask, delayed/frozen provenance, failed-refresh retention and independent account prices. Existing manual suites updated to intentional new behavior (58 passed).
- Task 3 complete: shared workspace renderer with invalidated request scopes and independent preferences. JavaScript suite 157 passed. Reproducible browser smoke in tools/smoke_action_plan_simulator.cjs exercised 38 account-scoped requests, zero real trigger writes and zero browser exceptions.
- Independent integration review identified position-side retention, delayed/frozen provenance, detail row arithmetic and oversized integer validation defects. All corrected with reproducing regressions. Legacy account migration also preserves new account-scoped records.
- Final validation: `python -m unittest discover` passed 445 tests, zero failures; all root JavaScript tests passed 157 tests, zero failures/skips; `git diff --check` passed. Headless Edge smoke passed 38 scoped requests with zero real trigger writes and zero browser exceptions.
- Delivery strategy: commit and push only codex/persistent-action-plan-simulator, open a PR targeting codex/action-plan-view-parity; no merge and no live IBKR validation. No GitHub Actions workflow is configured in this repository.
