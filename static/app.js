const menuItems = document.querySelectorAll('.menu-item');
const views = document.querySelectorAll('.view');

const positionsStatusEl = document.getElementById('status');
const positionsTable = document.getElementById('positions-table');
const positionsTableBody = positionsTable.querySelector('tbody');
const refreshBtn = document.getElementById('refresh-btn');
const positionSortHeaders = document.querySelectorAll('#positions-table th.sortable');

const analysisStatusEl = document.getElementById('analysis-status');
const analysisTable = document.getElementById('analysis-table');
const analysisTableBody = analysisTable.querySelector('tbody');
const analysisSortHeaders = document.querySelectorAll('#analysis-table th.sortable');
const analysisSymbolInput = document.getElementById('analysis-symbol-input');
const analysisAddBtn = document.getElementById('analysis-add-btn');
const analysisImportBtn = document.getElementById('analysis-import-btn');

const analysisListView = document.getElementById('analysis-list-view');
const analysisDetailView = document.getElementById('analysis-detail-view');
const analysisBackBtn = document.getElementById('analysis-back-btn');
const analysisDetailTitle = document.getElementById('analysis-detail-title');
const analysisDetailStatus = document.getElementById('analysis-detail-status');
const analysisSummary = document.getElementById('analysis-summary');
const analysisScenariosBody = document.querySelector('#analysis-scenarios-table tbody');
const analysisVariablesBody = document.querySelector('#analysis-variables-table tbody');
const analysisVersionBar = document.getElementById('analysis-version-bar');
const analysisVersionMeta = document.getElementById('analysis-version-meta');
const analysisVersionPrevBtn = document.getElementById('analysis-version-prev-btn');
const analysisVersionNextBtn = document.getElementById('analysis-version-next-btn');
const analysisVersionSelect = document.getElementById('analysis-version-select');
const analysisEditVariablesBtn = document.getElementById('analysis-edit-variables-btn');
const analysisAddVariableBtn = document.getElementById('analysis-add-variable-btn');
const analysisSaveVariablesBtn = document.getElementById('analysis-save-variables-btn');
const analysisCancelVariablesBtn = document.getElementById('analysis-cancel-variables-btn');
const analysisRerunBtn = document.getElementById('analysis-rerun-btn');

const configurationStatusEl = document.getElementById('configuration-status');
const configPromptBusinessModelEl = document.getElementById('config-prompt-business-model');
const configPromptKeyVariablesEl = document.getElementById('config-prompt-key-variables');
const configPromptScenariosEl = document.getElementById('config-prompt-scenarios');
const configSaveBtn = document.getElementById('config-save-btn');
const configResetBtn = document.getElementById('config-reset-btn');
const configPreviewSymbolInput = document.getElementById('config-preview-symbol-input');
const configPreviewBtn = document.getElementById('config-preview-btn');
const configPreviewOutput = document.getElementById('config-preview-output');

let latestPositions = [];
let positionSort = { key: 'symbol', direction: 'asc' };
let latestAnalysis = [];
let analysisSort = { key: 'symbol', direction: 'asc' };
let analysisDetailState = null;
let isEditingVariables = false;

function extractErrorMessage(payload, fallback) {
  if (!payload || typeof payload !== 'object') return fallback;
  return [payload.error, payload.details, payload.debugHint].filter(Boolean).join(' ') || fallback;
}
const formatNumber = (value, digits = 2) => (typeof value !== 'number' || Number.isNaN(value) ? 'N/A' : value.toLocaleString(undefined, { maximumFractionDigits: digits }));
const formatCurrencyValue = (value, currency, digits = 2) => {
  const formatted = formatNumber(value, digits);
  return !currency || formatted === 'N/A' ? formatted : `${formatted} ${currency}`;
};
const formatPercent = (value) => (typeof value !== 'number' || Number.isNaN(value) ? 'N/A' : `${value.toFixed(2)}%`);
const valueClass = (value) => (typeof value !== 'number' || Number.isNaN(value) || value === 0 ? '' : value > 0 ? 'pnl-positive' : 'pnl-negative');
const formatDateTime = (v) => {
  if (!v) return 'N/A';
  const d = new Date(v);
  return Number.isNaN(d.getTime()) ? v : d.toLocaleString();
};

