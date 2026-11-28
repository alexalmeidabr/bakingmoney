const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const html = fs.readFileSync('static/index.html','utf8');
const app = fs.readFileSync('static/app.js','utf8');
function functionSource(name) {
  const start = app.indexOf(`function ${name}(`);
  assert.notEqual(start, -1, `${name} exists`);
  const declarationStart = app.slice(start - 6, start) === 'async ' ? start - 6 : start;
  const opening = app.indexOf('{', app.indexOf(')', start));
  let depth = 0;
  for (let index = opening; index < app.length; index += 1) {
    if (app[index] === '{') depth += 1;
    if (app[index] === '}') depth -= 1;
    if (depth === 0) return app.slice(declarationStart, index + 1);
  }
  throw new Error(`${name} is incomplete`);
}
test('Simulator follows Action Plan and defaults to collapsed settings and one-time trigger copy', () => {
  assert.match(html,/data-view="action-plan">Action Plan<\/button>\s*<button[^>]+data-view="action-plan-simulator"/);
  assert.match(html,/<details id="simulation-settings">/);
  assert.match(html,/<input[^>]+id="simulation-copy"[^>]+checked/);
});
test('simulation routing isolates trigger writes while sharing market refresh', () => {
  const source = app.match(/function scopedPlanPath\([^]*?\n}/)[0];
  const path = vm.runInNewContext(source+'; scopedPlanPath');
  assert.equal(path('/api/manual-execution-triggers/ABC',12),'/api/action-plan-simulations/12/triggers/ABC');
  assert.equal(path('/api/action-plan?execution_modes=both',12),'/api/action-plan-simulations/12/action-plan?execution_modes=both');
  assert.equal(path('/api/manual-execution-quotes/refresh',12),'/api/manual-execution-quotes/refresh');
  assert.equal(path('/api/manual-execution-triggers/ABC',null),'/api/manual-execution-triggers/ABC');
});

function simulatorHarness() {
  const elements = new Map();
  const windowHandlers = {};
  const node = (id) => {
    if (!elements.has(id)) {
      const el = {
        id, value: '', checked: false, validity: { valid: true }, handlers: {},
        get valueAsNumber() { return Number(this.value); },
        addEventListener(type, fn) { this.handlers[type] = fn; },
        replaceChildren() { this.options = []; }, add(option) { this.options.push(option); },
        close() { this.open = false; }, showModal() { this.open = true; }, reset() {},
        fire(type) { return this.handlers[type]({ target: this, preventDefault() {} }); },
      };
      elements.set(id, el);
    }
    return elements.get(id);
  };
  const requests = [], plans = [];
  const context = vm.createContext({
    document: {getElementById: node}, Option: class { constructor(label,value) { Object.assign(this,{label,value}); } },
    window: {addEventListener(type, fn) { windowHandlers[type] = fn; }, confirm: () => false},
    selectedPortfolioAccountId: 'A', actionPlanExecutionMode: 'with', actionPlanShowNonExecutableRecommendations: false,
    actionPlanRatingFilters: [], actionPlanActionFilters: [], actionPlanLinearSort: {},
    getAllRatingFilterKeys: () => [], getAllActionPlanActionFilterKeys: () => [],
    manualTriggerDetailEl: null,
    setSelectedActionPlanRatings() {}, setSelectedActionPlanActions() {}, updateActionPlanSortHeaderState() {}, updateActionPlanModeButtons() {},
    clearActionPlanDisplay() {}, formatCurrencyValue: (value) => '$' + value,
    navigateBack() {}, navigateToScreen() {},
    loadActionPlan() { plans.push(vm.runInContext('selectedSimulation?.id', context)); },
    refreshActionPlanFromButton() {}, createPortfolioApiError: (p) => Error(p.error),
    currentTriggerValues: null,
    manualTriggerEditorValues() { return context.currentTriggerValues; },
    withSelectedPortfolioAccount: (url) => url + '?account_id=' + context.selectedPortfolioAccountId,
    fetch: (url, options) => new Promise((resolve) => requests.push({
      url, options, finish(payload, ok = true) { resolve({ ok, json: async () => payload }); },
    })),
  });
  vm.runInContext(app.slice(app.indexOf('const simulationEl ='), app.indexOf('function setView(')), context);
  const run = (code) => vm.runInContext(code, context);
  run('simulatorActive = true');
  return { run, requests, plans, el: (name) => node('simulation-' + name), context, windowHandlers };
}

