const assert = require('node:assert/strict');
const test = require('node:test');

const {
  parseCalendarDate,
  getMondayWeekRange,
  releaseDateMatchesEarningsCalendarDateFilters,
  earningsCalendarItemMatchesFilters,
  earningsReleaseTimingPriority,
  compareEarningsCalendarItems,
} = require('./static/earnings_calendar_date_filters.js');

const wednesday = new Date(2026, 7, 5, 15, 30);
const matches = (releaseDate, filter, today = wednesday) => (
  releaseDateMatchesEarningsCalendarDateFilters(releaseDate, today, new Set([filter]))
);
const iso = (value) => [
  value.getFullYear(),
  String(value.getMonth() + 1).padStart(2, '0'),
  String(value.getDate()).padStart(2, '0'),
].join('-');

test('week range is fixed to Monday through Sunday', () => {
  const range = getMondayWeekRange(wednesday);
  assert.equal(iso(range.start), '2026-08-03');
  assert.equal(iso(range.end), '2026-08-09');
});

test('Current Week includes Monday', () => {
  assert.equal(matches('2026-08-03', 'current_week'), true);
});

test('Current Week includes Sunday', () => {
  assert.equal(matches('2026-08-09', 'current_week'), true);
});

test('Current Week excludes the previous Sunday', () => {
  assert.equal(matches('2026-08-02', 'current_week'), false);
});

test('Current Week excludes the following Monday', () => {
  assert.equal(matches('2026-08-10', 'current_week'), false);
});

test('Next Week includes next Monday', () => {
  assert.equal(matches('2026-08-10', 'next_week'), true);
});

test('Next Week includes next Sunday', () => {
  assert.equal(matches('2026-08-16', 'next_week'), true);
});

test('Next Week excludes the current Sunday', () => {
  assert.equal(matches('2026-08-09', 'next_week'), false);
});

test('Next Week excludes the Monday after next week', () => {
  assert.equal(matches('2026-08-17', 'next_week'), false);
});

test('Monday starts Current Week and Next Week begins seven days later', () => {
  const monday = new Date(2026, 7, 3, 23, 59);
  assert.equal(matches('2026-08-03', 'current_week', monday), true);
  assert.equal(matches('2026-08-09', 'current_week', monday), true);
  assert.equal(matches('2026-08-10', 'next_week', monday), true);
});

test('Sunday remains in Current Week and Next Week starts the next day', () => {
  const sunday = new Date(2026, 7, 9, 8, 0);
  assert.equal(matches('2026-08-09', 'current_week', sunday), true);
  assert.equal(matches('2026-08-10', 'next_week', sunday), true);
});

test('missing release dates are excluded from week filters', () => {
  assert.equal(matches(null, 'current_week'), false);
  assert.equal(matches('', 'next_week'), false);
});

test('invalid and placeholder release dates are excluded without throwing', () => {
  for (const value of ['not-a-date', '2026-02-30', '0000-00-00', 'TBD']) {
    assert.doesNotThrow(() => matches(value, 'current_week'));
    assert.equal(matches(value, 'current_week'), false);
  }
});

test('existing release date filters retain their behavior', () => {
  assert.equal(matches('2026-08-01', 'past'), true);
  assert.equal(matches('2026-08-04', 'yesterday'), true);
  assert.equal(matches('2026-08-05', 'today'), true);
  assert.equal(matches('2026-08-06', 'tomorrow'), true);
  assert.equal(matches('2026-08-20', 'future'), true);
});

test('week filters combine with portfolio, fiscal year, and quarter filters', () => {
  const filters = {
    today: wednesday,
    selectedDateFilters: new Set(['current_week']),
    portfolioFilter: 'in_portfolio',
    selectedFiscalYears: new Set(['2026']),
    availableYearCount: 2,
    selectedFiscalQuarters: new Set(['Q3']),
    quarterOptionCount: 4,
  };
  const target = { release_date: '2026-08-09', in_portfolio: true, fiscal_year: 2026, fiscal_quarter: 'Q3' };
  assert.equal(earningsCalendarItemMatchesFilters(target, filters), true);
  assert.equal(earningsCalendarItemMatchesFilters({ ...target, release_date: '2026-08-10' }, filters), false);
  assert.equal(earningsCalendarItemMatchesFilters({ ...target, in_portfolio: false }, filters), false);
  assert.equal(earningsCalendarItemMatchesFilters({ ...target, fiscal_quarter: 'Q2' }, filters), false);
});

