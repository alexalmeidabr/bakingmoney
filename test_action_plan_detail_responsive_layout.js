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

test('primary Action Plan Detail metric sections still render all existing fields', () => {
  const expectedLabelsBySection = {
    'Action Summary': [
      'Symbol',
      'Company Name',
      'Action',
      'Target Gap Amount',
      'Raw Action Amount',
      'Desired Whole Shares',
      'Desired Whole-Share Amount',
      'Executable Action Amount',
      'Shares',
      'Funding Status',
      'Action Amount',
      'Rating',
      'Expected Price',
      'Upside',
      'Current Weight',
      'Target Mid',
      'Target Band',
      'Gap to Mid',
      'Trigger Price',
      'Distance to Trigger',
    ],
    'Position vs Target Band': [
      'Total Portfolio Value Used',
      'Current Position Market Value',
      'Current Position Weight',
      'Target Low',
      'Target Mid',
      'Target High',
      'Target Gap Amount',
      'Executable Action Amount',
      'Funding Status',
      'Action Amount to Mid',
    ],
    'Trigger Prices': [
      'Position Status',
      'Starter Buy Trigger',
      'Add Trigger',
      'Strong Add Trigger',
      'Trim Trigger',
      'Sell Trigger',
      'Relevant Trigger',
      'Relevant Trigger Type',
      'Dynamic Required Upside',
      'Trigger Quality Score',
      'Distance to Relevant Trigger',
    ],
  };

  for (const [section, labels] of Object.entries(expectedLabelsBySection)) {
    const renderedSection = renderedDetailSection(section);
    for (const label of labels) {
      assert.ok(renderedSection.includes(`['${label}'`), `Expected ${section} to keep ${label}`);
    }
  }
});