const triggerValues = (overrides = {}) => ({
  buy_trigger_price: '80', sell_trigger_price: '700', sell_trigger_direction: 'at_or_above',
  reserve_enabled: false, reserve_percentage: '0', ...overrides,
});

test('every normalized simulation trigger field participates in dirty tracking and reverting clears it', () => {
  const h = simulatorHarness();
  h.run("selectedSimulation = {id: 7, additional_cash_usd: 0}");
  h.context.currentTriggerValues = triggerValues();
  h.run("setManualTriggerBaseline('NVDA', currentTriggerValues)");
  assert.equal(h.run('simulationTriggerDirty()'), false);
  for (const [field, value] of Object.entries({
    buy_trigger_price: '81', sell_trigger_price: '701', sell_trigger_direction: 'at_or_below',
    reserve_enabled: true, reserve_percentage: '60',
  })) {
    h.context.currentTriggerValues = triggerValues({ [field]: value });
    assert.equal(h.run('simulationTriggerDirty()'), true, field);
  }
  h.context.currentTriggerValues = triggerValues({ buy_trigger_price: '80.0', reserve_percentage: '0.0' });
  assert.equal(h.run('simulationTriggerDirty()'), false);
  h.run("noteManualTriggerEdit()");
  assert.equal(h.run('simulationTriggerDirty()'), false);
  h.context.currentTriggerValues = triggerValues({ buy_trigger_price: '99' });
  h.run('simulatorActive = false');
  assert.equal(h.run('simulationTriggerDirty()'), false, 'real Action Plan remains unaffected');
});

test('an empty saved trigger matches the editor defaults and is clean', () => {
  const h = simulatorHarness();
  h.run("selectedSimulation = {id: 7, additional_cash_usd: 0}");
  h.context.currentTriggerValues = triggerValues({
    buy_trigger_price: '', sell_trigger_price: '', sell_trigger_direction: 'at_or_above',
  });
  h.run("setManualTriggerBaseline('NVDA', {})");
  assert.equal(h.run('simulationTriggerDirty()'), false);
});

test('trigger price refresh does not dirty the editor and beforeunload protects actual edits', () => {
  const h = simulatorHarness();
  h.run("selectedSimulation = {id: 7, additional_cash_usd: 0}");
  h.context.currentTriggerValues = triggerValues();
  h.run("setManualTriggerBaseline('NVDA', currentTriggerValues)");
  assert.equal(h.run('simulationTriggerDirty()'), false);
  const cleanEvent = { prevented: false, preventDefault() { this.prevented = true; } };
  h.windowHandlers.beforeunload(cleanEvent);
  assert.equal(cleanEvent.prevented, false);
  h.context.currentTriggerValues = triggerValues({ buy_trigger_price: '81' });
  const dirtyEvent = { prevented: false, returnValue: undefined, preventDefault() { this.prevented = true; } };
  h.windowHandlers.beforeunload(dirtyEvent);
  assert.equal(dirtyEvent.prevented, true);
  assert.equal(dirtyEvent.returnValue, '');
});

test('switching simulations rejects or explicitly discards unsaved trigger edits', async () => {
  const h = simulatorHarness();
  h.run("savedSimulations = [{id:1,name:'One',additional_cash_usd:0},{id:2,name:'Two',additional_cash_usd:0}]; selectedSimulation = savedSimulations[0]");
  h.el('select').value = '2';
  h.context.currentTriggerValues = triggerValues();
  h.run("setManualTriggerBaseline('NVDA', currentTriggerValues)");
  h.context.currentTriggerValues = triggerValues({ reserve_enabled: true });
  h.el('select').fire('change');
  assert.equal(h.run('selectedSimulation.id'), 1);
  assert.equal(h.el('select').value, 1);
  assert.equal(h.context.currentTriggerValues.reserve_enabled, true);
  h.context.window.confirm = () => true;
  h.el('select').value = '2';
  h.el('select').fire('change');
  await new Promise(setImmediate);
  assert.equal(h.run('selectedSimulation.id'), 2);
});

