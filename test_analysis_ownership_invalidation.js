const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const appJs = fs.readFileSync(path.join(__dirname, 'static', 'app.js'), 'utf8');

function functionBody(name) {
  const match = new RegExp(`(?:async\\s+)?function\\s+${name}\\s*\\(`).exec(appJs);
  const start = match ? match.index : -1;
  assert.notEqual(start, -1, `Expected ${name} to exist`);
  const bodyStart = appJs.indexOf('{', start);
  let depth = 0;
  for (let index = bodyStart; index < appJs.length; index += 1) {
    const char = appJs[index];
    if (char === '{') depth += 1;
    if (char === '}') depth -= 1;
    if (depth === 0) return appJs.slice(bodyStart + 1, index);
  }
  throw new Error(`Unable to parse ${name}`);
}

test('portfolio account change invalidates Analysis ownership before reloading account-scoped data', () => {
  const changeBody = functionBody('handlePortfolioAccountChange');
  assert.match(changeBody, /invalidateAnalysisOwnershipState\(\);/);
  assert.ok(
    changeBody.indexOf('invalidateAnalysisOwnershipState();') < changeBody.indexOf("clearPositionsDisplay('', 'status');"),
    'Analysis ownership must be invalidated before positions are cleared and reloaded',
  );

  const invalidateBody = functionBody('invalidateAnalysisOwnershipState');
  assert.match(invalidateBody, /latestPositionsOwnershipAvailable = false;/);
  assert.match(invalidateBody, /latestPositions = \[\];/);
  assert.match(invalidateBody, /portfolioFilter = 'all';/);
  assert.match(invalidateBody, /analysisPortfolioFilterEl\.disabled = true;/);
  assert.match(invalidateBody, /latestAnalysis = enrichAnalysisWithPortfolioStatus\(latestAnalysis\);/);
  assert.match(invalidateBody, /getActiveViewId\(\) === 'analysis'/);
  assert.match(invalidateBody, /renderAnalysisList\(\);/);
});

test('loadAnalysis failures cannot retain previous true or false ownership state', () => {
  const loadBody = functionBody('loadAnalysis');
  assert.match(loadBody, /catch \(error\) \{[\s\S]*invalidateAnalysisOwnershipState\(\);/);
  assert.match(loadBody, /positionsPayload\?\.code === 'account_not_found'[\s\S]*invalidateAnalysisOwnershipState\(\);/);
  assert.match(loadBody, /positionsPayload\?\.code === 'portfolio_data_unavailable'[\s\S]*invalidateAnalysisOwnershipState\(\);/);
  assert.doesNotMatch(loadBody, /catch \(error\) \{ analysisStatusEl\.textContent = `Error:/);
});

test('stale Analysis ownership responses are ignored after account switches', () => {
  assert.match(appJs, /let analysisOwnershipRequestId = 0;/);

  const changeBody = functionBody('handlePortfolioAccountChange');
  assert.match(changeBody, /analysisOwnershipRequestId \+= 1;/);

  const loadBody = functionBody('loadAnalysis');
  assert.match(loadBody, /const ownershipRequestId = analysisOwnershipRequestId \+= 1;/);
  assert.match(loadBody, /const requestAccountId = selectedPortfolioAccountId;/);
  assert.match(loadBody, /const ownershipRequestCurrent = \(\) => ownershipRequestId === analysisOwnershipRequestId && requestAccountId === selectedPortfolioAccountId;/);
  assert.match(loadBody, /if \(positionsResponse\?\.ok && ownershipRequestCurrent\(\)\) \{/);
  assert.match(loadBody, /if \(positionsResponse\?\.ok && ownershipRequestCurrent\(\)\) \{[\s\S]*latestPositions = mergePositionsWithAnalysis/);
});

test('Analysis rows render when positions request fails but analysis succeeds', () => {
  const loadBody = functionBody('loadAnalysis');
  assert.match(loadBody, /Promise\.allSettled/);
  assert.match(loadBody, /analysisResult\.status !== 'fulfilled'/);
  assert.match(loadBody, /positionsResult\.status === 'fulfilled'/);
  assert.match(loadBody, /positionsError/);
  assert.match(loadBody, /analysisStatusEl\.textContent = positionsError\s+\? `Loaded \$\{latestAnalysis\.length\} analysis symbol\(s\)\. Portfolio ownership unavailable: \$\{positionsError\.message\}`/);
  assert.doesNotMatch(loadBody, /Promise\.all\(\[/);
});
