const assert = require('node:assert/strict');
const fs = require('node:fs');
const test = require('node:test');
const vm = require('node:vm');

const {
  createController,
  normalizeScreen,
} = require('./static/navigation_history.js');

const appSource = fs.readFileSync('static/app.js', 'utf8');

function functionSource(name) {
  const marker = `function ${name}(`;
  const start = appSource.indexOf(marker);
  assert.notEqual(start, -1, `${name} exists`);
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

function appNavigationHarness() {
  const calls = [];
  const context = vm.createContext({
    navigationRenderGeneration: 0,
    selectedSimulation: { id: 1 },
    setView(view, options) { calls.push(['view', view, options]); return true; },
    setEarningsReviewTab(tab) { calls.push(['earnings-tab', tab]); },
    async loadEarningsReview() { calls.push(['earnings-list']); },
    async openAnalysisDetailForSymbol(symbol, options) { calls.push(['analysis-detail', symbol, options]); },
    async openActionPlanDetail(symbol, options) { calls.push(['action-detail', symbol, options]); },
    async openAlertDetail(alertId, options) { calls.push(['alert-detail', alertId, options]); },
    async openEarningsReviewSymbolHistory(symbol, options) { calls.push(['earnings-symbol', symbol, options]); },
    async openEarningsReviewRecordDetail(symbol, reviewId, options) { calls.push(['earnings-review', symbol, reviewId, options]); },
  });
  vm.runInContext(`${functionSource('renderNavigationScreen')}; this.renderNavigationScreen = renderNavigationScreen;`, context);
  return { calls, render: context.renderNavigationScreen };
}

function fakeElement() {
  return {
    textContent: '', className: '', innerHTML: '', disabled: false, value: '',
    classList: { add() {}, remove() {}, toggle() {} },
  };
}

function deferredJsonResponse(payload) {
  let finish;
  const promise = new Promise((resolve) => { finish = resolve; });
  return {
    fetch: () => promise,
    finish: () => finish({ ok: true, json: async () => payload }),
  };
}

function installNavigationAwareFunction(context, name) {
  vm.runInContext(
    `${functionSource('navigationRequestCurrent')}; ${functionSource(name)}; this.${name} = ${name};`,
    context,
  );
}

class MemoryHistory {
  constructor(entries = [{ state: null }], index = entries.length - 1) {
    this.entries = entries.map((entry) => ({ state: entry.state ?? null }));
    this.index = index;
    this.pushCount = 0;
    this.replaceCount = 0;
    this.goCalls = [];
    this.listeners = new Set();
  }

  get state() { return this.entries[this.index]?.state ?? null; }
  get length() { return this.entries.length; }

  addEventListener(type, listener) {
    if (type === 'popstate') this.listeners.add(listener);
  }

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
    this.goCalls.push(delta);
    const nextIndex = this.index + delta;
    if (nextIndex < 0 || nextIndex >= this.entries.length || nextIndex === this.index) return;
    this.index = nextIndex;
    const event = { state: this.state };
    queueMicrotask(() => this.listeners.forEach((listener) => listener(event)));
  }

  back() { this.go(-1); }
  forward() { this.go(1); }
}

function applicationEntry(sequence, screen) {
  return { state: { bakingMoneyNavigation: 1, sequence, screen } };
}

async function settle() {
  for (let index = 0; index < 8; index += 1) await new Promise((resolve) => setImmediate(resolve));
}

function harness({ entries, index, canLeave = () => true } = {}) {
  const history = new MemoryHistory(entries, index);
  const rendered = [];
  const controller = createController({
    history,
    eventTarget: history,
    render: async (screen) => { rendered.push(screen); return true; },
    canLeave,
    fallbackScreen: { view: 'analysis' },
  });
  return { history, rendered, controller };
}

