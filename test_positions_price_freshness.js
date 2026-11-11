const assert = require('node:assert/strict');
const fs = require('node:fs');
const test = require('node:test');
const vm = require('node:vm');

const appJs = fs.readFileSync('static/app.js', 'utf8').replace(/\r\n/g, '\n');
const stylesCss = fs.readFileSync('static/styles.css', 'utf8').replace(/\r\n/g, '\n');

test('My Positions visibly distinguishes cached stale prices', () => {
  assert.match(appJs, /function formatPositionPriceCell\(position\)/);
  assert.match(appJs, /price_status !== 'cached_stale'/);
  assert.match(appJs, /price-freshness-badge/);
  assert.match(appJs, /Current TWS refresh did not supply a usable price/);
  assert.match(stylesCss, /\.price-freshness-badge\s*\{/);
});

test('My Positions status presents incomplete quote diagnostics as a warning', () => {
  assert.match(appJs, /market_data_refresh\?\.incomplete/);
  assert.match(appJs, /Cached prices were used where available/);
});

test('Cached tooltip includes last successful time alongside a supplied warning', () => {
  const source = appJs.match(/function formatPositionPriceCell\(position\) \{[\s\S]*?\n\}/)?.[0];
  assert.ok(source);
  const formatter = vm.runInNewContext(`${source}; formatPositionPriceCell`, {
    formatCurrencyValue: (value) => `$${value}`,
    formatDateTime: () => '11 Nov 2026, 10:00',
    escapeHtml: (value) => value,
  });
  const html = formatter({
    price: 100,
    price_status: 'cached_stale',
    price_warning: 'Saved quote needs refresh.',
    price_last_successful_at: '2026-11-11T10:00:00+00:00',
  });
  assert.match(html, /Saved quote needs refresh\..*Last successful quote: 11 Nov 2026, 10:00/);
});
