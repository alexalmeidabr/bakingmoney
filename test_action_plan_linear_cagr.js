const assert = require('node:assert/strict');
const fs = require('node:fs');
const test = require('node:test');

const {
  formatCagrPercent,
  getLinearCagrValue,
  sortRowsByNumericValue,
} = require('./static/action_plan_sorting.js');

const indexHtml = fs.readFileSync('static/index.html', 'utf8');
const appJs = fs.readFileSync('static/app.js', 'utf8');

function tableHeaders(tableId) {
  const tableMatch = indexHtml.match(new RegExp(`<table[^>]+id="${tableId}"[\\s\\S]*?</table>`));
  assert.ok(tableMatch, `Expected table ${tableId} to exist`);
  const headerMatch = tableMatch[0].match(/<thead>[\s\S]*?<\/thead>/);
  assert.ok(headerMatch, `Expected table ${tableId} to include a header`);
  return [...headerMatch[0].matchAll(/<th\b[^>]*>([\s\S]*?)<\/th>/g)].map((match) =>
    match[1].replace(/<[^>]+>/g, '').trim()
  );
}

function sortByLinearCagr(rows, direction) {
  return sortRowsByNumericValue(rows, {
    direction,
    getValue: getLinearCagrValue,
  });
}

test('Linear Allocation action table has the shared 19-column layout', () => {
  const headers = tableHeaders('action-plan-linear-actions-table');
  assert.deepEqual(headers, [
    'Symbol', 'Action', 'Market Value', 'Target Gap', 'Action Amount', 'Shares', 'Funding',
    'Current Price', 'Rating', 'Release Date', 'Upside', 'CAGR', 'Core Confidence',
    'Potential Confidence', 'Momentum', 'Current Weight', 'Target Band', 'Gap to Mid',
    'Linear Score',
  ]);
});

test('Action Plan exposes only the Linear Allocation table', () => {
  assert.equal(indexHtml.includes('id="action-plan-linear-detail-table"'), false);
  assert.equal(indexHtml.includes('id="action-plan-table"'), false);
  assert.equal(indexHtml.includes('id="action-plan-tab-buckets"'), false);
});

test('Linear CAGR uses the same expected CAGR shown in Action Detail', () => {
  assert.equal(getLinearCagrValue({ expected_equity_cagr: 7.6, expected_cagr: 12.43 }), 12.43);
  assert.equal(getLinearCagrValue({ expected_cagr: 8 }), 8);
  assert.equal(getLinearCagrValue({ expected_equity_cagr: 8 }), null);
});

test('Linear CAGR formats percentages and invalid values safely', () => {
  assert.equal(formatCagrPercent(12.44), '12.4%');
  assert.equal(formatCagrPercent(8), '8.0%');
  assert.equal(formatCagrPercent(-3.45), '-3.5%');
  for (const value of [null, undefined, Number.NaN, Number.POSITIVE_INFINITY, 'bad']) {
    assert.equal(formatCagrPercent(value), '—');
  }
});

test('Linear CAGR sorting is numeric ascending with missing values last', () => {
  const rows = [
    { symbol: 'MISSING', expected_cagr: null },
    { symbol: 'HIGH', expected_cagr: 12.4 },
    { symbol: 'LOW', expected_cagr: -3.5 },
    { symbol: 'MID', expected_cagr: 8 },
    { symbol: 'FOUR', expected_cagr: 4 },
  ];
  assert.deepEqual(sortByLinearCagr(rows, 'asc').map((row) => row.symbol), ['LOW', 'FOUR', 'MID', 'HIGH', 'MISSING']);
});

test('Linear CAGR sorting is numeric descending with missing values last', () => {
  const rows = [
    { symbol: 'MISSING', expected_cagr: null },
    { symbol: 'HIGH', expected_cagr: 12.4 },
    { symbol: 'LOW', expected_cagr: -3.5 },
    { symbol: 'MID', expected_cagr: 8 },
    { symbol: 'FOUR', expected_cagr: 4 },
  ];
  assert.deepEqual(sortByLinearCagr(rows, 'desc').map((row) => row.symbol), ['HIGH', 'MID', 'FOUR', 'LOW', 'MISSING']);
});

test('Linear CAGR uses table precision and sorts by its displayed field', () => {
  assert.equal(formatCagrPercent(getLinearCagrValue({ expected_equity_cagr: 7.6, expected_cagr: 12.43 })), '12.4%');
  assert.ok(appJs.includes("if (key === 'expected_cagr')"));
  assert.ok(indexHtml.includes('data-sort-key="expected_cagr"'));
});
