const assert = require('node:assert/strict');
const fs = require('node:fs');
const test = require('node:test');
const vm = require('node:vm');

const { createController } = require('./static/navigation_history.js');

const appSource = fs.readFileSync('static/app.js', 'utf8');

function functionSource(name, required = true) {
  const marker = `function ${name}(`;
  const start = appSource.indexOf(marker);
  if (start === -1) {
    if (!required) return '';
    assert.fail(`${name} exists`);
  }
  const declarationStart = appSource.slice(start - 6, start) === 'async ' ? start - 6 : start;
  const opening = appSource.indexOf('{', appSource.indexOf(')', start));
  let depth = 0;
  for (let index = opening; index < appSource.length; index += 1) {
    if (appSource[index] === '{') depth += 1;
    if (appSource[index] === '}') depth -= 1;
    if (depth === 0) return appSource.slice(declarationStart, index + 1);
  }
  throw new Error(`${name} is incomplete`);
}

function deferredResponse(payload = {}) {
  let resolve;
  const promise = new Promise((finish) => { resolve = finish; });
  return {
    fetch: () => promise,
    succeed(nextPayload = payload) { resolve({ ok: true, json: async () => nextPayload }); },
    fail(message = 'request failed') { resolve({ ok: false, json: async () => ({ error: message }) }); },
  };
}

function fakeElement(overrides = {}) {
  return {
    textContent: '', className: '', disabled: false, value: '', files: [],
    ...overrides,
  };
}

class MemoryHistory {
  constructor(entries = [{ state: null }], index = entries.length - 1) {
    this.entries = entries.map(({ state }) => ({ state: state ?? null }));
    this.index = index;
    this.pushCount = 0;
    this.replaceCount = 0;
    this.listeners = new Set();
  }

  get state() { return this.entries[this.index]?.state ?? null; }
  get length() { return this.entries.length; }
  addEventListener(type, listener) { if (type === 'popstate') this.listeners.add(listener); }
  pushState(state) {
    this.entries.splice(this.index + 1, Infinity, { state });
    this.index += 1;
    this.pushCount += 1;
  }
  replaceState(state) {
    this.entries[this.index] = { state };
    this.replaceCount += 1;
  }
  go(delta) {
    const next = this.index + delta;
    if (next < 0 || next >= this.entries.length || next === this.index) return;
    this.index = next;
    const event = { state: this.state };
    queueMicrotask(() => this.listeners.forEach((listener) => listener(event)));
  }
  back() { this.go(-1); }
  forward() { this.go(1); }
}

function entry(sequence, screen) {
  return { state: { bakingMoneyNavigation: 1, sequence, screen } };
}

async function settle() {
  for (let index = 0; index < 8; index += 1) await new Promise((resolve) => setImmediate(resolve));
}

async function controllerAt(screen, priorScreens = [], futureScreens = []) {
  const screens = [...priorScreens, screen, ...futureScreens];
  const history = new MemoryHistory(
    screens.map((item, index) => entry(index, item)),
    priorScreens.length,
  );
  const controller = createController({
    history,
    eventTarget: history,
    render: async () => true,
  });
  await controller.initialize();
  return { controller, history };
}

test('captured controller context is invalidated by nested, Back, and away-then-back navigation', async () => {
  const detailA = { view: 'earnings-review', detail: { kind: 'earnings-review', symbol: 'AAA', reviewId: 1 } };
  const detailB = { view: 'earnings-review', detail: { kind: 'earnings-review', symbol: 'AAA', reviewId: 2 } };
  const { controller, history } = await controllerAt(detailA, [{ view: 'earnings-review' }]);
  const original = controller.captureContext();
  assert.equal(controller.isCurrentContext(original), true);

  await controller.navigate(detailB);
  assert.equal(controller.isCurrentContext(original), false, 'a different detail invalidates the context');

  history.back();
  await settle();
  assert.deepEqual(controller.currentScreen(), detailA);
  assert.equal(controller.isCurrentContext(original), false, 'returning to the same record is a newer context');
});

