# bakingmoney

## Local UI MVP

Local web UI for IBKR positions + watchlist using standard-library `http.server` and vanilla HTML/CSS/JS.

### Run it

1. Start Trader Workstation (TWS) and make sure API access is enabled.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. (Optional) set environment variables (or copy from `.env.example`):
   - `IB_HOST` (default `127.0.0.1`)
   - `IB_PORT` (default `7496`)
   - `IB_CLIENT_ID` (default `7`)
   - `IB_MARKET_DATA_TYPE` (default `3`, delayed data; use `1` for live)
   - `FINNHUB_API_KEY` (required for P/E and Forward P/E)
4. Run:
   ```bash
   py web_server.py
   ```
5. Open:
   http://127.0.0.1:8080

### Endpoints

- `GET /` -> serves the single-page UI.
- `GET /api/positions` -> returns IBKR positions as JSON (`symbol`, `position`, `avgCost`, `currency`).
- `GET /api/watchlist` -> returns watchlist as JSON (`symbol`, `price`, `pe`, `forwardPe`).
- `POST /api/watchlist` with body `{"symbol":"MSFT"}` -> adds symbol to watchlist.
- `DELETE /api/watchlist/{symbol}` -> removes symbol.
- `POST /api/watchlist/import-positions` -> adds all current position symbols to watchlist.

### Database

`bakingmoney.db` is created automatically with:

- `watchlist(symbol TEXT PRIMARY KEY, created_at TEXT)`
- `fundamentals_cache(symbol TEXT PRIMARY KEY, pe REAL, forward_pe REAL, updated_at TEXT)`

Finnhub fundamentals are cached for 24 hours.
