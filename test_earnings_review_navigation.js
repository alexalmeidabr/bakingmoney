const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const appJs = fs.readFileSync(path.join(__dirname, 'static', 'app.js'), 'utf8');
const indexHtml = fs.readFileSync(path.join(__dirname, 'static', 'index.html'), 'utf8');

function functionBody(name) {
  const start = appJs.indexOf(`function ${name}`);
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

function htmlElementSlice(id) {
  const start = indexHtml.indexOf(`id="${id}"`);
  assert.notEqual(start, -1, `Expected ${id} to exist`);
  const tableStart = indexHtml.lastIndexOf('<table', start);
  const elementStart = tableStart === -1 ? start : tableStart;
  const end = indexHtml.indexOf('</table>', start);
  return indexHtml.slice(elementStart, end === -1 ? indexHtml.length : end);
}

test('Earnings Review navigation has no browser hash behavior', () => {
  assert.doesNotMatch(appJs, /window\.location\.hash|location\.hash/);
  assert.doesNotMatch(appJs, /hashchange/);
  assert.doesNotMatch(appJs, /setEarningsReviewHash/);
  assert.doesNotMatch(appJs, /['"`]#earnings-review(?:\/|['"`])/);
});

test('Earnings Review menu item uses the same internal view pattern as other sections', () => {
  assert.match(indexHtml, /<button class="menu-item" data-view="earnings-review">Earnings Review<\/button>/);
  assert.doesNotMatch(indexHtml, /href="#earnings-review"/);
  assert.match(appJs, /const target = item\.dataset\.view;\s*setView\(target\);/);
  assert.match(appJs, /if \(target === 'earnings-review'\) \{\s*setEarningsReviewTab\('calendar'\);\s*loadEarningsReview\(\);/);
});

test('Earnings Review symbol and detail views render through internal state only', () => {
  const symbolHistoryBody = functionBody('openEarningsReviewSymbolHistory');
  assert.match(symbolHistoryBody, /earningsReviewSelectedSymbol = normalized;/);
  assert.match(symbolHistoryBody, /earningsReviewSelectedRecordId = null;/);
  assert.match(symbolHistoryBody, /showEarningsReviewSymbolHistoryView\(\);/);
  assert.doesNotMatch(symbolHistoryBody, /location\.hash|setEarningsReviewHash/);

  const recordDetailBody = functionBody('openEarningsReviewRecordDetail');
  assert.match(recordDetailBody, /earningsReviewSelectedSymbol = normalized;/);
  assert.match(recordDetailBody, /earningsReviewSelectedRecordId = Number\(reviewId\);/);
  assert.match(recordDetailBody, /showEarningsReviewDetail\(\);/);
  assert.doesNotMatch(recordDetailBody, /location\.hash|setEarningsReviewHash/);
});

test('Earnings Review back navigation remains internal', () => {
  assert.match(appJs, /earningsReviewBackBtn\.addEventListener\('click', async \(\) => \{\s*if \(earningsReviewSelectedSymbol\) \{\s*await openEarningsReviewSymbolHistory\(earningsReviewSelectedSymbol\);/);
  assert.match(appJs, /earningsReviewSymbolBackBtn\.addEventListener\('click', async \(\) => \{\s*await loadEarningsReview\(\);/);
  assert.doesNotMatch(appJs, /earningsReviewBackBtn[\s\S]*location\.hash/);
});

test('Other main navigation and Earnings Review company-detail return paths still exist', () => {
  for (const view of ['analysis', 'positions', 'action-plan', 'earnings-review', 'alerts', 'prompt', 'configuration', 'backup']) {
    assert.match(indexHtml, new RegExp(`data-view="${view}"`));
  }
  assert.match(appJs, /if \(targetView === 'analysis'\) \{ showAnalysisList\(\); if \(!skipLoad\) loadAnalysis\(\); \}/);
  assert.match(appJs, /if \(targetView === 'action-plan' && !skipLoad\) loadActionPlan\(\);/);
  assert.match(appJs, /if \(analysisDetailOrigin === 'earnings_review'\) \{\s*setView\('earnings-review', \{ skipLoad: true \}\);/);
  assert.match(appJs, /showAnalysisDetailFromOriginMenu\('earnings-review'\);/);
});

test('Earnings Review and Calendar remain global when portfolio account changes', () => {
  const reloadBody = functionBody('reloadPortfolioScopedViews');
  assert.doesNotMatch(reloadBody, /activeView === 'earnings-review'/);
  assert.doesNotMatch(reloadBody, /loadEarningsReview\(\)/);

  const calendarBody = functionBody('loadEarningsCalendar');
  assert.match(calendarBody, /fetch\('\/api\/earnings-review\/calendar'\)/);
  assert.doesNotMatch(calendarBody, /withSelectedPortfolioAccount/);
  assert.doesNotMatch(calendarBody, /portfolio_data_available|earningsCalendarOwnershipAvailable|earningsCalendarPortfolioFilter/);

  const reviewListBody = functionBody('refreshEarningsReviewListOnly');
  assert.match(reviewListBody, /fetch\('\/api\/earnings-review'\)/);
  assert.doesNotMatch(reviewListBody, /withSelectedPortfolioAccount/);
});

test('Earnings Calendar and Earnings Review do not render ownership UI', () => {
  assert.doesNotMatch(indexHtml, /earnings-calendar-portfolio-filter/);
  assert.doesNotMatch(htmlElementSlice('earnings-calendar-table'), /<th>Portfolio<\/th>/);
  assert.doesNotMatch(htmlElementSlice('earnings-review-table'), /<th>Portfolio<\/th>/);

  const calendarBody = functionBody('renderEarningsCalendarTable');
  assert.doesNotMatch(calendarBody, /ownershipStatus|in_portfolio|Portfolio unavailable|badge-portfolio/);

  const reviewBody = functionBody('renderEarningsReviewList');
  assert.doesNotMatch(reviewBody, /ownershipStatus|in_portfolio|Portfolio unavailable|ownershipText/);
});

test('Analysis renders unavailable ownership distinctly', () => {
  assert.match(appJs, /latestPositionsOwnershipAvailable \? portfolioSymbols\.has/);
  assert.match(appJs, /ownershipStatus\.ownershipBadge\(item\.inPortfolio\)/);
});
