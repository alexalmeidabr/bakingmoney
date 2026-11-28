# Browser History Navigation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add native, sequence-correct browser Back/Forward navigation for BakingMoney main and nested screens without losing edits or showing stale responses.

**Architecture:** A standalone dependency-injected History API controller owns validated structured entries, duplicate suppression, restoration, and cancelled-traversal compensation. `static/app.js` adapts those logical screens to existing view/detail functions and adds request-generation checks only where current nested loaders can race.

**Tech Stack:** Vanilla JavaScript, native History API, `node:test`, existing headless Microsoft Edge/CDP smoke infrastructure, Python `unittest` regression suite.

**Spec:** `docs/superpowers/specs/2026-11-28-browser-history-navigation-design.md`

## Global Constraints

- Use only `history.pushState`, `history.replaceState`, and `popstate`; do not add hashes or a routing framework.
- Preserve Simulator cash/manual-trigger confirmation and the conditional existing `beforeunload` behavior.
- Do not create history entries for startup, duplicate selections, refreshes, recalculations, or restoration.
- Preserve normal Back navigation beyond BakingMoney's first entry.
- Do not change calculations, IBKR integration, database schemas, or visual design.

## Review Focus

- A second Back/Forward action while cancelled-pop compensation is pending must still return browser and application state to the same entry (Task 1 rapid-compensation test).
- A valid nested reload state with a nonzero sequence must render without adding an entry (Task 1 reload test and Task 2 adapter test).
- A stale analysis, alert, or Earnings Review response must not overwrite a newer nested screen (Task 3 deferred-response tests).
- An internal Back at sequence zero must use its logical fallback without trying to leave the site (Task 1 fallback test and Task 2 integration test).
- The first application entry must not gain a sentinel or loop that prevents navigation to an earlier website (Task 1 outside-entry test and Task 4 browser assertion).

---

### Task 1: Sequence-indexed History controller

**Files:**
- Create: `static/navigation_history.js`
- Create: `test_browser_navigation.js`
- Modify: `static/index.html`

**Interfaces:**
- Produces: `BakingMoneyNavigation.normalizeScreen(value) -> normalized screen | null`.
- Produces: `BakingMoneyNavigation.createController({ history, eventTarget, render, canLeave, fallbackScreen })` with `initialize()`, `navigate(screen)`, `back(fallback)`, `currentScreen()`, and `currentSequence()`.
- History entry: `{ bakingMoneyNavigation: 1, sequence: integer, screen: normalizedScreen }`.

- [ ] **Step 1: Write failing controller tests**

Add `node:test` cases using a real in-memory history implementation for invalid-state fallback/`replaceState`, valid reload restoration, three-screen Back/Forward, repeated two-screen navigation, duplicate suppression, no push during restoration, and supported nested screen normalization.

- [ ] **Step 2: Run the controller test and verify RED**

Run: `node --test test_browser_navigation.js`
Expected: FAIL because `static/navigation_history.js` does not exist.

- [ ] **Step 3: Implement normalization and basic controller transitions**

Create the global/CommonJS-compatible module and add it before `app.js` in `static/index.html`. Render before pushing a user entry; treat a `false` render result as rejected. Preserve a valid state on initialization and replace invalid/missing state with Analysis sequence zero.

- [ ] **Step 4: Run the controller test and verify GREEN**

Run: `node --test test_browser_navigation.js`
Expected: all basic controller tests pass.

- [ ] **Step 5: Write failing cancellation and boundary tests**

Add cases for rejected Back, rejected Forward, repeated/rapid pop events during compensation, internal Back using history when sequence is positive, sequence-zero fallback, and Back beyond sequence zero leaving the application history normally.

- [ ] **Step 6: Run the focused test and verify RED**

Run: `node --test test_browser_navigation.js`
Expected: cancellation/boundary cases fail because compensation and `back()` are incomplete.

- [ ] **Step 7: Implement compensation and internal Back**

Use sequence deltas to return to the rendered entry after guard rejection. While compensating, reconcile unexpected intermediate application states back to that entry without rendering or pushing. Never replace/push an outside state and let `history.back()` at sequence zero follow normal browser behavior unless `back(fallback)` was explicitly requested by an internal button.

