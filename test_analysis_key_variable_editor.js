const assert = require('node:assert/strict');
const fs = require('node:fs');
const test = require('node:test');
const vm = require('node:vm');

const appJs = fs.readFileSync('static/app.js', 'utf8').replace(/\r\n/g, '\n');
const stylesCss = fs.readFileSync('static/styles.css', 'utf8').replace(/\r\n/g, '\n');

function functionSource(name) {
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

function cssBlock(selector) {
  const escapedSelector = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const match = stylesCss.match(new RegExp(`(^|\\n)${escapedSelector}\\s*\\{([\\s\\S]*?)\\}`));
  assert.ok(match, `Expected ${selector} CSS rule to exist`);
  return match[2];
}

test('Key Variable edit rows use a multiline textarea while preserving the text value selector', () => {
  const renderer = functionSource('renderVariablesTable');
  assert.match(renderer, /<textarea class="var-text var-text-input" rows="1">\$\{escapeHtml\(variable\.variable_text \|\| ''\)\}<\/textarea>/);
  assert.doesNotMatch(renderer, /<input class="var-text var-text-input" type="text"/);
  assert.match(functionSource('syncActiveAnalysisVariableRowsFromDom'), /row\.querySelector\('\.var-text'\)\?\.value/);
});

test('Key Variable editor autosizes existing and edited textareas from content height', () => {
  const autosize = functionSource('autoSizeAnalysisVariableTextarea');
  assert.match(autosize, /textarea\.style\.height\s*=\s*['"]auto['"]/);
  assert.match(autosize, /textarea\.scrollHeight/);
  assert.match(autosize, /textarea\.offsetHeight\s*-\s*textarea\.clientHeight/);
  assert.match(autosize, /textarea\.style\.height\s*=\s*`\$\{textarea\.scrollHeight\s*\+\s*borderHeight\}px`/);

  const renderer = functionSource('renderVariablesTable');
  assert.match(renderer, /querySelectorAll\('\.var-text-input'\)[\s\S]*autoSizeAnalysisVariableTextarea/);
  assert.match(renderer, /textarea\.addEventListener\('input',[\s\S]*autoSizeAnalysisVariableTextarea/);
});

test('Key Variable autosizing includes textarea borders when using border-box sizing', () => {
  const autoSize = vm.runInNewContext(`
    ${functionSource('autoSizeAnalysisVariableTextarea')}
    autoSizeAnalysisVariableTextarea;
  `);
  const textarea = {
    style: {},
    scrollHeight: 100,
    offsetHeight: 106,
    clientHeight: 100,
  };

  autoSize(textarea);

  assert.equal(textarea.style.height, '106px');
});

test('Key Variable textarea styles wrap and shrink within the existing Variable column', () => {
  const textarea = cssBlock('#analysis-variables-table .var-text-input');
  assert.match(textarea, /width:\s*100%/);
  assert.match(textarea, /min-width:\s*0/);
  assert.match(textarea, /box-sizing:\s*border-box/);
  assert.match(textarea, /line-height:\s*1\.35/);
  assert.match(textarea, /overflow-y:\s*hidden/);
  assert.match(textarea, /white-space:\s*pre-wrap/);
  assert.match(textarea, /overflow-wrap:\s*anywhere/);
  assert.match(textarea, /resize:\s*none/);

  const firstColumn = cssBlock('#analysis-variables-table th:nth-child(1),\n#analysis-variables-table td:nth-child(1)');
  assert.match(firstColumn, /width:\s*40%/);
});
