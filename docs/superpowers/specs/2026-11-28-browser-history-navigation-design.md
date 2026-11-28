# Browser History Navigation Design

## Intent

BakingMoney should participate in native browser Back/Forward navigation so users can retrace the actual sequence of sidebar and nested screens without losing Simulator edits, seeing stale data, or being trapped inside the application.

## Goals

- Represent every supported main and nested screen as structured `history.state` data.
- Use `replaceState` once for the initial entry and `pushState` only for meaningful user navigation.
- Restore screens through the existing `setView`, detail loaders, and renderers.
- Keep internal Back buttons aligned with the browser stack.
- Reject navigation safely when Simulator cash or manual-trigger edits are unsaved, then compensate for the already-completed browser traversal.
- Ignore stale asynchronous responses after rapid navigation or account changes.
- Preserve normal navigation to pages outside BakingMoney.

## Non-goals and anti-goals

- No URL routes, hashes, deep links, bookmarkable detail URLs, or third-party router.
- No visual redesign, calculation changes, persistence changes, or unrelated frontend refactor.
- Navigation restoration must never write holdings, trading preferences, simulations, or triggers.
- No unconditional `beforeunload` handler and no history sentinel that traps Back at the first BakingMoney entry.

## Constraints

The implementation remains vanilla JavaScript and uses `history.pushState`, `history.replaceState`, and `popstate`. Existing Simulator dirty-state confirmation and request/account scoping remain authoritative. The first application entry is replaced in place so an additional Back leaves BakingMoney normally.

## Approaches considered

1. **Sequence-indexed structured history controller (selected).** Store a validated logical screen plus an application marker and monotonically adjacent sequence number. This supports duplicate suppression, direction-aware compensation after rejected traversals, reload restoration, nested screens, and deterministic tests.
2. **Screen-only history state.** Smaller, but it cannot reliably calculate how to undo a cancelled Back/Forward traversal or reconcile repeated rapid attempts.
3. **URL router.** Provides deep links but violates the focused scope, conflicts with existing no-hash tests, and adds needless routing complexity.

## Design

`static/navigation_history.js` will expose a small dependency-injected controller and a BakingMoney screen normalizer. A valid state has an application/version marker, an integer `sequence`, and a normalized `screen`. Main screens use `{ view }`. Nested screens add `detail` data for company analysis, action detail, alert detail, Earnings Review company history, or Earnings Review record detail. The source `view` remains part of the screen, so a company analysis opened from Positions, Action Plan, or Simulator restores the correct sidebar and workspace.

On initialization, the controller validates the current state. A valid reload state is retained and rendered; otherwise Analysis replaces the current entry at sequence zero. `navigate(screen)` checks the existing Simulator guard, renders through an application adapter, and pushes only if the normalized screen differs from the current screen. Refresh/recalculate operations bypass navigation and therefore do not add entries.

On `popstate`, the browser has already moved. The controller validates the target and asks the same dirty-state guard before rendering. If rejected, it keeps the application screen unchanged and calls `history.go(currentSequence - targetSequence)`. A compensation mode ignores the resulting traversal as navigation, confirms arrival back at the current application entry, and recalculates if another rapid traversal changed the browser position before recovery completed. No sentinel is inserted before the initial entry, so Back beyond sequence zero follows normal browser behavior.

Internal Back buttons request controller Back when an earlier BakingMoney sequence is known. If a restored/direct first entry has no earlier application entry, they navigate to their existing logical fallback. This preserves existing button destinations without pushing duplicate parent screens during ordinary use.

The `app.js` adapter maps logical states to existing `setView`, analysis/action/alert/Earnings Review loaders, and uses no-history options during restoration. Navigation request generations are checked by nested async loaders that currently lack stale-response protection; existing Action Plan and account guards remain in place.

## Testing

- Node tests exercise the real controller with a deterministic in-memory History API: initialization/reload, duplicate suppression, repeated screen changes, Back/Forward, nested state sequences, rejected navigation recovery, repeated rapid attempts, invalid states, internal Back fallback, and leaving past the first entry.
- Integration-focused JavaScript tests exercise the application adapter/state mapping and stale-response generations.
- The existing headless Edge smoke test gains native `history.back()`/`history.forward()` checks across Action Plan, Simulator, and action detail, including internal Back and rejected unsaved Simulator navigation.
- Final validation runs every root JavaScript test, the full Python suite, the Edge smoke test, syntax checks, and `git diff --check`.

## Known boundary

Because URLs remain unchanged, reopening a copied URL cannot recreate a nested screen. Reloading the same history entry can restore its valid `history.state`, which is the intended scope for this change.