function compareValues(left, right, direction = 'asc') {
  if (left == null && right == null) return 0;
  if (left == null) return 1;
  if (right == null) return -1;
  const result = typeof left === 'number' && typeof right === 'number' ? left - right : String(left).localeCompare(String(right));
  return direction === 'asc' ? result : -result;
}
const sortPositions = (positions) => [...positions].sort((a, b) => compareValues(a[positionSort.key], b[positionSort.key], positionSort.direction));
const sortAnalysis = (items) => [...items].sort((a, b) => compareValues(a[analysisSort.key], b[analysisSort.key], analysisSort.direction));

function updateSortHeaderState() { positionSortHeaders.forEach((h) => { h.dataset.sortDirection = h.dataset.sortKey === positionSort.key ? positionSort.direction : ''; }); }
function updateAnalysisSortHeaderState() { analysisSortHeaders.forEach((h) => { h.dataset.sortDirection = h.dataset.sortKey === analysisSort.key ? analysisSort.direction : ''; }); }

function renderPositions() {
  positionsTableBody.innerHTML = '';
  sortPositions(latestPositions).forEach((position) => {
    const row = document.createElement('tr');
    row.innerHTML = `<td>${position.symbol ?? ''}</td><td>${formatNumber(position.position, 4)}</td><td>${formatCurrencyValue(position.price, position.currency)}</td><td>${formatNumber(position.avgCost)}</td><td class="${valueClass(position.changePercent)}">${formatPercent(position.changePercent)}</td><td>${formatCurrencyValue(position.marketValue, position.currency)}</td><td class="${valueClass(position.unrealizedPnL)}">${formatNumber(position.unrealizedPnL)}</td><td class="${valueClass(position.dailyPnL)}">${formatNumber(position.dailyPnL)}</td>`;
    positionsTableBody.appendChild(row);
  });
}

function renderAnalysisList() {
  analysisTableBody.innerHTML = '';
  sortAnalysis(latestAnalysis).forEach((item) => {
    const row = document.createElement('tr');
    row.innerHTML = `<td><button class="symbol-link" data-symbol="${item.symbol}">${item.symbol}</button></td><td>${formatCurrencyValue(item.current_price, 'USD')}</td><td>${formatCurrencyValue(item.expected_price, 'USD')}</td><td class="${valueClass(item.upside)}">${formatPercent(item.upside)}</td><td>${formatNumber(item.overall_confidence, 2)}</td><td><button class="remove-btn" data-symbol="${item.symbol}">Delete</button></td>`;
    analysisTableBody.appendChild(row);
  });
  analysisTableBody.querySelectorAll('.remove-btn').forEach((btn) => btn.addEventListener('click', async () => deleteAnalysis(btn.dataset.symbol)));
  analysisTableBody.querySelectorAll('.symbol-link').forEach((btn) => btn.addEventListener('click', async () => loadAnalysisDetail(btn.dataset.symbol)));
}

function showAnalysisList() { analysisListView.classList.remove('hidden'); analysisDetailView.classList.add('hidden'); }
function setView(targetView) {
  menuItems.forEach((item) => item.classList.toggle('active', item.dataset.view === targetView));
  views.forEach((view) => view.classList.toggle('active', view.id === targetView));
  if (targetView === 'analysis') { showAnalysisList(); loadAnalysis(); }
  if (targetView === 'positions') loadPositions();
  if (targetView === 'configuration') loadConfiguration();
}
menuItems.forEach((item) => item.addEventListener('click', () => setView(item.dataset.view)));

function selectedVersionIndex() {
  if (!analysisDetailState) return -1;
  return (analysisDetailState.versions || []).findIndex((v) => Number(v.id) === Number(analysisDetailState.selected_version_id));
}

function renderVersionControls() {
  if (!analysisDetailState) return;
  const versions = analysisDetailState.versions || [];
  const idx = selectedVersionIndex();
  analysisVersionBar.classList.remove('hidden');
  analysisVersionSelect.innerHTML = '';
  versions.forEach((version) => {
    const opt = document.createElement('option');
    opt.value = version.id;
    opt.textContent = `V${version.version_number} • ${formatDateTime(version.created_at)}`;
    analysisVersionSelect.appendChild(opt);
  });
  analysisVersionSelect.value = String(analysisDetailState.selected_version_id);
  analysisVersionPrevBtn.disabled = idx <= 0;
  analysisVersionNextBtn.disabled = idx >= versions.length - 1;
  const current = versions[idx];
  analysisVersionMeta.textContent = current ? `Version ${current.version_number} created ${formatDateTime(current.created_at)} (${current.source_trigger || 'unknown'})` : '';
}

