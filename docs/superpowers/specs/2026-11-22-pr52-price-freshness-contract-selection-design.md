# PR #52 Price Freshness and Contract Selection Design

## Intent

Make the shared Action Plan price resolver select the freshest usable evidence without inventing exchange timestamps, and make unowned-symbol pricing use a persisted, explicitly qualified IBKR contract instead of choosing among contracts by recency. The regular Action Plan and Simulator continue to call the same resolver and calculation engine.

## Goals and non-goals

- A genuinely newly received live or delayed streaming observation may use its retrieval time as a conservative freshness proxy when no reliable market observation time exists.
- Historical closes, frozen/delayed-frozen snapshots, cached values, failed refreshes, and legacy rows without acquisition evidence never receive that proxy.
- Persistence and resolution use one ranking function, preserving the same result across restart.
- Owned positions require their exact contract. Unowned symbols use an account-scoped qualified selection, a sole unambiguous known contract, or an explicit safe fallback; multiple conflicting identities are never resolved by price recency.
- Keep old observations, simulations, triggers, calculations, account isolation, and timestamp meanings intact. Do not add polling, mandatory network calls to Action Plan GET, CI, trading, UI redesign, or investment-methodology changes.

## Approaches considered

1. **Separate acquisition evidence and persistent selection (chosen).** Persist explicit streaming-acquisition classification with each observation and store the active qualified contract in a small account/symbol mapping table. This keeps quote history and instrument selection independent and survives restart, backup, and contract transitions.
2. **Session-only qualification.** Reject ambiguity after restart until another refresh. This is simpler but loses an identity the application already established.
3. **An active flag on observation rows.** This avoids a table but couples mutable instrument selection to immutable quote history and makes transitions and cleanup harder to reason about.

## Freshness policy

Each normalized observation retains separate `market_observed_at`, `retrieved_at`, and `persisted_at` values plus optional `security_type`, `currency`, and `acquisition_kind` metadata:

- `streaming_live`: received from a current live `reqMktData` acquisition, excluding close/previous-close and frozen data.
- `streaming_delayed`: received from a current delayed stream, excluding close/previous-close and delayed-frozen data.
- `snapshot`: closing, frozen, or delayed-frozen data; its retrieval time is not market-freshness evidence.
- absent: cached/legacy data with no proven acquisition classification.

The common rank uses `market_observed_at` when available. Otherwise, only `streaming_live` and `streaming_delayed` may use `retrieved_at` as an effective freshness time. Comparable effective times are ordered chronologically, so a newer known market timestamp still beats an earlier streaming retrieval, while a new streaming retrieval can beat an older known observation. Equal times prefer reliable market time, then live over delayed over frozen/cached classification. Observations without comparable freshness use deterministic source quality and retrieval metadata only as lower-level tie-breakers; a later-retrieved snapshot cannot displace a known or streaming-fresh observation.

The acquisition pipeline assigns `acquisition_kind` only when the current `reqMktData` subscription records a matching price-field tick event for the selected price source. Request completion, a populated ticker snapshot, or feed classification alone is insufficient. Live bid/ask-derived prices require a current bid or ask event; last prices require a current last event; delayed equivalents require their delayed tick events. Reliable bid/ask tick times remain market observation timestamps. A valid price without matching current-acquisition evidence stays usable but receives no streaming freshness proxy. Unknown-time streaming prices carry an explicit warning that receipt time, not exchange time, determined freshness.

`persist_observation()` and `resolve_price()` both call the same rank. Invalid, non-finite, unavailable, older, or lower-confidence observations cannot replace the retained observation for the same account/symbol/contract.

## Contract selection policy

Add `action_plan_contract_selections` keyed by `(account_id, symbol)`, containing a non-empty `contract_key`, validated security type/currency, and qualification timestamp. Observations also retain available security type/currency so a sole legacy candidate can be checked before it is inferred. The explicit Trigger Price Refresh handler writes or updates this mapping only after IBKR qualification returns exactly one matching stock contract for the requested symbol/currency and owned-contract constraint. Quote acquisition may subsequently fail without inventing or changing a price; the successfully qualified identity remains the safe selection. Failed or ambiguous qualification does not change the mapping.

Resolution order is:

1. An owned position's exact contract.
2. For an unowned symbol, its persisted account-scoped qualified contract.
3. Without a selection, one usable known-contract candidate only, after validating the available symbol/security/currency metadata, with an explicit inferred-not-verified identity warning.
4. Without any known contract, a legacy unknown-identity observation only, with the existing explicit warning.
5. Multiple conflicting known contracts, a missing selected-contract quote, or an owned position without identity uses analysis fallback/unavailable with a clear contract warning; it never chooses another contract by recency.

A later successful qualification safely changes the mapping while retaining historical observations for the old contract. Account reconciliation includes the new table. Full SQLite backups automatically contain it; initialization creates it for existing and restored databases without rebuilding or deleting the observation table.

## Testing and delivery

Add focused resolver, persistence, acquisition-classification, trigger, whole-share, Action Plan/Simulator parity, qualification failure/transition, migration/restart, account-isolation, and backup tests. Tests first reproduce both reviewed failures. Run `python -m unittest discover`, every root `test_*.js`, `node tools/smoke_action_plan_simulator.cjs`, and `git diff --check`. Commit and push only `codex/persistent-action-plan-simulator`, update existing PR #52, preserve its `codex/action-plan-view-parity` base, and do not merge.