test('delete duplicate and refresh are blocked by unsaved trigger edits until discard is confirmed', () => {
  const h = simulatorHarness();
  h.run("selectedSimulation = {id:7,name:'Saved',additional_cash_usd:0}; savedSimulations=[selectedSimulation]");
  h.context.currentTriggerValues = triggerValues();
  h.run("setManualTriggerBaseline('NVDA', currentTriggerValues)");
  h.context.currentTriggerValues = triggerValues({ reserve_percentage: '50' });
  h.el('duplicate').fire('click');
  h.el('refresh').fire('click');
  h.el('delete').fire('click');
  assert.equal(h.requests.length, 0);
  assert.equal(h.plans.length, 0);
});

test('applying new cash cannot silently discard unsaved trigger edits', () => {
  const h = simulatorHarness();
  h.run("selectedSimulation = {id:7,name:'Saved',additional_cash_usd:10}; savedSimulations=[selectedSimulation]");
  h.el('cash').value = '20';
  h.context.currentTriggerValues = triggerValues();
  h.run("setManualTriggerEditorValues = (values) => { currentTriggerValues = {...values}; }");
  h.run("setManualTriggerBaseline('NVDA', currentTriggerValues)");
  h.context.currentTriggerValues = triggerValues({ sell_trigger_price: '710' });
  h.el('settings-form').fire('submit');
  assert.equal(h.requests.length, 0);
  assert.equal(h.context.currentTriggerValues.sell_trigger_price, '710');

  h.context.window.confirm = () => true;
  h.el('settings-form').fire('submit');
  assert.equal(h.requests.length, 1);
  assert.equal(JSON.parse(h.requests[0].options.body).additional_cash_usd, 20);
  assert.equal(h.context.currentTriggerValues.sell_trigger_price, 700);
});

function triggerPersistenceHarness() {
  const status = { textContent: '', className: '' };
  const saveButton = { disabled: false };
  const clearButton = { disabled: false };
  const inputField = { disabled: false };
  const requests = [];
  let reloads = 0;
  const context = vm.createContext({
    selectedPortfolioAccountId: 'A', selectedSimulation: { id: 7 }, simulatorActive: true,
    actionPlanDetailRequestId: 1, manualTriggerEditRevision: 0,
    manualTriggerMutations: new Map(), currentTriggerValues: triggerValues(),
    manualTriggerDetailEl: { querySelector(selector) {
      if (selector === '[data-trigger-status]') return status;
      if (selector === '[data-trigger-action="save"]') return saveButton;
      if (selector === '[data-trigger-action="clear"]') return clearButton;
      return inputField;
    } },
    manualTriggerEditorValues() { return context.currentTriggerValues; },
    setManualTriggerEditorValues(values) { context.currentTriggerValues = { ...values }; },
    withSelectedPortfolioAccount: (url) => url + '?account_id=A',
    createPortfolioApiError: (payload) => Error(payload.error || 'request failed'),
    loadActionPlan: async () => { reloads += 1; return true; },
    renderManualTriggerDetail() {},
    fetch: (url, options) => new Promise((resolve) => requests.push({
      url, options, finish(payload, ok = true, statusCode = ok ? 200 : 500) {
        resolve({ ok, status: statusCode, json: async () => payload });
      },
    })),
  });
  vm.runInContext(`let manualTriggerBaseline = null;
    ${functionSource('normalizeManualTriggerValues')}
    ${functionSource('manualTriggerContextKey')}
    ${functionSource('setManualTriggerMutationControls')}
    ${functionSource('beginManualTriggerMutation')}
    ${functionSource('manualTriggerMutationContextIsActive')}
    ${functionSource('finishManualTriggerMutation')}
    ${functionSource('setManualTriggerBaseline')}
    ${functionSource('manualTriggerDirty')}
    ${functionSource('simulationTriggerDirty')}
    ${functionSource('validateManualTriggerForm')}
    ${functionSource('saveManualTrigger')}
    ${functionSource('clearManualTrigger')}`, context);
  return {
    context, requests, status, saveButton, clearButton, inputField,
    reloads: () => reloads, run: (code) => vm.runInContext(code, context),
  };
}

