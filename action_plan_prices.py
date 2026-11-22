"""Select and retain market observations shared by both Action Plan workspaces."""
import math
from datetime import datetime, timedelta, timezone

BUY_ACTIONS = {"Strong Add", "Add", "Starter Buy"}
SELL_ACTIONS = {"Sell", "Strong Sell", "Trim", "Strong Trim"}

# Reliable market time determines recency. Source quality is only a fallback
# when market times are equal or unavailable. Retrieval time is the final
# deterministic tie-break between otherwise equivalent unknown-time quotes.
SOURCE_QUALITY = {
    "cached": 1,
    "delayed_frozen": 2,
    "frozen": 3,
    "delayed": 4,
    "live": 5,
}


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


def _iso(value):
    timestamp = _time(value)
    return timestamp.isoformat() if timestamp else None


def _source_kind(raw, source):
    lowered = str(source or "").lower()
    delayed = bool(raw.get("delayed") or "delay" in lowered)
    closing = any(part in lowered for part in ("close", "prevclose", "previous_close"))
    frozen = bool(raw.get("frozen") or "frozen" in lowered or closing)
    persisted = bool(raw.get("persisted"))
    cached = persisted or raw.get("price_status") == "cached_stale" or lowered == "cached" or lowered.startswith("cached_")
    if cached:
        return "cached", delayed, frozen
    if delayed and frozen:
        return "delayed_frozen", delayed, frozen
    if delayed:
        return "delayed", delayed, frozen
    if frozen:
        return "frozen", delayed, frozen
    return "live", delayed, frozen


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

    bid_at, ask_at = _time(raw.get("bid_tick_at")), _time(raw.get("ask_tick_at"))
    explicit_market_time = _time(raw.get("market_observed_at")) or _time(raw.get("observed_at"))
    # A coherent pair is only as new as its older side. Never promote request
    # completion or a legacy success timestamp to an exchange observation.
    market_time = min(bid_at, ask_at) if bid is not None and bid_at and ask_at else explicit_market_time
    retrieved_time = (
        _time(raw.get("retrieved_at"))
        or _time(raw.get("price_retrieved_at"))
        or _time(raw.get("refresh_at"))
    )
    if retrieved_time is None and explicit_market_time is None:
        retrieved_time = _time(raw.get("price_last_successful_at"))
    persisted_time = _time(raw.get("persisted_at"))
    source_kind, delayed, frozen = _source_kind(raw, source)
    market_iso = market_time.isoformat() if market_time else None
    retrieved_iso = retrieved_time.isoformat() if retrieved_time else None
    display_time = market_iso or retrieved_iso
    timestamp_kind = "market_observation" if market_iso else "retrieval" if retrieved_iso else "unknown"
    return dict(
        price=price, price_source=source, source_kind=source_kind,
        source_quality=SOURCE_QUALITY[source_kind], contract_key=raw.get("contract_key"),
        symbol=raw.get("symbol"), market_observed_at=market_iso, retrieved_at=retrieved_iso,
        persisted_at=persisted_time.isoformat() if persisted_time else None,
        price_timestamp_kind=timestamp_kind, price_last_successful_at=display_time,
        bid=bid, ask=ask, bid_tick_at=bid_at.isoformat() if bid_at else None,
        ask_tick_at=ask_at.isoformat() if ask_at else None, price_status=raw.get("price_status"),
        delayed=delayed, frozen=frozen, price_warning=raw.get("price_warning"),
        persisted=bool(raw.get("persisted")),
    )


def _rank(observation):
    market_time = observation.get("market_observed_at")
    return (
        market_time is not None,
        market_time or "",
        observation.get("source_quality", 0),
        observation.get("bid") is not None,
        observation.get("retrieved_at") or "",
    )