function renderAnalysisDetail() {
  const item = analysisDetailState.version;
  analysisDetailTitle.textContent = `Analysis: ${analysisDetailState.symbol}`;
  analysisSummary.innerHTML = `<div class="summary-grid"><div class="summary-item"><div class="label">Symbol</div><div class="value">${item.symbol}</div></div><div class="summary-item"><div class="label">Company Name</div><div class="value">${item.company_name || 'N/A'}</div></div><div class="summary-item"><div class="label">Current Price</div><div class="value">${formatCurrencyValue(item.current_price, 'USD')}</div></div><div class="summary-item"><div class="label">Expected Price</div><div class="value">${formatCurrencyValue(item.expected_price, 'USD')}</div></div><div class="summary-item"><div class="label">Upside</div><div class="value ${valueClass(item.upside)}">${formatPercent(item.upside)}</div></div><div class="summary-item"><div class="label">Confidence Level</div><div class="value">${formatNumber(item.overall_confidence, 2)}</div></div></div><p><strong>Business Model:</strong> ${item.business_model || 'N/A'}</p><p><strong>Business Summary:</strong> ${item.business_summary || 'N/A'}</p><p><strong>Assumptions:</strong> ${item.assumptions || 'N/A'}</p>`;
  analysisSummary.classList.remove('hidden');

  analysisScenariosBody.innerHTML = '';
  (item.scenarios || []).forEach((scenario) => {
    const row = document.createElement('tr');
    row.innerHTML = `<td>${scenario.scenario_name}</td><td>${formatCurrencyValue(scenario.price_low, 'USD')}</td><td>${formatCurrencyValue(scenario.price_high, 'USD')}</td><td>${formatPercent(scenario.cagr_low)}</td><td>${formatPercent(scenario.cagr_high)}</td><td>${formatPercent((scenario.probability || 0) * 100)}</td>`;
    analysisScenariosBody.appendChild(row);
  });

  renderVariablesTable();
  renderVersionControls();
  const edits = analysisDetailState.saved_key_variable_edits;
  const canRerun = edits && Number(edits.based_on_version_id) === Number(item.id);
  analysisRerunBtn.disabled = !canRerun;
}

function renderVariablesTable() {
  const variables = isEditingVariables
    ? (analysisDetailState.saved_key_variable_edits?.based_on_version_id === analysisDetailState.version.id
      ? analysisDetailState.saved_key_variable_edits.key_variables
      : analysisDetailState.version.key_variables)
    : analysisDetailState.version.key_variables;

  analysisVariablesBody.innerHTML = '';
  variables.forEach((variable) => {
    const row = document.createElement('tr');
    const variableType = variable.variable_type || 'Bullish';
    row.innerHTML = isEditingVariables
      ? `<td><input class="var-text var-text-input" type="text" value="${variable.variable_text || ''}"></td><td><select class="var-type"><option value="Bullish" ${variableType === 'Bullish' ? 'selected' : ''}>Bullish</option><option value="Bearish" ${variableType === 'Bearish' ? 'selected' : ''}>Bearish</option></select></td><td><input class="var-confidence" type="number" min="0" max="10" step="1" value="${variable.confidence}"></td><td><input class="var-importance" type="number" min="0" max="10" step="1" value="${variable.importance}"></td><td><button class="var-delete-btn">Delete</button></td>`
      : `<td>${variable.variable_text}</td><td>${variableType}</td><td>${formatNumber(variable.confidence, 2)}</td><td>${formatNumber(variable.importance, 2)}</td><td>—</td>`;
    analysisVariablesBody.appendChild(row);
  });

  if (isEditingVariables) {
    analysisVariablesBody.querySelectorAll('.var-delete-btn').forEach((button) => {
      button.addEventListener('click', () => {
        button.closest('tr')?.remove();
      });
    });
  }

  analysisEditVariablesBtn.classList.toggle('hidden', isEditingVariables);
  analysisAddVariableBtn.classList.toggle('hidden', !isEditingVariables);
  analysisSaveVariablesBtn.classList.toggle('hidden', !isEditingVariables);
  analysisCancelVariablesBtn.classList.toggle('hidden', !isEditingVariables);
}

