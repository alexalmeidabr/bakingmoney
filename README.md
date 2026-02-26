# bakingmoney

Baking Money is a local portfolio dashboard using FastAPI + ib_insync + SQLite.

## Environment

Create `.env` (do not commit it) from `.env.example`:

```bash
cp .env.example .env
```

Defaults:

- `IB_HOST=127.0.0.1`
- `IB_PORT=7496`
- `IB_CLIENT_ID=7`

## Run locally (Windows-friendly)

```bash
python -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python server.py
```

App URLs:

- `http://127.0.0.1:8000/holdings`
- `http://127.0.0.1:8000/watchlist`

## API endpoints

- `GET /api/health`
- `GET /api/holdings`
- `GET /api/watchlist`
- `POST /api/watchlist`
- `DELETE /api/watchlist/{ticker}`
- `GET /api/scenarios/{ticker}?horizon_years=5`
- `PUT /api/scenarios/{ticker}?horizon_years=5`

## Notes

- SQLite DB (`bakingmoney.db`) is auto-created on startup (no migrations required for MVP).
- Ratios are placeholders for now with TODO markers for future fundamentals integration.
- Scenario defaults are deterministic starter values and stored in DB for future editing.

## Tests

```bash
pytest -q
```