test('Save and Clear share one in-flight mutation slot for the editor context', async () => {
  const h = triggerPersistenceHarness();
  h.run("setManualTriggerBaseline('NVDA', currentTriggerValues)");
  const firstSave = h.run("saveManualTrigger('NVDA')");
  const secondSave = h.run("saveManualTrigger('NVDA')");
  const blockedClear = h.run("clearManualTrigger('NVDA')");
  assert.equal(h.requests.length, 1);
  assert.equal(h.saveButton.disabled, true);
  assert.equal(h.clearButton.disabled, true);
  assert.equal(h.inputField.disabled, false);
  h.requests[0].finish({ trigger: { buy_trigger_price: 80 } });
  await Promise.all([firstSave, secondSave, blockedClear]);
  assert.equal(h.requests.length, 1);
  assert.equal(h.reloads(), 1);
  assert.equal(h.saveButton.disabled, false);
  assert.equal(h.clearButton.disabled, false);

  const clear = h.run("clearManualTrigger('NVDA')");
  const blockedSave = h.run("saveManualTrigger('NVDA')");
  assert.equal(h.requests.length, 2);
  h.requests[1].finish({ deleted: true });
  await Promise.all([clear, blockedSave]);
  assert.equal(h.requests.length, 2);
  assert.equal(h.reloads(), 2);
});

test('successful Save keeps newer edits dirty and recalculates the submitted context once', async () => {
  const h = triggerPersistenceHarness();
  h.run("setManualTriggerBaseline('NVDA', currentTriggerValues)");
  h.context.currentTriggerValues = triggerValues({ buy_trigger_price: '81' });
  const save = h.run("saveManualTrigger('NVDA')");
  h.context.currentTriggerValues = triggerValues({ buy_trigger_price: '82' });
  h.context.manualTriggerEditRevision += 1;
  h.requests[0].finish({ trigger: { buy_trigger_price: 81 } });
  await save;
  assert.equal(h.context.currentTriggerValues.buy_trigger_price, '82');
  assert.equal(h.run('simulationTriggerDirty()'), true);
  assert.equal(h.reloads(), 1);
  assert.match(h.status.textContent, /newer trigger changes remain unsaved/);
});

test('real Action Plan Save labels newer edits unsaved without submitting them', async () => {
  const h = triggerPersistenceHarness();
  h.context.simulatorActive = false;
  h.context.selectedSimulation = null;
  h.run("setManualTriggerBaseline('NVDA', currentTriggerValues)");
  h.context.currentTriggerValues = triggerValues({ buy_trigger_price: '81' });
  const save = h.run("saveManualTrigger('NVDA')");
  h.context.currentTriggerValues = triggerValues({ buy_trigger_price: '82' });
  h.context.manualTriggerEditRevision += 1;
  h.requests[0].finish({ trigger: { buy_trigger_price: 81 } });
  await save;
  assert.equal(h.requests.length, 1);
  assert.equal(JSON.parse(h.requests[0].options.body).buy_trigger_price, 81);
  assert.equal(h.context.currentTriggerValues.buy_trigger_price, '82');
  assert.equal(h.run('manualTriggerDirty()'), true);
  assert.match(h.status.textContent, /newer trigger changes remain unsaved/);
});

test('failed Save keeps newer edits dirty, reports failure, and does not recalculate', async () => {
  const h = triggerPersistenceHarness();
  h.run("setManualTriggerBaseline('NVDA', currentTriggerValues)");
  h.context.currentTriggerValues = triggerValues({ buy_trigger_price: '81' });
  const save = h.run("saveManualTrigger('NVDA')");
  h.context.currentTriggerValues = triggerValues({ buy_trigger_price: '82' });
  h.context.manualTriggerEditRevision += 1;
  h.requests[0].finish({ error: 'offline' }, false);
  await save;
  assert.equal(h.context.currentTriggerValues.buy_trigger_price, '82');
  assert.equal(h.run('simulationTriggerDirty()'), true);
  assert.equal(h.reloads(), 0);
  assert.match(h.status.textContent, /offline/);
  assert.equal(h.saveButton.disabled, false);
  assert.equal(h.clearButton.disabled, false);
});

test('late Save response cannot update another account simulation or stock editor', async () => {
  const h = triggerPersistenceHarness();
  h.run("setManualTriggerBaseline('NVDA', currentTriggerValues)");
  h.context.currentTriggerValues = triggerValues({ buy_trigger_price: '81' });
  const save = h.run("saveManualTrigger('NVDA')");
  h.context.selectedPortfolioAccountId = 'B';
  h.context.selectedSimulation = { id: 9 };
  h.context.actionPlanDetailRequestId = 2;
  h.context.currentTriggerValues = triggerValues({ buy_trigger_price: '95' });
  h.run("setManualTriggerBaseline('MSFT', currentTriggerValues)");
  h.status.textContent = 'New editor';
  h.requests[0].finish({ trigger: { buy_trigger_price: 81 } });
  await save;
  assert.equal(h.context.currentTriggerValues.buy_trigger_price, '95');
  assert.equal(h.run('simulationTriggerDirty()'), false);
  assert.equal(h.reloads(), 0);
  assert.equal(h.status.textContent, 'New editor');
});