function accountChangeHarness({ screen, priorScreens = [], futureScreens = [] }) {
  const reloads = [];
  const context = vm.createContext({
    isUpdatingPortfolioAccountSelect: false,
    simulatorActive: false,
    selectedPortfolioAccountId: 'account-1',
    portfolioAccountChangeRequestId: 0,
    portfolioAccountSelectEl: { value: 'account-2' },
    selectedSimulation: null,
    analysisOwnershipRequestId: 0,
    normalizePortfolioAccountId: (value) => value || null,
    discardSimulationEdits: () => true,
    rememberPlanPreferences() {},
    clearSimulationContext() {},
    resetActionPlanExecutionMode() {},
    localStorage: { setItem() {}, removeItem() {} },
    PORTFOLIO_ACCOUNT_STORAGE_KEY: 'account',
    renderPortfolioAccountSelector() {},
    invalidateAnalysisOwnershipState() {},
    clearPositionsDisplay() {},
    clearActionPlanDisplay() {},
    reloadPortfolioScopedViews() {
      let resolve;
      const promise = new Promise((finish) => { resolve = finish; });
      reloads.push(resolve);
      return promise;
    },
  });
  return controllerAt(screen, priorScreens, futureScreens).then(({ controller, history }) => {
    context.browserNavigationController = controller;
    vm.runInContext(`${functionSource('handlePortfolioAccountChange')}; this.changeAccount = handlePortfolioAccountChange;`, context);
    return { context, controller, history, reloads };
  });
}

test('account switch from Action Detail synchronizes the same entry to its list', async () => {
  const detail = { view: 'action-plan', detail: { kind: 'action', symbol: 'AAA' } };
  const h = await accountChangeHarness({ screen: detail });
  const length = h.history.length;
  const pending = h.context.changeAccount();
  h.reloads[0]();
  await pending;
  assert.deepEqual(h.controller.currentScreen(), { view: 'action-plan' });
  assert.deepEqual(h.history.state.screen, { view: 'action-plan' });
  assert.equal(h.history.length, length);
});

test('account switch completion cannot replace later Analysis navigation', async () => {
  const detail = { view: 'action-plan', detail: { kind: 'action', symbol: 'AAA' } };
  const h = await accountChangeHarness({ screen: detail });
  const pending = h.context.changeAccount();
  await h.controller.navigate({ view: 'analysis' });
  h.reloads[0]();
  await pending;
  assert.deepEqual(h.controller.currentScreen(), { view: 'analysis' });
  assert.deepEqual(h.history.state.screen, { view: 'analysis' });
});

test('account switch completion cannot replace a later Action Detail', async () => {
  const detail = { view: 'action-plan', detail: { kind: 'action', symbol: 'AAA' } };
  const h = await accountChangeHarness({ screen: detail });
  const pending = h.context.changeAccount();
  const newer = { view: 'action-plan', detail: { kind: 'action', symbol: 'BBB' } };
  await h.controller.navigate(newer);
  h.reloads[0]();
  await pending;
  assert.deepEqual(h.controller.currentScreen(), newer);
  assert.deepEqual(h.history.state.screen, newer);
});

test('account switch completion cannot replace browser Back while reload is pending', async () => {
  const detail = { view: 'action-plan', detail: { kind: 'action', symbol: 'AAA' } };
  const h = await accountChangeHarness({ screen: detail, priorScreens: [{ view: 'positions' }] });
  const pending = h.context.changeAccount();
  h.history.back();
  await settle();
  h.reloads[0]();
  await pending;
  assert.deepEqual(h.controller.currentScreen(), { view: 'positions' });
  assert.deepEqual(h.history.state.screen, { view: 'positions' });
});

test('account switch completion cannot replace browser Forward while reload is pending', async () => {
  const detail = { view: 'action-plan', detail: { kind: 'action', symbol: 'AAA' } };
  const h = await accountChangeHarness({ screen: detail, futureScreens: [{ view: 'backup' }] });
  const pending = h.context.changeAccount();
  h.history.forward();
  await settle();
  h.reloads[0]();
  await pending;
  assert.deepEqual(h.controller.currentScreen(), { view: 'backup' });
  assert.deepEqual(h.history.state.screen, { view: 'backup' });
});