test('multiple selected date filters preserve existing union behavior', () => {
  const selected = new Set(['today', 'next_week']);
  assert.equal(releaseDateMatchesEarningsCalendarDateFilters('2026-08-05', wednesday, selected), true);
  assert.equal(releaseDateMatchesEarningsCalendarDateFilters('2026-08-12', wednesday, selected), true);
  assert.equal(releaseDateMatchesEarningsCalendarDateFilters('2026-08-08', wednesday, selected), false);
});

test('ISO release dates are parsed as local calendar dates without UTC conversion', () => {
  const parsed = parseCalendarDate('2026-08-03');
  assert.equal(parsed.getFullYear(), 2026);
  assert.equal(parsed.getMonth(), 7);
  assert.equal(parsed.getDate(), 3);
  assert.equal(parsed.getHours(), 0);
});

test('Earnings Calendar dates remain sorted ascending', () => {
  const items = [
    { symbol: 'LATE', release_date: '2026-08-11', release_timing: 'Before Open' },
    { symbol: 'EARLY', release_date: '2026-08-10', release_timing: 'After Close' },
  ];
  items.sort((left, right) => compareEarningsCalendarItems(left, right, 'asc'));
  assert.deepEqual(items.map((item) => item.symbol), ['EARLY', 'LATE']);
});

test('Before Open sorts before After Close on the same date', () => {
  const items = [
    { symbol: 'AMC', release_date: '2026-08-10', release_timing: 'After Close' },
    { symbol: 'BMO', release_date: '2026-08-10', release_timing: 'Before Open' },
  ];
  items.sort(compareEarningsCalendarItems);
  assert.deepEqual(items.map((item) => item.symbol), ['BMO', 'AMC']);
});

test('unknown timing sorts after recognized same-day timings', () => {
  const items = [
    { symbol: 'UNKNOWN', release_date: '2026-08-10', release_timing: 'During Market' },
    { symbol: 'AFTER', release_date: '2026-08-10', release_timing: 'After Close' },
    { symbol: 'BEFORE', release_date: '2026-08-10', release_timing: 'Before Open' },
  ];
  items.sort(compareEarningsCalendarItems);
  assert.deepEqual(items.map((item) => item.symbol), ['BEFORE', 'AFTER', 'UNKNOWN']);
});

test('BMO is treated as Before Open', () => {
  assert.equal(earningsReleaseTimingPriority('BMO'), earningsReleaseTimingPriority('Before Open'));
});

test('AMC is treated as After Close', () => {
  assert.equal(earningsReleaseTimingPriority('AMC'), earningsReleaseTimingPriority('After Close'));
});

test('release timing priority is case-insensitive', () => {
  assert.equal(earningsReleaseTimingPriority('before open'), 0);
  assert.equal(earningsReleaseTimingPriority('BEFORE OPEN'), 0);
  assert.equal(earningsReleaseTimingPriority('after close'), 1);
  assert.equal(earningsReleaseTimingPriority('AFTER CLOSE'), 1);
});

test('same-date and same-priority ties sort deterministically by ticker', () => {
  const items = [
    { symbol: 'ZZZ', release_date: '2026-08-10', release_timing: 'Before Open' },
    { symbol: 'AAA', release_date: '2026-08-10', release_timing: 'BMO' },
  ];
  items.sort(compareEarningsCalendarItems);
  assert.deepEqual(items.map((item) => item.symbol), ['AAA', 'ZZZ']);
});

test('timing sorting works after Current Week and Next Week filtering', () => {
  const items = [
    { symbol: 'CURRENT_AFTER', release_date: '2026-08-09', release_timing: 'AMC' },
    { symbol: 'CURRENT_BEFORE', release_date: '2026-08-09', release_timing: 'BMO' },
    { symbol: 'NEXT_AFTER', release_date: '2026-08-10', release_timing: 'After Close' },
    { symbol: 'NEXT_BEFORE', release_date: '2026-08-10', release_timing: 'before open' },
  ];
  const forFilter = (filter) => items
    .filter((item) => releaseDateMatchesEarningsCalendarDateFilters(item.release_date, wednesday, new Set([filter])))
    .sort(compareEarningsCalendarItems)
    .map((item) => item.symbol);
  assert.deepEqual(forFilter('current_week'), ['CURRENT_BEFORE', 'CURRENT_AFTER']);
  assert.deepEqual(forFilter('next_week'), ['NEXT_BEFORE', 'NEXT_AFTER']);
});
