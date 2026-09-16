const assert = require('node:assert/strict');
const test = require('node:test');

const {
  normalizeOwnershipStatus,
  ownershipMatchesPortfolioFilter,
  ownershipBadge,
  ownershipText,
} = require('./static/ownership_status.js');

test('ownership availability is explicit and not inferred from empty positions', () => {
  assert.equal(normalizeOwnershipStatus(true, true), true);
  assert.equal(normalizeOwnershipStatus(false, true), false);
  assert.equal(normalizeOwnershipStatus(false, false), null);
  assert.equal(normalizeOwnershipStatus(true, false), null);
  assert.equal(normalizeOwnershipStatus(undefined, true), null);
});

test('ownership filters match strict true and strict false only', () => {
  assert.equal(ownershipMatchesPortfolioFilter(true, 'in_portfolio'), true);
  assert.equal(ownershipMatchesPortfolioFilter(false, 'in_portfolio'), false);
  assert.equal(ownershipMatchesPortfolioFilter(null, 'in_portfolio'), false);

  assert.equal(ownershipMatchesPortfolioFilter(false, 'not_in_portfolio'), true);
  assert.equal(ownershipMatchesPortfolioFilter(true, 'not_in_portfolio'), false);
  assert.equal(ownershipMatchesPortfolioFilter(null, 'not_in_portfolio'), false);
  assert.equal(ownershipMatchesPortfolioFilter(null, 'all'), true);
});

test('ownership display has distinct unavailable labels', () => {
  assert.deepEqual(ownershipBadge(true), { className: 'badge-portfolio-in', label: 'In Portfolio' });
  assert.deepEqual(ownershipBadge(false), { className: 'badge-portfolio-out', label: 'Not in Portfolio' });
  assert.deepEqual(ownershipBadge(null), { className: 'badge-portfolio-unavailable', label: 'Portfolio unavailable' });
  assert.equal(ownershipText(true), 'Yes');
  assert.equal(ownershipText(false), 'No');
  assert.equal(ownershipText(null), 'Unavailable');
});
