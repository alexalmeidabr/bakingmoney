const assert = require('node:assert/strict');
const fs = require('node:fs');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync('static/app.js', 'utf8');
const html = fs.readFileSync('static/index.html', 'utf8');

function functionSource(name) {
  const start = source.indexOf(`function ${name}(`);
  assert.notEqual(start, -1, `${name} exists`);
  const declarationStart = source.slice(start - 6, start) === 'async ' ? start - 6 : start;
  const parameterStart = source.indexOf('(', start);
  let parameterDepth = 0;
  let parameterEnd = -1;
  for (let index = parameterStart; index < source.length; index += 1) {
    if (source[index] === '(') parameterDepth += 1;
    if (source[index] === ')') parameterDepth -= 1;
    if (parameterDepth === 0) { parameterEnd = index; break; }
  }
  const opening = source.indexOf('{', parameterEnd + 1);
  let depth = 0;
  for (let index = opening; index < source.length; index += 1) {
    if (source[index] === '{') depth += 1;
    if (source[index] === '}') depth -= 1;
    if (depth === 0) return source.slice(declarationStart, index + 1);
  }
  throw new Error(`${name} is incomplete`);
}

function helpers(...names) {
  const context = {
    escapeHtml: (value) => String(value),
    formatCurrencyValue: (value) => `$${Number(value).toFixed(2)}`,
  };
  const dependencies = names.some((name) => ['getManualTriggerPresentation', 'getActionPlanPriceDisplay'].includes(name)) ? [functionSource('manualQuoteExpired')] : [];
  return vm.runInNewContext(`${dependencies.join('\n')}\n${names.map(functionSource).join('\n')}\n({${names.join(',')}})`, context);
}

test('mode selection uses cached backend rows without changing recommendations', () => {
  const { getDisplayedLinearActionPlanItems } = helpers('getDisplayedLinearActionPlanItems');
  const payload = {
    linear_action_plan: [{ symbol: 'NVDA', action: 'Add', suggested_share_count: 5 }],
    manual_execution: { linear_action_plan: [{ symbol: 'NVDA', action: 'Watch', recommended_action: 'Add', suggested_share_count: 0 }] },
  };
  assert.equal(getDisplayedLinearActionPlanItems(payload, 'without')[0].suggested_share_count, 5);
  assert.equal(getDisplayedLinearActionPlanItems(payload, 'with')[0].recommended_action, 'Add');
  assert.equal(getDisplayedLinearActionPlanItems(payload, 'with')[0].suggested_share_count, 0);
  assert.match(source, /execution_modes=both/);
  assert.match(html, /Without Triggers/);
  assert.match(html, /With Triggers/);
  assert.match(html, /Refresh Trigger Prices/);
});

test('manual execution labels separate price eligibility, funding, and guardrails', () => {
  const { getManualTriggerPresentation } = helpers('getManualTriggerPresentation');
  assert.equal(getManualTriggerPresentation({ recommended_action: 'Add', manual_trigger_status: 'waiting', suggested_share_count: 0 }).status, 'Waiting');
  assert.equal(getManualTriggerPresentation({ recommended_action: 'Add', manual_trigger_status: 'eligible', suggested_share_count: 0 }).status, 'Eligible, unfunded');
  assert.equal(getManualTriggerPresentation({ recommended_action: 'Add', manual_trigger_status: 'eligible', suggested_share_count: 3, executable_action_amount: 237 }).status, 'Eligible, funded');
  assert.equal(getManualTriggerPresentation({ recommended_action: 'Add', manual_trigger_status: 'price_confirmation_required' }).status, 'Price confirmation required');
  assert.equal(getManualTriggerPresentation({ recommended_action: 'Watch / Rating Guardrail', manual_trigger_status: 'no_manual_trigger' }).status, 'Guardrail blocked');
});

test('expired verification is never presented as eligible or funded', () => {
  const { getManualTriggerPresentation } = helpers('getManualTriggerPresentation');
  const expiredAt = new Date(Date.now() - 1000).toISOString();
  assert.equal(getManualTriggerPresentation({ manual_trigger_status: 'eligible', suggested_share_count: 3,
    executable_action_amount: 237, manual_verified_quote_expires_at: expiredAt }).status, 'Price confirmation required');
});