test('only the latest rapid account switch may synchronize navigation and owns the final account', async () => {
  const detail = { view: 'action-plan', detail: { kind: 'action', symbol: 'AAA' } };
  const h = await accountChangeHarness({ screen: detail });
  const first = h.context.changeAccount();
  h.context.portfolioAccountSelectEl.value = 'account-3';
  const second = h.context.changeAccount();

  h.reloads[0]();
  await first;
  assert.deepEqual(h.controller.currentScreen(), detail, 'older completion is ignored');
  assert.equal(h.context.selectedPortfolioAccountId, 'account-3');

  h.reloads[1]();
  await second;
  assert.deepEqual(h.controller.currentScreen(), { view: 'action-plan' });
  assert.equal(h.context.selectedPortfolioAccountId, 'account-3');
  assert.equal(h.history.pushCount, 0);
});

function installEarningsOperation(context, name) {
  const helpers = [
    'captureEarningsReviewScreenContext',
    'earningsReviewScreenContextIsCurrent',
    'captureEarningsReviewOperationContext',
    'earningsReviewOperationContextIsCurrent',
    'refreshEarningsReviewOperationContext',
  ].map((helper) => functionSource(helper, false)).join('\n');
  vm.runInContext(`${helpers}\n${functionSource(name)}; this.operation = ${name};`, context);
}

test('fresh Earnings screens reset controls disabled by an operation on the previous screen', async () => {
  const detailRequest = deferredResponse({ item: {
    symbol: 'BBB', fiscal_year: 2026, fiscal_quarter: 'Q4', documents: [],
    key_variables_snapshot: [], watchpoints_by_variable: [], watchpoint_results: [],
  } });
  const detailContext = vm.createContext({
    navigationRenderGeneration: 1,
    earningsReviewSelectedSymbol: null,
    earningsReviewSelectedRecordId: null,
    earningsReviewDetailTitleEl: fakeElement(), earningsReviewDetailHeaderEl: fakeElement(),
    earningsReviewDetailMetaEl: fakeElement(), earningsReviewGenerateBtn: fakeElement(),
    earningsReviewAnalyseBtn: fakeElement(), earningsReviewKeyVariablesBody: fakeElement(),
    earningsReviewWatchpointsEl: fakeElement(), earningsReviewSnapshotSummaryEl: fakeElement(),
    earningsReviewDocumentsTableBody: fakeElement(), earningsReviewDocumentsStatusEl: fakeElement(),
    earningsReviewDocumentFileEl: fakeElement(), earningsReviewDocumentFileNameEl: fakeElement(),
    earningsReviewDocumentUploadBtn: fakeElement({ disabled: true }),
    setEarningsReviewTab() {}, showEarningsReviewDetail() {}, fetch: detailRequest.fetch,
    extractErrorMessage: () => 'error', formatDate: String, formatDateTime: String,
    renderEarningsSnapshotSummary() {}, renderEarningsKeyVariables() {},
    renderEarningsWatchpoints() {}, renderEarningsReviewDocuments() {},
  });
  vm.runInContext(`${functionSource('navigationRequestCurrent')}; ${functionSource('openEarningsReviewRecordDetail')}; this.open = openEarningsReviewRecordDetail;`, detailContext);
  const detailPending = detailContext.open('BBB', 2, { navigationGeneration: 1 });
  assert.equal(detailContext.earningsReviewDocumentUploadBtn.disabled, true);
  detailRequest.succeed();
  await detailPending;
  assert.equal(detailContext.earningsReviewDocumentUploadBtn.disabled, false);

  const symbolRequest = deferredResponse({ item: { symbol: 'BBB', records: [] } });
  const symbolContext = vm.createContext({
    navigationRenderGeneration: 1,
    earningsReviewSelectedSymbol: null, earningsReviewSelectedRecordId: null,
    earningsReviewSymbolHistory: null, earningsReviewSymbolTitleEl: fakeElement(),
    earningsReviewSymbolHeaderEl: fakeElement(), earningsReviewSymbolStatusEl: fakeElement(),
    earningsReviewSymbolTableBody: fakeElement(), earningsReviewCreateSubmitBtn: fakeElement({ disabled: true }),
    setEarningsReviewTab() {}, showEarningsReviewSymbolHistoryView() {}, fetch: symbolRequest.fetch,
    extractErrorMessage: () => 'error', renderEarningsReviewSymbolHistoryTable() {},
  });
  vm.runInContext(`${functionSource('navigationRequestCurrent')}; ${functionSource('openEarningsReviewSymbolHistory')}; this.open = openEarningsReviewSymbolHistory;`, symbolContext);
  const symbolPending = symbolContext.open('BBB', { navigationGeneration: 1 });
  assert.equal(symbolContext.earningsReviewCreateSubmitBtn.disabled, false);
  symbolRequest.succeed();
  await symbolPending;
});