test('normalizes every supported main and nested application screen', () => {
  for (const view of ['analysis', 'positions', 'action-plan', 'action-plan-simulator', 'earnings-review', 'alerts', 'prompt', 'configuration', 'backup']) {
    assert.deepEqual(normalizeScreen({ view }), { view });
  }
  assert.deepEqual(normalizeScreen({ view: 'analysis', detail: { kind: 'analysis', symbol: 'nvda' } }),
    { view: 'analysis', detail: { kind: 'analysis', symbol: 'NVDA' } });
  assert.deepEqual(normalizeScreen({ view: 'positions', detail: { kind: 'analysis', symbol: 'nvda' } }),
    { view: 'positions', detail: { kind: 'analysis', symbol: 'NVDA' } });
  assert.deepEqual(normalizeScreen({ view: 'action-plan', detail: { kind: 'action', symbol: 'msft' } }),
    { view: 'action-plan', detail: { kind: 'action', symbol: 'MSFT' } });
  assert.deepEqual(normalizeScreen({ view: 'action-plan-simulator', detail: { kind: 'analysis', symbol: 'msft' } }),
    { view: 'action-plan-simulator', detail: { kind: 'analysis', symbol: 'MSFT' } });
  assert.deepEqual(normalizeScreen({ view: 'alerts', detail: { kind: 'alert', alertId: 17 } }),
    { view: 'alerts', detail: { kind: 'alert', alertId: '17' } });
  assert.deepEqual(normalizeScreen({ view: 'earnings-review', detail: { kind: 'earnings-symbol', symbol: 'amd' } }),
    { view: 'earnings-review', detail: { kind: 'earnings-symbol', symbol: 'AMD' } });
  assert.deepEqual(normalizeScreen({ view: 'earnings-review', detail: { kind: 'earnings-review', symbol: 'amd', reviewId: 9 } }),
    { view: 'earnings-review', detail: { kind: 'earnings-review', symbol: 'AMD', reviewId: 9 } });
  assert.equal(normalizeScreen({ view: 'backup', detail: { kind: 'alert', alertId: 1 } }), null);
  assert.equal(normalizeScreen({ view: 'unknown' }), null);
});

test('Simulator nested states keep simulation identity distinct for the same symbol', async () => {
  const first = {
    view: 'action-plan-simulator', simulationId: 1,
    detail: { kind: 'action', symbol: 'ABC' },
  };
  const second = {
    view: 'action-plan-simulator', simulationId: 2,
    detail: { kind: 'action', symbol: 'ABC' },
  };
  assert.deepEqual(normalizeScreen(first), { ...first, simulationId: '1' });
  assert.deepEqual(normalizeScreen(second), { ...second, simulationId: '2' });
  const h = harness({ entries: [applicationEntry(0, first)] });
  await h.controller.initialize();
  await h.controller.navigate(second);
  assert.equal(h.history.pushCount, 1);
  assert.equal(h.history.state.screen.simulationId, '2');
});

test('navigation back to the rendered screen supersedes a different in-flight render', async () => {
  const simulationDetail = (id) => ({
    view: 'action-plan-simulator', simulationId: String(id),
    detail: { kind: 'action', symbol: 'ABC' },
  });
  const history = new MemoryHistory([applicationEntry(0, simulationDetail(2))]);
  const rendered = [];
  let releaseFirst;
  let initialized = false;
  const controller = createController({
    history,
    eventTarget: history,
    render: async (screen) => {
      rendered.push(screen.simulationId);
      if (initialized && screen.simulationId === '1') {
        await new Promise((resolve) => { releaseFirst = resolve; });
      }
      return true;
    },
  });
  await controller.initialize();
  initialized = true;
  const first = controller.navigate(simulationDetail(1));
  await settle();
  assert.equal(typeof releaseFirst, 'function');

  const second = controller.navigate(simulationDetail(2));
  await second;
  assert.deepEqual(rendered, ['2', '1', '2']);
  assert.equal(history.pushCount, 0);
  assert.deepEqual(controller.currentScreen(), simulationDetail(2));

  releaseFirst();
  await first;
  assert.equal(history.pushCount, 0);
  assert.deepEqual(controller.currentScreen(), simulationDetail(2));
});

test('initializes a missing or invalid entry with Analysis using replaceState', async () => {
  const h = harness();
  assert.equal(await h.controller.initialize(), true);
  assert.deepEqual(h.rendered, [{ view: 'analysis' }]);
  assert.equal(h.history.replaceCount, 1);
  assert.equal(h.history.pushCount, 0);
  assert.deepEqual(h.history.state, {
    bakingMoneyNavigation: 1,
    sequence: 0,
    screen: { view: 'analysis' },
  });
});