test('expired verified price is hidden instead of shown as a current sizing price', () => {
  const { getActionPlanPriceDisplay } = helpers('getActionPlanPriceDisplay');
  const expired = { current_price: 79, manual_verified_price: 79, manual_verified_quote_at: 'old',
    manual_verified_quote_expires_at: new Date(Date.now() - 1000).toISOString() };
  const displayed = getActionPlanPriceDisplay(expired, true);
  assert.equal(displayed.price, 'Expired');
  assert.match(displayed.title, /expired/i);
  assert.equal(getActionPlanPriceDisplay(expired, false).price, '$79.00');
});

test('complete editor values validate price and reservation limits', () => {
  const { validateManualTriggerForm } = helpers('validateManualTriggerForm');
  const base = { buy_trigger_price: '80', sell_trigger_price: '700', sell_trigger_direction: 'at_or_above', reserve_enabled: true, reserve_percentage: '60' };
  assert.equal(validateManualTriggerForm(base).value.reserve_percentage, 60);
  assert.equal(validateManualTriggerForm({ ...base, reserve_percentage: '0' }).value.reserve_percentage, 0);
  assert.equal(validateManualTriggerForm({ ...base, reserve_percentage: '100' }).value.reserve_percentage, 100);
  assert.equal(validateManualTriggerForm({ ...base, buy_trigger_price: '' }).value.buy_trigger_price, null);
  assert.ok(validateManualTriggerForm({ ...base, buy_trigger_price: '-1' }).error);
  assert.ok(validateManualTriggerForm({ ...base, sell_trigger_price: 'Infinity' }).error);
  assert.ok(validateManualTriggerForm({ ...base, reserve_percentage: '101' }).error);
  assert.ok(validateManualTriggerForm({ ...base, sell_trigger_direction: 'invalid' }).error);
  assert.match(source, /manual-execution-triggers/);
});

test('mode switch re-renders the cached payload without a fetch', () => {
  const pressed = {};
  let renders = 0;
  const context = {
    actionPlanExecutionMode: 'without',
    actionPlanWithoutTriggersBtn: { setAttribute: (_key, value) => { pressed.without = value; } },
    actionPlanWithTriggersBtn: { setAttribute: (_key, value) => { pressed.with = value; } },
    latestActionPlanDetailPayload: null,
    renderActionPlan: () => { renders += 1; },
    fetch: () => { throw new Error('toggle must not fetch'); },
  };
  vm.runInNewContext(`${functionSource('updateActionPlanModeButtons')}\n${functionSource('setActionPlanExecutionMode')}\nsetActionPlanExecutionMode('with');`, context);
  assert.equal(context.actionPlanExecutionMode, 'with');
  assert.deepEqual(pressed, { without: 'false', with: 'true' });
  assert.equal(renders, 1);
});

test('blocked Buy remains under Add filter in manual mode', () => {
  const context = {
    latestActionPlanPayload: {
      linear_action_plan: [{ symbol: 'NVDA', action: 'Add', rating: 'Buy' }],
      manual_execution: { linear_action_plan: [{ symbol: 'NVDA', recommended_action: 'Add', action: 'Watch', rating: 'Buy' }] },
    },
    actionPlanExecutionMode: 'with',
    getSelectedActionPlanRatings: () => new Set(),
    getSelectedActionPlanActions: () => new Set(['add']),
    ACTION_PLAN_ACTION_FILTER_OPTIONS: ['add', 'watch'],
    getActionPlanActionFilterKey: (value) => value.toLowerCase(),
  };
  const rows = vm.runInNewContext(`${functionSource('getDisplayedLinearActionPlanItems')}\n${functionSource('getFilteredLinearActionPlanItems')}\ngetFilteredLinearActionPlanItems()`, context);
  assert.deepEqual(rows.map((row) => row.symbol), ['NVDA']);
});

