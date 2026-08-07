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

test('Linear Allocation action table includes CAGR between Upside and Core Confidence', () => {
  const headers = tableHeaders('action-plan-linear-actions-table');
  assert.ok(headers.includes('CAGR'));
  assert.ok(headers.includes('Rating'));
  assert.ok(headers.includes('Upside'));
  assert.ok(headers.includes('Core Confidence'));
  assert.ok(headers.includes('Potential Confidence'));
  assert.equal(headers[headers.indexOf('Upside') + 1], 'CAGR');
  assert.ok(headers.indexOf('CAGR') < headers.indexOf('Core Confidence'));
});

test('Linear Allocation detail table also keeps CAGR immediately after Upside', () => {
  const headers = tableHeaders('action-plan-linear-detail-table');
  assert.equal(headers[headers.indexOf('Upside') + 1], 'CAGR');
  assert.ok(headers.indexOf('CAGR') < headers.indexOf('Core Net'));
});

test('Bucket Allocation table remains unchanged by the Linear CAGR column', () => {
  const headers = tableHeaders('action-plan-table');
  assert.ok(headers.includes('Upside'));
  assert.ok(headers.includes('Core Confidence'));
  assert.equal(headers.includes('CAGR'), false);
  assert.equal(headers[headers.indexOf('Upside') + 1], 'Core Confidence');
});

test('Linear CAGR uses expected_equity_cagr before legacy expected CAGR fields', () => {
  assert.equal(getLinearCagrValue({ expected_equity_cagr: 12.4, expected_cagr: 99 }), 12.4);
  assert.equal(getLinearCagrValue({ expected_cagr: 8 }), 8);
  assert.equal(getLinearCagrValue({ weighted_expected_cagr: -3.5 }), -3.5);
  assert.equal(getLinearCagrValue({ scenario_expected_cagr: 4 }), 4);
  assert.equal(getLinearCagrValue({ expected_equity_cagr: null, expected_cagr: 8 }), null);
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
    { symbol: 'MISSING', expected_equity_cagr: null },
    { symbol: 'HIGH', expected_equity_cagr: 12.4 },
    { symbol: 'LOW', expected_equity_cagr: -3.5 },
    { symbol: 'MID', expected_equity_cagr: 8 },
    { symbol: 'FOUR', expected_equity_cagr: 4 },
  ];
  assert.deepEqual(sortByLinearCagr(rows, 'asc').map((row) => row.symbol), ['LOW', 'FOUR', 'MID', 'HIGH', 'MISSING']);
});

test('Linear CAGR sorting is numeric descending with missing values last', () => {
  const rows = [
    { symbol: 'MISSING', expected_equity_cagr: null },
    { symbol: 'HIGH', expected_equity_cagr: 12.4 },
    { symbol: 'LOW', expected_equity_cagr: -3.5 },
    { symbol: 'MID', expected_equity_cagr: 8 },
    { symbol: 'FOUR', expected_equity_cagr: 4 },
  ];
  assert.deepEqual(sortByLinearCagr(rows, 'desc').map((row) => row.symbol), ['HIGH', 'MID', 'FOUR', 'LOW', 'MISSING']);
});

test('Linear renderer uses the CAGR source and never stringifies invalid numeric sentinels', () => {
  assert.ok(appJs.includes('getLinearCagrValue(item)'));
  assert.ok(appJs.includes('formatLinearCagrPercent(item)'));
  assert.ok(appJs.includes('cagr-cell ${valueClass(cagr)}'));
  assert.ok(indexHtml.includes('data-sort-key="expected_equity_cagr"'));
});