test('restores a valid reload entry without replacing or pushing it', async () => {
  const screen = { view: 'alerts', detail: { kind: 'alert', alertId: '42' } };
  const h = harness({ entries: [applicationEntry(3, screen)] });
  assert.equal(await h.controller.initialize(), true);
  assert.deepEqual(h.rendered, [screen]);
  assert.equal(h.history.replaceCount, 0);
  assert.equal(h.history.pushCount, 0);
  assert.equal(h.controller.currentSequence(), 3);
});

test('navigates across three screens and restores them with Back and Forward', async () => {
  const h = harness();
  await h.controller.initialize();
  await h.controller.navigate({ view: 'positions' });
  await h.controller.navigate({ view: 'action-plan' });
  assert.equal(h.history.pushCount, 2);
  assert.equal(h.controller.currentSequence(), 2);

  h.history.back();
  await settle();
  assert.deepEqual(h.controller.currentScreen(), { view: 'positions' });
  h.history.back();
  await settle();
  assert.deepEqual(h.controller.currentScreen(), { view: 'analysis' });
  h.history.forward();
  await settle();
  h.history.forward();
  await settle();
  assert.deepEqual(h.controller.currentScreen(), { view: 'action-plan' });
  assert.equal(h.history.pushCount, 2, 'popstate restoration must not push');
});

test('repeated navigation between two screens records the real sequence', async () => {
  const h = harness();
  await h.controller.initialize();
  await h.controller.navigate({ view: 'positions' });
  await h.controller.navigate({ view: 'analysis' });
  await h.controller.navigate({ view: 'positions' });
  assert.deepEqual(h.history.entries.map((entry) => entry.state?.screen), [
    { view: 'analysis' }, { view: 'positions' }, { view: 'analysis' }, { view: 'positions' },
  ]);
  assert.deepEqual(h.history.entries.map((entry) => entry.state?.sequence), [0, 1, 2, 3]);
});

test('selecting the active screen does not render or add a duplicate entry', async () => {
  const h = harness();
  await h.controller.initialize();
  assert.equal(await h.controller.navigate({ view: 'analysis' }), true);
  assert.equal(h.history.pushCount, 0);
  assert.deepEqual(h.rendered, [{ view: 'analysis' }]);
});

test('nested entries restore the actual path instead of a predetermined parent', async () => {
  const h = harness();
  await h.controller.initialize();
  await h.controller.navigate({ view: 'positions' });
  await h.controller.navigate({ view: 'positions', detail: { kind: 'analysis', symbol: 'NVDA' } });
  await h.controller.navigate({ view: 'action-plan' });
  await h.controller.navigate({ view: 'action-plan', detail: { kind: 'action', symbol: 'MSFT' } });
  for (const expected of [
    { view: 'action-plan' },
    { view: 'positions', detail: { kind: 'analysis', symbol: 'NVDA' } },
    { view: 'positions' },
  ]) {
    h.history.back();
    await settle();
    assert.deepEqual(h.controller.currentScreen(), expected);
  }
});

test('rejecting Back compensates to the rendered browser entry', async () => {
  let permit = true;
  const h = harness({ canLeave: () => permit });
  await h.controller.initialize();
  await h.controller.navigate({ view: 'positions' });
  await h.controller.navigate({ view: 'action-plan-simulator' });
  permit = false;

  h.history.back();
  await settle();

  assert.equal(h.history.index, 2);
  assert.equal(h.history.state.sequence, 2);
  assert.deepEqual(h.controller.currentScreen(), { view: 'action-plan-simulator' });
  assert.deepEqual(h.history.goCalls.slice(-2), [-1, 1]);
});

test('rejecting Forward compensates to the rendered browser entry', async () => {
  let permit = true;
  const h = harness({ canLeave: () => permit });
  await h.controller.initialize();
  await h.controller.navigate({ view: 'positions' });
  await h.controller.navigate({ view: 'action-plan-simulator' });
  h.history.back();
  await settle();
  permit = false;

  h.history.forward();
  await settle();

  assert.equal(h.history.index, 1);
  assert.equal(h.history.state.sequence, 1);
  assert.deepEqual(h.controller.currentScreen(), { view: 'positions' });
  assert.deepEqual(h.history.goCalls.slice(-2), [1, -1]);
});

