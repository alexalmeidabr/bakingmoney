# Manual Execution Triggers

Manual triggers delay execution of an existing Linear Allocation recommendation. They do not change company ratings, allocation scores, target bands, or saved analysis prices. BakingMoney never places an order from this screen.

## Workflow

1. Open **Action Plan**. **Without Triggers** shows the existing funded plan. **With Triggers** shows the manual execution plan from the same Action Plan response. Switching modes makes no API request.
2. Open a symbol. Enter an optional **Buy at or below** price and an optional shared **Sell/Trim trigger price** with direction. The Sell/Trim setting applies to Sell, Strong Sell, Trim, and Strong Trim recommendations.
3. Enable **Reserve cash while waiting for Buy trigger** and choose 0–100% if desired. The requested amount is a planning earmark; it does not restrict IBKR cash. The editor retains this preference even while the current recommendation is Hold or Sell.
4. Select **Save Triggers** to write the complete preference object, or **Clear Triggers** to delete it. Only one Save or Clear request can be active for the same account, Action Plan or simulation, and symbol. Both mutation buttons are disabled while that request is pending, but the fields remain editable. A successful save reloads the dual-mode plan once. Edits made during the request remain visible and unsaved until the user explicitly saves again. A reload failure is reported separately from persistence success.
5. Select **Refresh Trigger Prices** to ask TWS for a newer usable market price for applicable manual triggers. The detail editor also has **Refresh This Trigger Price**. Quote refresh is explicit; there is no polling or TWS request during Action Plan GET or mode switching.

The manual table keeps the original investment recommendation visible. Trigger status is separate from funded amount and whole shares. **Eligible, unfunded** means the price condition is satisfied but the trade has no funded whole shares. Guardrails remain visible. The manual summary separates Dynamic Reserve from requested, fulfilled, and unfulfilled manual reservations, including the portions backed by current cash-like funds and projected Sell/Trim proceeds.

## API

`GET /api/action-plan?execution_modes=both&account_id=...` returns the unchanged baseline `linear_action_plan` and `summary.linear_summary`, plus `manual_execution.linear_action_plan`, `manual_execution.summary`, and `manual_execution.price_verification`. Detail GET with `execution_modes=both` returns `action_detail` and `manual_execution_detail`.

Existing preference endpoints are `GET /api/manual-execution-triggers/{symbol}`, `PUT /api/manual-execution-triggers/{symbol}`, and `DELETE /api/manual-execution-triggers/{symbol}`. PUT replaces the complete object:

```json
{
  "buy_trigger_price": 80,
  "sell_trigger_price": 700,
  "sell_trigger_direction": "at_or_above",
  "reserve_enabled": true,
  "reserve_percentage": 60
}
```

`POST /api/manual-execution-quotes/refresh?account_id=...` accepts `{"symbols":["NVDA","META"]}`. It validates and deduplicates 1–25 symbols, checks that each has a saved analysis version, resolves the selected account, and returns one result per symbol. A result reports a usable quote or explains why the refresh failed. TWS connection failure returns HTTP 503 with per-symbol feedback. Partial market-data failures return HTTP 200 with results for each requested symbol. An unsuccessful refresh leaves the last usable planning price available.

## Latest usable price

Both Action Plan workspaces select prices from the selected account's position market data and available contract-matched observations, including explicit quote refreshes saved in SQLite. Market observation time, retrieval time, and persistence time are separate metadata. Known timestamps are normalized to UTC. Request completion is recorded as retrieval time and is never promoted to an exchange observation time.

A usable observation with a known market time outranks one whose market time is unknown. Among known observations, the newer market observation wins even when it is delayed and the older observation is live. Bid/ask observations use the older side's market timestamp when both sides form one coherent snapshot; BakingMoney never combines sides from different candidates.

When market times are equal or unavailable, source quality is the deterministic fallback: live, delayed, frozen or closing, delayed-frozen, then previously cached market data. A persisted observation is treated as cached for a tie even though its original source remains visible. A coherent two-sided quote breaks a tie within the same class. Retrieval time breaks only otherwise equivalent ties; it does not make an unknown-time quote newer than a known market observation or let a later-retrieved close outrank a live source. Saved company analysis remains outside this market ordering as the final fallback. When all sources lack a positive finite price, the trigger shows **Price Unavailable**.

A two-sided observation supplies its midpoint as the reference when it has no separate market price. Buy triggers compare the ask and Sell/Trim triggers compare the bid. The trigger detail identifies the side and the time used. A single-price observation supplies the same value for display and evaluation. The price condition is **Eligible** or **Waiting** regardless of quote age. A cached, delayed, older, or unknown-time price may differ from the price currently available in the market.

Price displays say **market observed at** only when that timestamp is known. Retrieval-only quotes say **retrieved at**; otherwise the time is shown as unknown. Explicit refreshes collect market data only when requested. An owned symbol uses only an observation whose IBKR contract identity matches the position. An unowned symbol uses the existing uniquely qualified USD SMART stock rules; known contract identities take priority over a legacy unknown identity. An unknown-only legacy observation remains available with an explicit identity warning and is never matched to an owned contract. Usable explicit observations survive restart and are isolated by portfolio account and contract. Refreshing market data leaves research inputs intact.

SQLite observations and position-cache rows store nullable `market_observed_at`, `retrieved_at`, and `persisted_at` fields. Observations use the composite key `(account_id, symbol, contract_key)`, so a qualified contract transition preserves both identities instead of overwriting the earlier one. Database initialization transactionally copies the original symbol-keyed table into the contract-keyed schema and verifies the row count before replacing it. A legacy `price_last_successful_at` remains readable as retrieval metadata only when neither explicit retrieval metadata nor an explicit market time exists; migration never reinterprets it as a confirmed exchange timestamp.

## Screenshots

These screenshots use synthetic portfolio rows rendered in Chrome. They contain no user portfolio data or live TWS quote.

![Action Plan without triggers](screenshots/action-plan-without-triggers.png)

![Action Plan with triggers](screenshots/action-plan-with-triggers.png)

![Manual trigger editor](screenshots/manual-execution-trigger-editor.png)

Regenerate with `node tools/capture_manual_execution_screenshots.js` on a machine with Chrome. The script uses a temporary browser profile and a local static server; it does not open the application database.

## Manual TWS checks

- Verify a live unowned Buy with ask below threshold becomes eligible, releases its reservation, and sizes whole shares at that ask.
- Verify an ask above threshold remains waiting; check the same for Sell/Trim using bid and both direction choices.
- Disconnect TWS and repeat the refresh. Confirm the failure feedback and verify that an earlier usable price still evaluates the trigger.
- Request a symbol with delayed data. Check the source and timestamp used for the trigger.
- Switch between two accounts with the same symbol and distinct preferences. Check each account's price and reservations.
- Reopen the application after more than five minutes. Verify that a last-known usable price can still satisfy a trigger.

The plan evaluates available observations when calculated. It does not track intraday threshold crossings between observations.
