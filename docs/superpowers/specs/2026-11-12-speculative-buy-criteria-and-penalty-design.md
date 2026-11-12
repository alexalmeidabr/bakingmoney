# Speculative Buy Criteria and Linear Allocation Penalty Design

## Intent

Strengthen Speculative Buy so it requires both importance-weighted bullish Potential confidence and breadth of distinct bullish Potential Driver variables. Reduce the Linear Allocation score of stocks that remain Speculative Buy by a configurable multiplicative penalty.

## Goals

- Add persisted Rating Settings defaults of `5.0` minimum Potential Bullish Confidence and `2` minimum bullish Potential Drivers.
- Derive the count once from effective Key Variables where category is `Potential Driver` and type is `Bullish`.
- Keep existing rating precedence and confidence paths intact, adding both conditions only to Speculative Buy.
- Add a persisted Linear Allocation penalty defaulting to `0.15`, applied once through the existing factor and diagnostics.
- Surface settings and concise explanations in the established configuration UI.

## Non-goals

- No changes to non-Speculative Buy rating thresholds, scenario calculations, allocation caps, Dynamic Reserve, portfolio isolation, or stored analysis data.
- No schema migration; existing settings use fallback defaults.

## Approach

Considered options:

1. Recalculate counts separately in each list/detail/allocation caller. This risks different effective-version selection and duplicate logic.
2. Add the count to the existing confidence breakdown and thread that context into the existing rating call sites. This reuses the validated effective variables and makes list/detail/allocation agree.
3. Store a materialized count with each analysis. This would require migrations and could become stale after Key Variable edits.

Chosen approach: option 2. Extend the confidence breakdown with `bullish_potential_driver_count`, pass it into rating evaluation, and add the score penalty to `_linear_stock_penalty_factor` alongside existing penalties.

## Constraints

- Confidence comparison uses the existing importance-weighted value and `>=`.
- Count is a nonnegative integer setting; it counts qualifying records, once each.
- Missing potential bullish confidence never qualifies.
- Penalty is a `0..1` fraction, multiplicative, visible in diagnostics, and applies only to `Speculative Buy`.
- Existing persisted databases and backups remain compatible through fallback settings.
