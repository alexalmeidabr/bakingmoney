# bakingmoney

## Local UI MVP (Step 1)

This repo now includes a simple local web UI for viewing IBKR positions using a standard-library Python server (`http.server`) and vanilla HTML/CSS/JS.

### Run it

1. Start Trader Workstation (TWS) and make sure API access is enabled.
2. (Optional) set environment variables (or copy from `.env.example`):
   - `IB_HOST` (default `127.0.0.1`)
   - `IB_PORT` (default `7496`)
   - `IB_CLIENT_ID` (default `7`)
   - `IB_MARKET_DATA_TYPE` (default `3`, delayed data; use `1` for live)
3. Run:
   ```bash
   py web_server.py
   ```
4. Open:
   http://127.0.0.1:8080

### Endpoints

- `GET /` -> serves the single-page UI.
- `GET /api/positions` -> returns IBKR positions as JSON (`symbol`, `position`, `price`, `avgCost`, `changePercent`, `marketValue`, `unrealizedPnL`, `dailyPnL`, and `currency` when available).