test('newer same-record follow-up refresh wins when secondary responses resolve out of order', async () => {
  const detail = { view: 'earnings-review', detail: { kind: 'earnings-review', symbol: 'AAA', reviewId: 1 } };
  const { controller } = await controllerAt(detail);
  const refreshes = [];
  const rendered = { list: null, detail: null };
  const context = vm.createContext({
    browserNavigationController: controller,
    navigationRenderGeneration: 30,
    earningsReviewRefreshRequestId: 0,
    earningsReviewSelectedSymbol: 'AAA',
    earningsReviewSelectedRecordId: 1,
    refreshEarningsReviewListOnly(options) {
      let resolve;
      const promise = new Promise((finish) => { resolve = finish; });
      refreshes.push({
        resolve(value) {
          if (!options?.requestCurrent || options.requestCurrent()) rendered.list = value;
          resolve();
        },
      });
      return promise;
    },
    openEarningsReviewRecordDetail(_symbol, _reviewId, options) {
      if (!options?.requestCurrent || options.requestCurrent()) rendered.detail = rendered.list;
      return true;
    },
  });
  const helpers = [
    'captureEarningsReviewScreenContext', 'earningsReviewScreenContextIsCurrent',
    'captureEarningsReviewOperationContext', 'earningsReviewOperationContextIsCurrent',
    'refreshEarningsReviewOperationContext',
  ].map((name) => functionSource(name)).join('\n');
  vm.runInContext(`${helpers}; this.capture = captureEarningsReviewOperationContext; this.refresh = refreshEarningsReviewOperationContext;`, context);
  const operationContext = context.capture('AAA', 1);
  const older = context.refresh(operationContext);
  const newer = context.refresh(operationContext);
  refreshes[1].resolve('newer');
  await newer;
  refreshes[0].resolve('older');
  await older;
  assert.deepEqual(rendered, { list: 'newer', detail: 'newer' });
});

async function earningsRecordMutationHarness(name) {
  const symbolScreen = { view: 'earnings-review', detail: { kind: 'earnings-symbol', symbol: 'AAA' } };
  const { controller } = await controllerAt(symbolScreen);
  const request = deferredResponse();
  const navigations = [];
  const context = vm.createContext({
    browserNavigationController: controller,
    navigationRenderGeneration: 20,
    earningsReviewSelectedSymbol: 'AAA',
    earningsReviewCreateYearEl: fakeElement({ value: '2026' }),
    earningsReviewCreateQuarterEl: fakeElement({ value: 'Q4' }),
    earningsReviewCreateReleaseDateEl: fakeElement(),
    earningsReviewSymbolStatusEl: fakeElement(),
    earningsReviewCreateSubmitBtn: fakeElement(),
    window: { confirm: () => true },
    fetch: request.fetch,
    extractErrorMessage: (payload, fallback) => payload?.error || fallback,
    toggleEarningsReviewCreateForm() {},
    async navigateToScreen(screen) { navigations.push(['to', screen]); },
    async navigateBack(screen) { navigations.push(['back', screen]); },
  });
  const helpers = [
    'captureEarningsReviewScreenContext',
    'earningsReviewScreenContextIsCurrent',
  ].map((helper) => functionSource(helper, false)).join('\n');
  vm.runInContext(`${helpers}\n${functionSource(name)}; this.operation = ${name};`, context);
  return {
    context, controller, request, navigations,
    async navigateAway() {
      await controller.navigate({ view: 'analysis' });
      context.navigationRenderGeneration += 1;
      context.earningsReviewSelectedSymbol = null;
    },
  };
}

