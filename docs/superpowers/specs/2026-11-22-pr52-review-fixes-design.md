# PR #52 Review Fixes Design

## Intent

Correct the reviewed Action Plan Simulator defects without redesigning the simulator: market timestamps must retain their actual meaning, quote selection must have deterministic source precedence, and unsaved simulation trigger edits must receive the same loss protection as Additional Cash.

## Constraints

- Keep PR #52 on `codex/persistent-action-plan-simulator` with base `codex/action-plan-view-parity`.
- Preserve the existing allocation engine, research prices, simulator persistence model, account isolation, explicit refresh behavior, and Action Plan UI inherited from PR #51.
- Do not merge either PR, create another PR, add trading behavior, or add unrelated simulator features.

## Approaches

1. **Explicit timestamp metadata through the existing pipeline (selected).** Add nullable market-observation, retrieval, and persistence timestamps to saved observations and the position cache; preserve the legacy timestamp only as compatibility metadata. Rank by known market time first, then documented source quality, then retrieval time only as a deterministic same-quality fallback. This is backward compatible and keeps the existing resolver boundary.
2. **Reinterpret `price_last_successful_at` as an exchange timestamp.** This is smaller but rejected because historical rows contain retrieval times and the review explicitly forbids promoting them to confirmed market observations.
3. **Replace the latest-observation table with an append-only quote ledger.** This gives richer history but is unnecessary for the reviewed behavior and would broaden persistence, backup, and cleanup scope.

For the editor, extend the shared trigger form with a normalized saved baseline and a revision/context token. Simulator navigation checks both cash and trigger dirtiness, while the real Action Plan keeps its current behavior. Duplicating the form or silently autosaving was rejected because it would fork validation/persistence behavior or violate the requested discard semantics.

## Behavior

- Known market timestamps are normalized to UTC. A newer known delayed observation may beat an older live one.
- A known market timestamp beats an unknown one. Equal or unknown market times use: live, delayed, frozen, delayed-frozen, cached market data; saved analysis remains outside market ranking as the final fallback.
- Retrieval time is labeled as retrieval metadata and never presented as exchange observation time. It can only break ties between otherwise equivalent unknown-time candidates.
- Persisted legacy timestamps remain readable as retrieval metadata; migration does not backfill them into market-observation columns.
- Failed or invalid refreshes do not replace a usable saved observation. Bid/ask sides remain one snapshot and are never assembled across candidates.
- Simulator trigger dirtiness compares normalized values for all five fields with the last loaded or successfully saved baseline. Refresh-only updates do not dirty the editor, reverted values clear dirtiness, failed writes preserve edits, and stale async completions cannot replace newer edits.

## Validation

Add focused Python and JavaScript regressions for the review matrix, then run the complete Python suite, every root `test_*.js`, the simulator browser smoke test, and `git diff --check`. Update the existing PR description with the actual results and limitations, then commit and push only the existing PR branch.