async function loadAnalysisDetail(symbol, versionId = null) {
  analysisDetailStatus.textContent = `Loading ${symbol} detail…`;
  analysisDetailStatus.className = 'status';
  analysisSummary.classList.add('hidden');
  analysisListView.classList.add('hidden');
  analysisDetailView.classList.remove('hidden');
  isEditingVariables = false;

  try {
    const query = versionId ? `?version_id=${encodeURIComponent(versionId)}` : '';
    const response = await fetch(`/api/analysis/${encodeURIComponent(symbol)}${query}`);
    const payload = await response.json();
    if (!response.ok) throw new Error(extractErrorMessage(payload, 'Unable to load details'));
    analysisDetailState = payload.analysis;
    renderAnalysisDetail();
    analysisDetailStatus.textContent = `Loaded ${symbol} detail.`;
  } catch (error) {
    analysisDetailStatus.textContent = `Error: ${error.message}`;
    analysisDetailStatus.className = 'status error';
  }
}

function collectEditedVariables() {
  return [...analysisVariablesBody.querySelectorAll('tr')].map((row, idx) => ({
    variable_text: row.querySelector('.var-text')?.value?.trim() || '',
    variable_type: row.querySelector('.var-type')?.value || analysisDetailState.version.key_variables[idx]?.variable_type || 'Bullish',
    confidence: Number(row.querySelector('.var-confidence')?.value),
    importance: Number(row.querySelector('.var-importance')?.value),
  }));
}

async function saveEditedVariables() {
  const variables = collectEditedVariables();
  const symbol = analysisDetailState.symbol;
  const versionId = analysisDetailState.version.id;
  analysisDetailStatus.textContent = 'Saving key variable edits…';

  try {
    const response = await fetch(`/api/analysis/${encodeURIComponent(symbol)}/key-variables`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ version_id: versionId, key_variables: variables }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(extractErrorMessage(payload, 'Unable to save key variables'));
    analysisDetailState = payload.analysis;
    isEditingVariables = false;
    renderAnalysisDetail();
    analysisDetailStatus.textContent = 'Key variable edits saved.';
  } catch (error) {
    analysisDetailStatus.textContent = `Error: ${error.message}`;
    analysisDetailStatus.className = 'status error';
  }
}

async function rerunScenarios() {
  const symbol = analysisDetailState.symbol;
  const versionId = analysisDetailState.version.id;
  analysisDetailStatus.textContent = 'Re-running scenarios…';

  try {
    const response = await fetch(`/api/analysis/${encodeURIComponent(symbol)}/rerun-scenarios`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ version_id: versionId }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(extractErrorMessage(payload, 'Unable to re-run scenarios'));
    analysisDetailState = payload.analysis;
    isEditingVariables = false;
    renderAnalysisDetail();
    loadAnalysis();
    analysisDetailStatus.textContent = 'Scenarios re-run and new version created.';
  } catch (error) {
    analysisDetailStatus.textContent = `Error: ${error.message}`;
    analysisDetailStatus.className = 'status error';
  }
}

async function loadPositions() { /* unchanged */
  positionsStatusEl.textContent = 'Loading positions…'; positionsStatusEl.className = 'status'; positionsTable.classList.add('hidden');
  try { const response = await fetch('/api/positions'); const payload = await response.json(); if (!response.ok) throw new Error(extractErrorMessage(payload, 'Request failed'));
    latestPositions = payload.positions || []; if (!latestPositions.length) { positionsTableBody.innerHTML = ''; positionsStatusEl.textContent = 'No positions found.'; return; }
    updateSortHeaderState(); renderPositions(); positionsStatusEl.textContent = `Loaded ${latestPositions.length} position(s).`; positionsTable.classList.remove('hidden');
  } catch (error) { positionsStatusEl.textContent = `Error: ${error.message}`; positionsStatusEl.className = 'status error'; }
}

async function loadAnalysis() {
  analysisStatusEl.textContent = 'Loading analysis…'; analysisStatusEl.className = 'status'; analysisTable.classList.add('hidden');
  try { const response = await fetch('/api/analysis'); const payload = await response.json(); if (!response.ok) throw new Error(extractErrorMessage(payload, 'Request failed'));
    latestAnalysis = payload.analysis || []; analysisTableBody.innerHTML = ''; if (!latestAnalysis.length) { analysisStatusEl.textContent = 'Analysis is empty.'; return; }
    updateAnalysisSortHeaderState(); renderAnalysisList(); analysisStatusEl.textContent = `Loaded ${latestAnalysis.length} analysis symbol(s).`; analysisTable.classList.remove('hidden');
  } catch (error) { analysisStatusEl.textContent = `Error: ${error.message}`; analysisStatusEl.className = 'status error'; }
}

