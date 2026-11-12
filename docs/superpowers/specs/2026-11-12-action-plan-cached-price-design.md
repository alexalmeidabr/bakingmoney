# Action Plan Cached-Price Restoration Design

## Intent

Restore Action Plan sizing and funding when a valid saved quote exists, while retaining quote freshness warnings and the safeguards for genuinely unavailable prices.

## Root Cause

PR #44 correctly marks saved quotes `cached_stale` after an application restart or an incomplete TWS refresh. Action Plan then incorrectly treats that freshness status as unavailable in both cash-constrained execution layers and in `block_stale_price_execution`, replacing valid actions with `Watch / Price Refresh`. It also sizes trade shares from the analysis price rather than the owned position’s cached quote.

## Approach

1. Keep the existing `tws_received`, `cached_stale`, and `unavailable` metadata.
2. Centralize Action Plan sizing-price selection: a valid position quote first, otherwise an explicitly labelled valid analysis-price fallback.
3. Recompute owned market value from the selected valid position quote and quantity; retain unknown values when no valid price exists.
4. Treat `cached_stale` as a warning-only state. Execution and funding guard only on the absence of a valid sizing price.
5. Preserve existing reserve, funding, whole-share, account-isolation, and Linear Allocation calculations.

## Non-goals

- No changes to quote retrieval, contract identity, rating/analysis/scenario calculations, allocation methodology, backup schema, or multi-account ownership architecture.

## Compatibility

Existing databases continue to load saved quotes as `cached_stale` after restart. These rows become usable immediately, with their existing warning and quote timestamp preserved.
