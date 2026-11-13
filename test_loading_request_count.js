const assert = require('node:assert/strict');
const fs = require('node:fs');
const test = require('node:test');

const source = fs.readFileSync('static/app.js', 'utf8');
const positions = source.slice(source.indexOf('async function loadPositions('), source.indexOf('async function loadAnalysis('));
const analysis = source.slice(source.indexOf('async function loadAnalysis('), source.indexOf('async function rerunSelectedSymbolsScenarios('));

test('My Positions uses enriched positions without a redundant full analysis request', () => {
  assert.doesNotMatch(positions, /fetch\('\/api\/analysis'\)/);
  assert.match(positions, /latestPositions = positionsPayload\.positions \|\| \[\]/);
});

test('Analysis loads ownership through the lightweight selected-account response', () => {
  assert.match(analysis, /withSelectedPortfolioAccount\('\/api\/positions\?ownership=1'\)/);
  assert.match(analysis, /fetch\('\/api\/analysis'\)/);
});

test('Analysis ownership responses cannot replace full My Positions rows', () => {
  const ownershipSymbols = source.slice(source.indexOf('function getPortfolioSymbols('), source.indexOf('function enrichAnalysisWithPortfolioStatus('));
  assert.match(analysis, /latestAnalysisOwnershipPositions = positionsPayload\.positions \|\| \[\]/);
  assert.doesNotMatch(analysis, /latestPositions = positionsPayload\.positions \|\| \[\]/);
  assert.match(ownershipSymbols, /latestAnalysisOwnershipPositions/);
});
