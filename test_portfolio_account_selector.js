const assert = require('node:assert/strict');
const fs = require('node:fs');
const test = require('node:test');

const {
  getAccountLabel,
  getAccountOptionLabel,
  isPortfolioAccountScopedUrl,
  resolveInitialPortfolioAccount,
  withPortfolioAccount,
} = require('./static/portfolio_account_selector.js');

const indexHtml = fs.readFileSync('static/index.html', 'utf8');
const appJs = fs.readFileSync('static/app.js', 'utf8');

const account = (id, ready = true, extra = {}) => ({
  account_id: id,
  masked_account_id: `****${id.slice(-4)}`,
  portfolio_data_available: ready,
  ...extra,
});

test('labels prefer display names and fall back to masked ids', () => {
  assert.equal(getAccountLabel(account('DU123456', true, { display_name: 'Main Portfolio' })), 'Main Portfolio');
  assert.equal(getAccountLabel(account('DU654321')), '****4321');
});

test('unavailable account labels are visibly marked without exposing raw ids', () => {
  assert.equal(getAccountOptionLabel(account('DU222222', false)), '****2222 - portfolio data unavailable');
});

test('restores a valid saved account even when portfolio data is unavailable', () => {
  assert.deepEqual(
    resolveInitialPortfolioAccount([account('DU111111', true), account('DU222222', false)], 'DU222222'),
    { selectedAccountId: 'DU222222', shouldClearSaved: false, shouldSaveSelection: false },
  );
});

test('clears invalid saved accounts and auto-selects a deterministic fallback', () => {
  assert.deepEqual(
    resolveInitialPortfolioAccount([account('DU333333', true)], 'DU999999'),
    { selectedAccountId: 'DU333333', shouldClearSaved: true, shouldSaveSelection: true },
  );
});

test('auto-selects one account and one ready account among multiple accounts', () => {
  assert.deepEqual(
    resolveInitialPortfolioAccount([account('DU111111')], null),
    { selectedAccountId: 'DU111111', shouldClearSaved: false, shouldSaveSelection: true },
  );
  assert.deepEqual(
    resolveInitialPortfolioAccount([account('DU111111', false), account('DU222222', true)], null),
    { selectedAccountId: 'DU222222', shouldClearSaved: false, shouldSaveSelection: true },
  );
});

test('does not choose arbitrarily when multiple accounts are equally ready', () => {
  assert.deepEqual(
    resolveInitialPortfolioAccount([account('DU111111', true), account('DU222222', true)], null),
    { selectedAccountId: null, shouldClearSaved: false, shouldSaveSelection: false },
  );
});

test('empty account lists clear saved selection and preserve the empty state', () => {
  assert.deepEqual(
    resolveInitialPortfolioAccount([], 'DU111111'),
    { selectedAccountId: null, shouldClearSaved: true, shouldSaveSelection: false },
  );
});

test('adds selected account only to portfolio-scoped urls', () => {
  assert.equal(withPortfolioAccount('/api/positions', 'DU123456'), '/api/positions?account_id=DU123456');
  assert.equal(withPortfolioAccount('/api/positions?refresh=1', 'DU123456'), '/api/positions?refresh=1&account_id=DU123456');
  assert.equal(withPortfolioAccount('/api/action-plan', 'DU123456'), '/api/action-plan?account_id=DU123456');
  assert.equal(withPortfolioAccount('/api/action-plan/AAPL', 'DU123456'), '/api/action-plan/AAPL?account_id=DU123456');
  assert.equal(withPortfolioAccount('/api/analysis', 'DU123456'), '/api/analysis');
  assert.equal(withPortfolioAccount('/api/ib-accounts', 'DU123456'), '/api/ib-accounts');
  assert.equal(withPortfolioAccount('/api/positions', ''), '/api/positions');
});

test('portfolio scoped url detection is narrow', () => {
  assert.equal(isPortfolioAccountScopedUrl('/api/positions'), true);
  assert.equal(isPortfolioAccountScopedUrl('/api/action-plan/MSFT'), true);
  assert.equal(isPortfolioAccountScopedUrl('/api/action-plan-settings'), false);
  assert.equal(isPortfolioAccountScopedUrl('/api/analysis'), false);
});

test('global account selector is loaded before app startup', () => {
  assert.ok(indexHtml.includes('id="portfolio-account-select"'));
  assert.ok(indexHtml.includes('id="portfolio-account-status"'));
  assert.ok(indexHtml.indexOf('/static/portfolio_account_selector.js') < indexHtml.indexOf('/static/app.js'));
});

test('account changes clear stale portfolio views and reload the active portfolio context', () => {
  assert.ok(appJs.includes("portfolioAccountSelectEl?.addEventListener('change', handlePortfolioAccountChange)"));
  assert.ok(appJs.includes("localStorage.setItem(PORTFOLIO_ACCOUNT_STORAGE_KEY, selectedPortfolioAccountId)"));
  assert.ok(appJs.includes("clearPositionsDisplay('', 'status')"));
  assert.ok(appJs.includes("clearActionPlanDisplay('', 'status')"));
  assert.ok(appJs.includes('await reloadPortfolioScopedViews()'));
});

test('portfolio-dependent fetches use the scoped account helper', () => {
  assert.ok(appJs.includes("withSelectedPortfolioAccount(options.refresh ? '/api/positions?refresh=1' : '/api/positions')"));
  assert.ok(appJs.includes("withSelectedPortfolioAccount('/api/action-plan')"));
  assert.ok(appJs.includes('withSelectedPortfolioAccount(`/api/action-plan/${encodeURIComponent(symbol)}`)'));
  assert.ok(appJs.includes("fetch('/api/ib-accounts')"));
  assert.ok(appJs.includes("fetch('/api/analysis')"));
});
