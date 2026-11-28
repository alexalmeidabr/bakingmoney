const assert = require('node:assert/strict');
const fs = require('node:fs');
const test = require('node:test');

const appJs = fs.readFileSync('static/app.js', 'utf8');

test('Linear Action Plan renders cached-price warnings as informational current-price context', () => {
  const vm = require('node:vm');
  const functions = appJs.slice(appJs.indexOf('function getActionPlanPriceDisplay'), appJs.indexOf('function updateManualTriggerCurrentPriceReference'));
  const display = vm.runInNewContext(functions + '; getActionPlanPriceDisplay', {formatCurrencyValue: (value) => '$' + value});
  const row = {current_price: 32, price_source: 'analysis_fallback', price_warning: 'Using a saved analysis price.'};
  const result = display(row, false);
  assert.equal(result.price, '$32');
  assert.equal(result.warning, true);
  assert.match(result.title, /analysis fallback.*time unknown.*saved analysis price/);
  assert.match(appJs, /displayedPrice\.warning \? ' ⚠' : ''/);
  assert.match(appJs, /item\.price_refresh_diagnostic \|\| item\.price_warning/);
});