def _warning(item, now):
    warnings = []
    if item.get("price_warning"):
        warnings.append(item["price_warning"])
    source_kind = item.get("source_kind") or _source_kind(item, item.get("price_source"))[0]
    delayed = bool(item.get("delayed") or "delay" in str(item.get("price_source") or "").lower())
    frozen = bool(item.get("frozen") or "frozen" in str(item.get("price_source") or "").lower())
    if delayed and frozen:
        warnings.append("Delayed-frozen market data.")
    elif delayed:
        warnings.append("Delayed market data.")
    elif frozen or source_kind == "frozen":
        warnings.append("Frozen or closing market data.")
    if item.get("persisted") or source_kind == "cached":
        warnings.append("Using a saved market price.")

    market_time = _time(item.get("market_observed_at"))
    retrieved_time = _time(item.get("retrieved_at"))
    if market_time is None:
        if retrieved_time is None:
            warnings.append("Market observation and retrieval times are unknown.")
        else:
            warnings.append(f"Market observation time is unknown; quote retrieved at {retrieved_time.isoformat()}.")
    age_time = market_time or retrieved_time
    if age_time is not None and now - age_time > timedelta(minutes=5):
        warnings.append("Last-known price may differ from the current market.")
    return " ".join(dict.fromkeys(warnings)) or None


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
        return dict(
            price=item["price"], price_source=item["price_source"], price_status=status,
            market_observed_at=item["market_observed_at"], retrieved_at=item["retrieved_at"],
            persisted_at=item["persisted_at"], price_timestamp_kind=item["price_timestamp_kind"],
            price_last_successful_at=item["price_last_successful_at"],
            price_warning=_warning(item, datetime.now(timezone.utc)),
            price_sizing_source="position_quote" if is_position else "market_observation",
            contract_key=item["contract_key"], manual_quote_proof=item if item["bid"] else None,
        )
    price = _positive(analysis.get("current_price"))
    if price:
        return dict(
            price=price, price_source="analysis_fallback", price_status=position.get("price_status"),
            market_observed_at=None, retrieved_at=None, persisted_at=None,
            price_timestamp_kind="unknown", price_last_successful_at=None,
            price_sizing_source="analysis_price_fallback",
            price_warning="Using saved analysis price because no usable IBKR market observation is available.",
        )
    return dict(
        price=None, price_source=None, price_status="unavailable",
        market_observed_at=None, retrieved_at=None, persisted_at=None,
        price_timestamp_kind="unknown", price_last_successful_at=None,
        price_warning="No usable market price is available for Action Plan sizing.",
        price_sizing_source="unavailable",
    )


def evaluate_trigger(row, preference, now=None):
    row, preference = row or {}, preference or {}
    action = row.get("recommended_action") or row.get("action")
    buy = action in BUY_ACTIONS
    direction = "at_or_below" if buy else preference.get("sell_trigger_direction") or "at_or_above"
    trigger = _positive(preference.get("buy_trigger_price" if buy else "sell_trigger_price"))
    if not buy and action not in SELL_ACTIONS:
        trigger = None
    result = dict(
        status="no_manual_trigger", manual_trigger_price=trigger,
        manual_trigger_direction=direction if trigger else None, verified_price=None,
        verified_quote_at=None, verified_market_observed_at=None, verified_retrieved_at=None,
        verified_quote_time_kind="unknown", verified_quote_expires_at=None,
        verification_reason=None, price_source=None,
    )
    if trigger is None:
        return result

    price = _positive(row.get("current_price"))
    market_observed_at = _iso(row.get("market_observed_at"))
    retrieved_at = _iso(row.get("retrieved_at")) or (
        _iso(row.get("price_last_successful_at")) if market_observed_at is None else None
    )
    source = row.get("price_source")
    selected = _observation(row.get("manual_quote_proof") or {})
    row_observation = _observation({
        **row, "price": price, "market_observed_at": market_observed_at, "retrieved_at": retrieved_at,
    }) if price is not None else None
    if selected is None or row_observation is None:
        current_proof = selected is not None
    elif selected.get("market_observed_at") and row_observation.get("market_observed_at"):
        current_proof = selected["market_observed_at"] >= row_observation["market_observed_at"]
    elif row_observation.get("market_observed_at"):
        current_proof = False
    elif selected.get("market_observed_at"):
        current_proof = True
    else:
        current_proof = _rank(selected) >= _rank(row_observation)
    if selected and selected["bid"] and current_proof and all(
            not row.get(key) or not selected.get(key) or row[key] == selected[key]
            for key in ("contract_key", "symbol")):
        side = "ask" if buy else "bid"
        price = selected[side]
        market_observed_at = selected[side + "_tick_at"] or selected["market_observed_at"]
        retrieved_at = selected["retrieved_at"]
        source = f"{selected['price_source']} ({side})"
    if price is None:
        result.update(status="price_unavailable", verification_reason="No usable market price is available.")
        return result
    reached = price <= trigger if direction == "at_or_below" else price >= trigger
    timestamp_kind = "market_observation" if market_observed_at else "retrieval" if retrieved_at else "unknown"
    observed_at = market_observed_at or retrieved_at
    warning = row.get("price_warning")
    if not warning:
        warning = _warning({
            "price_source": source or "cached", "market_observed_at": market_observed_at,
            "retrieved_at": retrieved_at, "price_status": row.get("position_price_status"),
        }, now or datetime.now(timezone.utc))
    result.update(
        status="eligible" if reached else "waiting", verified_price=price,
        verified_quote_at=observed_at, verified_market_observed_at=market_observed_at,
        verified_retrieved_at=retrieved_at, verified_quote_time_kind=timestamp_kind,
        price_source=source, verification_reason=warning,
    )
    return result


