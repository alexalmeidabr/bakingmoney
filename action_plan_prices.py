"""Select and retain market observations shared by both Action Plan workspaces."""
import math
from datetime import datetime, timedelta, timezone

BUY_ACTIONS = {"Strong Add", "Add", "Starter Buy"}
SELL_ACTIONS = {"Sell", "Strong Sell", "Trim", "Strong Trim"}


def _positive(value):
    if isinstance(value, bool):
        return None
    try:
        value = float(value)
    except (ValueError, TypeError, OverflowError):
        return None
    return value if math.isfinite(value) and value > 0 else None


def _time(value):
    try:
        timestamp = datetime.fromisoformat(value) if isinstance(value, str) else value
        if isinstance(timestamp, datetime) and timestamp.utcoffset() is not None:
            return timestamp.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        pass
    return None


def _observation(raw):
    source = raw.get("market_data_source") or raw.get("price_source") or raw.get("source") or "cached"
    bid, ask = _positive(raw.get("bid")), _positive(raw.get("ask"))
    if bid is None or ask is None or ask < bid:
        bid = ask = None
    price = _positive(raw.get("price"))
    if price is None and bid is not None:
        price = bid + (ask - bid) / 2
    if price is None:
        return None
    # Price-specific times precede receipt time. A quote pair is as old as
    # its older side. A refresh of the same snapshot cannot advance it.
    observed = _time(raw.get("observed_at")) or _time(raw.get("price_last_successful_at"))
    bid_at, ask_at = _time(raw.get("bid_tick_at")), _time(raw.get("ask_tick_at"))
    if observed is None and bid and bid_at and ask_at:
        observed = min(bid_at, ask_at)
    observed = observed or _time(raw.get("refresh_at"))
    return dict(price=price, price_source=source, contract_key=raw.get("contract_key"),
                symbol=raw.get("symbol"), price_last_successful_at=observed.isoformat() if observed else None,
                bid=bid, ask=ask, bid_tick_at=bid_at.isoformat() if bid_at else None,
                ask_tick_at=ask_at.isoformat() if ask_at else None, price_status=raw.get("price_status"),
                delayed=bool(raw.get("delayed") or "delay" in source.lower()),
                price_warning=raw.get("price_warning"), persisted=bool(raw.get("persisted")))


def _rank(observation):
    return (observation["price_last_successful_at"] or "", observation["bid"] is not None,
            not observation["delayed"], not observation["persisted"])


def _warning(item, now):
    warnings = []
    if item.get("price_warning"):
        warnings.append(item["price_warning"])
    if item.get("delayed"):
        warnings.append("Delayed market data.")
    elif "frozen" in item["price_source"].lower():
        warnings.append("Frozen market data.")
    elif item.get("persisted") or item.get("price_status") == "cached_stale" or item["price_source"] == "cached":
        warnings.append("Using a saved market price.")
    observed = _time(item.get("price_last_successful_at"))
    if observed is None:
        warnings.append("Observation time is unknown.")
    elif now - observed > timedelta(minutes=5):
        warnings.append("Last-known price may differ from the current market.")
    return " ".join(warnings) or None


def resolve_price(position, analysis, observations=()):
    position, analysis = position or {}, analysis or {}
    symbol = position.get("symbol") or analysis.get("symbol")
    contract = position.get("contract_key")
    candidates = []
    for raw in [position, *(observations or ())]:
        if not raw or (symbol and raw.get("symbol") and raw["symbol"] != symbol):
            continue
        if position.get("account_id") and raw.get("account_id") not in (None, position["account_id"]):
            continue
        if contract and raw.get("contract_key") != contract:
            continue
        item = _observation(raw)
        if item:
            candidates.append((item, raw is position))
    if candidates:
        item, is_position = max(candidates, key=lambda candidate: _rank(candidate[0]))
        status = item["price_status"] or ("cached_stale" if item["persisted"] else "tws_received")
        return dict(price=item["price"], price_source=item["price_source"], price_status=status,
                    price_last_successful_at=item["price_last_successful_at"],
                    price_warning=_warning(item, datetime.now(timezone.utc)),
                    price_sizing_source="position_quote" if is_position else "market_observation",
                    contract_key=item["contract_key"], manual_quote_proof=item if item["bid"] else None)
    price = _positive(analysis.get("current_price"))
    if price:
        return dict(price=price, price_source="analysis_fallback", price_status=position.get("price_status"),
                    price_last_successful_at=None, price_sizing_source="analysis_price_fallback",
                    price_warning="Using saved analysis price because no usable IBKR market observation is available.")
    return dict(price=None, price_source=None, price_status="unavailable", price_last_successful_at=None,
                price_warning="No usable market price is available for Action Plan sizing.", price_sizing_source="unavailable")