test('manual summary displays backend reservation and proceeds figures', () => {
  const { renderManualReservationSummary } = helpers('renderManualReservationSummary');
  const summary = {
    available_buy_budget_before_manual_reservations: 5000,
    requested_reservations: 3000, fulfilled_reservations: 2200, unfulfilled_reservations: 800,
    fulfilled_reservations_from_current_cash_like: 1200,
    fulfilled_reservations_from_projected_proceeds: 1000,
    available_buy_budget: 2800, funded_add_amount: 1500, remaining_buy_budget: 1300,
    executable_sell_trim_proceeds: 2000,
  };
  const rendered = renderManualReservationSummary(summary);
  assert.match(rendered, /Requested Manual Reservations[\s\S]*\$3000\.00/);
  assert.match(rendered, /Unfulfilled Manual Reservations[\s\S]*\$800\.00/);
  assert.match(rendered, /Reservations from Projected Sell\/Trim Proceeds[\s\S]*\$1000\.00/);
  assert.match(rendered, /Remaining Buy Budget[\s\S]*\$1300\.00/);
  assert.doesNotMatch(rendered, /Dynamic Reserve Target/);
});

test('save submits complete replacement and reports reload failure as persisted', async () => {
  const status = { textContent: '', className: '' };
  const calls = [];
  const context = {
    selectedPortfolioAccountId: 'U_ACCOUNT_A', actionPlanDetailRequestId: 1,
    manualTriggerDetailEl: { querySelector: () => status },
    manualTriggerEditorValues: () => ({
      buy_trigger_price: '80', sell_trigger_price: '700', sell_trigger_direction: 'at_or_below',
      reserve_enabled: true, reserve_percentage: '60',
    }),
    withSelectedPortfolioAccount: (url) => `${url}?account_id=U_ACCOUNT_A`,
    fetch: async (url, options) => { calls.push({ url, options }); return { ok: true, json: async () => ({ trigger: {} }) }; },
    loadActionPlan: async () => false,
  };
  await vm.runInNewContext(`${functionSource('validateManualTriggerForm')}\n${functionSource('saveManualTrigger')}\nsaveManualTrigger('NVDA')`, context);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].options.method, 'PUT');
  assert.deepEqual(JSON.parse(calls[0].options.body), {
    buy_trigger_price: 80, sell_trigger_price: 700, sell_trigger_direction: 'at_or_below',
    reserve_enabled: true, reserve_percentage: 60,
  });
  assert.match(status.textContent, /saved, but Action Plan reload failed/);
});

test('manual detail warns on blocked Sell and shows partial reservation', () => {
  const explanation = { innerHTML: '' };
  const context = {
    actionPlanExecutionMode: 'with',
    manualTriggerDetailEl: { querySelector: () => explanation },
    latestActionPlanPayload: { manual_execution: { linear_action_plan: [{
      symbol: 'META', recommended_action: 'Strong Sell', manual_trigger_status: 'waiting',
      manual_trigger_price: 700, manual_trigger_direction: 'at_or_above',
      requested_reservation: 3000, fulfilled_reservation: 2200, unfulfilled_reservation: 800,
      fulfilled_reservation_from_current_cash_like: 1200,
      fulfilled_reservation_from_projected_proceeds: 1000,
    }] } },
    renderActionPlanDetail: () => {},
    getDisplayedLinearActionPlanItems: (payload) => payload.manual_execution.linear_action_plan,
    renderActionPlanMetricList: (items) => items.map(([key, value]) => `${key}: ${value}`).join('|'),
    escapeHtml: String,
    formatCurrencyValue: (value) => `$${Number(value || 0).toFixed(2)}`,
    formatPercent: (value) => `${Number(value || 0)}%`,
    formatNumber: (value) => String(value ?? 0),
  };
  vm.runInNewContext(`${functionSource('manualQuoteExpired')}\n${functionSource('getManualTriggerPresentation')}\n${functionSource('manualTriggerLabel')}\n${functionSource('renderSelectedActionPlanDetail')}\nrenderSelectedActionPlanDetail({action_detail: {symbol: 'META', action: 'Strong Sell'}})`, context);
  assert.match(explanation.innerHTML, /manual price condition currently prevents execution/);
  assert.match(explanation.innerHTML, /Requested Reservation: \$3000\.00/);
  assert.match(explanation.innerHTML, /Unfulfilled Reservation: \$800\.00/);
  assert.match(explanation.innerHTML, /Projected Sell\/Trim Proceeds: \$1000\.00/);
});

