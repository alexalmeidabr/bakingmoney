# Action Plan Simulator

Select a portfolio account and open **Action Plan Simulator**, directly below **Action Plan** in the sidebar. Each saved simulation belongs to the selected account.

## Create and run a simulation

1. Choose **New Simulation** and enter a name and a nonnegative amount of **Additional Cash (USD)**.
2. Leave **Copy current Action Plan triggers** selected to start with a one-time copy of the account's saved trigger settings, or choose **Start without triggers**.
3. Choose **Create & Run**. Open **Without Triggers** to see the funded Linear Allocation plan, or **With Triggers** to include the simulation's trigger conditions and cash reservations.

Open a symbol to edit **Simulation Triggers**. Set a Buy threshold, Sell/Trim threshold and direction, or the percentage of a waiting purchase to reserve. Saving or clearing affects only this simulation. Later changes in the regular Action Plan or another simulation are independent.

## Change or revisit a simulation

Choose a saved simulation in the selector. Expand its settings, edit additional cash, and choose **Apply & Recalculate** to save the amount and apply it to the plan. You can rename a simulation, duplicate its current assumptions and triggers under another name, or delete it after confirmation. A duplicate can be edited independently. Switching portfolio accounts shows that account's own simulations.

The database retains the name, account, additional cash and manual triggers across restarts. Reopening the plan recalculates it from the latest available real holdings, cash, analysis and market observations. For example, adding $20,000 increases both portfolio value and available cash-like funds by $20,000. Existing shares and their prices stay the same. Their weights, dollar targets, reserve dollars, funding priorities and executable whole-share quantities are recalculated against the larger portfolio.

The regular Action Plan and Simulator use the same price selection and allocation engine. A last-known market price can satisfy a trigger even when TWS is disconnected. Read the displayed price source, timestamp and warning when assessing the result. [Manual execution trigger details](manual-execution-triggers.md)

Simulated deposits exist only in the calculation. Saving or running a simulation neither transfers funds nor places brokerage orders.

## Persistence and validation

SQLite stores simulation assumptions in `action_plan_simulations` and their independent preferences in `action_plan_simulation_triggers`. Last-known account market observations are stored in `action_plan_price_observations`; positions retain their existing cache. The normal database backup includes all three tables. Restoring an older backup creates missing tables during initialization. Calculated plans and portfolio snapshots are not saved as simulation data.

Additional cash accepts finite numeric amounts between $0 and $1 billion. Names must contain 1–200 characters. Unsaved cash edits keep the previous results visible and are explicitly discarded or applied before switching contexts or refreshing.

## Developer validation

Run `python -m unittest discover` and all root `test_*.js` files with `node --test`. For a synthetic browser check, run `node tools/smoke_action_plan_simulator.cjs` from the repository root with Node 22+ and Microsoft Edge. Set `BROWSER_PATH` to another Chromium browser executable or `CDP_PORT` if needed. The smoke test uses temporary browser state and mocked HTTP responses; it never opens the application database or brokerage connection.