test('saving clears dirty state while failed saving retains edited values', async () => {
  const h = triggerPersistenceHarness();
  h.run("setManualTriggerBaseline('NVDA', currentTriggerValues)");
  h.context.currentTriggerValues = triggerValues({ buy_trigger_price: '81' });
  assert.equal(h.run('simulationTriggerDirty()'), true);
  const save = h.run("saveManualTrigger('NVDA')");
  h.requests[0].finish({ trigger: { buy_trigger_price: 81 } });
  await save;
  assert.equal(h.run('simulationTriggerDirty()'), false);
  h.context.currentTriggerValues = triggerValues({ buy_trigger_price: '82' });
  const failed = h.run("saveManualTrigger('NVDA')");
  h.requests[1].finish({ error: 'offline' }, false);
  await failed;
  assert.equal(h.context.currentTriggerValues.buy_trigger_price, '82');
  assert.equal(h.run('simulationTriggerDirty()'), true);
  assert.match(h.status.textContent, /offline/);
});

test('clear updates the baseline but a late response cannot overwrite newer edits', async () => {
  const h = triggerPersistenceHarness();
  h.run("setManualTriggerBaseline('NVDA', currentTriggerValues)");
  const clear = h.run("clearManualTrigger('NVDA')");
  h.context.currentTriggerValues = triggerValues({ buy_trigger_price: '83' });
  h.context.manualTriggerEditRevision += 1;
  h.requests[0].finish({ deleted: true });
  await clear;
  assert.equal(h.context.currentTriggerValues.buy_trigger_price, '83');
  assert.equal(h.run('simulationTriggerDirty()'), true);
  assert.match(h.status.textContent, /newer trigger changes remain unsaved/);
  const second = h.run("clearManualTrigger('NVDA')");
  h.requests[1].finish({ deleted: true });
  await second;
  assert.equal(h.run('simulationTriggerDirty()'), false);
  assert.equal(h.context.currentTriggerValues.buy_trigger_price, null);
});

test('account switching and opening another symbol are cancelled when trigger discard is rejected', async () => {
  const h = simulatorHarness();
  h.run("selectedSimulation = {id:7,additional_cash_usd:0}");
  h.context.currentTriggerValues = triggerValues();
  h.run("setManualTriggerBaseline('NVDA', currentTriggerValues)");
  h.context.currentTriggerValues = triggerValues({ sell_trigger_price: '710' });
  let accountRenderCount = 0;
  Object.assign(h.context, {
    isUpdatingPortfolioAccountSelect: false,
    portfolioAccountSelectEl: { value: 'B' },
    renderPortfolioAccountSelector() { accountRenderCount += 1; },
  });
  h.run(functionSource('handlePortfolioAccountChange'));
  await h.run('handlePortfolioAccountChange()');
  assert.equal(h.context.selectedPortfolioAccountId, 'A');
  assert.equal(accountRenderCount, 1);
  h.run(functionSource('openActionPlanDetail'));
  const opened = await h.run("openActionPlanDetail('MSFT')");
  assert.equal(opened, false);
  assert.equal(h.context.currentTriggerValues.sell_trigger_price, '710');
});

test('Action Detail Back delegates to browser history while direct sidebar rendering retains its guard', () => {
  const h = simulatorHarness();
  h.run("selectedSimulation = {id:7,additional_cash_usd:0}");
  h.context.currentTriggerValues = triggerValues();
  h.run("setManualTriggerBaseline('NVDA', currentTriggerValues)");
  h.context.currentTriggerValues = triggerValues({ buy_trigger_price: '81' });
  let listShows = 0;
  Object.assign(h.context, {
    actionPlanDetailBackBtn: h.el('test-detail-back'),
    showActionPlanList() { listShows += 1; },
    navigateBack(fallback) {
      assert.equal(fallback.view, 'action-plan-simulator');
      if (h.run('discardSimulationEdits()')) listShows += 1;
    },
  });
  const backStart = app.indexOf("actionPlanDetailBackBtn.addEventListener('click'");
  h.run(app.slice(backStart, app.indexOf('\n});', backStart) + 4));
  h.el('test-detail-back').fire('click');
  assert.equal(listShows, 0);

  h.run(functionSource('setView'));
  assert.equal(h.run("setView('positions')"), false);
  h.context.window.confirm = () => true;
  h.el('test-detail-back').fire('click');
  assert.equal(listShows, 1);
});