test('completed record creation cannot redirect after leaving its symbol history', async () => {
  const h = await earningsRecordMutationHarness('createEarningsReviewRecord');
  const pending = h.context.operation();
  await h.navigateAway();
  h.context.earningsReviewSymbolStatusEl.textContent = 'Analysis status';
  h.request.succeed({ item: { id: 7 } });
  await pending;
  assert.deepEqual(h.navigations, []);
  assert.equal(h.context.earningsReviewSymbolStatusEl.textContent, 'Analysis status');
});

test('completed record deletion cannot navigate Back after leaving its symbol history', async () => {
  const h = await earningsRecordMutationHarness('deleteEarningsReviewRecord');
  const pending = h.context.operation({ reviewId: 7, fiscalYear: 2026, fiscalQuarter: 'Q4' });
  await h.navigateAway();
  h.context.earningsReviewSymbolStatusEl.textContent = 'Analysis status';
  h.request.succeed();
  await pending;
  assert.deepEqual(h.navigations, []);
  assert.equal(h.context.earningsReviewSymbolStatusEl.textContent, 'Analysis status');
});

async function earningsHarness(name, { file = false } = {}) {
  const detailA = { view: 'earnings-review', detail: { kind: 'earnings-review', symbol: 'AAA', reviewId: 1 } };
  const { controller, history } = await controllerAt(detailA);
  const request = deferredResponse();
  const opened = [];
  let listRefreshes = 0;
  const context = vm.createContext({
    browserNavigationController: controller,
    navigationRenderGeneration: 10,
    earningsReviewRefreshRequestId: 0,
    earningsReviewSelectedSymbol: 'AAA',
    earningsReviewSelectedRecordId: 1,
    earningsReviewGenerateBtn: fakeElement(),
    earningsReviewAnalyseBtn: fakeElement(),
    earningsReviewDetailMetaEl: fakeElement(),
    earningsReviewDocumentsStatusEl: fakeElement(),
    earningsReviewDocumentFileEl: fakeElement({ files: file ? [{ name: 'report.pdf' }] : [] }),
    earningsReviewDocumentFileNameEl: fakeElement({ textContent: file ? 'report.pdf' : 'No file chosen' }),
    earningsReviewDocumentTypeEl: fakeElement({ value: 'Transcript' }),
    earningsReviewDocumentUploadBtn: fakeElement(),
    FormData: class { append() {} },
    window: { confirm: () => true },
    fetch: request.fetch,
    extractErrorMessage: (payload, fallback) => payload?.error || fallback,
    async refreshEarningsReviewListOnly() { listRefreshes += 1; },
    async openEarningsReviewRecordDetail(symbol, reviewId, options) {
      opened.push({ symbol, reviewId, options });
      context.earningsReviewSelectedSymbol = symbol;
      context.earningsReviewSelectedRecordId = reviewId;
    },
  });
  installEarningsOperation(context, name);
  return {
    context, controller, history, request, opened,
    get listRefreshes() { return listRefreshes; },
    async navigate(screen) {
      await controller.navigate(screen);
      context.navigationRenderGeneration += 1;
      context.earningsReviewSelectedSymbol = screen.detail?.symbol ?? null;
      context.earningsReviewSelectedRecordId = screen.detail?.kind === 'earnings-review' ? screen.detail.reviewId : null;
    },
  };
}

test('Generate refreshes A without adding history when its exact context remains active', async () => {
  const h = await earningsHarness('generateEarningsWatchpoints');
  const length = h.history.length;
  const pending = h.context.operation();
  h.request.succeed();
  await pending;
  assert.equal(h.listRefreshes, 1);
  assert.deepEqual(h.opened.map(({ symbol, reviewId }) => [symbol, reviewId]), [['AAA', 1]]);
  assert.equal(h.history.length, length);
  assert.deepEqual(h.controller.currentScreen(), h.history.state.screen);
});

