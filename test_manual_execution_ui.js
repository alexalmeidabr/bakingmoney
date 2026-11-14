const assert = require('node:assert/strict');
const fs = require('node:fs');
const test = require('node:test');
const vm = require('node:vm');
const { withPortfolioAccount } = require('./static/portfolio_account_selector.js');

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
    manualExecutionCalculationState: 'current',
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
  let requestedUrl;
  let reloads = 0;
  const context = {
    selectedPortfolioAccountId: 'U_ACCOUNT_A', actionPlanQuoteRequestId: 0,
    isPortfolioAccountSelectionRequired: () => false,
    latestActionPlanPayload: {},
    getDisplayedLinearActionPlanItems: () => [{ symbol: 'NVDA', manual_trigger_price: 80 }],
    actionPlanQuoteStatusEl: status, manualTriggerDetailEl: { querySelector: () => null },
    actionPlanRefreshTriggerPricesBtn: { disabled: false },
    withSelectedPortfolioAccount: (url) => withPortfolioAccount(url, context.selectedPortfolioAccountId),
    fetch: (url) => { requestedUrl = url; return new Promise((resolve) => { finish = resolve; }); },
    loadActionPlan: async () => { reloads += 1; return true; },
  };
  const pending = vm.runInNewContext(`${functionSource('refreshTriggerPrices')}\nrefreshTriggerPrices()`, context);
  assert.equal(new URL(requestedUrl, 'http://local').searchParams.get('account_id'), 'U_ACCOUNT_A');
  context.selectedPortfolioAccountId = 'U_ACCOUNT_B';
  finish({ ok: true, json: async () => ({ results: [{ symbol: 'NVDA', status: 'verified' }] }) });
  await pending;
  assert.equal(reloads, 0);
  assert.match(status.textContent, /Refreshing live prices/);
});

test('a late verified quote for account A cannot replace account B confirmation state for the same symbol', async () => {
  const status = { textContent: '', className: '' };
  const requests = [];
  const reloadAccounts = [];
  let finishA;
  const context = {
    selectedPortfolioAccountId: 'U_ACCOUNT_A', actionPlanQuoteRequestId: 0,
    isPortfolioAccountSelectionRequired: () => false,
    latestActionPlanPayload: {}, getDisplayedLinearActionPlanItems: () => [{ symbol: 'NVDA', manual_trigger_price: 80 }],
    actionPlanQuoteStatusEl: status, manualTriggerDetailEl: { querySelector: () => null },
    actionPlanRefreshTriggerPricesBtn: { disabled: false },
    actionPlanDetailViewEl: { classList: { contains: () => true } },
    withSelectedPortfolioAccount: (url) => withPortfolioAccount(url, context.selectedPortfolioAccountId),
    fetch: (url) => {
      requests.push(url);
      const account = new URL(url, 'http://local').searchParams.get('account_id');
      return account === 'U_ACCOUNT_A' ? new Promise((resolve) => { finishA = resolve; })
        : Promise.resolve({ ok: true, json: async () => ({ results: [{ symbol: 'NVDA', status: 'confirmation_required', reason: 'No live bid' }] }) });
    },
    loadActionPlan: async () => { reloadAccounts.push(context.selectedPortfolioAccountId); return true; },
  };
  vm.runInNewContext(functionSource('refreshTriggerPrices'), context);
  const pendingA = context.refreshTriggerPrices();
  context.selectedPortfolioAccountId = 'U_ACCOUNT_B';
  await context.refreshTriggerPrices();
  assert.match(status.textContent, /1 require confirmation/);
  finishA({ ok: true, json: async () => ({ results: [{ symbol: 'NVDA', status: 'verified' }] }) });
  await pendingA;
  assert.deepEqual(requests.map((url) => new URL(url, 'http://local').searchParams.get('account_id')), ['U_ACCOUNT_A', 'U_ACCOUNT_B']);
  assert.deepEqual(reloadAccounts, ['U_ACCOUNT_B']);
  assert.match(status.textContent, /1 require confirmation/);
  assert.doesNotMatch(status.textContent, /1 live price verified/);
});