test('late list and mutation results cannot replace a different account or simulation', async () => {
  const h = simulatorHarness();
  const first = h.run('loadSimulations()');
  h.context.selectedPortfolioAccountId = 'B';
  const second = h.run('loadSimulations()');
  h.requests[1].finish({simulations: [{id:2, name:'B only', additional_cash_usd:200}]});
  await second;
  h.requests[0].finish({simulations: [{id:1, name:'A only', additional_cash_usd:100}]});
  await first;
  assert.equal(h.el('summary').textContent, 'B only · +$200 · Simulation Triggers');
  assert.deepEqual(h.plans, [2]);
  const save = h.run("mutateSimulation('/2','PUT',{additional_cash_usd:300})");
  h.context.selectedPortfolioAccountId = 'A';
  const back = h.run('loadSimulations()');
  h.requests[3].finish({simulations: [{id:1, name:'A only', additional_cash_usd:100}]});
  await back;
  h.requests[2].finish({simulation:{id:2,name:'Stale',additional_cash_usd:300}});
  await save;
  assert.deepEqual(h.plans,[2,1]);
  assert.equal(h.el('cash').value,100);
});

test('pending cash stays separate from saved results and rejected navigation preserves input', async () => {
  const h = simulatorHarness();
  const initial = h.run('loadSimulations()');
  h.requests[0].finish({simulations: [{id:7, name:'Saved', additional_cash_usd:20000}]});
  await initial;
  h.el('cash').value = '30000';
  h.el('cash').fire('input');
  assert.match(h.el('status').textContent,/Unsaved changes/);
  assert.equal(h.run('discardSimulationEdits()'),false);
  let refreshes = 0;
  h.context.refreshActionPlanFromButton = () => { refreshes++; };
  h.el('refresh').fire('click');
  assert.equal(refreshes, 0);
  assert.equal(h.el('cash').value,'30000');
  assert.equal(h.run('selectedSimulation.additional_cash_usd'),20000);
  assert.deepEqual(h.plans,[7]);
  h.el('settings-form').fire('submit');
  assert.equal(h.requests[1].url,'/api/action-plan-simulations/7?account_id=A');
  assert.deepEqual(JSON.parse(h.requests[1].options.body),{additional_cash_usd:30000});
  assert.equal(h.run('selectedSimulation.additional_cash_usd'),20000);
  h.requests[1].finish({simulation:{id:7,name:'Saved',additional_cash_usd:30000}});
  await new Promise(setImmediate);
  assert.equal(h.run('simulationCashDirty()'),false);
  assert.deepEqual(h.plans,[7,7]);
});

test('every simulator endpoint is scoped through the global portfolio account selector', () => {
  const {withPortfolioAccount} = require('./static/portfolio_account_selector');
  for (const suffix of ['', '/5', '/5/duplicate', '/5/triggers/XYZ', '/5/action-plan?execution_modes=both']) {
    const url = new URL(withPortfolioAccount('/api/action-plan-simulations' + suffix, 'ACCOUNT-B'),'http://local');
    assert.equal(url.searchParams.get('account_id'),'ACCOUNT-B');
    if (suffix.includes('execution_modes')) assert.equal(url.searchParams.get('execution_modes'),'both');
  }
});

test('creation, duplication and deletion select the saved record and reload its plan', async () => {
  const h = simulatorHarness();
  h.el('name').value = 'Extra cash';
  h.el('new-cash').value = '20000';
  h.el('copy').checked = true;
  h.el('dialog').open = true;
  h.el('create-form').fire('submit');
  assert.deepEqual(JSON.parse(h.requests[0].options.body), {
    name: 'Extra cash', additional_cash_usd: 20000, copy_current_triggers: true,
  });
  h.requests[0].finish({simulation:{id:1,name:'Extra cash',additional_cash_usd:20000}});
  await new Promise(setImmediate);
  assert.equal(h.el('dialog').open,false);
  h.el('duplicate').fire('click');
  assert.match(h.requests[1].url,/\/1\/duplicate\?account_id=A$/);
  h.requests[1].finish({simulation:{id:2,name:'Extra cash copy',additional_cash_usd:20000}});
  await new Promise(setImmediate);
  assert.equal(h.run('selectedSimulation.id'),2);
  h.el('delete').fire('click');
  assert.equal(h.requests.length,2);
  h.context.window.confirm = () => true;
  h.el('delete').fire('click');
  assert.equal(h.requests[2].options.method,'DELETE');
  h.requests[2].finish({deleted:true});
  await new Promise(setImmediate);
  assert.deepEqual(h.plans,[1,2,1]);
  assert.equal(h.run('savedSimulations.length'),1);
});

