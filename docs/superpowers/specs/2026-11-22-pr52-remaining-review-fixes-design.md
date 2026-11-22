# PR #52 Remaining Review Fixes Design

## Intent

Close the three remaining PR #52 correctness gaps without changing simulator calculations, trigger semantics, or the PR #51 dependency: serialize mutations within one trigger editor context, persist market observations by contract identity, and stop treating a legacy timestamp as retrieval metadata when an explicit market observation exists.

## Constraints

- Keep PR #52 on `codex/persistent-action-plan-simulator` with base `codex/action-plan-view-parity`.
- Preserve all existing simulation CRUD, allocation, trigger, quote-precedence, provenance, migration, and backup behavior.
- Use test-first fixes and avoid unrelated refactoring, UI redesign, automated trading, CI work, or new dependencies.

## Approaches

### Trigger mutation concurrency

1. A single global busy flag was rejected because an old request from another account, simulation, or symbol would unnecessarily block the active editor.
2. A context-keyed in-flight map is selected. The key uses account, real/simulation identity, and symbol. Save and Clear share the same lock, disable only their mutation buttons, leave inputs editable, capture the submitted payload and context, and release controls only for the matching active editor.

### Contract identity persistence

1. Rejecting a new contract when `(account_id, symbol)` already exists was rejected because it cannot retain two valid contracts or handle a legitimate identifier transition.
2. A composite `(account_id, symbol, contract_key)` persistence key is selected. Storage uses a non-null internal sentinel for unknown identity while loaded observations expose it as unknown. Migration transactionally rebuilds the table, copies every row, verifies row count, and only then replaces the old schema.

`load_observations()` groups all observations by symbol. Owned positions continue to accept only an exact contract match. For unowned symbols, known-contract observations outrank legacy unknown-identity rows; an unknown-only legacy row remains usable with an explicit identity warning. Qualified manual refresh behavior is unchanged, and distinct historical contracts remain available across restart and backup/restore.

### Legacy timestamp fallback

Position-cache persistence writes explicit `retrieved_at` or `price_retrieved_at` when present. It consults `price_last_successful_at` only when both explicit retrieval metadata and `market_observed_at` are absent.

## Validation

Add focused JavaScript race tests, Python contract/migration/restart tests, and position-cache round-trip tests. Then run the complete Python and root JavaScript suites, the synthetic browser smoke test, and `git diff --check`. Update and push only PR #52; do not merge.