test('two rapid rejected Back traversals reconcile to one rendered entry', async () => {
  let permit = true;
  const h = harness({ canLeave: () => permit });
  await h.controller.initialize();
  await h.controller.navigate({ view: 'positions' });
  await h.controller.navigate({ view: 'action-plan-simulator' });
  permit = false;

  h.history.back();
  h.history.back();
  await settle();

  assert.equal(h.history.index, 2);
  assert.equal(h.history.state.sequence, 2);
  assert.equal(h.controller.currentSequence(), 2);
  assert.deepEqual(h.controller.currentScreen(), { view: 'action-plan-simulator' });
  assert.deepEqual(h.rendered, [
    { view: 'analysis' }, { view: 'positions' }, { view: 'action-plan-simulator' },
  ]);
});

test('internal Back traverses history when an earlier application entry exists', async () => {
  const h = harness();
  await h.controller.initialize();
  await h.controller.navigate({ view: 'positions' });
  await h.controller.navigate({ view: 'positions', detail: { kind: 'analysis', symbol: 'NVDA' } });

  assert.equal(await h.controller.back({ view: 'positions' }), true);
  await settle();

  assert.equal(h.history.index, 1);
  assert.deepEqual(h.controller.currentScreen(), { view: 'positions' });
  assert.equal(h.history.pushCount, 2);
});

test('internal Back at sequence zero navigates to its logical fallback', async () => {
  const detail = { view: 'alerts', detail: { kind: 'alert', alertId: '8' } };
  const h = harness({ entries: [applicationEntry(0, detail)] });
  await h.controller.initialize();

  assert.equal(await h.controller.back({ view: 'alerts' }), true);

  assert.deepEqual(h.controller.currentScreen(), { view: 'alerts' });
  assert.equal(h.history.pushCount, 1);
  assert.equal(h.history.state.sequence, 1);
});

test('browser Back beyond the first application entry remains outside BakingMoney', async () => {
  const h = harness({ entries: [{ state: null }, applicationEntry(0, { view: 'analysis' })], index: 1 });
  await h.controller.initialize();

  h.history.back();
  await settle();

  assert.equal(h.history.index, 0);
  assert.equal(h.history.state, null);
  assert.equal(h.history.replaceCount, 0);
  assert.deepEqual(h.history.goCalls, [-1]);
});

test('application adapter restores every main screen and Earnings Review list', async () => {
  const h = appNavigationHarness();
  for (const view of ['analysis', 'positions', 'action-plan', 'action-plan-simulator', 'alerts', 'prompt', 'configuration', 'backup']) {
    h.calls.length = 0;
    assert.equal(await h.render({ view }), true);
    assert.deepEqual(JSON.parse(JSON.stringify(h.calls)), [['view', view, { skipDiscard: true }]]);
  }
  h.calls.length = 0;
  assert.equal(await h.render({ view: 'earnings-review' }), true);
  assert.deepEqual(JSON.parse(JSON.stringify(h.calls)), [
    ['view', 'earnings-review', { skipDiscard: true }],
    ['earnings-tab', 'calendar'],
    ['earnings-list'],
  ]);
});

test('application adapter restores nested screens with their source sidebar', async () => {
  const cases = [
    [
      { view: 'analysis', detail: { kind: 'analysis', symbol: 'AMD' } },
      ['analysis-detail', 'AMD', { origin: 'analysis', skipNavigation: true, navigationGeneration: 1 }],
    ],
    [
      { view: 'positions', detail: { kind: 'analysis', symbol: 'NVDA' } },
      ['analysis-detail', 'NVDA', { origin: 'positions', skipNavigation: true, navigationGeneration: 1 }],
    ],
    [
      { view: 'action-plan', detail: { kind: 'action', symbol: 'MSFT' } },
      ['action-detail', 'MSFT', { skipNavigation: true, navigationGeneration: 1 }],
    ],
    [
      { view: 'action-plan-simulator', detail: { kind: 'action', symbol: 'MSFT' } },
      ['action-detail', 'MSFT', { skipNavigation: true, navigationGeneration: 1 }],
    ],
    [
      { view: 'action-plan-simulator', detail: { kind: 'analysis', symbol: 'META' } },
      ['analysis-detail', 'META', { origin: 'action_plan', skipNavigation: true, navigationGeneration: 1 }],
    ],
    [
      { view: 'alerts', detail: { kind: 'alert', alertId: '7' } },
      ['alert-detail', '7', { skipNavigation: true, navigationGeneration: 1 }],
    ],
    [
      { view: 'earnings-review', detail: { kind: 'earnings-symbol', symbol: 'AMD' } },
      ['earnings-symbol', 'AMD', { skipNavigation: true, navigationGeneration: 1 }],
    ],
    [
      { view: 'earnings-review', detail: { kind: 'earnings-review', symbol: 'AMD', reviewId: 9 } },
      ['earnings-review', 'AMD', 9, { skipNavigation: true, navigationGeneration: 1 }],
    ],
  ];

  for (const [screen, expectedDetailCall] of cases) {
    const h = appNavigationHarness();
    assert.equal(await h.render(screen), true);
    assert.deepEqual(JSON.parse(JSON.stringify(h.calls[0])), ['view', screen.view, { skipDiscard: true, skipLoad: true }]);
    assert.deepEqual(JSON.parse(JSON.stringify(h.calls.at(-1))), expectedDetailCall);
  }
});

