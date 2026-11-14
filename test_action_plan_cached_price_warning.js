const assert = require('node:assert/strict');
const fs = require('node:fs');
const test = require('node:test');

const appJs = fs.readFileSync('static/app.js', 'utf8');

test('Linear Action Plan renders cached-price warnings as informational current-price context', () => {
  assert.match(appJs, /item\.price_warning \|\| \(item\.price_source === 'analysis_fallback'/);
  assert.match(appJs, /displayedPrice\.warning \? ' ⚠' : ''/);
  assert.match(appJs, /item\.price_refresh_diagnostic \|\| item\.price_warning/);
});
