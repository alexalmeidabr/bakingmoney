# Manual Execution Triggers UI and quote verification

The Action Plan loads baseline and manual Linear Allocation results together. The default view displays the existing baseline. Switching views uses cached data; saving a trigger or explicitly refreshing quotes reloads it once. Investment recommendations remain separate from manual execution and funding status.

The detail view edits the complete account-and-symbol preference through the existing PUT and DELETE endpoints. It displays baseline recommendations beside manual status, verified bid/ask evidence, and reservation accounting. The list uses the backend's manual summary and amounts without recalculating cash in JavaScript.

`POST /api/manual-execution-quotes/refresh` accepts a bounded list of analyzed symbols, resolves the selected portfolio account, qualifies stock contracts in TWS, and collects live bid and ask events with the existing observation safeguards. Valid proofs live only in server memory under the database/account key. A failed attempt clears prior proof for requested symbols. Action Plan GET performs no TWS work. Proof expires after five minutes. For unowned symbols, manual evaluation and sizing use verified ask; baseline saved analysis prices and holdings are unchanged. Owned symbols retain their position quote verification path.

Frontend requests capture account and request generation. A response for an earlier account or an obsolete detail request cannot replace current UI state. Quote refresh is explicit and reports per-symbol outcomes.

No order placement, polling, analysis price update, or investment methodology change is included.
