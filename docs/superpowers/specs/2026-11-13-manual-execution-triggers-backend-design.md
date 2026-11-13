# Manual Execution Triggers Backend Design

## Goal and boundary

Keep the existing Action Plan response and calculation unchanged by default. An explicit `execution_modes=both` request calculates the same recommendations and Linear Allocation targets once, then runs two independent execution passes: the current pass and a pass with manual price gates and cash reservations. No API places orders or monitors prices in the background.

## Persistence and API

`manual_execution_triggers` uses `(account_id, symbol)` as its primary key. It stores optional Buy and Sell/Trim prices, Sell/Trim direction (`at_or_above` by default), `reserve_enabled`, a 0–100 `reserve_percentage`, and creation/update timestamps. Initialization uses `CREATE TABLE IF NOT EXISTS`. SQLite backup snapshots include the table automatically; old backups remain valid and gain the table on initialization after restore, so it is not added to the old-backup required-table list.

Routes use the existing `account_id` query parameter and `resolve_portfolio_account(..., allow_none_when_empty=False)`. `GET /api/manual-execution-triggers` returns `{"triggers": [...]}`; `GET /api/manual-execution-triggers/{symbol}` returns `{"trigger": {...}}` or 404; `PUT` replaces that symbol's preference and returns `{"trigger": {...}}`; `DELETE` returns `{"deleted": true}` or 404. PUT accepts optional `buy_trigger_price`, `sell_trigger_price`, `sell_trigger_direction`, `reserve_enabled`, and `reserve_percentage`. Null/omitted prices clear conditions. A saved reservation preference without a Buy price is allowed but inactive. Invalid symbols, prices, directions, percentages, booleans, and unknown or ambiguous accounts receive 4xx responses. No account identifiers or financial values enter logs.

Default `GET /api/action-plan` and `GET /api/action-plan/{symbol}` retain their current JSON contracts. With `execution_modes=both`, the list response adds `manual_execution: {linear_action_plan: [...], summary: {...}, price_verification: {...}}`; the detail response adds `manual_execution_detail`. The existing `action_plan`, `linear_action_plan`, `summary`, and `action_detail` remain baseline values.

## Calculation flow

`build_action_plan` loads global analysis and selected-account portfolio data once. `compute_linear_action_plan` calculates scoring, caps, Dynamic Reserve, target bands, and pre-funding recommendations once. At the funding boundary, it copies the pre-funding rows so mutable execution fields cannot leak between variants. The baseline copy follows the existing execution path verbatim. The manual copy adds `recommended_action`, `manual_trigger_status`, `manual_trigger_price`, `manual_trigger_direction`, price-verification diagnostics, and requested/fulfilled/unfulfilled reservation fields before passing through the same whole-share, minimum-trade, priority, and Bootstrap machinery.

Buy actions (`Starter Buy`, `Add`, `Strong Add`) use one Buy maximum price. Sell/Trim actions (`Trim`, `Strong Trim`, `Sell`, `Strong Sell`) use one shared threshold and direction. A relevant trigger is `eligible` only when the current verified quote satisfies it; otherwise it is `waiting` or `price_confirmation_required`. No trigger is `no_manual_trigger`. Waiting and unconfirmed actions retain their recommendation and planned amount but receive zero currently executable shares, amount, and projected sell proceeds. They are excluded from normal Buy funding and Bootstrap.

An owned position quote is verified only if `load_positions_cache` identifies it as received from TWS in this server session, its source is `marketPrice` or `last`, its successful timestamp is within five minutes, and its price is valid. Saved analysis prices, persisted cached quotes, close/previous-close values, and delayed quotes cannot satisfy a trigger. The current analysis-price table has no trustworthy per-symbol quote provenance for unowned stocks; these return `price_confirmation_required`. PR 2 must provide an explicit verified-quote refresh path for unowned symbols and pass its source, timestamp, and value into this execution layer. Action Plan GET never initiates a TWS request.

## Reservation and funding

Only a blocked Buy intention with an enabled, positive reservation preference requests funds. Its estimated additional purchase is the whole-share amount toward the existing target midpoint at the configured Buy price:

`gap = max(0, portfolio_value_used * target_weight_mid / 100 - max(0, owned_share_quantity) * buy_trigger_price)`

`planned_shares = floor(gap / buy_trigger_price)`; `planned_purchase = planned_shares * buy_trigger_price`; `requested_reservation = planned_purchase * reserve_percentage / 100`. A planned lot below the configured minimum trade amount requests zero. This formula never changes rating, score, target weight, scenario assumptions, or the current quote used for eligible execution.

The manual execution pass first counts proceeds from eligible sells/trims. Existing Dynamic Reserve is subtracted from cash plus those projected proceeds. Blocked Buy reservations are then fulfilled in the existing Linear action-priority order, potentially partially. Fulfilled reservations are subtracted from the eligible Buy budget before the existing normal and Bootstrap funding paths run. Each reservation reports how much depends on existing cash and how much on projected eligible-sell proceeds; projected proceeds are never represented as cash already held. Summary totals reconcile requested, fulfilled, unfulfilled, immediate Buy funding, and remaining budget without double counting.

## Regression safeguards

Tests compare the default and opt-in baseline payloads field-for-field, exercise waiting/eligible/unverified thresholds, whole-share and minimum trade behavior, blocked sells and Bootstrap, partial reservation priority, Dynamic Reserve, account isolation, CRUD validation, backup/restore, and restart behavior. Full Python and Node suites and syntax/diff checks are required before the draft PR.