test('application adapter selects the simulation stored in a restored nested screen', async () => {
  const calls = [];
  const context = vm.createContext({
    navigationRenderGeneration: 0,
    selectedSimulation: { id: 1 },
    setView: () => true,
    async selectSimulation(id) { calls.push(['simulation', id]); context.selectedSimulation = { id }; },
    async openActionPlanDetail(symbol, options) { calls.push(['detail', symbol, options]); },
  });
  vm.runInContext(`${functionSource('renderNavigationScreen')}; this.renderNavigationScreen = renderNavigationScreen;`, context);
  await context.renderNavigationScreen({
    view: 'action-plan-simulator', simulationId: '2', detail: { kind: 'action', symbol: 'ABC' },
  });
  assert.deepEqual(JSON.parse(JSON.stringify(calls)), [
    ['simulation', '2'],
    ['detail', 'ABC', { skipNavigation: true, navigationGeneration: 1 }],
  ]);
});

test('application adapter returns false when the existing view guard rejects navigation', async () => {
  const context = vm.createContext({
    navigationRenderGeneration: 0,
    setView: () => false,
  });
  vm.runInContext(`${functionSource('renderNavigationScreen')}; this.renderNavigationScreen = renderNavigationScreen;`, context);
  assert.equal(await context.renderNavigationScreen({ view: 'positions' }), false);
});

test('application entry points use the centralized controller instead of pushing on refresh', () => {
  assert.match(appSource, /function navigateToScreen\(screen\)/);
  assert.match(appSource, /function navigateBack\(fallback\)/);
  assert.match(appSource, /loadPortfolioAccounts\(\{ preserveCurrent: false \}\)\.finally\(initializeBrowserNavigation\)/);
  assert.match(appSource, /menuItems\.forEach[\s\S]*navigateToScreen\(\{ view: target \}\)/);
  assert.match(appSource, /simulationId: selectedSimulation\?\.id/);
  assert.doesNotMatch(functionSource('refreshActionPlanFromButton'), /navigateToScreen|pushState/);
});

test('Simulator dirty cash and trigger values survive rejected rapid Back navigation', async () => {
  const dirty = { cash: '25000', trigger: '81' };
  let confirmDiscard = false;
  const canLeaveNavigation = vm.runInNewContext(
    `${functionSource('canLeaveNavigation')}; canLeaveNavigation`,
    {
      discardSimulationEdits() {
        if (!confirmDiscard) return false;
        dirty.cash = '20000';
        dirty.trigger = '80';
        return true;
      },
    },
  );
  const h = harness({ canLeave: canLeaveNavigation });
  await h.controller.initialize();
  await h.controller.navigate({ view: 'positions' });
  await h.controller.navigate({ view: 'action-plan-simulator' });

  h.history.back();
  h.history.back();
  await settle();
  assert.equal(h.history.state.sequence, 2);
  assert.deepEqual(dirty, { cash: '25000', trigger: '81' });
  assert.deepEqual(h.controller.currentScreen(), { view: 'action-plan-simulator' });

  confirmDiscard = true;
  h.history.back();
  await settle();
  assert.equal(h.history.state.sequence, 1);
  assert.deepEqual(dirty, { cash: '20000', trigger: '80' });
  assert.deepEqual(h.controller.currentScreen(), { view: 'positions' });
});