test('an older account Action Plan response cannot replace the new account cache', async () => {
  let finish;
  let renders = 0;
  const context = {
    selectedPortfolioAccountId: 'U_ACCOUNT_A', actionPlanRequestId: 0,
    manualQuoteExpiryTimer: null,
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

test('manual trigger requests and quote refresh route to the selected account across an account change', async () => {
  const requests = [];
  const loaded = [];
  const status = { textContent: '', className: '' };
  const context = {
    selectedPortfolioAccountId: 'U_ACCOUNT_A', actionPlanDetailRequestId: 0, actionPlanQuoteRequestId: 0,
    latestActionPlanDetailPayload: null, latestActionPlanPayload: {}, actionPlanExecutionMode: 'with',
    manualTriggerDetailEl: { innerHTML: '', querySelector: () => status },
    actionPlanDetailStatusEl: { textContent: '', className: '' },
    actionPlanQuoteStatusEl: { textContent: '', className: '' },
    actionPlanRefreshTriggerPricesBtn: { disabled: false },
    actionPlanDetailViewEl: { classList: { contains: () => true } },
    isPortfolioAccountSelectionRequired: () => false,
    getDisplayedLinearActionPlanItems: () => [{ symbol: 'BRK/B', manual_trigger_price: 80 }],
    renderActionPlanDetail: () => {}, renderSelectedActionPlanDetail: () => {},
    renderManualTriggerDetail: (_symbol, trigger) => { if (trigger) loaded.push(trigger.buy_trigger_price); },
    loadActionPlan: async () => true,
    manualTriggerEditorValues: () => ({ buy_trigger_price: context.selectedPortfolioAccountId === 'U_ACCOUNT_A' ? '80' : '90',
      sell_trigger_price: '', sell_trigger_direction: 'at_or_above', reserve_enabled: false, reserve_percentage: '0' }),
    withSelectedPortfolioAccount: (url) => withPortfolioAccount(url, context.selectedPortfolioAccountId),
    fetch: async (url, options = {}) => {
      requests.push({ url, method: options.method || 'GET', body: options.body });
      if (url.includes('/api/manual-execution-triggers/') && options.method !== 'DELETE' && options.method !== 'PUT')
        return { ok: true, json: async () => ({ trigger: { buy_trigger_price: new URL(url, 'http://local').searchParams.get('account_id') === 'U_ACCOUNT_A' ? 80 : 90 } }) };
      if (url.includes('/api/manual-execution-quotes/refresh'))
        return { ok: true, json: async () => ({ results: [{ symbol: 'BRK/B', status: 'verified' }] }) };
      return { ok: true, json: async () => ({ action_detail: { symbol: 'BRK/B' }, trigger: {} }) };
    },
  };
  const functions = ['openActionPlanDetail', 'validateManualTriggerForm', 'saveManualTrigger', 'clearManualTrigger', 'refreshTriggerPrices'];
  vm.runInNewContext(functions.map(functionSource).join('\n'), context);
  await context.openActionPlanDetail('BRK/B');
  await context.saveManualTrigger('BRK/B');
  await context.clearManualTrigger('BRK/B');
  await context.refreshTriggerPrices(['BRK/B']);
  context.selectedPortfolioAccountId = 'U_ACCOUNT_B';
  await context.openActionPlanDetail('BRK/B');
  await context.saveManualTrigger('BRK/B');
  await context.clearManualTrigger('BRK/B');
  await context.refreshTriggerPrices(['BRK/B']);
  for (const account of ['U_ACCOUNT_A', 'U_ACCOUNT_B']) {
    const accountRequests = requests.filter(({ url }) => new URL(url, 'http://local').searchParams.get('account_id') === account);
    assert.deepEqual(accountRequests.filter(({ url }) => url.includes('/api/manual-execution-triggers/')).map(({ method }) => method), ['GET', 'PUT', 'DELETE', 'GET', 'PUT', 'DELETE'].slice(account === 'U_ACCOUNT_A' ? 0 : 3, account === 'U_ACCOUNT_A' ? 3 : 6));
    assert.ok(accountRequests.some(({ url }) => url.includes('/api/manual-execution-quotes/refresh')));
    assert.ok(accountRequests.some(({ url }) => url.includes('/api/manual-execution-triggers/BRK%2FB')));
  }
  assert.deepEqual(loaded, [80, 90]);
  assert.deepEqual(requests.filter(({ method }) => method === 'PUT').map(({ body }) => JSON.parse(body).buy_trigger_price), [80, 90]);
  assert.equal(requests.length, 10);
});

function expiringPlanFixture() {
  const expiresAt = new Date(Date.now() + 1000).toISOString();
  const old = {
    linear_action_plan: [{ symbol: 'SELL' }, { symbol: 'BUY' }],
    manual_execution: {
      summary: { dynamic_reserve_pct: 10, target_reserve_amount: 1000, executable_sell_trim_proceeds: 10000,
        available_buy_budget: 10000, funded_add_amount: 10000, fulfilled_reservations: 3000 },
      linear_action_plan: [
        { symbol: 'SELL', recommended_action: 'Sell', action: 'Sell', manual_trigger_status: 'eligible',
          manual_verified_quote_expires_at: expiresAt, executable_action_amount: 10000, suggested_share_count: 100 },
        { symbol: 'BUY', recommended_action: 'Add', action: 'Add', manual_trigger_status: 'eligible',
          manual_verified_quote_expires_at: expiresAt, executable_action_amount: 10000, suggested_share_count: 100,
          requested_reservation: 3000, fulfilled_reservation: 3000, fulfilled_reservation_from_projected_proceeds: 3000 },
      ],
    },
  };
  const fresh = {
    ...old,
    manual_execution: {
      summary: { ...old.manual_execution.summary, executable_sell_trim_proceeds: 0, available_buy_budget: 0,
        funded_add_amount: 0, fulfilled_reservations: 0 },
      linear_action_plan: old.manual_execution.linear_action_plan.map((item) => ({ ...item,
        manual_trigger_status: 'price_confirmation_required', executable_action_amount: 0,
        suggested_share_count: 0, fulfilled_reservation: 0, fulfilled_reservation_from_projected_proceeds: 0 })),
    },
  };
  return { expiresAt, old, fresh };
}

function expiryHarness(old, fetch) {
  const scheduled = [];
  const requests = [];
  const explanation = { innerHTML: '' };
  const editor = { value: 'unsaved 42' };
  let now = Date.now();
  const context = {
    Date: class extends Date { static now() { return now; } },
    setTimeout: (callback, delay) => { const timer = { callback, delay }; scheduled.push(timer); return timer; },
    clearTimeout: () => {},
    manualQuoteExpiryTimer: null, manualExecutionCalculationState: 'current', actionPlanPendingRequest: null,
    latestActionPlanPayload: old, latestActionPlanDetailPayload: { action_detail: { symbol: 'BUY', action: 'Add', rating: 'Buy' } },
    selectedActionPlanDetail: { symbol: 'BUY' }, actionPlanExecutionMode: 'with',
    selectedPortfolioAccountId: 'U_ACCOUNT_A', actionPlanRequestId: 0, actionPlanDetailRequestId: 0,
    actionPlanLinearActionsTableBody: {}, actionPlanSummaryEl: { innerHTML: '' },
    actionPlanStatusEl: { textContent: '', className: '' }, actionPlanDetailStatusEl: { textContent: '', className: '' },
    actionPlanDetailViewEl: { classList: { contains: () => false } },
    manualTriggerDetailEl: { querySelector: (selector) => selector === '#manual-execution-explanation' ? explanation : editor },
    isPortfolioAccountSelectionRequired: () => false, showActionPlanList: () => {},
    renderLinearAllocationRows: () => {}, renderActionPlanDetail: (item) => { context.selectedActionPlanDetail = item; },
    renderActionPlanMetricList: (items) => items.map(([label, value]) => `${label}: ${value}`).join('|'),
    renderActionPlanSummaryCards: () => '',
    escapeHtml: String, formatPercent: (value) => `${value}%`, formatNumber: (value) => String(value ?? 0),
    formatCurrencyValue: (value) => `$${Number(value || 0).toFixed(2)}`,
    isPortfolioAccountBlockingError: () => false,
    createPortfolioApiError: (_payload, message) => new Error(message),
    withSelectedPortfolioAccount: (url) => withPortfolioAccount(url, context.selectedPortfolioAccountId),
    fetch: async (url) => { requests.push(url); return fetch(url); },
  };
  const names = ['getDisplayedLinearActionPlanItems', 'manualQuoteExpired', 'getManualTriggerPresentation',
    'manualTriggerLabel', 'renderManualReservationSummary', 'renderManualPlanSummary', 'renderActionPlan',
    'renderSelectedActionPlanDetail', 'loadActionPlan', 'refreshOpenActionPlanDetailAfterExpiry',
    'handleManualQuoteExpiry', 'refreshActionPlanFromButton'];
  vm.runInNewContext(names.map(functionSource).join('\n'), context);
  return { context, scheduled, requests, explanation, editor, advanceTo: (value) => { now = value; } };
}

test('one expired Sell quote recalculates all Buy funding without refreshing TWS or replacing an open editor', async () => {
  const { expiresAt, old, fresh } = expiringPlanFixture();
  const h = expiryHarness(old, async (url) => ({ ok: true, json: async () => url.includes('/api/action-plan/BUY')
    ? { action_detail: { symbol: 'BUY', action: 'Add', rating: 'Buy' } } : fresh }));
  h.context.renderActionPlan();
  assert.equal(h.scheduled.length, 1);
  h.advanceTo(Date.parse(expiresAt) + 1);
  const first = h.scheduled[0].callback();
  const duplicate = h.scheduled[0].callback();
  assert.match(h.context.actionPlanSummaryEl.innerHTML, /Recalculating/);
  assert.doesNotMatch(h.context.actionPlanSummaryEl.innerHTML, /\$10000\.00/);
  assert.doesNotMatch(h.explanation.innerHTML, /\$10000\.00|\$3000\.00/);
  await Promise.all([first, duplicate]);
  assert.equal(h.context.manualExecutionCalculationState, 'current');
  assert.equal(h.context.latestActionPlanPayload.manual_execution.summary.executable_sell_trim_proceeds, 0);
  assert.equal(h.editor.value, 'unsaved 42');
  assert.equal(h.context.actionPlanExecutionMode, 'with');
  assert.deepEqual(h.requests.map((url) => new URL(url, 'http://local').pathname), ['/api/action-plan', '/api/action-plan/BUY']);
  assert.ok(h.requests.every((url) => new URL(url, 'http://local').searchParams.get('account_id') === 'U_ACCOUNT_A'));
  assert.doesNotMatch(h.requests.join(' '), /manual-execution-quotes|tws/i);
});

test('failed expiry recalculation hides stale funding and manual refresh retries without losing detail', async () => {
  const { expiresAt, old, fresh } = expiringPlanFixture();
  let attempts = 0;
  const h = expiryHarness(old, async (url) => {
    if (url.includes('/api/action-plan/BUY')) return { ok: true, json: async () => ({ action_detail: { symbol: 'BUY', rating: 'Buy' } }) };
    attempts += 1;
    return attempts === 1 ? { ok: false, json: async () => ({ error: 'temporary' }) }
      : { ok: true, json: async () => fresh };
  });
  h.context.renderActionPlan();
  h.advanceTo(Date.parse(expiresAt) + 1);
  await h.scheduled[0].callback();
  assert.equal(h.context.manualExecutionCalculationState, 'outdated');
  assert.match(h.context.actionPlanSummaryEl.innerHTML, /outdated/i);
  assert.doesNotMatch(h.context.actionPlanSummaryEl.innerHTML, /\$10000\.00|\$3000\.00/);
  assert.match(h.explanation.innerHTML, /Outdated; refresh Action Plan/);
  assert.match(h.explanation.innerHTML, /trigger price expired and the Action Plan could not be recalculated/i);
  assert.doesNotMatch(h.explanation.innerHTML, /\$10000\.00|\$3000\.00/);
  assert.equal(h.editor.value, 'unsaved 42');
  assert.equal(h.scheduled.length, 1);
  await h.context.refreshActionPlanFromButton();
  assert.equal(h.context.manualExecutionCalculationState, 'current');
  assert.equal(h.context.latestActionPlanPayload.manual_execution.summary.executable_sell_trim_proceeds, 0);
  assert.equal(attempts, 2);
  assert.equal(h.editor.value, 'unsaved 42');
  assert.deepEqual(h.requests.map((url) => new URL(url, 'http://local').pathname),
    ['/api/action-plan', '/api/action-plan', '/api/action-plan/BUY']);
});

test('late expiry recalculation for a prior account cannot replace the new account plan or detail', async () => {
  const { expiresAt, old, fresh } = expiringPlanFixture();
  let finish;
  const h = expiryHarness(old, () => new Promise((resolve) => { finish = resolve; }));
  h.context.renderActionPlan();
  h.advanceTo(Date.parse(expiresAt) + 1);
  const pending = h.scheduled[0].callback();
  assert.equal(h.requests.length, 1);
  assert.equal(new URL(h.requests[0], 'http://local').searchParams.get('account_id'), 'U_ACCOUNT_A');
  h.context.selectedPortfolioAccountId = 'U_ACCOUNT_B';
  h.context.actionPlanRequestId += 1;
  h.context.actionPlanDetailRequestId += 1;
  h.context.latestActionPlanPayload = { linear_action_plan: [{ symbol: 'OTHER' }] };
  h.context.manualExecutionCalculationState = 'current';
  finish({ ok: true, json: async () => fresh });
  await pending;
  assert.equal(h.context.latestActionPlanPayload.linear_action_plan[0].symbol, 'OTHER');
  assert.equal(h.context.manualExecutionCalculationState, 'current');
  assert.equal(h.requests.length, 1);
});

test('quote expiry recalculates while Without Triggers is selected and preserves that mode', async () => {
  const { expiresAt, old, fresh } = expiringPlanFixture();
  const h = expiryHarness(old, async () => ({ ok: true, json: async () => fresh }));
  h.context.actionPlanExecutionMode = 'without';
  h.context.actionPlanDetailViewEl.classList.contains = () => true;
  h.context.renderActionPlan();
  assert.equal(h.scheduled.length, 1);
  h.advanceTo(Date.parse(expiresAt) + 1);
  await h.scheduled[0].callback();
  assert.equal(h.context.actionPlanExecutionMode, 'without');
  assert.equal(h.context.latestActionPlanPayload.manual_execution.summary.executable_sell_trim_proceeds, 0);
  assert.deepEqual(h.requests.map((url) => new URL(url, 'http://local').pathname), ['/api/action-plan']);
});

test('late expiry detail response cannot overwrite a newly opened symbol', async () => {
  const { expiresAt, old, fresh } = expiringPlanFixture();
  let finishDetail;
  let detailStarted;
  const started = new Promise((resolve) => { detailStarted = resolve; });
  const h = expiryHarness(old, (url) => url.includes('/api/action-plan/BUY')
    ? new Promise((resolve) => { finishDetail = resolve; detailStarted(); })
    : Promise.resolve({ ok: true, json: async () => fresh }));
  h.context.renderActionPlan();
  h.advanceTo(Date.parse(expiresAt) + 1);
  const pending = h.scheduled[0].callback();
  await started;
  h.context.actionPlanDetailRequestId += 1;
  h.context.selectedActionPlanDetail = { symbol: 'OTHER' };
  h.context.latestActionPlanDetailPayload = { action_detail: { symbol: 'OTHER' } };
  finishDetail({ ok: true, json: async () => ({ action_detail: { symbol: 'BUY' } }) });
  await pending;
  assert.equal(h.context.latestActionPlanDetailPayload.action_detail.symbol, 'OTHER');
  assert.equal(h.context.selectedActionPlanDetail.symbol, 'OTHER');
});

test('an older detail reload for the same symbol cannot replace a newer Action Plan reload', async () => {
  const { old } = expiringPlanFixture();
  const finish = [];
  const h = expiryHarness(old, () => new Promise((resolve) => { finish.push(resolve); }));
  h.context.actionPlanRequestId = 1;
  const first = h.context.refreshOpenActionPlanDetailAfterExpiry('U_ACCOUNT_A', 'BUY', 0);
  h.context.actionPlanRequestId = 2;
  const second = h.context.refreshOpenActionPlanDetailAfterExpiry('U_ACCOUNT_A', 'BUY', 0);
  finish[1]({ ok: true, json: async () => ({ action_detail: { symbol: 'BUY', rating: 'New' } }) });
  await second;
  finish[0]({ ok: true, json: async () => ({ action_detail: { symbol: 'BUY', rating: 'Old' } }) });
  await first;
  assert.equal(h.context.latestActionPlanDetailPayload.action_detail.rating, 'New');
});

test('a cleared expiry timer callback cannot reload a different account plan', async () => {
  const { expiresAt, old, fresh } = expiringPlanFixture();
  const h = expiryHarness(old, async () => ({ ok: true, json: async () => fresh }));
  h.context.renderActionPlan();
  h.advanceTo(Date.parse(expiresAt) + 1);
  h.context.selectedPortfolioAccountId = 'U_ACCOUNT_B';
  h.context.actionPlanRequestId += 1;
  await h.scheduled[0].callback();
  assert.equal(h.requests.length, 0);
});

test('a quote expiring during an ordinary Action Plan request still gets a fresh recalculation', async () => {
  const { expiresAt, old, fresh } = expiringPlanFixture();
  let finishFirst;
  let calls = 0;
  const h = expiryHarness(old, (url) => {
    if (url.includes('/api/action-plan/BUY')) return Promise.resolve({ ok: true, json: async () => ({ action_detail: { symbol: 'BUY' } }) });
    calls += 1;
    return calls === 1 ? new Promise((resolve) => { finishFirst = resolve; })
      : Promise.resolve({ ok: true, json: async () => fresh });
  });
  h.context.renderActionPlan();
  const pending = h.context.loadActionPlan({ preserveDetail: true });
  h.advanceTo(Date.parse(expiresAt) + 1);
  await h.scheduled[0].callback();
  assert.equal(h.context.manualExecutionCalculationState, 'recalculating');
  assert.doesNotMatch(h.context.actionPlanSummaryEl.innerHTML, /\$10000\.00/);
  assert.equal(calls, 1);
  finishFirst({ ok: true, json: async () => old });
  await pending;
  assert.equal(calls, 2);
  assert.equal(h.context.latestActionPlanPayload.manual_execution.summary.executable_sell_trim_proceeds, 0);
  assert.equal(h.context.manualExecutionCalculationState, 'current');
});

test('a mode re-render during a pending reload does not issue a second request at expiry', async () => {
  const { expiresAt, old, fresh } = expiringPlanFixture();
  let finishFirst;
  let calls = 0;
  const h = expiryHarness(old, (url) => {
    if (url.includes('/api/action-plan/BUY')) return Promise.resolve({ ok: true, json: async () => ({ action_detail: { symbol: 'BUY' } }) });
    calls += 1;
    return calls === 1 ? new Promise((resolve) => { finishFirst = resolve; })
      : Promise.resolve({ ok: true, json: async () => fresh });
  });
  h.context.renderActionPlan();
  const pending = h.context.loadActionPlan({ preserveDetail: true });
  h.context.renderActionPlan();
  h.advanceTo(Date.parse(expiresAt) + 1);
  await h.scheduled[0].callback();
  await h.scheduled[1].callback();
  assert.equal(calls, 1);
  assert.equal(h.context.manualExecutionCalculationState, 'recalculating');
  finishFirst({ ok: true, json: async () => old });
  await pending;
  assert.equal(calls, 2);
  assert.equal(h.context.latestActionPlanPayload.manual_execution.summary.executable_sell_trim_proceeds, 0);
});

test('manual allocation rows mask stale execution figures and then render backend recalculation', () => {
  const { old, fresh } = expiringPlanFixture();
  const rows = [];
  const body = { innerHTML: '', appendChild: (row) => rows.push(row), querySelectorAll: () => [] };
  const table = { classList: { toggle: () => {} }, querySelectorAll: () => [], querySelector: () => ({ textContent: '' }) };
  const makeRow = () => {
    const fields = Object.fromEntries(['.action-amount-cell', '.shares-cell', '.funding-cell'].map((key) => [key, { textContent: '' }]));
    const manualCells = Array.from({ length: 5 }, () => ({ textContent: '' }));
    return { innerHTML: '', cells: Array.from({ length: 21 }, () => ({ textContent: '' })),
      querySelector: (selector) => fields[selector] || null,
      querySelectorAll: (selector) => selector === '.manual-only' ? manualCells : [], fields, manualCells };
  };
  const context = {
    latestActionPlanPayload: old, actionPlanExecutionMode: 'with', manualExecutionCalculationState: 'outdated',
    actionPlanLinearActionsTableBody: body, actionPlanLinearDetailTableBody: null,
    document: { getElementById: () => table, createElement: makeRow },
    window: { ActionPlanSorting: { getLinearCagrValue: () => 0 } },
    getDisplayedLinearActionPlanItems: (payload) => payload.manual_execution.linear_action_plan,
    getFilteredLinearActionPlanItems: () => context.latestActionPlanPayload.manual_execution.linear_action_plan,
    sortLinearActionPlanItems: (items) => items,
    getActionPlanPriceDisplay: () => ({ price: '$100.00', title: 'price', warning: false }),
    getManualTriggerPresentation: () => ({ status: 'Eligible, funded', tone: 'success' }),
    manualTriggerLabel: () => 'trigger', formatCurrencyValue: (value) => `$${Number(value || 0).toFixed(2)}`,
    formatPercent: (value) => `${value ?? 0}%`, formatNumber: (value) => String(value ?? 0),
    formatLinearReleaseDate: () => '', renderLinearReleaseDateWarning: () => '',
    formatLinearCagrPercent: () => '', formatConfidenceDiffDisplay: () => '', formatLinearMomentum: () => '',
    formatSuggestedShareCount: (item) => String(item.suggested_share_count ?? 0),
    valueClass: () => '', escapeHtml: String, manualQuoteExpired: () => false,
    hasLinearTargetCap: () => false,
  };
  vm.runInNewContext(functionSource('renderLinearAllocationRows'), context);
  context.renderLinearAllocationRows();
  assert.equal(rows.length, 2);
  for (const row of rows) {
    assert.equal(row.fields['.shares-cell'].textContent, 'Outdated');
    assert.equal(row.fields['.funding-cell'].textContent, 'Outdated');
    assert.equal(row.manualCells[3].textContent, 'Outdated');
    assert.equal(row.manualCells[4].textContent, 'Outdated');
  }
  rows.length = 0;
  context.latestActionPlanPayload = fresh;
  context.manualExecutionCalculationState = 'current';
  context.renderLinearAllocationRows();
  assert.equal(rows.length, 2);
  assert.ok(rows.every((row) => !row.innerHTML.includes('$10000.00')));
  assert.ok(rows.every((row) => row.innerHTML.includes('$0.00')));
});

test('clearing an account plan cancels its expiry timer and invalidates pending responses', () => {
  const timer = {};
  let cleared;
  const context = {
    actionPlanRequestId: 3, actionPlanDetailRequestId: 5, actionPlanQuoteRequestId: 7,
    manualQuoteExpiryTimer: timer, manualExecutionCalculationState: 'outdated', actionPlanPendingRequest: { id: 3, account: 'U_ACCOUNT_A' },
    clearTimeout: (value) => { cleared = value; }, showActionPlanList: () => {},
    actionPlanSummaryEl: { innerHTML: 'old' }, actionPlanLinearActionsTableBody: { innerHTML: 'old' },
    actionPlanDetailContentEl: { innerHTML: 'old' }, manualTriggerDetailEl: { innerHTML: 'dirty' },
    actionPlanQuoteStatusEl: { textContent: 'old' }, actionPlanRefreshTriggerPricesBtn: { disabled: true },
    actionPlanStatusEl: { textContent: '', className: '' },
  };
  vm.runInNewContext(`${functionSource('clearActionPlanDisplay')}\nclearActionPlanDisplay('Select account')`, context);
  assert.equal(cleared, timer);
  assert.equal(context.manualQuoteExpiryTimer, null);
  assert.equal(context.manualExecutionCalculationState, 'current');
  assert.equal(context.actionPlanPendingRequest, null);
  assert.deepEqual([context.actionPlanRequestId, context.actionPlanDetailRequestId, context.actionPlanQuoteRequestId], [4, 6, 8]);
  assert.equal(context.actionPlanStatusEl.textContent, 'Select account');
});
