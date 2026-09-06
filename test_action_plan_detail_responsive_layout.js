const assert = require('node:assert/strict');
const fs = require('node:fs');
const test = require('node:test');
const vm = require('node:vm');

const stylesCss = fs.readFileSync('static/styles.css', 'utf8').replace(/\r\n/g, '\n');
const appJs = fs.readFileSync('static/app.js', 'utf8').replace(/\r\n/g, '\n');

function cssBlock(selector) {
  const escapedSelector = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const match = stylesCss.match(new RegExp(`(^|\\n)${escapedSelector}\\s*\\{([\\s\\S]*?)\\}`));
  assert.ok(match, `Expected ${selector} CSS rule to exist`);
  return match[2];
}

function renderedDetailSection(title) {
  const match = appJs.match(new RegExp(`<section class="detail-card"><h4>${title}</h4>\\$\\{renderActionPlanMetric(?:List|Rows)\\(\\[([\\s\\S]*?)\\]\\)\\}`));
  assert.ok(match, `Expected ${title} detail section to render metric cards`);
  return match[1];
}

function renderedDetailSectionLabels(title) {
  const section = renderedDetailSection(title);
  return [...section.matchAll(/\['([^']+)'/g)].map((match) => match[1]);
}

function renderedFullDetailSection(title) {
  const start = appJs.indexOf(`<section class="detail-card"><h4>${title}</h4>`);
  assert.notEqual(start, -1, `Expected ${title} detail section to exist`);
  const next = appJs.indexOf('<section class="detail-card"><h4>', start + 1);
  assert.notEqual(next, -1, `Expected ${title} to be followed by another detail section`);
  return appJs.slice(start, next);
}

function renderedMetricRows(title) {
  const section = renderedDetailSection(title);
  const rows = [];
  let current = '';
  let depth = 0;
  for (const line of section.split('\n')) {
    if (!current && !/^\s*\[/.test(line)) continue;
    current += `${line}\n`;
    depth += (line.match(/\[/g) || []).length;
    depth -= (line.match(/\]/g) || []).length;
    if (current && depth <= 0) {
      const labels = [...current.matchAll(/\['([^']+)'/g)].map((labelMatch) => labelMatch[1]);
      if (labels.length) rows.push(labels);
      current = '';
      depth = 0;
    }
  }
  if (current) {
    const labels = [...current.matchAll(/\['([^']+)'/g)].map((labelMatch) => labelMatch[1]);
    if (labels.length) rows.push(labels);
  }
  return rows;
}

function appFunctionSource(name) {
  const start = appJs.indexOf(`function ${name}(`);
  assert.notEqual(start, -1, `Expected ${name} to exist`);
  const bodyStart = appJs.indexOf('{', start);
  let depth = 0;
  for (let index = bodyStart; index < appJs.length; index += 1) {
    if (appJs[index] === '{') depth += 1;
    if (appJs[index] === '}') depth -= 1;
    if (depth === 0) return appJs.slice(start, index + 1);
  }
  throw new Error(`Could not parse ${name}`);
}

function linearAdjustmentFormatters() {
  const context = {
    escapeHtml: (value) => String(value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;'),
    isFiniteNumber: (value) => typeof value === 'number' && Number.isFinite(value),
    formatPercent: (value) => (typeof value !== 'number' || Number.isNaN(value) ? 'N/A' : `${value.toFixed(2)}%`),
  };
  return vm.runInNewContext(`
    ${appFunctionSource('formatLinearPenaltyApplied')}
    ${appFunctionSource('formatLinearBonusApplied')}
    ${appFunctionSource('formatFrontierOptionalityApplied')}
    ${appFunctionSource('formatActionDetailWeight')}
    ({ formatLinearPenaltyApplied, formatLinearBonusApplied, formatFrontierOptionalityApplied, formatActionDetailWeight });
  `, context);
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

test('Linear score metric rows keep fixed logical grouping without horizontal overflow', () => {
  const rowStack = cssBlock('.action-detail-metric-rows');
  assert.match(rowStack, /display:\s*flex/);
  assert.match(rowStack, /flex-direction:\s*column/);
  const cardRow = cssBlock('.linear-score-card-row');
  assert.match(cardRow, /display:\s*flex/);
  assert.match(cardRow, /flex-wrap:\s*wrap/);
  assert.match(cardRow, /justify-content:\s*flex-start/);
  assert.match(cardRow, /max-width:\s*100%/);
  assert.doesNotMatch(cardRow, /1fr/);
  const metricCard = cssBlock('.linear-score-card-row .detail-metric-card');
  assert.match(metricCard, /flex:\s*0 1 200px/);
  assert.match(metricCard, /max-width:\s*220px/);
  assert.match(metricCard, /min-width:\s*170px/);
  assert.match(stylesCss, /@media \(max-width:\s*600px\)[\s\S]*\.linear-score-card-row \.detail-metric-card[\s\S]*flex:\s*1 1 100%[\s\S]*max-width:\s*none/);
});

test('Action Plan Detail containers can shrink inside the app shell', () => {
  assert.match(cssBlock('.layout'), /grid-template-columns:\s*240px minmax\(0,\s*1fr\)/);
  assert.match(cssBlock('.content'), /min-width:\s*0/);
  assert.match(cssBlock('#action-plan-detail-view .detail-card'), /min-width:\s*0/);
  assert.match(cssBlock('#action-plan'), /overflow-x:\s*hidden/);
  assert.match(cssBlock('#action-plan-detail-view,\n#action-plan-detail-content'), /min-width:\s*0/);
});

test('Company Detail renders Frontier Score as autosaving select only', () => {
  const optionsMatch = appJs.match(/const FRONTIER_SCORE_OPTIONS = \[([^\]]+)\];/);
  assert.ok(optionsMatch, 'Expected Frontier Score options constant');
  assert.deepEqual(
    optionsMatch[1].split(',').map((value) => value.trim()),
    ['0', '0.5', '1', '1.5', '2', '2.5', '3', '3.5', '4', '4.5', '5'],
  );

  const renderer = appFunctionSource('renderFrontierOptionalitySection');
  assert.ok(renderer.includes('Frontier Score'));
  assert.ok(renderer.includes('frontier-score-field'));
  assert.ok(renderer.includes('<select id="analysis-frontier-score-select" class="earnings-calendar-select">'));
  assert.ok(renderer.includes('renderFrontierScoreOptions(frontier.score)'));
  assert.ok(!renderer.includes('Frontier Optionality Score'));
  assert.ok(!renderer.includes('Frontier Optionality Notes'));
  assert.ok(!renderer.includes('Edit Frontier Optionality'));
  assert.ok(!renderer.includes('textarea'));
  assert.ok(!renderer.includes('type="number"'));

  const save = appFunctionSource('saveFrontierScore');
  assert.ok(save.includes('JSON.stringify({ frontier_optionality_score: score })'));
  assert.ok(!save.includes('frontier_optionality_notes'));
  assert.ok(appJs.includes("analysisSummary.addEventListener('change'"));
  assert.ok(appJs.includes("target.id === 'analysis-frontier-score-select'"));
  assert.ok(appJs.includes('saveFrontierScore(target.value)'));

  const field = cssBlock('.frontier-score-field');
  assert.match(field, /align-items:\s*start/);
  assert.match(field, /max-width:\s*220px/);
  const compactSelect = cssBlock('.earnings-calendar-date-input,\n.earnings-calendar-select');
  assert.match(compactSelect, /height:\s*36px/);
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
      'Expected Price',
      'Upside',
      'Expected CAGR',
    ],
    'Position vs Target Band': [
      'Current Position Market Value',
      'Target Gap Amount',
      'Target Market Value',
      'Current Position Weight',
      'Target Low',
      'Target Mid',
      'Target High',
      'Gap to Mid',
    ],
    'Linear Target Calculation': [
      'Linear Score',
      'Core Confidence Weight',
      'Core Confidence Net',
      'Core Confidence Score',
      'Upside Weight',
      'Upside',
      'Upside Score',
      'Expected CAGR Weight',
      'Expected CAGR',
      'Expected CAGR Score',
      'Potential Confidence Weight',
      'Potential Confidence Net',
      'Potential Confidence Score',
      'Confidence Quality Weight',
      'Confidence Quality Score',
      'Penalty Factor',
      'Penalty Applied',
      'Rating Bonus Factor',
      'Bonus Applied',
    ],
    'Target Band Calculation': [
      'Current Position Weight',
      'Target Low',
      'Target Mid',
      'Target High',
      'Target Band',
      'Linear Score',
      'Score Allocation Power',
      'Powered Linear Score',
      'Total Powered Linear Score',
      'Target Allocation Pool',
      'Pre-Cap Target Mid',
      'Add Band Tolerance',
      'Trim Band Tolerance',
      'Cap Applied',
      'Cap Reason',
      'Pre-Reserve Target Mid',
      'Reserve Scale Factor',
      'Final Target Mid',
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
  assert.ok(summary.includes("['Current Price', formatActionDetailCurrencyValue(item.current_price, 'USD')]"));
  assert.ok(summary.includes("['Current Market Value', formatActionDetailCurrencyValue(item.current_position_market_value, 'USD')]"));
  assert.ok(summary.includes("['Expected Price', formatActionDetailCurrencyValue(item.expected_price, 'USD')]"));
  assert.ok(summary.includes("['Upside', formatActionDetailPercent(item.upside)]"));
  assert.ok(summary.includes("['Expected CAGR', formatActionDetailPercent(item.expected_cagr)]"));
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
    'Current Weight',
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

test('Position vs Target Band renders exactly the required Linear row fields in order', () => {
  assert.deepEqual(renderedDetailSectionLabels('Position vs Target Band'), [
    'Current Position Market Value',
    'Target Gap Amount',
    'Target Market Value',
    'Current Position Weight',
    'Target Low',
    'Target Mid',
    'Target High',
    'Gap to Mid',
  ]);
});

test('Position vs Target Band sources current Linear target-band values', () => {
  const position = renderedDetailSection('Position vs Target Band');
  assert.ok(position.includes("['Current Position Market Value', formatActionDetailCurrencyValue(item.current_position_market_value, 'USD')]"));
  assert.ok(position.includes("['Target Gap Amount', formatActionDetailCurrencyValue(item.target_gap_amount, 'USD')]"));
  assert.ok(position.includes("['Target Market Value', formatActionDetailCurrencyValue(getLinearTargetMarketValue(item), 'USD')]"));
  assert.ok(position.includes("['Current Position Weight', formatActionDetailPercent(item.current_position_weight)]"));
  assert.ok(position.includes("['Target Low', formatActionDetailPercent(item.target_weight_low)]"));
  assert.ok(position.includes("['Target Mid', formatActionDetailPercent(item.target_weight_mid)]"));
  assert.ok(position.includes("['Target High', formatActionDetailPercent(item.target_weight_high)]"));
  assert.ok(position.includes("['Gap to Mid', formatActionDetailPercent(item.position_gap_to_mid)]"));
});

test('Target Market Value is calculated from portfolio value and Linear target midpoint', () => {
  const helper = appJs.slice(
    appJs.indexOf('function getLinearTargetMarketValue(item)'),
    appJs.indexOf('function renderActionPlanDetail(item)'),
  );
  assert.match(helper, /item\?\.portfolio_value_used \?\? item\?\.total_portfolio_value/);
  assert.match(helper, /item\?\.target_weight_mid/);
  assert.match(helper, /return total \* targetMid \/ 100/);
});

test('Position vs Target Band omits execution, funding, trigger, bucket, and explanation fields', () => {
  const position = renderedDetailSection('Position vs Target Band');
  const labels = renderedDetailSectionLabels('Position vs Target Band');
  for (const obsolete of [
    'Total Portfolio Value Used',
    'Executable Action Amount',
    'Executable Shares',
    'Funding Status',
    'Unfunded Amount',
    'Unfunded Shares',
    'Available Buy Budget',
    'Funding Priority Score',
    'Action Amount to Mid',
    'Desired Action Amount',
    'Desired Whole Shares',
    'Desired Whole-Share Amount',
    'Position Status',
    'Trigger Price',
    'Distance to Trigger',
    'Rating Bucket',
    'Bucket Sizing',
  ]) {
    assert.ok(!labels.includes(obsolete), `Expected Position vs Target Band to omit ${obsolete}`);
  }
  for (const obsolete of [
    'getActionPlanAmountDetailLabel',
    'action_amount_cash_note',
    'minimum_trade_size_reason',
    'whole_share_diagnostic_reason',
    'whole_share_diagnostic_warning',
    '<p>',
    'null',
    'undefined',
    'NaN',
    'Infinity',
    'N/A',
    '2.12%',
    '3.18%',
  ]) {
    assert.ok(!position.includes(obsolete), `Expected Position vs Target Band to omit ${obsolete}`);
  }
});

test('Linear Target Calculation renders score inputs in order with Linear Score first', () => {
  assert.deepEqual(renderedDetailSectionLabels('Linear Target Calculation'), [
    'Linear Score',
    'Core Confidence Weight',
    'Core Confidence Net',
    'Core Confidence Score',
    'Upside Weight',
    'Upside',
    'Upside Score',
    'Expected CAGR Weight',
    'Expected CAGR',
    'Expected CAGR Score',
    'Potential Confidence Weight',
    'Potential Confidence Net',
    'Potential Confidence Score',
    'Confidence Quality Weight',
    'Confidence Quality Score',
    'Penalty Factor',
    'Penalty Applied',
    'Rating Bonus Factor',
    'Bonus Applied',
    'Frontier Score',
    'Frontier Boost Factor',
    'Frontier Boost Applied',
    'Linear Score Before Frontier Boost',
    'Linear Score After Boost',
  ]);
});

test('Linear Target Calculation renders score cards in requested logical rows', () => {
  const section = renderedFullDetailSection('Linear Target Calculation');
  const rowHelper = appFunctionSource('renderActionPlanMetricRows');
  assert.ok(section.includes('renderActionPlanMetricRows'), 'Expected Linear Target Calculation to use row renderer');
  assert.ok(rowHelper.includes('linear-score-card-row'), 'Expected compact Linear score row class');
  assert.ok(rowHelper.includes('detail-metric-card'), 'Expected compact Linear score card class');
  assert.ok(rowHelper.includes('linear-score-card-row-${rowClass(items)}'), 'Expected row count modifier class');
  assert.deepEqual(renderedMetricRows('Linear Target Calculation'), [
    ['Linear Score'],
    ['Core Confidence Weight', 'Core Confidence Net', 'Core Confidence Score'],
    ['Upside Weight', 'Upside', 'Upside Score'],
    ['Expected CAGR Weight', 'Expected CAGR', 'Expected CAGR Score'],
    ['Potential Confidence Weight', 'Potential Confidence Net', 'Potential Confidence Score'],
    ['Confidence Quality Weight', 'Confidence Quality Score'],
    ['Penalty Factor', 'Penalty Applied'],
    ['Rating Bonus Factor', 'Bonus Applied'],
    ['Frontier Score', 'Frontier Boost Factor', 'Frontier Boost Applied'],
    ['Linear Score Before Frontier Boost', 'Linear Score After Boost'],
  ]);
});

test('Linear Target Calculation sources backend Linear score diagnostics', () => {
  const section = renderedDetailSection('Linear Target Calculation');
  assert.ok(section.includes("['Linear Score', formatActionDetailNumber(score.linear_score ?? item.linear_allocation_score)]"));
  assert.ok(section.includes("['Core Confidence Weight', formatActionDetailWeight(weights.linear_core_confidence_weight)]"));
  assert.ok(section.includes("['Core Confidence Net', formatActionDetailNet(item.core_confidence_diff)]"));
  assert.ok(section.includes("['Core Confidence Score', formatActionDetailNumber(score.core_net_score)]"));
  assert.ok(section.includes("['Upside Weight', formatActionDetailWeight(weights.linear_upside_weight)]"));
  assert.ok(section.includes("['Upside', formatActionDetailPercent(item.upside)]"));
  assert.ok(section.includes("['Upside Score', formatActionDetailNumber(score.upside_score)]"));
  assert.ok(section.includes("['Expected CAGR Weight', formatActionDetailWeight(weights.linear_expected_cagr_weight)]"));
  assert.ok(section.includes("['Expected CAGR', formatActionDetailPercent(item.expected_cagr)]"));
  assert.ok(section.includes("['Expected CAGR Score', formatActionDetailNumber(score.expected_cagr_score)]"));
  assert.ok(section.includes("['Potential Confidence Weight', formatActionDetailWeight(weights.linear_potential_confidence_weight)]"));
  assert.ok(section.includes("['Potential Confidence Net', formatActionDetailNet(item.potential_confidence_diff)]"));
  assert.ok(section.includes("['Potential Confidence Score', formatActionDetailNumber(score.potential_net_score)]"));
  assert.ok(section.includes("['Confidence Quality Weight', formatActionDetailWeight(weights.linear_confidence_quality_weight)]"));
  assert.ok(section.includes("['Confidence Quality Score', formatActionDetailNumber(score.confidence_quality_score)]"));
  assert.ok(section.includes("['Penalty Factor', formatActionDetailNumber(score.penalty_factor)]"));
  assert.ok(section.includes("['Penalty Applied', formatLinearPenaltyApplied(score)]"));
  assert.ok(section.includes("['Rating Bonus Factor', formatActionDetailNumber(score.rating_bonus_factor)]"));
  assert.ok(section.includes("['Bonus Applied', formatLinearBonusApplied(score)]"));
  assert.ok(section.includes("['Frontier Score', `${formatActionDetailNumber(score.frontier_optionality_score)} / 5`]"));
  assert.ok(section.includes("['Frontier Boost Factor', formatActionDetailNumber(score.frontier_optionality_boost_factor)]"));
  assert.ok(section.includes("['Frontier Boost Applied', formatFrontierOptionalityApplied(score)]"));
  assert.ok(section.includes("['Linear Score Before Frontier Boost', formatActionDetailNumber(score.linear_score_before_frontier_boost)]"));
  assert.ok(section.includes("['Linear Score After Boost', formatActionDetailNumber(score.linear_score ?? item.linear_allocation_score)]"));
  assert.ok(!section.includes('Frontier Boost Reason'));
  assert.ok(!section.includes('Frontier Optionality Reason'));
  assert.ok(!section.includes('Frontier Optionality Applied Reason'));
});

test('Action Detail omits Decision Path and Action-Relevant Key Variables sections', () => {
  const detailRenderer = appJs.slice(
    appJs.indexOf('function renderActionPlanDetail(item)'),
    appJs.indexOf('async function openActionPlanDetail(symbol)'),
  );
  for (const obsolete of [
    '<h4>Decision Path</h4>',
    '<h4>Action-Relevant Key Variables</h4>',
    'renderDecisionPath',
    'renderActionRelevantVariables',
    'PASS:',
    'FAIL:',
    'RESULT:',
  ]) {
    assert.ok(!detailRenderer.includes(obsolete), `Expected detail renderer to omit ${obsolete}`);
  }
});

test('Linear Target Calculation places adjustment reason cards after their factors', () => {
  const labels = renderedDetailSectionLabels('Linear Target Calculation');
  assert.equal(labels[labels.indexOf('Penalty Factor') + 1], 'Penalty Applied');
  assert.equal(labels[labels.indexOf('Rating Bonus Factor') + 1], 'Bonus Applied');
  assert.equal(labels[labels.indexOf('Rating Bonus Factor') + 2], 'Frontier Score');
});

test('Linear Target Calculation groups each score component as weight input score', () => {
  const labels = renderedDetailSectionLabels('Linear Target Calculation');
  const before = (left, right) => assert.ok(labels.indexOf(left) < labels.indexOf(right), `Expected ${left} before ${right}`);
  before('Core Confidence Weight', 'Core Confidence Net');
  before('Core Confidence Net', 'Core Confidence Score');
  before('Upside Weight', 'Upside');
  before('Upside', 'Upside Score');
  before('Expected CAGR Weight', 'Expected CAGR');
  before('Expected CAGR', 'Expected CAGR Score');
  before('Potential Confidence Weight', 'Potential Confidence Net');
  before('Potential Confidence Net', 'Potential Confidence Score');
  before('Confidence Quality Weight', 'Confidence Quality Score');
});

test('Linear adjustment reason formatters render readable penalty and bonus text', () => {
  const { formatLinearPenaltyApplied, formatLinearBonusApplied, formatFrontierOptionalityApplied, formatActionDetailWeight } = linearAdjustmentFormatters();
  assert.equal(formatLinearPenaltyApplied({ penalties_applied: [], penalty_factor: 1 }), 'None');
  assert.equal(
    formatLinearPenaltyApplied({
      penalties_applied: [{ key: 'core_confidence_penalty', label: 'Core confidence below threshold', penalty: 0.15 }],
      penalty_factor: 0.85,
    }),
    'Core confidence below threshold',
  );
  assert.equal(
    formatLinearPenaltyApplied({
      penalties_applied: [
        { key: 'core_confidence_penalty', label: 'Core confidence below threshold', penalty: 0.15 },
        { key: 'upside_penalty', label: 'Upside below threshold', penalty: 0.2 },
      ],
      penalty_factor: 0.68,
    }),
    'Core confidence below threshold; Upside below threshold',
  );
  assert.equal(formatLinearPenaltyApplied({ penalties_applied: [], penalty_factor: 0.95 }), 'Penalty applied');
  assert.equal(formatLinearBonusApplied({ rating_bonus_reason: 'Buy rating bonus', rating_bonus_factor: 1.01 }), 'Buy rating bonus');
  assert.equal(formatLinearBonusApplied({ rating_bonus_reason: 'Strong Buy rating bonus', rating_bonus_factor: 1.02 }), 'Strong Buy rating bonus');
  assert.equal(formatLinearBonusApplied({ rating_bonus_factor: 1 }), 'No rating bonus');
  assert.equal(formatFrontierOptionalityApplied({ frontier_optionality_applied: true }), 'Yes');
  assert.equal(formatFrontierOptionalityApplied({ frontier_optionality_applied: false, frontier_optionality_applied_reason: 'Sell rating' }), 'No — Sell rating');
  assert.equal(formatFrontierOptionalityApplied({ frontier_optionality_applied: false }), 'No');
  assert.equal(formatActionDetailWeight(0.25), '25.00%');
  assert.equal(formatActionDetailWeight(0.2), '20.00%');
  assert.equal(formatActionDetailWeight(null), '—');
});

test('Linear Target Calculation explanation appears below cards and describes current method', () => {
  const section = renderedFullDetailSection('Linear Target Calculation');
  const metricIndex = section.indexOf('${renderActionPlanMetricRows([');
  const explanationIndex = section.indexOf('<div class="action-detail-explanation">');
  assert.ok(explanationIndex > metricIndex, 'Expected explanation below the card grid');
  for (const text of [
    'How this target is calculated',
    'Expected CAGR',
    'Upside',
    'Core Confidence',
    'Potential Confidence',
    'Confidence Quality',
    'Penalty Factor',
    'Rating Bonus Factor',
    'Frontier Score',
    'stock-specific caps',
    'Dynamic Reserve',
    'band tolerances',
  ]) {
    assert.ok(section.includes(text), `Expected Linear Target explanation to mention ${text}`);
  }
  assert.ok(!section.includes('Bucket Allocation'));
  assert.ok(!section.includes('Trigger Prices'));
});

test('Linear Target Calculation omits bucket, trigger, and old allocation fields', () => {
  const section = renderedFullDetailSection('Linear Target Calculation');
  const labels = renderedDetailSectionLabels('Linear Target Calculation');
  for (const obsolete of [
    'Rating Bucket',
    'Total Weighted Eligible Count in Bucket',
    'Max Effective Count',
    'Weighted Count Used',
    'Bucket Weight / Effective Stock',
    'Uncapped Bucket Target',
    'Bucket Raw Target',
    'Bucket Effective Target',
    'Eligible Count in Bucket',
    'Weighted Count',
    'Bucket Share',
    'Bucket Sizing Score',
    'Bucket Sizing Risk Modifier',
    'Total Bucket Allocation Score',
    'Company Allocation Score',
    'Bucket Score',
    'Allocation Score',
    'Trigger Price',
    'Distance to Trigger',
    'Target Before Caps / Adjustments',
    'Cap Applied',
    'Cap Amount',
    'Cap Reason',
    'Target After Cap Low',
    'Target After Cap Mid',
    'Target After Cap High',
    'Reserve Scale Factor',
    'Final Target Low',
    'Final Target Mid',
    'Final Target High',
    'Final Target Band',
  ]) {
    assert.ok(!labels.includes(obsolete), `Expected Linear Target Calculation to omit ${obsolete}`);
  }
  for (const obsolete of [
    'target_weight_breakdown.rating_bucket',
    'target_weight_breakdown.bucket_',
    'score_breakdown.bucket_',
    'weighted_count',
    'company_bucket_score',
    'null',
    'undefined',
    'NaN',
    'Infinity',
    'N/A',
    '[]',
    '{}',
  ]) {
    assert.ok(!section.includes(obsolete), `Expected Linear Target Calculation to omit ${obsolete}`);
  }
});

test('Linear Score Breakdown section is replaced by Target Band Calculation', () => {
  const detailRenderer = appJs.slice(
    appJs.indexOf('function renderActionPlanDetail(item)'),
    appJs.indexOf('async function openActionPlanDetail(symbol)'),
  );
  assert.ok(!detailRenderer.includes('<h4>Linear Score Breakdown</h4>'));
  assert.ok(detailRenderer.includes('<h4>Target Band Calculation</h4>'));
});

test('Target Band Calculation renders final band and diagnostics in order', () => {
  assert.deepEqual(renderedDetailSectionLabels('Target Band Calculation'), [
    'Current Position Weight',
    'Target Low',
    'Target Mid',
    'Target High',
    'Target Band',
    'Linear Score',
    'Score Allocation Power',
    'Powered Linear Score',
    'Total Powered Linear Score',
    'Target Allocation Pool',
    'Pre-Cap Target Mid',
    'Add Band Tolerance',
    'Trim Band Tolerance',
    'Cap Applied',
    'Cap Reason',
    'Pre-Reserve Target Mid',
    'Reserve Scale Factor',
    'Final Target Mid',
  ]);
});

test('Target Band Calculation sources current Linear target-band diagnostics', () => {
  const section = renderedDetailSection('Target Band Calculation');
  assert.ok(section.includes("['Current Position Weight', formatActionDetailPercent(item.current_position_weight)]"));
  assert.ok(section.includes("['Target Low', formatActionDetailPercent(item.target_weight_low)]"));
  assert.ok(section.includes("['Target Mid', formatActionDetailPercent(item.target_weight_mid)]"));
  assert.ok(section.includes("['Target High', formatActionDetailPercent(item.target_weight_high)]"));
  assert.ok(section.includes("['Target Band', targetBand]"));
  assert.ok(section.includes("['Linear Score', formatActionDetailNumber(score.linear_score ?? item.linear_allocation_score)]"));
  assert.ok(section.includes("['Score Allocation Power', formatActionDetailNumber(item.linear_score_allocation_power)]"));
  assert.ok(section.includes("['Powered Linear Score', formatActionDetailNumber(item.linear_powered_score ?? item.linear_allocation_weight)]"));
  assert.ok(section.includes("['Total Powered Linear Score', formatActionDetailNumber(item.linear_total_powered_score)]"));
  assert.ok(section.includes("['Target Allocation Pool', formatActionDetailPercent(item.linear_target_allocation_pool)]"));
  assert.ok(section.includes("['Pre-Cap Target Mid', formatActionDetailPercent(target.target_before_caps ?? item.linear_target_mid_before_caps ?? item.uncapped_target_mid)]"));
  assert.ok(section.includes("['Add Band Tolerance', formatActionDetailPercent(item.linear_add_band_tolerance_pct)]"));
  assert.ok(section.includes("['Trim Band Tolerance', formatActionDetailPercent(item.linear_trim_band_tolerance_pct)]"));
  assert.ok(section.includes("['Cap Applied', formatActionDetailPercent(target.cap_amount ?? item.cap_applied ?? item.linear_cap_applied)]"));
  assert.ok(section.includes("['Cap Reason', escapeHtml(target.cap_reason || item.cap_reason || item.linear_cap_reason || '—')]"));
  assert.ok(section.includes("['Pre-Reserve Target Mid', formatActionDetailPercent(target.target_after_cap_mid ?? item.pre_reserve_target_mid)]"));
  assert.ok(section.includes("['Reserve Scale Factor', formatActionDetailNumber(target.reserve_scale_factor ?? item.reserve_scale_factor)]"));
  assert.ok(section.includes("['Final Target Mid', formatActionDetailPercent(target.final_target_mid ?? item.target_weight_mid)]"));
});

test('Target Band Calculation explanation appears below cards and describes band method', () => {
  const section = renderedFullDetailSection('Target Band Calculation');
  const metricIndex = section.indexOf('${renderActionPlanMetricList([');
  const explanationIndex = section.indexOf('<div class="action-detail-explanation">');
  assert.ok(explanationIndex > metricIndex, 'Expected Target Band explanation below the card grid');
  for (const text of [
    'How this target band is calculated',
    'Linear Score',
    'Score Allocation Power',
    'powered scores',
    'Dynamic Reserve',
    'Add Band Tolerance',
    'Trim Band Tolerance',
  ]) {
    assert.ok(section.includes(text), `Expected Target Band explanation to mention ${text}`);
  }
  assert.match(section, /stock-specific caps/i);
  assert.ok(!section.includes('Bucket Allocation'));
  assert.ok(!section.includes('Trigger Prices'));
});

test('Target Band Calculation omits score, bucket, trigger, and action labels', () => {
  const section = renderedFullDetailSection('Target Band Calculation');
  const labels = renderedDetailSectionLabels('Target Band Calculation');
  for (const obsolete of [
    'Upside Score',
    'Core Confidence Score',
    'Potential Confidence Score',
    'Expected CAGR Score',
    'Confidence Quality Score',
    'Core Conviction Score',
    'Potential Conviction Score',
    'Core Risk Modifier',
    'Allocation Risk Modifier',
    'Allocation Score',
    'Bucket Sizing Score',
    'Bucket Sizing Risk Modifier',
    'Weighted Count',
    'Company Allocation Score',
    'Total Bucket Allocation Score',
    'Rating Bucket',
    'Bucket Share',
    'Trigger Price',
    'Distance to Trigger',
    'Strong Add',
    'Starter Buy',
    'Strong Trim',
  ]) {
    assert.ok(!labels.includes(obsolete), `Expected Target Band Calculation to omit ${obsolete}`);
  }
  for (const obsolete of [
    'Bucket Allocation',
    'Trigger Prices',
    'null',
    'undefined',
    'NaN',
    'Infinity',
    'N/A',
    '[]',
    '{}',
  ]) {
    assert.ok(!section.includes(obsolete), `Expected Target Band Calculation to omit ${obsolete}`);
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
  assert.match(detailRenderer, /Target Band Calculation/);
  assert.ok(!detailRenderer.includes('Linear Score Breakdown'));
});