test('Simulator dirty trigger value survives rejected Forward navigation', async () => {
  let trigger = '80';
  let confirmDiscard = true;
  const canLeaveNavigation = vm.runInNewContext(
    `${functionSource('canLeaveNavigation')}; canLeaveNavigation`,
    {
      discardSimulationEdits() {
        if (!confirmDiscard) return false;
        trigger = '80';
        return true;
      },
    },
  );
  const h = harness({ canLeave: canLeaveNavigation });
  await h.controller.initialize();
  await h.controller.navigate({ view: 'action-plan-simulator' });
  await h.controller.navigate({ view: 'positions' });
  h.history.back();
  await settle();
  trigger = '99';
  confirmDiscard = false;

  h.history.forward();
  await settle();

  assert.equal(h.history.state.sequence, 1);
  assert.equal(trigger, '99');
  assert.deepEqual(h.controller.currentScreen(), { view: 'action-plan-simulator' });
});

test('browser navigation controller delegates Simulator leave checks to the existing discard guard', () => {
  const initializeSource = functionSource('initializeBrowserNavigation');
  assert.match(initializeSource, /canLeave: canLeaveNavigation/);
  const guardCalls = [];
  const guard = vm.runInNewContext(`${functionSource('canLeaveNavigation')}; canLeaveNavigation`, {
    discardSimulationEdits() { guardCalls.push('discard'); return false; },
  });
  assert.equal(guard({ view: 'positions' }, { view: 'analysis' }), true);
  assert.equal(guard({ view: 'action-plan-simulator' }, { view: 'positions' }), false);
  assert.equal(guard({ view: 'action-plan-simulator', detail: { kind: 'action', symbol: 'NVDA' } }, { view: 'analysis' }), false);
  assert.deepEqual(guardCalls, ['discard', 'discard']);
});

test('an older Analysis detail response cannot overwrite a newer navigation generation', async () => {
  const deferred = deferredJsonResponse({ analysis: { symbol: 'OLD' } });
  let renders = 0;
  const context = vm.createContext({
    navigationRenderGeneration: 1,
    analysisDetailStatus: fakeElement(), analysisSummary: fakeElement(),
    analysisListView: fakeElement(), analysisDetailView: fakeElement(),
    analysisDetailOrigin: 'analysis', analysisDetailState: null,
    showAnalysisDetailFromPositionsOrigin() {}, showAnalysisDetailFromActionPlanOrigin() {},
    showAnalysisDetailFromEarningsReviewOrigin() {}, updateAnalysisBackButton() {},
    isEditingVariables: false, activeAnalysisVariableCategory: 'Core Driver',
    editableAnalysisVariables: null, isEditingBusinessModel: false, isEditingBusinessSummary: false,
    activeScenarioOverlayTab: 'bakingmoney', fetch: deferred.fetch,
    extractErrorMessage: () => 'error', hasExternalScenarioOverlay: () => false,
    renderAnalysisDetail() { renders += 1; },
  });
  installNavigationAwareFunction(context, 'loadAnalysisDetail');
  const pending = context.loadAnalysisDetail('OLD', null, { navigationGeneration: 1 });
  context.navigationRenderGeneration = 2;
  deferred.finish();
  await pending;
  assert.equal(context.analysisDetailState, null);
  assert.equal(renders, 0);
});

test('an older Alert detail response cannot overwrite a newer navigation generation', async () => {
  const deferred = deferredJsonResponse({ alert: { symbol: 'OLD', status: 'New' } });
  const context = vm.createContext({
    navigationRenderGeneration: 1, currentAlertDetailId: null, currentAlertDetailSymbol: null,
    currentAlertNavigationIds: [], alertsListView: fakeElement(), alertDetailView: fakeElement(),
    alertDetailStatusEl: fakeElement(), alertDetailPanelsEl: fakeElement(), alertDetailTitleEl: fakeElement(),
    alertDetailTypeEl: fakeElement(), alertDetailAffectedEl: fakeElement(), alertDetailEventEl: fakeElement(),
    alertDetailDateEl: fakeElement(), alertDetailSuggestedEl: fakeElement(), alertDetailReviewBtn: fakeElement(),
    alertDetailDismissBtn: fakeElement(), alertDetailPrevBtn: fakeElement(), alertDetailNextBtn: fakeElement(),
    alertDetailOpenAnalysisBtn: fakeElement(), alertDetailKeyvarsStatusEl: fakeElement(),
    getFilteredAlerts: () => [{ id: '1' }], getCurrentAlertIndexWithinFiltered: () => 0,
    fetch: deferred.fetch, extractErrorMessage: () => 'error', formatDate: String, formatDateTime: String,
    renderAlertSources() {}, loadAlertDetailAnalysis: async () => {},
  });
  installNavigationAwareFunction(context, 'openAlertDetail');
  const pending = context.openAlertDetail('1', { navigationGeneration: 1 });
  context.navigationRenderGeneration = 2;
  context.currentAlertDetailId = '2';
  deferred.finish();
  await pending;
  assert.equal(context.currentAlertDetailId, '2');
  assert.equal(context.currentAlertDetailSymbol, null);
  assert.equal(context.alertDetailTitleEl.textContent, '');
});

