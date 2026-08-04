const assert = require('node:assert/strict');
const test = require('node:test');

const {
  getTargetBandMidpoint,
  sortRowsByNumericValue,
} = require('./static/action_plan_sorting.js');

function sortByTargetBand(items, direction = 'asc', secondaryKey = null) {
  return sortRowsByNumericValue(items, {
    direction,
    getValue: getTargetBandMidpoint,
    getSecondaryValue: secondaryKey ? (item) => item[secondaryKey] : null,
    secondaryDirection: 'desc',
  });
}

test('uses explicit bucket and linear midpoint fields without parsing display text', () => {
  assert.equal(getTargetBandMidpoint({ target_weight_low: 4, target_weight_mid: 6, target_weight_high: 8, target_band: '100% – 200%' }), 6);
  assert.equal(getTargetBandMidpoint({ linear_target_weight_low: 5, linear_target_weight_mid: 7, linear_target_weight_high: 9, target_weight_mid: 6 }), 7);
});

test('falls back to a complete numeric low/high pair', () => {
  assert.equal(getTargetBandMidpoint({ target_weight_low: 4, target_weight_high: 8 }), 6);
  assert.equal(getTargetBandMidpoint({ linear_target_weight_low: '5', linear_target_weight_high: '9' }), 7);
  assert.equal(getTargetBandMidpoint({ target_weight_low: 4, target_weight_mid: 6 }), null);
  assert.equal(getTargetBandMidpoint({ target_weight_low: 'bad', target_weight_high: 8 }), null);
  assert.equal(getTargetBandMidpoint({ target_weight_low: 4, target_weight_mid: 'bad', target_weight_high: 8 }), null);
});

test('orders the documented ranges by raw decimal midpoint in both directions', () => {
  const rows = [
    { symbol: 'MID', target_weight_low: 4, target_weight_high: 6, display: '4.0%–6.0%' },
    { symbol: 'HIGH', target_weight_low: 8, target_weight_high: 12, display: '8.0%–12.0%' },
    { symbol: 'LOW', target_weight_low: 1.5, target_weight_high: 2.5, display: '1.5%–2.5%' },
    { symbol: 'DECIMAL', target_weight_low: 2.25, target_weight_high: 4.75, display: '2.25%–4.75%' },
  ];
  assert.deepEqual(sortByTargetBand(rows, 'asc').map((row) => row.symbol), ['LOW', 'DECIMAL', 'MID', 'HIGH']);
  assert.deepEqual(sortByTargetBand(rows, 'desc').map((row) => row.symbol), ['HIGH', 'MID', 'DECIMAL', 'LOW']);
});

test('sorts numerically rather than lexically', () => {
  const rows = [
    { symbol: 'TWENTY', target_weight_low: 19, target_weight_mid: 20, target_weight_high: 21 },
    { symbol: 'THREE', target_weight_low: 2, target_weight_mid: 3, target_weight_high: 4 },
    { symbol: 'ELEVEN', target_weight_low: 10, target_weight_mid: 11, target_weight_high: 12 },
  ];
  assert.deepEqual(sortByTargetBand(rows).map((row) => row.symbol), ['THREE', 'ELEVEN', 'TWENTY']);
  assert.deepEqual(sortByTargetBand(rows, 'desc').map((row) => row.symbol), ['TWENTY', 'ELEVEN', 'THREE']);
});

test('keeps missing and invalid target bands last in both directions', () => {
  const rows = [
    { symbol: 'MISSING' },
    { symbol: 'VALID', target_weight_low: 4, target_weight_mid: 5, target_weight_high: 6 },
    { symbol: 'INVALID', target_weight_low: 'bad', target_weight_mid: 'not-a-number', target_weight_high: 6 },
  ];
  assert.equal(sortByTargetBand(rows, 'asc')[0].symbol, 'VALID');
  assert.equal(sortByTargetBand(rows, 'desc')[0].symbol, 'VALID');
});

test('preserves secondary ordering and uses ticker as the final deterministic tie-break', () => {
  const rows = [
    { symbol: 'ZZZ', target_weight_low: 4, target_weight_mid: 5, target_weight_high: 6, target_gap_amount: 20 },
    { symbol: 'BBB', target_weight_low: 3, target_weight_mid: 5, target_weight_high: 7, target_gap_amount: 40 },
    { symbol: 'AAA', target_weight_low: 2, target_weight_mid: 5, target_weight_high: 8, target_gap_amount: 40 },
  ];
  assert.deepEqual(sortByTargetBand(rows, 'asc', 'target_gap_amount').map((row) => row.symbol), ['AAA', 'BBB', 'ZZZ']);
});

test('the shared sorter still handles other numeric columns', () => {
  const rows = [{ symbol: 'B', current_weight: 8 }, { symbol: 'A', current_weight: 2 }];
  const sorted = sortRowsByNumericValue(rows, { getValue: (row) => row.current_weight });
  assert.deepEqual(sorted.map((row) => row.symbol), ['A', 'B']);
});

test('target band sorting composes with filtering', () => {
  const rows = [
    { symbol: 'KEEP_HIGH', action: 'Add', target_weight_low: 8, target_weight_high: 12 },
    { symbol: 'DROP', action: 'Trim', target_weight_low: 1, target_weight_high: 2 },
    { symbol: 'KEEP_LOW', action: 'Add', target_weight_low: 4, target_weight_high: 6 },
  ];
  const filtered = rows.filter((row) => row.action === 'Add');
  assert.deepEqual(sortByTargetBand(filtered).map((row) => row.symbol), ['KEEP_LOW', 'KEEP_HIGH']);
});