async function addAnalysisSymbol() {
  const symbol = analysisSymbolInput.value.trim().toUpperCase(); if (!symbol) return;
  analysisStatusEl.textContent = `Analyzing ${symbol}…`; analysisStatusEl.className = 'status';
  try { const response = await fetch('/api/analysis', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ symbol }) });
    const payload = await response.json(); if (!response.ok) throw new Error(extractErrorMessage(payload, 'Unable to add analysis'));
    analysisSymbolInput.value = ''; await loadAnalysis();
  } catch (error) { analysisStatusEl.textContent = `Error: ${error.message}`; analysisStatusEl.className = 'status error'; }
}

async function importAnalysisFromPositions() {
  analysisStatusEl.textContent = 'Importing from positions…'; analysisStatusEl.className = 'status';
  try { const response = await fetch('/api/analysis/import-from-positions', { method: 'POST' }); const payload = await response.json();
    if (!response.ok && response.status !== 207) throw new Error(extractErrorMessage(payload, 'Unable to import analysis'));
    await loadAnalysis();
    const importedCount = payload.importedSymbols?.length || 0;
    const skippedCount = payload.skippedSymbols?.length || 0;
    const failedCount = payload.failures?.length || 0;
    if (failedCount) {
      analysisStatusEl.textContent = `Imported ${importedCount} symbol(s), skipped ${skippedCount} existing, ${failedCount} failed.`;
      analysisStatusEl.className = 'status error';
    } else {
      analysisStatusEl.textContent = `Imported ${importedCount} symbol(s), skipped ${skippedCount} existing.`;
      analysisStatusEl.className = 'status';
    }
  } catch (error) { analysisStatusEl.textContent = `Error: ${error.message}`; analysisStatusEl.className = 'status error'; }
}

async function deleteAnalysis(symbol) {
  analysisStatusEl.textContent = `Deleting ${symbol}…`; analysisStatusEl.className = 'status';
  try { const response = await fetch(`/api/analysis/${encodeURIComponent(symbol)}`, { method: 'DELETE' }); const payload = await response.json();
    if (!response.ok) throw new Error(extractErrorMessage(payload, 'Unable to delete')); await loadAnalysis();
  } catch (error) { analysisStatusEl.textContent = `Error: ${error.message}`; analysisStatusEl.className = 'status error'; }
}

async function loadConfiguration() { /* unchanged */
  configurationStatusEl.textContent = 'Loading configuration…'; configurationStatusEl.className = 'status';
  try { const response = await fetch('/api/configuration/prompts'); const payload = await response.json(); if (!response.ok) throw new Error(extractErrorMessage(payload, 'Unable to load configuration'));
    const templates = payload.templates || {}; const sources = payload.sources || {};
    configPromptBusinessModelEl.value = templates.analysis_prompt_business_model || '';
    configPromptKeyVariablesEl.value = templates.analysis_prompt_key_variables || '';
    configPromptScenariosEl.value = templates.analysis_prompt_scenarios || '';
    configurationStatusEl.textContent = `Loaded prompt templates (business=${sources.analysis_prompt_business_model || 'default'}, key=${sources.analysis_prompt_key_variables || 'default'}, scenarios=${sources.analysis_prompt_scenarios || 'default'}).`;
  } catch (error) { configurationStatusEl.textContent = `Error: ${error.message}`; configurationStatusEl.className = 'status error'; }
}

async function saveConfiguration() { /* unchanged */
  configurationStatusEl.textContent = 'Saving configuration…'; configurationStatusEl.className = 'status';
  try { const response = await fetch('/api/configuration/prompts', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ templates: { analysis_prompt_business_model: configPromptBusinessModelEl.value, analysis_prompt_key_variables: configPromptKeyVariablesEl.value, analysis_prompt_scenarios: configPromptScenariosEl.value } }) });
    const payload = await response.json(); if (!response.ok) throw new Error(extractErrorMessage(payload, 'Unable to save configuration')); configurationStatusEl.textContent = 'Configuration saved.';
  } catch (error) { configurationStatusEl.textContent = `Error: ${error.message}`; configurationStatusEl.className = 'status error'; }
}

async function resetConfiguration() {
  configurationStatusEl.textContent = 'Restoring default prompts…'; configurationStatusEl.className = 'status';
  try { const response = await fetch('/api/configuration/prompts/reset', { method: 'POST' }); const payload = await response.json(); if (!response.ok) throw new Error(extractErrorMessage(payload, 'Unable to reset configuration'));
    const templates = payload.templates || {}; configPromptBusinessModelEl.value = templates.analysis_prompt_business_model || ''; configPromptKeyVariablesEl.value = templates.analysis_prompt_key_variables || ''; configPromptScenariosEl.value = templates.analysis_prompt_scenarios || '';
    configurationStatusEl.textContent = 'Default prompts restored.';
  } catch (error) { configurationStatusEl.textContent = `Error: ${error.message}`; configurationStatusEl.className = 'status error'; }
}

