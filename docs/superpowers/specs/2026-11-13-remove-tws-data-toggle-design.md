# Automatic TWS Market-Data Design

## Intent

Remove the user-controlled `Data from TWS` switch so that existing explicit
refresh actions request IBKR/TWS prices whenever a connection is available.
Valid cached quotes remain the fallback when TWS is unavailable or quotes are
partial; no background polling or allocation/rating methodology changes.

## Goals

- Remove the checkbox, its client state, and `use_tws_data` API/configuration
  dependency.
- Make legacy persisted `use_tws_data = 0` harmless.
- Preserve existing quote qualification, batching, retries, delayed prices,
  timeout behavior, account isolation, and cached-price Action Plan support.
- Report whether quotes were received, partial, cached, or unavailable without
  implying that a position refresh also refreshed prices.

## Non-goals

- No schema migration, provider change, background subscription/polling, or
  changes to analysis, ratings, Linear Allocation, Dynamic Reserve, or
  Speculative Buy rules.

## Approaches

1. Force the persisted setting to true. Rejected: it keeps a hidden feature
   flag and makes connection availability a configuration concern.
2. Ignore the setting in market-data paths while retaining legacy storage.
   Chosen: it is backward compatible and makes the actual request outcome the
   source of truth.
3. Remove the setting and migrate/delete every old record. Rejected: adds
   unnecessary destructive database behavior.

## Design

`fetch_ib_prices`, historical-close fallback, and the positions refresh call
their existing IBKR paths directly. Connection/request exceptions continue to
produce their established diagnostics and leave cached values intact. General
configuration no longer returns, accepts, or saves `use_tws_data`; older
clients may submit it and it is ignored.

The positions endpoint always attempts quote requests for qualified contracts.
Its status distinguishes successful quotes, partial/cached quote fallback, and
unavailable quotes. The frontend removes the switch elements, related state,
handlers, and configuration payload field while retaining the account selector
layout.