def _ensure_column(conn, name, definition):
    columns = {row[1] for row in conn.execute("PRAGMA table_info(action_plan_price_observations)")}
    if name not in columns:
        conn.execute(f"ALTER TABLE action_plan_price_observations ADD COLUMN {name} {definition}")


def init_schema(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS action_plan_price_observations (
            account_id TEXT NOT NULL, symbol TEXT NOT NULL, contract_key TEXT,
            price REAL NOT NULL CHECK(price > 0), price_source TEXT NOT NULL,
            price_last_successful_at TEXT, market_observed_at TEXT, retrieved_at TEXT,
            persisted_at TEXT, bid REAL, ask REAL,
            bid_tick_at TEXT, ask_tick_at TEXT, delayed INTEGER NOT NULL,
            price_warning TEXT, PRIMARY KEY(account_id, symbol)
        )
    """)
    _ensure_column(conn, "market_observed_at", "TEXT")
    _ensure_column(conn, "retrieved_at", "TEXT")
    _ensure_column(conn, "persisted_at", "TEXT")


def _row_dict(cursor, row):
    return dict(zip((field[0] for field in cursor.description), row))


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

    cursor = conn.execute(
        "SELECT * FROM action_plan_price_observations WHERE account_id=? AND symbol=?",
        (account_id, symbol),
    )
    existing_row = cursor.fetchone()
    if existing_row is not None:
        existing = _observation({**_row_dict(cursor, existing_row), "persisted": True})
        if existing is not None and _rank(item) <= _rank(existing):
            return False

    values = dict(item, account_id=account_id, symbol=symbol,
                  persisted_at=datetime.now(timezone.utc).isoformat())
    conn.execute("""
        INSERT INTO action_plan_price_observations
        (account_id,symbol,contract_key,price,price_source,price_last_successful_at,
         market_observed_at,retrieved_at,persisted_at,bid,ask,bid_tick_at,ask_tick_at,delayed,price_warning)
        VALUES (:account_id,:symbol,:contract_key,:price,:price_source,:price_last_successful_at,
                :market_observed_at,:retrieved_at,:persisted_at,:bid,:ask,:bid_tick_at,:ask_tick_at,:delayed,:price_warning)
        ON CONFLICT(account_id,symbol) DO UPDATE SET
            contract_key=excluded.contract_key, price=excluded.price, price_source=excluded.price_source,
            price_last_successful_at=excluded.price_last_successful_at,
            market_observed_at=excluded.market_observed_at, retrieved_at=excluded.retrieved_at,
            persisted_at=excluded.persisted_at, bid=excluded.bid, ask=excluded.ask,
            bid_tick_at=excluded.bid_tick_at, ask_tick_at=excluded.ask_tick_at,
            delayed=excluded.delayed, price_warning=excluded.price_warning
    """, values)
    return True


def load_observations(conn, account_id):
    cursor = conn.execute("SELECT * FROM action_plan_price_observations WHERE account_id=?", (account_id,))
    columns = [field[0] for field in cursor.description]
    items = (dict(zip(columns, row), persisted=True) for row in cursor)
    return {item["symbol"]: item for item in items}
