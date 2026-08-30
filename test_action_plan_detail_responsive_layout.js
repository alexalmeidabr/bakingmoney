const assert = require('node:assert/strict');
const fs = require('node:fs');
const test = require('node:test');

const stylesCss = fs.readFileSync('static/styles.css', 'utf8');
const appJs = fs.readFileSync('static/app.js', 'utf8');

function cssBlock(selector) {
  const escapedSelector = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const match = stylesCss.match(new RegExp(`(^|\\n)${escapedSelector}\\s*\\{([\\s\\S]*?)\\}`));
  assert.ok(match, `Expected ${selector} CSS rule to exist`);
  return match[2];
}

function renderedDetailSection(title) {
  const match = appJs.match(new RegExp(`<section class="detail-card"><h4>${title}</h4>\\$\\{renderActionPlanMetricList\\(\\[([\\s\\S]*?)\\]\\)\\}`));
  assert.ok(match, `Expected ${title} detail section to render metric cards`);
  return match[1];
}

function renderedDetailSectionLabels(title) {
  const section = renderedDetailSection(title);
  return [...section.matchAll(/\['([^']+)'/g)].map((match) => match[1]);
}

test('Action Plan Detail metrics use a responsive shrinkable grid', () => {
  const metrics = cssBlock('.action-detail-metrics');
  assert.match(metrics, /display:\s*grid/);
  assert.match(metrics, /repeat\(auto-fit,\s*minmax\(min\(180px,\s*100%\),\s*1fr\)\)/);
  assert.match(metrics, /max-width:\s*100%/);
  assert.match(metrics, /min-width:\s*0/);

  assert.match(cssBlock('.action-detail-metrics div'), /min-width:\s*0/);
  assert.match(cssBlock('.action-detail-metrics dd'), /overflow-wrap:\s*anywhere/);
});

test('Action Plan Detail containers can shrink inside the app shell', () => {
  assert.match(cssBlock('.layout'), /grid-template-columns:\s*240px minmax\(0,\s*1fr\)/);
  assert.match(cssBlock('.content'), /min-width:\s*0/);
  assert.match(cssBlock('#action-plan-detail-view .detail-card'), /min-width:\s*0/);
  assert.match(cssBlock('#action-plan'), /overflow-x:\s*hidden/);
  assert.match(cssBlock('#action-plan-detail-view,\n#action-plan-detail-content'), /min-width:\s*0/);
});

test('modern Linear Action Plan Detail sections keep responsive metric cards', () => {
  const expectedLabelsBySection = {
    'Action Summary': [
      'Symbol',
      'Company Name',
      'Action',
      'Action Amount',
      'Action Shares Amount',
      'Rating',
      'Current Price',
      'Current Market Value',
      'Current Weight',
      'Expected Price',
      'Upside',
      'Expected CAGR',
    ],
    'Position vs Target Band': [
      'Total Portfolio Value Used',
      'Current Position Market Value',
      'Current Position Weight',
      'Position Status',
      'Target Low',
      'Target Mid',
      'Target High',
      'Gap to Mid',
      'Target Gap Amount',
      'Desired Action Amount',
      'Desired Whole Shares',
      'Desired Whole-Share Amount',
      'Executable Action Amount',
      'Executable Shares',
      'Funding Status',
      'Unfunded Amount',
      'Unfunded Shares',
      'Available Buy Budget',
    ],
    'Linear Target Calculation': [
      'Linear Score',
      'Target Before Caps / Adjustments',
      'Cap Applied',
      'Cap Reason',
      'Target After Cap Mid',
      'Reserve Scale Factor',
      'Final Target Low',
      'Final Target Mid',
      'Final Target High',
      'Final Target Band',
    ],
    'Linear Score Breakdown': [
      'Expected CAGR Score',
      'Upside Score',
      'Core Confidence Score',
      'Potential Confidence Score',
      'Confidence Quality Score',
      'Penalty Factor',
      'Rating Bonus Factor',
      'Linear Score',
    ],
  };

  for (const [section, labels] of Object.entries(expectedLabelsBySection)) {
    const renderedSection = renderedDetailSection(section);
    for (const label of labels) {
      assert.ok(renderedSection.includes(`['${label}'`), `Expected ${section} to keep ${label}`);
    }
  }
});

test('Action Summary renders exactly the required Linear row fields in order', () => {
  assert.deepEqual(renderedDetailSectionLabels('Action Summary'), [
    'Symbol',
    'Company Name',
    'Action',
    'Action Amount',
    'Action Shares Amount',
    'Rating',
    'Current Price',
    'Current Market Value',
    'Current Weight',
    'Expected Price',
    'Upside',
    'Expected CAGR',
  ]);
});

test('Action Summary sources action, amount, shares, and market values from the Linear row item', () => {
  const summary = renderedDetailSection('Action Summary');
  assert.ok(summary.includes("['Action', escapeHtml(item.action || 'Hold')]"));
  assert.ok(summary.includes("['Action Amount', escapeHtml(item.action_amount_label || '—')]"));
  assert.ok(summary.includes("['Action Shares Amount', formatSuggestedShareCount(item)]"));
  assert.ok(summary.includes("['Current Price', formatCurrencyValue(item.current_price, 'USD')]"));
  assert.ok(summary.includes("['Current Market Value', formatCurrencyValue(item.current_position_market_value, 'USD')]"));
  assert.ok(summary.includes("['Current Weight', formatPercent(item.current_position_weight)]"));
  assert.ok(summary.includes("['Expected Price', formatCurrencyValue(item.expected_price, 'USD')]"));
  assert.ok(summary.includes("['Upside', formatPercent(item.upside)]"));
  assert.ok(summary.includes("['Expected CAGR', formatPercent(item.expected_cagr)]"));
});

test('Action Summary omits old target, funding, trigger, and explanation fields', () => {
  const summary = renderedDetailSection('Action Summary');
  const labels = renderedDetailSectionLabels('Action Summary');
  for (const obsolete of [
    'Release Date',
    'Target Low',
    'Target Mid',
    'Target High',
    'Target Band',
    'Gap to Mid',
    'Target Gap Amount',
    'Funding Status',
    'Linear Score',
    'Trigger Price',
    'Distance to Trigger',
    'Shares',
  ]) {
    assert.ok(!labels.includes(obsolete), `Expected Action Summary to omit ${obsolete}`);
  }
  for (const obsolete of [
    'linear_explanation',
    'reason',
    '<p>',
  ]) {
    assert.ok(!summary.includes(obsolete), `Expected Action Summary to omit ${obsolete}`);
  }
});

test('Linear Action Plan Detail omits obsolete trigger and bucket UI', () => {
  const detailRenderer = appJs.slice(
    appJs.indexOf('function renderActionPlanDetail(item)'),
    appJs.indexOf('async function openActionPlanDetail(symbol)'),
  );
  for (const obsolete of [
    'Trigger Prices',
    'Starter Buy Trigger',
    'Relevant Trigger',
    'Distance to Trigger',
    'Target Weight Calculation',
    'Rating Bucket',
    'Bucket Sizing',
    'Weighted Count',
    'Strong Add',
    'Starter Buy',
    'Strong Trim',
    'position reduction rule',
  ]) {
    assert.ok(!detailRenderer.includes(obsolete), `Expected detail renderer to omit ${obsolete}`);
  }
  assert.match(detailRenderer, /linear_allocation_score/);
  assert.match(detailRenderer, /linear_target_breakdown/);
  assert.match(detailRenderer, /linear_score_breakdown/);
});
