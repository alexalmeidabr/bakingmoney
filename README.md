# bakingmoney

## Local UI MVP

Local web UI for IBKR positions + AI-powered analysis using standard-library `http.server` and vanilla HTML/CSS/JS.

### Run it

1. Start Trader Workstation (TWS) and make sure API access is enabled.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create a local `.env` file in the project root (this file is local-only and should not be committed).
   Example:
   ```env
   OPENAI_API_KEY=your_openai_api_key
   IB_HOST=127.0.0.1
   IB_PORT=7496
   IB_CLIENT_ID=7
   ```
4. (Optional) override or add environment variables in `.env` (or copy from `.env.example`):
   - `IB_HOST` (default `127.0.0.1`)
   - `IB_PORT` (default `7496`)
   - `IB_CLIENT_ID` (default `7`)
   - `IB_MARKET_DATA_TYPE` (default `3`, delayed data; use `1` for live)
   - `OPENAI_API_KEY` (required for Analysis generation)
   - `OPENAI_MODEL` (optional, default `gpt-5`)
5. Run:
   ```bash
   py web_server.py
   ```
6. Open:
   http://127.0.0.1:8080

### Endpoints

- `GET /` -> serves the single-page UI.
- `GET /api/positions` -> returns IBKR positions as JSON (`symbol`, `position`, `price`, `avgCost`, `changePercent`, `marketValue`, `unrealizedPnL`, `dailyPnL`, `currency`).
- `GET /api/analysis` -> list analyzed symbols (`symbol`, `expected_price`, `upside`, `overall_confidence`).
- `GET /api/analysis/{symbol}` -> detail for a symbol (`scenarios`, `key_variables`, assumptions + summary fields).
- `POST /api/analysis` with body `{"symbol":"MSFT"}` -> generates analysis via ChatGPT Thinking Mode and stores normalized rows.
- `POST /api/analysis/import-from-positions` -> imports symbols from current IBKR positions and generates analyses.
- `DELETE /api/analysis/{symbol}` -> removes analysis symbol and all child rows.

### Database

`bakingmoney.db` is created automatically with:

- `analysis_symbols(id INTEGER PK, symbol UNIQUE, current_price, expected_price, upside, overall_confidence, assumptions_text, raw_ai_response, timestamps)`
- `analysis_scenarios(id INTEGER PK, analysis_symbol_id FK, scenario_name, price/cagr ranges, probability, timestamps)`
- `analysis_key_variables(id INTEGER PK, analysis_symbol_id FK, variable_text, variable_type, confidence, importance, timestamps)`