test('an older Earnings company-history response cannot overwrite a newer navigation generation', async () => {
  const deferred = deferredJsonResponse({ item: { symbol: 'OLD', company_name: 'Old Co', records: [] } });
  let renders = 0;
  const context = vm.createContext({
    navigationRenderGeneration: 1, earningsReviewSelectedSymbol: null,
    earningsReviewSelectedRecordId: null, earningsReviewSymbolHistory: null,
    earningsReviewSymbolTitleEl: fakeElement(), earningsReviewSymbolHeaderEl: fakeElement(),
    earningsReviewSymbolStatusEl: fakeElement(), earningsReviewSymbolTableBody: fakeElement(),
    setEarningsReviewTab() {}, showEarningsReviewSymbolHistoryView() {}, fetch: deferred.fetch,
    extractErrorMessage: () => 'error', renderEarningsReviewSymbolHistoryTable() { renders += 1; },
  });
  installNavigationAwareFunction(context, 'openEarningsReviewSymbolHistory');
  const pending = context.openEarningsReviewSymbolHistory('OLD', { navigationGeneration: 1 });
  context.navigationRenderGeneration = 2;
  context.earningsReviewSelectedSymbol = 'NEW';
  deferred.finish();
  await pending;
  assert.equal(context.earningsReviewSelectedSymbol, 'NEW');
  assert.equal(context.earningsReviewSymbolHistory, null);
  assert.equal(renders, 0);
});

test('an older Earnings review response cannot overwrite a newer navigation generation', async () => {
  const deferred = deferredJsonResponse({ item: { symbol: 'OLD', fiscal_year: 2026, fiscal_quarter: 'Q1', documents: [] } });
  let renders = 0;
  const context = vm.createContext({
    navigationRenderGeneration: 1, earningsReviewSelectedSymbol: null, earningsReviewSelectedRecordId: null,
    earningsReviewDetailTitleEl: fakeElement(), earningsReviewDetailHeaderEl: fakeElement(),
    earningsReviewDetailMetaEl: fakeElement(), earningsReviewGenerateBtn: fakeElement(),
    earningsReviewAnalyseBtn: fakeElement(), earningsReviewKeyVariablesBody: fakeElement(),
    earningsReviewWatchpointsEl: fakeElement(), earningsReviewSnapshotSummaryEl: fakeElement(),
    earningsReviewDocumentsTableBody: fakeElement(), earningsReviewDocumentsStatusEl: fakeElement(),
    earningsReviewDocumentFileEl: fakeElement(), earningsReviewDocumentFileNameEl: fakeElement(),
    setEarningsReviewTab() {}, showEarningsReviewDetail() {}, fetch: deferred.fetch,
    extractErrorMessage: () => 'error', formatDate: String, formatDateTime: String,
    renderEarningsSnapshotSummary() { renders += 1; }, renderEarningsKeyVariables() { renders += 1; },
    renderEarningsWatchpoints() { renders += 1; }, renderEarningsReviewDocuments() { renders += 1; },
  });
  installNavigationAwareFunction(context, 'openEarningsReviewRecordDetail');
  const pending = context.openEarningsReviewRecordDetail('OLD', 1, { navigationGeneration: 1 });
  context.navigationRenderGeneration = 2;
  context.earningsReviewSelectedSymbol = 'NEW';
  context.earningsReviewSelectedRecordId = 2;
  deferred.finish();
  await pending;
  assert.equal(context.earningsReviewSelectedSymbol, 'NEW');
  assert.equal(context.earningsReviewSelectedRecordId, 2);
  assert.equal(renders, 0);
});
