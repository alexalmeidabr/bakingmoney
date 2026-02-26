import app  # noqa: F401
import os
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .database import Base, engine, get_db
from .ib_service import IBService
from .models import RatioCache, Scenario, WatchlistItem
from .scenarios import default_scenarios_from_price
from .schemas import ScenarioUpsertRequest, WatchlistIn

load_dotenv()

IB_HOST = os.getenv("IB_HOST", "127.0.0.1")
IB_PORT = int(os.getenv("IB_PORT", "7496"))
IB_CLIENT_ID = int(os.getenv("IB_CLIENT_ID", "7"))

app = FastAPI(title="Baking Money")
templates = Jinja2Templates(directory="templates")
ib_service = IBService(host=IB_HOST, port=IB_PORT, client_id=IB_CLIENT_ID)


def get_or_create_ratios(db: Session, ticker: str):
    ratio = db.query(RatioCache).filter(RatioCache.ticker == ticker).first()
    if not ratio:
        ratio = RatioCache(
            ticker=ticker,
            pe=None,
            ps=None,
            ev_ebitda=None,
            dividend_yield=None,
        )
        db.add(ratio)
        db.commit()
        db.refresh(ratio)
    return {
        "pe": ratio.pe,
        "ps": ratio.ps,
        "ev_ebitda": ratio.ev_ebitda,
        "dividend_yield": ratio.dividend_yield,
        "todo": "TODO: integrate fundamentals provider for production ratios.",
    }


def get_scenarios_map(db: Session, ticker: str, horizon_years: int = 5):
    rows = (
        db.query(Scenario)
        .filter(Scenario.ticker == ticker.upper(), Scenario.horizon_years == horizon_years)
        .all()
    )
    if not rows:
        starter = default_scenarios_from_price(ticker.upper(), None, horizon_years=horizon_years)
        for row in starter:
            db.add(Scenario(**row))
        db.commit()
        rows = (
            db.query(Scenario)
            .filter(Scenario.ticker == ticker.upper(), Scenario.horizon_years == horizon_years)
            .all()
        )

    mapping = {}
    for row in rows:
        mapping[row.scenario_type] = {
            "price_low": row.price_low,
            "price_high": row.price_high,
            "cagr_low": row.cagr_low,
            "cagr_high": row.cagr_high,
            "probability": row.probability,
            "assumptions_risks": row.assumptions_risks,
            "what_to_look_for": row.what_to_look_for,
        }
    return mapping


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    ib_service.safe_connect()


@app.get("/api/health")
def api_health():
    return ib_service.health()


@app.get("/api/holdings")
def api_holdings(db: Session = Depends(get_db)):
    positions = ib_service.get_positions()
    payload = []
    for pos in positions:
        ticker = pos.contract.symbol
        price_result = ib_service.get_last_price(ticker)
        payload.append(
            {
                "ticker": ticker,
                "name": pos.contract.localSymbol or ticker,
                "currency": price_result.currency,
                "last_price": price_result.price,
                "warning": price_result.warning,
                "position": pos.position,
                "avg_cost": pos.avgCost,
                "ratios": get_or_create_ratios(db, ticker),
                "scenarios": get_scenarios_map(db, ticker),
            }
        )
    return payload


@app.get("/api/watchlist")
def api_watchlist(db: Session = Depends(get_db)):
    items = db.query(WatchlistItem).order_by(WatchlistItem.ticker.asc()).all()
    payload = []
    for item in items:
        ticker = item.ticker.upper()
        price_result = ib_service.get_last_price(ticker)
        payload.append(
            {
                "ticker": ticker,
                "name": ticker,
                "currency": price_result.currency,
                "last_price": price_result.price,
                "warning": price_result.warning,
                "ratios": get_or_create_ratios(db, ticker),
                "scenarios": get_scenarios_map(db, ticker),
            }
        )
    return payload


@app.post("/api/watchlist")
def api_add_watchlist(payload: WatchlistIn, db: Session = Depends(get_db)):
    ticker = payload.ticker.strip().upper()
    if not ticker:
        raise HTTPException(status_code=400, detail="Ticker is required")
    exists = db.query(WatchlistItem).filter(WatchlistItem.ticker == ticker).first()
    if exists:
        return {"ok": True, "ticker": ticker, "message": "Already exists"}
    db.add(WatchlistItem(ticker=ticker))
    db.commit()
    get_scenarios_map(db, ticker)
    return {"ok": True, "ticker": ticker}


@app.delete("/api/watchlist/{ticker}")
def api_delete_watchlist(ticker: str, db: Session = Depends(get_db)):
    item = db.query(WatchlistItem).filter(WatchlistItem.ticker == ticker.upper()).first()
    if not item:
        raise HTTPException(status_code=404, detail="Ticker not found")
    db.delete(item)
    db.commit()
    return {"ok": True}


@app.get("/api/scenarios/{ticker}")
def api_get_scenarios(ticker: str, horizon_years: int = Query(5), db: Session = Depends(get_db)):
    return {
        "ticker": ticker.upper(),
        "horizon_years": horizon_years,
        "scenarios": get_scenarios_map(db, ticker, horizon_years=horizon_years),
    }


@app.put("/api/scenarios/{ticker}")
def api_put_scenarios(
    ticker: str,
    payload: ScenarioUpsertRequest,
    horizon_years: int = Query(5),
    db: Session = Depends(get_db),
):
    ticker = ticker.upper()
    existing = (
        db.query(Scenario)
        .filter(Scenario.ticker == ticker, Scenario.horizon_years == horizon_years)
        .all()
    )
    for row in existing:
        db.delete(row)
    db.flush()

    for scenario in payload.scenarios:
        db.add(
            Scenario(
                ticker=ticker,
                scenario_type=scenario.scenario_type,
                horizon_years=horizon_years,
                price_low=scenario.price_low,
                price_high=scenario.price_high,
                cagr_low=scenario.cagr_low,
                cagr_high=scenario.cagr_high,
                probability=scenario.probability,
                assumptions_risks=scenario.assumptions_risks,
                what_to_look_for=scenario.what_to_look_for,
            )
        )
    db.commit()
    return {"ok": True, "ticker": ticker, "horizon_years": horizon_years}


@app.get("/", response_class=HTMLResponse)
def home_redirect():
    return RedirectResponse(url="/holdings", status_code=302)


@app.get("/holdings", response_class=HTMLResponse)
def holdings_page(request: Request, db: Session = Depends(get_db)):
    rows = api_holdings(db)
    return templates.TemplateResponse(
        "holdings.html", {"request": request, "rows": rows, "page_title": "Holdings"}
    )


@app.get("/watchlist", response_class=HTMLResponse)
def watchlist_page(request: Request, db: Session = Depends(get_db)):
    rows = api_watchlist(db)
    return templates.TemplateResponse(
        "watchlist.html", {"request": request, "rows": rows, "page_title": "Watchlist"}
    )


@app.post("/watchlist/add")
def watchlist_add_form(ticker: str = "", db: Session = Depends(get_db)):
    api_add_watchlist(WatchlistIn(ticker=ticker), db)
    return RedirectResponse(url="/watchlist", status_code=303)


@app.post("/watchlist/delete/{ticker}")
def watchlist_delete_form(ticker: str, db: Session = Depends(get_db)):
    api_delete_watchlist(ticker, db)
    return RedirectResponse(url="/watchlist", status_code=303)