test('explicit quote refresh reports partial success and reloads once', async () => {
  const status = { textContent: '', className: '' };
  const button = { disabled: false };
  let reloads = 0;
  const requests = [];
  const context = {
    selectedPortfolioAccountId: 'U_ACCOUNT_A', actionPlanQuoteRequestId: 0,
    isPortfolioAccountSelectionRequired: () => false,
    latestActionPlanPayload: {},
    getDisplayedLinearActionPlanItems: () => [
      { symbol: 'NVDA', manual_trigger_price: 80 },
      { symbol: 'META', manual_trigger_price: 700 },
    ],
    actionPlanQuoteStatusEl: status, manualTriggerDetailEl: { querySelector: () => null },
    actionPlanRefreshTriggerPricesBtn: button,
    actionPlanDetailViewEl: { classList: { contains: () => true } },
    withSelectedPortfolioAccount: (url) => `${url}?account_id=U_ACCOUNT_A`,
    fetch: async (url, options) => {
      requests.push({ url, options });
      return { ok: true, json: async () => ({ results: [
        { symbol: 'NVDA', status: 'verified' },
        { symbol: 'META', status: 'confirmation_required', reason: 'Live bid and ask unavailable' },
      ] }) };
    },
    loadActionPlan: async () => { reloads += 1; return true; },
  };
  await vm.runInNewContext(`${functionSource('refreshTriggerPrices')}\nrefreshTriggerPrices()`, context);
  assert.equal(requests.length, 1);
  assert.deepEqual(JSON.parse(requests[0].options.body).symbols, ['NVDA', 'META']);
  assert.equal(reloads, 1);
  assert.match(status.textContent, /1 live price verified; 1 require confirmation/);
  assert.equal(button.disabled, false);
});

test('an older account quote response cannot reload or overwrite the selected account', async () => {
  const status = { textContent: '', className: '' };
  let finish;
  let reloads = 0;
  const context = {
    selectedPortfolioAccountId: 'U_ACCOUNT_A', actionPlanQuoteRequestId: 0,
    isPortfolioAccountSelectionRequired: () => false,
    latestActionPlanPayload: {},
    getDisplayedLinearActionPlanItems: () => [{ symbol: 'NVDA', manual_trigger_price: 80 }],
    actionPlanQuoteStatusEl: status, manualTriggerDetailEl: { querySelector: () => null },
    actionPlanRefreshTriggerPricesBtn: { disabled: false },
    withSelectedPortfolioAccount: (url) => url,
    fetch: () => new Promise((resolve) => { finish = resolve; }),
    loadActionPlan: async () => { reloads += 1; return true; },
  };
  const pending = vm.runInNewContext(`${functionSource('refreshTriggerPrices')}\nrefreshTriggerPrices()`, context);
  context.selectedPortfolioAccountId = 'U_ACCOUNT_B';
  finish({ ok: true, json: async () => ({ results: [{ symbol: 'NVDA', status: 'verified' }] }) });
  await pending;
  assert.equal(reloads, 0);
  assert.match(status.textContent, /Refreshing live prices/);
});

test('an older account Action Plan response cannot replace the new account cache', async () => {
  let finish;
  let renders = 0;
  const context = {
    selectedPortfolioAccountId: 'U_ACCOUNT_A', actionPlanRequestId: 0,
    actionPlanLinearActionsTableBody: {},
    latestActionPlanPayload: { linear_action_plan: [{ symbol: 'NEW' }] },
    showActionPlanList: () => {}, isPortfolioAccountSelectionRequired: () => false,
    actionPlanStatusEl: { textContent: '', className: '' },
    withSelectedPortfolioAccount: (url) => url,
    fetch: () => new Promise((resolve) => { finish = resolve; }),
    renderActionPlan: () => { renders += 1; },
  };
  const pending = vm.runInNewContext(`${functionSource('loadActionPlan')}\nloadActionPlan()`, context);
  context.selectedPortfolioAccountId = 'U_ACCOUNT_B';
  finish({ ok: true, json: async () => ({ linear_action_plan: [{ symbol: 'OLD' }] }) });
  await pending;
  assert.equal(context.latestActionPlanPayload.linear_action_plan[0].symbol, 'NEW');
  assert.equal(renders, 0);
});

