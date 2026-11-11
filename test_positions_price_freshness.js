const assert = require('node:assert/strict');
const fs = require('node:fs');
const test = require('node:test');

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