- [ ] **Step 8: Run the focused and complete JavaScript suites**

Run: `node --test test_browser_navigation.js`
Expected: PASS.

Run: `$files = Get-ChildItem -File -Filter 'test_*.js' | Sort-Object Name | ForEach-Object { $_.FullName }; node --test $files`
Expected: all tests pass.

- [ ] **Step 9: Commit**

```powershell
git add static/navigation_history.js static/index.html test_browser_navigation.js docs/superpowers/specs/2026-11-28-browser-history-navigation-design.md docs/superpowers/plans/2026-11-28-browser-history-navigation.md
git commit -m "feat: add browser history navigation controller"
```

### Task 2: Application screen adapter and nested navigation

**Files:**
- Modify: `static/app.js`
- Modify: `test_browser_navigation.js`
- Modify: `test_earnings_review_navigation.js`

**Interfaces:**
- Consumes: Task 1 `BakingMoneyNavigation.createController` and normalized screen schema.
- Produces: `renderNavigationScreen(screen) -> Promise<boolean>`, `navigateToScreen(screen)`, `navigateBack(fallback)`, and initial `initializeBrowserNavigation()`.

- [ ] **Step 1: Write failing application-navigation tests**

Cover sidebar sequences and active sidebar restoration; Analysis list/detail from Analysis and Positions; Action Plan/Simulator action detail; company analysis from Action Plan/Simulator; Alerts detail; Earnings Review list/company/review; same-screen selection; refresh/recalculate without navigation; and internal Back using actual history with a fallback only at sequence zero. Update the Earnings Review no-hash expectations to allow native History API state.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `node --test test_browser_navigation.js test_earnings_review_navigation.js`
Expected: new integration cases fail because `app.js` is not wired to the controller.

- [ ] **Step 3: Implement the application adapter**

Initialize after account discovery, preserving a valid reload entry. Convert menu and nested click handlers to logical navigation requests. Restore through `setView`, `openAnalysisDetailForSymbol`, `openActionPlanDetail`, `openAlertDetail`, `openEarningsReviewSymbolHistory`, and `openEarningsReviewRecordDetail` with explicit no-history/restoration options. Keep Simulator identity in the source `view` for analysis/action detail restoration.

- [ ] **Step 4: Integrate internal Back buttons**

Route Analysis, Action Detail, Alert Detail, and both Earnings Review Back buttons through `navigateBack(fallbackScreen)`. Preserve their existing destination if the current entry has no earlier BakingMoney sequence.

- [ ] **Step 5: Run focused and complete JavaScript suites**

Run: `node --test test_browser_navigation.js test_earnings_review_navigation.js test_action_plan_simulator_ui.js`
Expected: PASS.

Run: `$files = Get-ChildItem -File -Filter 'test_*.js' | Sort-Object Name | ForEach-Object { $_.FullName }; node --test $files`
Expected: all tests pass.

- [ ] **Step 6: Commit**

```powershell
git add static/app.js test_browser_navigation.js test_earnings_review_navigation.js
git commit -m "feat: connect application screens to browser history"
```

### Task 3: Dirty-state rejection and stale asynchronous response protection

**Files:**
- Modify: `static/app.js`
- Modify: `test_browser_navigation.js`
- Modify: `test_action_plan_simulator_ui.js`

**Interfaces:**
- Consumes: Task 1 controller `canLeave` callback and Task 2 logical screens.
- Produces: navigation-generation checks for analysis, alert, and Earnings Review nested requests while retaining existing Action Plan/account request IDs.

- [ ] **Step 1: Write failing dirty-navigation tests**

Exercise browser Back/Forward from a Simulator screen with dirty cash, dirty manual triggers, confirmation rejection, later acceptance, and repeated navigation attempts. Assert rejected transitions keep the same logical screen and cleanly restore the browser entry without discarding values.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `node --test test_browser_navigation.js test_action_plan_simulator_ui.js`
Expected: dirty `popstate` cases fail before the adapter delegates to `discardSimulationEdits()`.