def evaluate_trigger(row, preference, now=None):
    row, preference = row or {}, preference or {}
    action = row.get("recommended_action") or row.get("action")
    buy = action in BUY_ACTIONS
    direction = "at_or_below" if buy else preference.get("sell_trigger_direction") or "at_or_above"
    trigger = _positive(preference.get("buy_trigger_price" if buy else "sell_trigger_price"))
    if not buy and action not in SELL_ACTIONS:
        trigger = None
    result = dict(status="no_manual_trigger", manual_trigger_price=trigger,
                  manual_trigger_direction=direction if trigger else None, verified_price=None,
                  verified_quote_at=None, verified_quote_expires_at=None, verification_reason=None, price_source=None)
    if trigger is None:
        return result
    price = _positive(row.get("current_price"))
    observed_at = row.get("price_last_successful_at")
    source = row.get("price_source")
    proof = row.get("manual_quote_proof") or {}
    selected = _observation(proof)
    row_time = _time(observed_at)
    proof_time = _time(selected["price_last_successful_at"]) if selected else None
    current_proof = row_time is None or (proof_time is not None and proof_time >= row_time)
    if selected and selected["bid"] and current_proof and all(
            not row.get(key) or not selected.get(key) or row[key] == selected[key]
            for key in ("contract_key", "symbol")):
        side = "ask" if buy else "bid"
        price = selected[side]
        observed_at = selected[side + "_tick_at"] or selected["price_last_successful_at"]
        source = f"{selected['price_source']} ({side})"
    if price is None:
        result.update(status="price_unavailable", verification_reason="No usable market price is available.")
        return result
    reached = price <= trigger if direction == "at_or_below" else price >= trigger
    warning = row.get("price_warning")
    if not warning:
        warning = _warning(dict(price_source=source or "cached", price_last_successful_at=observed_at,
                                price_status=row.get("position_price_status")), now or datetime.now(timezone.utc))
    result.update(status="eligible" if reached else "waiting", verified_price=price,
                  verified_quote_at=observed_at, price_source=source, verification_reason=warning)
    return result


def init_schema(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS action_plan_price_observations (
            account_id TEXT NOT NULL, symbol TEXT NOT NULL, contract_key TEXT,
            price REAL NOT NULL CHECK(price > 0), price_source TEXT NOT NULL,
            price_last_successful_at TEXT, bid REAL, ask REAL,
            bid_tick_at TEXT, ask_tick_at TEXT, delayed INTEGER NOT NULL,
            price_warning TEXT, PRIMARY KEY(account_id, symbol)
        )
    """)


def persist_observation(conn, account_id, symbol, observation):
    """Atomically retain a successful refresh. The caller owns the transaction."""
    symbol = (symbol or "").strip().upper()
    if not account_id or not symbol or not observation or observation.get("symbol") not in (None, symbol):
        return False
    if observation.get("account_id") not in (None, account_id):
        return False
    item = _observation(observation)
    if item is None:
        return False
    row = conn.execute("""
        INSERT INTO action_plan_price_observations
        (account_id,symbol,contract_key,price,price_source,price_last_successful_at,
         bid,ask,bid_tick_at,ask_tick_at,delayed,price_warning)
        VALUES (:account_id,:symbol,:contract_key,:price,:price_source,:price_last_successful_at,
                :bid,:ask,:bid_tick_at,:ask_tick_at,:delayed,:price_warning)
        ON CONFLICT(account_id,symbol) DO UPDATE SET
            contract_key=excluded.contract_key, price=excluded.price, price_source=excluded.price_source,
            price_last_successful_at=excluded.price_last_successful_at, bid=excluded.bid, ask=excluded.ask,
            bid_tick_at=excluded.bid_tick_at, ask_tick_at=excluded.ask_tick_at,
            delayed=excluded.delayed, price_warning=excluded.price_warning
        WHERE (coalesce(excluded.price_last_successful_at,''),excluded.bid IS NOT NULL,-excluded.delayed)
            >= (coalesce(action_plan_price_observations.price_last_successful_at,''),
                action_plan_price_observations.bid IS NOT NULL,-action_plan_price_observations.delayed)
    """, dict(item, account_id=account_id, symbol=symbol))
    return bool(row.rowcount)


def load_observations(conn, account_id):
    cursor = conn.execute("SELECT * FROM action_plan_price_observations WHERE account_id=?", (account_id,))
    columns = [field[0] for field in cursor.description]
    items = (dict(zip(columns, row), persisted=True) for row in cursor)
    return {item["symbol"]: item for item in items}
