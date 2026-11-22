const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const html = fs.readFileSync('static/index.html','utf8');
const app = fs.readFileSync('static/app.js','utf8');
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
    window: {addEventListener() {}, confirm: () => false},
    selectedPortfolioAccountId: 'A', actionPlanExecutionMode: 'with', actionPlanShowNonExecutableRecommendations: false,
    actionPlanRatingFilters: [], actionPlanActionFilters: [], actionPlanLinearSort: {},
    getAllRatingFilterKeys: () => [], getAllActionPlanActionFilterKeys: () => [],
    setSelectedActionPlanRatings() {}, setSelectedActionPlanActions() {}, updateActionPlanSortHeaderState() {}, updateActionPlanModeButtons() {},
    clearActionPlanDisplay() {}, formatCurrencyValue: (value) => '$' + value,
    loadActionPlan() { plans.push(vm.runInContext('selectedSimulation?.id', context)); },
    refreshActionPlanFromButton() {}, createPortfolioApiError: (p) => Error(p.error),
    withSelectedPortfolioAccount: (url) => url + '?account_id=' + context.selectedPortfolioAccountId,
    fetch: (url, options) => new Promise((resolve) => requests.push({
      url, options, finish(payload, ok = true) { resolve({ ok, json: async () => payload }); },
    })),
  });
  vm.runInContext(app.slice(app.indexOf('const simulationEl ='), app.indexOf('function setView(')), context);
  const run = (code) => vm.runInContext(code, context);
  run('simulatorActive = true');
  return { run, requests, plans, el: (name) => node('simulation-' + name), context };
}

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
  h.run("actionPlanExecutionMode = 'without'");
  const functions = ['setView','showAnalysisDetailFromOriginMenu','showAnalysisDetailFromActionPlanOrigin','openAnalysisDetailForSymbol'];
  for (const name of functions) h.run(app.match(new RegExp('(?:async )?function ' + name + '\\([^]*?\\n}'))[0]);
  for (const source of ['actionPlanOpenAnalysisBtn','analysisBackBtn']) {
    const start = app.indexOf(source + ".addEventListener('click'");
    h.run(app.slice(start, app.indexOf('\n});', start) + 4));
  }
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