test('an older detail response cannot restore a previous account editor', async () => {
  const pendingResponses = [];
  let detailsRendered = 0;
  let editorRendered = 0;
  const panel = { innerHTML: 'old editor' };
  const context = {
    selectedPortfolioAccountId: 'U_ACCOUNT_A', actionPlanDetailRequestId: 0,
    latestActionPlanDetailPayload: null, manualTriggerDetailEl: panel,
    isPortfolioAccountSelectionRequired: () => false,
    latestActionPlanPayload: {}, actionPlanExecutionMode: 'with',
    getDisplayedLinearActionPlanItems: () => [],
    renderActionPlanDetail: () => {},
    actionPlanDetailStatusEl: { textContent: '', className: '' },
    withSelectedPortfolioAccount: (url) => url,
    fetch: () => new Promise((resolve) => { pendingResponses.push(resolve); }),
    renderSelectedActionPlanDetail: () => { detailsRendered += 1; },
    renderManualTriggerDetail: () => { editorRendered += 1; },
  };
  const pending = vm.runInNewContext(`${functionSource('openActionPlanDetail')}\nopenActionPlanDetail('NVDA')`, context);
  assert.equal(panel.innerHTML, '');
  context.selectedPortfolioAccountId = 'U_ACCOUNT_B';
  pendingResponses[0]({ ok: true, json: async () => ({ action_detail: { symbol: 'NVDA' } }) });
  pendingResponses[1]({ ok: true, json: async () => ({ trigger: {} }) });
  await pending;
  assert.equal(detailsRendered, 0);
  assert.equal(editorRendered, 0);
});

test('opening detail loads the account-specific saved trigger into the editor', async () => {
  const loaded = [];
  const context = {
    selectedPortfolioAccountId: 'U_ACCOUNT_A', actionPlanDetailRequestId: 0,
    latestActionPlanDetailPayload: null, manualTriggerDetailEl: { innerHTML: '' },
    isPortfolioAccountSelectionRequired: () => false,
    latestActionPlanPayload: {}, actionPlanExecutionMode: 'with',
    getDisplayedLinearActionPlanItems: () => [],
    renderActionPlanDetail: () => {},
    actionPlanDetailStatusEl: { textContent: '', className: '' },
    withSelectedPortfolioAccount: (url) => `${url}&account_id=U_ACCOUNT_A`,
    fetch: async (url) => url.includes('manual-execution-triggers')
      ? { ok: true, json: async () => ({ trigger: { buy_trigger_price: 80, sell_trigger_price: 700,
        sell_trigger_direction: 'at_or_below', reserve_enabled: true, reserve_percentage: 60 } }) }
      : { ok: true, json: async () => ({ action_detail: { symbol: 'NVDA' }, manual_execution_detail: { symbol: 'NVDA' } }) },
    renderSelectedActionPlanDetail: () => {},
    renderManualTriggerDetail: (symbol, trigger) => loaded.push({ symbol, trigger }),
  };
  await vm.runInNewContext(`${functionSource('openActionPlanDetail')}\nopenActionPlanDetail('NVDA')`, context);
  assert.equal(loaded.length, 1);
  assert.equal(loaded[0].symbol, 'NVDA');
  assert.equal(loaded[0].trigger.reserve_percentage, 60);
  assert.equal(loaded[0].trigger.sell_trigger_direction, 'at_or_below');
});

test('Clear Triggers uses DELETE and reloads the plan once', async () => {
  const status = { textContent: '', className: '' };
  const calls = [];
  let reloads = 0;
  const context = {
    selectedPortfolioAccountId: 'U_ACCOUNT_A', actionPlanDetailRequestId: 1,
    manualTriggerDetailEl: { querySelector: () => status },
    withSelectedPortfolioAccount: (url) => `${url}?account_id=U_ACCOUNT_A`,
    fetch: async (url, options) => { calls.push({ url, options }); return { ok: true, json: async () => ({ deleted: true }) }; },
    renderManualTriggerDetail: (_symbol, preference) => { assert.equal(preference, null); },
    loadActionPlan: async () => { reloads += 1; return true; },
  };
  await vm.runInNewContext(`${functionSource('clearManualTrigger')}\nclearManualTrigger('NVDA')`, context);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].options.method, 'DELETE');
  assert.equal(reloads, 1);
  assert.equal(status.textContent, 'Triggers cleared.');
});