- [ ] **Step 3: Connect the existing Simulator guard**

Use `discardSimulationEdits()` as the controller's `canLeave` callback whenever the rendered state belongs to Simulator. Avoid a second confirmation inside restoration by passing the existing skip-discard option into `setView`/detail rendering.

- [ ] **Step 4: Write failing stale-response tests**

Use deferred fetch responses to prove an older Analysis detail, Alert detail, Earnings Review company history, or Earnings Review record cannot overwrite the newer navigation state. Include an account switch around portfolio-scoped Action Plan restoration.

- [ ] **Step 5: Run focused tests and verify RED**

Run: `node --test test_browser_navigation.js test_action_plan_simulator_ui.js`
Expected: at least one deferred nested response updates state after navigation and fails its assertion.

- [ ] **Step 6: Add minimal request-generation checks**

Increment a shared navigation render generation on each logical screen restoration and check the captured generation after each relevant await. Preserve the stronger existing request/account checks in Action Plan and Simulator code.

- [ ] **Step 7: Run focused and complete JavaScript suites**

Run: `node --test test_browser_navigation.js test_action_plan_simulator_ui.js`
Expected: PASS.

Run: `$files = Get-ChildItem -File -Filter 'test_*.js' | Sort-Object Name | ForEach-Object { $_.FullName }; node --test $files`
Expected: all tests pass.

- [ ] **Step 8: Commit**

```powershell
git add static/app.js test_browser_navigation.js test_action_plan_simulator_ui.js
git commit -m "fix: keep restored navigation state consistent"
```

### Task 4: Real-browser Back/Forward coverage and final verification

**Files:**
- Modify: `tools/smoke_action_plan_simulator.cjs`
- Modify: `docs/superpowers/plans/2026-11-28-browser-history-navigation.md`

**Interfaces:**
- Consumes: completed browser controller and application adapter.
- Produces: headless Edge assertions for native browser traversal, internal Back, unsaved-edit cancellation, and first-entry behavior.

- [ ] **Step 1: Extend the Edge smoke test before changing production behavior further**

Add real browser interactions for Action Plan → Simulator → action detail, Back twice, Forward twice, internal Action Detail Back, duplicate sidebar selection, refresh without entry creation, rejected dirty-Simulator Back followed by accepted Back, and a prior same-origin outside page proving Back beyond sequence zero is not trapped.

- [ ] **Step 2: Run the smoke test and address failures test-first**

Run: `node tools/smoke_action_plan_simulator.cjs`
Expected: PASS with navigation assertions and zero browser exceptions; any discovered defect first receives a focused failing Node regression test before production code changes.

- [ ] **Step 3: Run final verification**

Run: `node --check static/navigation_history.js`

Run: `node --check static/app.js`

Run: `$files = Get-ChildItem -File -Filter 'test_*.js' | Sort-Object Name | ForEach-Object { $_.FullName }; node --test $files`

Run: `& 'C:\Users\alexa\Documents\bakingmoney\venv\Scripts\python.exe' -m unittest discover`

Run: `node tools/smoke_action_plan_simulator.cjs`

Run: `git diff --check origin/main...HEAD`

Expected: syntax checks succeed, 0 JavaScript failures, 481 Python tests pass, Edge smoke passes, and diff check reports no errors.

- [ ] **Step 4: Commit final browser coverage**

```powershell
git add tools/smoke_action_plan_simulator.cjs docs/superpowers/plans/2026-11-28-browser-history-navigation.md
git commit -m "test: cover native browser history navigation"
```

- [ ] **Step 5: Request whole-branch code review**

Review `origin/main...HEAD` against the design and user requirements. Resolve every Critical or Important finding and rerun the affected tests.

- [ ] **Step 6: Push and create the PR**

Push `codex/browser-history-navigation`, create a PR targeting `main` titled `Support browser Back/Forward navigation across BakingMoney screens`, and include the history model, nested/internal Back behavior, unsaved-edit handling, actual test results, manual test steps, and limitations. Do not merge.