test('returning to a saved simulation restores its execution mode without sharing another simulation’s mode', async () => {
  const h = simulatorHarness();
  const initial = h.run('loadSimulations()');
  h.requests[0].finish({simulations: [
    {id:1,name:'First',additional_cash_usd:0},
    {id:2,name:'Second',additional_cash_usd:100},
  ]});
  await initial;
  h.run("actionPlanExecutionMode = 'without'; actionPlanShowNonExecutableRecommendations = true");
  await h.run('selectSimulation(2)');
  assert.equal(h.run('actionPlanExecutionMode'),'with');
  assert.equal(h.run('actionPlanShowNonExecutableRecommendations'),false);
  await h.run('selectSimulation(1)');
  assert.equal(h.run('actionPlanExecutionMode'),'without');
  assert.equal(h.run('actionPlanShowNonExecutableRecommendations'),true);
});

test('opening full analysis and returning retains the simulator, stock detail, execution mode and editor', async () => {
  const h = simulatorHarness();
  const active = (id, dataset = {}) => ({id, dataset, classList:{toggle(key,on) { this[key] = on; }}});
  const views = [active('action-plan'), active('action-plan-simulator'), active('analysis')];
  const menuItems = views.map(({id}) => active('',{view:id}));
  const detail = {symbol:'ABC'};
  const load = h.run('loadSimulations()');
  h.requests[0].finish({simulations:[{id:7,name:'Selected',additional_cash_usd:20000}]});
  await load;
  Object.assign(h.context, {
    views, menuItems, selectedActionPlanDetail:detail, analysisDetailOrigin:'analysis',
    analysisBackBtn:h.el('test-back'), actionPlanOpenAnalysisBtn:h.el('test-open'),
    loadAnalysisDetail: async symbol => { assert.equal(symbol,'ABC'); },
  });
  views[1].classList.active = true;
  menuItems[1].classList.active = true;
  h.run("actionPlanExecutionMode = 'without'");
  const functions = ['setView','showAnalysisDetailFromOriginMenu','showAnalysisDetailFromActionPlanOrigin','openAnalysisDetailForSymbol'];
  for (const name of functions) h.run(app.match(new RegExp('(?:async )?function ' + name + '\\([^]*?\\n}'))[0]);
  h.context.navigateToScreen = (screen) => {
    if (!h.run('discardSimulationEdits()')) return false;
    if (screen.detail?.kind === 'analysis') return h.run(`openAnalysisDetailForSymbol(${JSON.stringify(screen.detail.symbol)}, {origin:'action_plan'})`);
    return false;
  };
  h.context.navigateBack = (fallback) => h.run(`setView(${JSON.stringify(fallback.view)}, {skipLoad:true})`);
  for (const source of ['actionPlanOpenAnalysisBtn','analysisBackBtn']) {
    const start = app.indexOf(source + ".addEventListener('click'");
    h.run(app.slice(start, app.indexOf('\n});', start) + 4));
  }
  h.context.currentTriggerValues = triggerValues();
  h.run("setManualTriggerBaseline('ABC', currentTriggerValues)");
  h.context.currentTriggerValues = triggerValues({ buy_trigger_price: '81' });
  h.el('test-open').fire('click');
  assert.equal(views.find(v => v.classList.active).id,'action-plan-simulator');
  h.context.window.confirm = () => true;
  h.el('test-open').fire('click');
  assert.equal(views.find(v => v.classList.active).id,'analysis');
  assert.equal(menuItems.find(v => v.classList.active).dataset.view,'action-plan-simulator');
  h.el('test-back').fire('click');
  assert.equal(views.find(v => v.classList.active).id,'action-plan-simulator');
  assert.equal(h.run('selectedSimulation.id'),7);
  assert.equal(h.run('selectedActionPlanDetail'),detail);
  assert.equal(h.run('actionPlanExecutionMode'),'without');
  assert.equal(h.requests.length,1);
  assert.deepEqual(h.plans,[7]);
});