test('Generate for A cannot reopen A after navigation to record B with the same symbol', async () => {
  const h = await earningsHarness('generateEarningsWatchpoints');
  const pending = h.context.operation();
  const detailB = { view: 'earnings-review', detail: { kind: 'earnings-review', symbol: 'AAA', reviewId: 2 } };
  await h.navigate(detailB);
  h.context.earningsReviewDetailMetaEl.textContent = 'B status';
  h.request.succeed();
  await pending;
  assert.deepEqual(h.opened, []);
  assert.equal(h.listRefreshes, 0);
  assert.equal(h.context.earningsReviewDetailMetaEl.textContent, 'B status');
  assert.deepEqual(h.controller.currentScreen(), detailB);
  assert.deepEqual(h.history.state.screen, detailB);
});

test('Analyse for A cannot update UI after navigation to another section', async () => {
  const h = await earningsHarness('analyseEarningsWatchpoints');
  const pending = h.context.operation();
  await h.navigate({ view: 'analysis' });
  h.context.earningsReviewDetailMetaEl.textContent = 'Analysis status';
  h.request.succeed();
  await pending;
  assert.deepEqual(h.opened, []);
  assert.equal(h.context.earningsReviewDetailMetaEl.textContent, 'Analysis status');
  assert.deepEqual(h.controller.currentScreen(), { view: 'analysis' });
});

test('Upload for A cannot refresh or clear document state after navigation to B', async () => {
  const h = await earningsHarness('uploadEarningsReviewDocument', { file: true });
  const pending = h.context.operation();
  const detailB = { view: 'earnings-review', detail: { kind: 'earnings-review', symbol: 'BBB', reviewId: 2 } };
  await h.navigate(detailB);
  h.context.earningsReviewDocumentsStatusEl.textContent = 'B documents';
  h.context.earningsReviewDocumentFileNameEl.textContent = 'b.pdf';
  h.request.succeed();
  await pending;
  assert.deepEqual(h.opened, []);
  assert.equal(h.listRefreshes, 0);
  assert.equal(h.context.earningsReviewDocumentsStatusEl.textContent, 'B documents');
  assert.equal(h.context.earningsReviewDocumentFileNameEl.textContent, 'b.pdf');
});

test('Delete document for A cannot refresh after navigation to another section', async () => {
  const h = await earningsHarness('deleteEarningsReviewDocument');
  const pending = h.context.operation('doc-1', 'a.pdf');
  await h.navigate({ view: 'alerts' });
  h.context.earningsReviewDocumentsStatusEl.textContent = 'Alerts status';
  h.request.succeed();
  await pending;
  assert.deepEqual(h.opened, []);
  assert.equal(h.listRefreshes, 0);
  assert.equal(h.context.earningsReviewDocumentsStatusEl.textContent, 'Alerts status');
});

test('failed Earnings operation after navigation away cannot overwrite current status or controls', async () => {
  const h = await earningsHarness('generateEarningsWatchpoints');
  const pending = h.context.operation();
  await h.navigate({ view: 'analysis' });
  h.context.earningsReviewDetailMetaEl.textContent = 'Current status';
  h.context.earningsReviewGenerateBtn.disabled = true;
  h.request.fail('old failure');
  await pending;
  assert.equal(h.context.earningsReviewDetailMetaEl.textContent, 'Current status');
  assert.equal(h.context.earningsReviewGenerateBtn.disabled, true);
});

test('away then back to A does not let an older Earnings completion overwrite the newer render', async () => {
  const h = await earningsHarness('generateEarningsWatchpoints');
  const pending = h.context.operation();
  await h.navigate({ view: 'analysis' });
  await h.navigate({ view: 'earnings-review', detail: { kind: 'earnings-review', symbol: 'AAA', reviewId: 1 } });
  h.context.earningsReviewDetailMetaEl.textContent = 'New A render';
  h.request.succeed();
  await pending;
  assert.deepEqual(h.opened, []);
  assert.equal(h.context.earningsReviewDetailMetaEl.textContent, 'New A render');
});