async function previewConfiguration() {
  const symbol = configPreviewSymbolInput.value.trim().toUpperCase(); if (!symbol) { configPreviewOutput.textContent = 'Enter a symbol to preview.'; return; }
  configPreviewOutput.textContent = 'Rendering preview…';
  try { const response = await fetch('/api/configuration/prompts/preview', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ symbol }) });
    const payload = await response.json(); if (!response.ok) throw new Error(extractErrorMessage(payload, 'Unable to preview prompt'));
    const rendered = payload.rendered_prompts || {}; configPreviewOutput.textContent = `Symbol: ${payload.symbol}\nPrice: ${payload.price}\n\n[Business Model Prompt]\n${rendered.analysis_prompt_business_model || ''}\n\n[Key Variables Prompt]\n${rendered.analysis_prompt_key_variables || ''}\n\n[Scenarios Prompt]\n${rendered.analysis_prompt_scenarios || ''}`;
  } catch (error) { configPreviewOutput.textContent = `Error: ${error.message}`; }
}

positionSortHeaders.forEach((header) => header.addEventListener('click', () => {
  const { sortKey } = header.dataset; if (!sortKey) return;
  if (positionSort.key === sortKey) positionSort.direction = positionSort.direction === 'asc' ? 'desc' : 'asc'; else positionSort = { key: sortKey, direction: 'asc' };
  updateSortHeaderState(); renderPositions();
}));
analysisSortHeaders.forEach((header) => header.addEventListener('click', () => {
  const { sortKey } = header.dataset; if (!sortKey) return;
  if (analysisSort.key === sortKey) analysisSort.direction = analysisSort.direction === 'asc' ? 'desc' : 'asc'; else analysisSort = { key: sortKey, direction: 'asc' };
  updateAnalysisSortHeaderState(); renderAnalysisList();
}));

refreshBtn.addEventListener('click', loadPositions);
analysisAddBtn.addEventListener('click', addAnalysisSymbol);
analysisImportBtn.addEventListener('click', importAnalysisFromPositions);
analysisSymbolInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') addAnalysisSymbol(); });
analysisBackBtn.addEventListener('click', showAnalysisList);
analysisEditVariablesBtn.addEventListener('click', () => { isEditingVariables = true; renderVariablesTable(); });
analysisAddVariableBtn.addEventListener('click', () => {
  if (!isEditingVariables) return;
  const row = document.createElement('tr');
  row.innerHTML = '<td><input class="var-text var-text-input" type="text" value=""></td><td><select class="var-type"><option value="Bullish" selected>Bullish</option><option value="Bearish">Bearish</option></select></td><td><input class="var-confidence" type="number" min="0" max="10" step="1" value="5"></td><td><input class="var-importance" type="number" min="0" max="10" step="1" value="5"></td><td><button class="var-delete-btn">Delete</button></td>';
  analysisVariablesBody.appendChild(row);
  row.querySelector('.var-delete-btn')?.addEventListener('click', () => row.remove());
  row.querySelector('.var-text')?.focus();
});
analysisCancelVariablesBtn.addEventListener('click', () => { isEditingVariables = false; renderVariablesTable(); });
analysisSaveVariablesBtn.addEventListener('click', saveEditedVariables);
analysisRerunBtn.addEventListener('click', rerunScenarios);
analysisVersionPrevBtn.addEventListener('click', () => {
  const idx = selectedVersionIndex(); const prev = analysisDetailState.versions[idx - 1]; if (prev) loadAnalysisDetail(analysisDetailState.symbol, prev.id);
});
analysisVersionNextBtn.addEventListener('click', () => {
  const idx = selectedVersionIndex(); const next = analysisDetailState.versions[idx + 1]; if (next) loadAnalysisDetail(analysisDetailState.symbol, next.id);
});
analysisVersionSelect.addEventListener('change', () => loadAnalysisDetail(analysisDetailState.symbol, analysisVersionSelect.value));

configSaveBtn.addEventListener('click', saveConfiguration);
configResetBtn.addEventListener('click', resetConfiguration);
configPreviewBtn.addEventListener('click', previewConfiguration);
configPreviewSymbolInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') previewConfiguration(); });

updateSortHeaderState();
updateAnalysisSortHeaderState();
setView('analysis');
