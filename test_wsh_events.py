#!/usr/bin/env python3
r"""
Standalone Wall Street Horizon (WSH) diagnostic for IBKR/TWS API access.

Windows example:
  cd C:\Users\alexa\Documents\bakingmoney
  .\.venv\Scripts\activate
  python test_wsh_events.py --symbol MSFT --port 7496

Before running:
  - Start TWS or IB Gateway first.
  - Enable API connections in TWS/IB Gateway.
  - Use port 7496 for live TWS or 7497 for paper TWS, unless your setup differs.

This script is diagnostic only; it does not modify BakingMoney data or place trades.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import date, timedelta
from typing import Any

try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

try:
    from ib_insync import IB, Stock
except Exception as exc:  # pragma: no cover - diagnostic environment dependent
    IB = None  # type: ignore[assignment]
    Stock = None  # type: ignore[assignment]
    IMPORT_ERROR = exc
else:
    IMPORT_ERROR = None

try:
    from ib_insync import WshEventData
except Exception as exc:  # pragma: no cover - version dependent
    WshEventData = None  # type: ignore[assignment]
    WSH_EVENT_DATA_IMPORT_ERROR = exc
else:
    WSH_EVENT_DATA_IMPORT_ERROR = None


def print_section(title: str) -> None:
    print(f"\n===== {title} =====")


def truncate_text(value: Any, max_chars: int = 5000) -> str:
    text = value if isinstance(value, str) else repr(value)
    if len(text) <= max_chars:
        return text
    return f"{text[:max_chars]}\n... [truncated {len(text) - max_chars} chars]"


def parse_json_payload(payload: Any) -> Any | None:
    if payload is None:
        return None
    if isinstance(payload, (dict, list)):
        return payload
    if not isinstance(payload, str):
        payload = str(payload)
    payload = payload.strip()
    if not payload:
        return None
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return None


def pretty_print_json_preview(payload: Any, max_chars: int = 5000) -> None:
    parsed = parse_json_payload(payload)
    if parsed is None:
        print("Parsed JSON: not valid JSON or empty response")
        return
    pretty = json.dumps(parsed, indent=2, sort_keys=True)
    print(truncate_text(pretty, max_chars=max_chars))


def count_events(parsed_payload: Any) -> int | None:
    if isinstance(parsed_payload, list):
        return len(parsed_payload)
    if isinstance(parsed_payload, dict):
        for key in ("events", "data", "results", "wshe_ed", "wsh_ed"):
            value = parsed_payload.get(key)
            if isinstance(value, list):
                return len(value)
        # Some WSH responses are dictionaries keyed by event id/date.
        if parsed_payload and all(isinstance(value, dict) for value in parsed_payload.values()):
            return len(parsed_payload)
    return None


def metadata_mentions_earnings(metadata: Any) -> bool:
    text = json.dumps(metadata).lower() if isinstance(metadata, (dict, list)) else str(metadata).lower()
    return any(token in text for token in ("wshe_ed", "wsh_ed", "earnings"))


def build_wsh_filter(con_id: int, event_key: str, limit: int = 20) -> dict[str, Any]:
    return {
        "country": "All",
        "watchlist": [str(con_id)],
        "limit_region": 10,
        "limit": limit,
        event_key: "true",
    }


def request_wsh_metadata(ib: Any, errors: list[str]) -> tuple[Any | None, bool]:
    print_section("WSH METADATA")
    if not hasattr(ib, "getWshMetaData"):
        message = "ib_insync/IB object does not expose getWshMetaData(). Unsupported ib_insync/TWS API version?"
        print(message)
        errors.append(message)
        return None, False
    try:
        metadata = ib.getWshMetaData()
    except Exception as exc:  # pragma: no cover - live diagnostic
        message = (
            "WSH metadata request failed. This may indicate missing API entitlement, missing subscription access, "
            "Market Data API acknowledgement not accepted, or unsupported TWS/API version."
        )
        print(message)
        print(f"Exception: {type(exc).__name__}: {exc}")
        errors.append(f"metadata: {type(exc).__name__}: {exc}")
        return None, False

    print("Raw metadata response:")
    print(truncate_text(metadata))
    print("\nParsed metadata preview:")
    pretty_print_json_preview(metadata)
    parsed = parse_json_payload(metadata)
    earnings_hint = metadata_mentions_earnings(parsed if parsed is not None else metadata)
    print(f"\nMetadata mentions earnings/wshe_ed/wsh_ed: {earnings_hint}")
    return metadata, bool(metadata)


def request_wsh_events(ib: Any, con_id: int, days: int, errors: list[str]) -> tuple[bool, int | None]:
    print_section("WSH EVENT REQUEST")
    if WshEventData is None:
        detail = f" ({type(WSH_EVENT_DATA_IMPORT_ERROR).__name__}: {WSH_EVENT_DATA_IMPORT_ERROR})" if WSH_EVENT_DATA_IMPORT_ERROR else ""
        message = f"ib_insync does not expose WshEventData. Upgrade ib_insync / TWS API before testing WSH events.{detail}"
        print(message)
        errors.append(message)
        return False, None
    if not hasattr(ib, "getWshEventData"):
        message = "ib_insync/IB object does not expose getWshEventData(). Unsupported ib_insync/TWS API version?"
        print(message)
        errors.append(message)
        return False, None

    start = date.today()
    end = start + timedelta(days=days)
    event_keys = ["wshe_ed", "wsh_ed"]
    best_count: int | None = None
    any_events = False

    for event_key in event_keys:
        filter_payload = build_wsh_filter(con_id, event_key)
        print(f"\nTrying event filter key: {event_key}")
        print("Filter payload:")
        print(json.dumps(filter_payload, indent=2, sort_keys=True))
        print(f"Date range: {start:%Y%m%d} to {end:%Y%m%d}")

        try:
            request = WshEventData(
                startDate=start.strftime("%Y%m%d"),
                endDate=end.strftime("%Y%m%d"),
                filter=json.dumps(filter_payload),
            )
            response = ib.getWshEventData(request)
        except Exception as exc:  # pragma: no cover - live diagnostic
            print(f"WSH event request failed for {event_key}: {type(exc).__name__}: {exc}")
            errors.append(f"events {event_key}: {type(exc).__name__}: {exc}")
            continue

        print_section(f"WSH EVENTS ({event_key})")
        print("Raw event response:")
        print(truncate_text(response))
        print("\nParsed event preview:")
        pretty_print_json_preview(response)
        parsed = parse_json_payload(response)
        event_count = count_events(parsed)
        print(f"\nEvent count: {event_count if event_count is not None else 'unknown'}")
        if event_count is not None:
            best_count = event_count if best_count is None else max(best_count, event_count)
            any_events = any_events or event_count > 0
        elif response:
            any_events = True

        if any_events:
            break

    if not any_events:
        print(
            "\nMetadata worked but no events were returned. This may mean no event in the selected date range, "
            "the event filter key is different, or the subscription does not include this event type through API."
        )
    return any_events, best_count


def main() -> int:
    parser = argparse.ArgumentParser(description="Test IBKR Wall Street Horizon corporate events access via TWS API.")
    parser.add_argument("--symbol", default="MSFT", help="Stock symbol to test (default: MSFT)")
    parser.add_argument("--host", default="127.0.0.1", help="TWS/IB Gateway host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=7496, help="TWS/IB Gateway port (7496 live, 7497 paper; default: 7496)")
    parser.add_argument("--client-id", type=int, default=88, help="API client id (default: 88)")
    parser.add_argument("--days", type=int, default=180, help="Number of future days to request (default: 180)")
    args = parser.parse_args()

    errors: list[str] = []
    connected = False
    contract_qualified = False
    metadata_received = False
    events_received = False
    event_count: int | None = None
    ib = None

    if IMPORT_ERROR is not None:
        print_section("SUMMARY")
        print(f"ib_insync import failed: {type(IMPORT_ERROR).__name__}: {IMPORT_ERROR}")
        print("Install project dependencies / activate the virtual environment, then retry.")
        return 2

    try:
        print_section("CONNECTION")
        print(f"Connecting to TWS/IB Gateway at {args.host}:{args.port} with client id {args.client_id}")
        ib = IB()
        try:
            ib.connect(args.host, args.port, clientId=args.client_id, timeout=10)
            connected = bool(ib.isConnected())
        except Exception as exc:  # pragma: no cover - live diagnostic
            print(f"Connection failed: {type(exc).__name__}: {exc}")
            print("Check that TWS/IB Gateway is running, the port is correct, and API connections are enabled.")
            errors.append(f"connection: {type(exc).__name__}: {exc}")
            return 1

        print(f"Connected: {connected}")
        try:
            accounts = ib.managedAccounts()
            print(f"Managed accounts: {accounts}")
        except Exception as exc:  # pragma: no cover - live diagnostic
            print(f"Managed accounts unavailable: {type(exc).__name__}: {exc}")
            errors.append(f"managedAccounts: {type(exc).__name__}: {exc}")

        print_section("CONTRACT")
        contract = Stock(args.symbol.upper(), "SMART", "USD")
        try:
            qualified = ib.qualifyContracts(contract)
        except Exception as exc:  # pragma: no cover - live diagnostic
            print(f"Contract qualification failed: {type(exc).__name__}: {exc}")
            errors.append(f"contract: {type(exc).__name__}: {exc}")
            return 1
        if not qualified:
            print(f"No qualified contract returned for {args.symbol}.")
            errors.append("contract: no qualified contract returned")
            return 1
        contract = qualified[0]
        contract_qualified = True
        print(f"Symbol: {contract.symbol}")
        print(f"conId: {contract.conId}")
        print(f"exchange: {contract.exchange}")
        print(f"primaryExchange: {getattr(contract, 'primaryExchange', '')}")
        print(f"currency: {contract.currency}")

        _, metadata_received = request_wsh_metadata(ib, errors)
        events_received, event_count = request_wsh_events(ib, int(contract.conId), args.days, errors)
        return 0
    finally:
        if ib is not None:
            try:
                if ib.isConnected():
                    ib.disconnect()
                    print("\nDisconnected from IB.")
            except Exception as exc:  # pragma: no cover - live diagnostic
                errors.append(f"disconnect: {type(exc).__name__}: {exc}")
        print_section("SUMMARY")
        print(f"connected: {str(connected).lower()}")
        print(f"contract_qualified: {str(contract_qualified).lower()}")
        print(f"metadata_received: {str(metadata_received).lower()}")
        print(f"events_received: {str(events_received).lower()}")
        print(f"event_count: {event_count if event_count is not None else 'unknown'}")
        print(f"errors: {errors}")


if __name__ == "__main__":
    sys.exit(main())
