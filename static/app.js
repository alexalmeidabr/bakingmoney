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
const analysisSelectAllEl = document.getElementById('analysis-select-all');
const analysisSymbolInput = document.getElementById('analysis-symbol-input');
const analysisPortfolioFilterEl = document.getElementById('analysis-portfolio-filter');
const analysisAddBtn = document.getElementById('analysis-add-btn');
const analysisImportBtn = document.getElementById('analysis-import-btn');
const analysisRefreshPricesBtn = document.getElementById('analysis-refresh-prices-btn');
const analysisRerunSelectedBtn = document.getElementById('analysis-rerun-selected-btn');

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
const analysisScenarioInfoBtn = document.getElementById('analysis-scenario-info-btn');
const analysisScenarioInfoModal = document.getElementById('analysis-scenario-info-modal');
const analysisScenarioInfoText = document.getElementById('analysis-scenario-info-text');
const analysisScenarioInfoCloseBtn = document.getElementById('analysis-scenario-info-close-btn');

const promptStatusEl = document.getElementById('prompt-status');
const promptBusinessModelEl = document.getElementById('prompt-business-model');
const promptKeyVariablesEl = document.getElementById('prompt-key-variables');
const promptScenariosEl = document.getElementById('prompt-scenarios');
const promptSaveBtn = document.getElementById('prompt-save-btn');
const promptResetBtn = document.getElementById('prompt-reset-btn');
const promptPreviewSymbolInput = document.getElementById('prompt-preview-symbol-input');
const promptPreviewBtn = document.getElementById('prompt-preview-btn');
const promptPreviewOutput = document.getElementById('prompt-preview-output');

const configurationStatusEl = document.getElementById('configuration-status');
const configIbPriceWaitSecondsEl = document.getElementById('config-ib-price-wait-seconds');
const configScenarioMultiPassEnabledEl = document.getElementById('config-scenario-multi-pass-enabled');
const configScenarioPassCountEl = document.getElementById('config-scenario-pass-count');
const configSaveBtn = document.getElementById('config-save-btn');

let latestPositions = [];
let positionSort = { key: 'symbol', direction: 'asc' };
let latestAnalysis = [];
let analysisSort = { key: 'upside', direction: 'desc' };
let portfolioFilter = 'all';
let selectedAnalysisSymbols = new Set();
let analysisDetailState = null;
let isEditingVariables = false;
let isEditingBusinessModel = false;

const POSITIONS_CACHE_KEY = 'bakingmoney.latestPositions';

function loadCachedPositions() {
  try {
    const raw = localStorage.getItem(POSITIONS_CACHE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch (_error) {
    return [];
  }
}

function saveCachedPositions(positions) {
  try {
    localStorage.setItem(POSITIONS_CACHE_KEY, JSON.stringify(Array.isArray(positions) ? positions : []));
  } catch (_error) {
    // Ignore localStorage write failures.
  }
}

latestPositions = loadCachedPositions();

async function getScenarioPassCountForStatus() {
  try {
    const response = await fetch('/api/configuration/general');
    const payload = await response.json();
    if (!response.ok) return 1;
    const settings = payload.settings || {};
    if (!settings.scenario_multi_pass_enabled) return 1;
    const count = Number(settings.scenario_pass_count || 1);
    return Number.isFinite(count) && count > 1 ? Math.floor(count) : 1;
  } catch (_error) {
    return 1;
  }
}

function buildScenarioStatusMessage(symbol, passCount) {
  const suffix = passCount > 1 ? ` (multi-pass: ${passCount})` : '';
  return `Building scenarios for ${symbol}${suffix}…`;
}

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
const formatConfidencePair = (bullish, bearish) => `${formatNumber(bullish, 2)} / ${formatNumber(bearish, 2)}`;
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

function getPortfolioSymbols() {
  return new Set(
    latestPositions
      .filter((position) => Number(position?.position) > 0)
      .map((position) => String(position.symbol || '').toUpperCase())
      .filter(Boolean),
  );
}

function enrichAnalysisWithPortfolioStatus(items) {
  const portfolioSymbols = getPortfolioSymbols();
  return items.map((item) => ({
    ...item,
    inPortfolio: portfolioSymbols.has(String(item.symbol || '').toUpperCase()),
  }));
}

function getFilteredAnalysisItems() {
  if (portfolioFilter === 'in_portfolio') return latestAnalysis.filter((item) => item.inPortfolio === true);
  if (portfolioFilter === 'not_in_portfolio') return latestAnalysis.filter((item) => item.inPortfolio === false);
  return latestAnalysis;
}

function renderAnalysisList() {
  analysisTableBody.innerHTML = '';
  sortAnalysis(getFilteredAnalysisItems()).forEach((item) => {
    const row = document.createElement('tr');
    row.innerHTML = `<td><input type="checkbox" class="analysis-row-select" data-symbol="${item.symbol}" ${selectedAnalysisSymbols.has(item.symbol) ? 'checked' : ''}></td><td><button class="symbol-link" data-symbol="${item.symbol}">${item.symbol}</button></td><td>V${item.analysis_version || 'N/A'} / ${item.scenario_pass_count || 1}</td><td>${formatCurrencyValue(item.current_price, 'USD')}</td><td>${formatCurrencyValue(item.expected_price, 'USD')}</td><td class="${valueClass(item.upside)}">${formatPercent(item.upside)}</td><td><span class="badge ${item.inPortfolio ? 'badge-portfolio-in' : 'badge-portfolio-out'}">${item.inPortfolio ? 'In Portfolio' : 'Not in Portfolio'}</span></td><td>${formatConfidencePair(item.bullish_confidence, item.bearish_confidence)}</td><td><button class="remove-btn" data-symbol="${item.symbol}">Delete</button></td>`;
    analysisTableBody.appendChild(row);
  });
  analysisTableBody.querySelectorAll('.remove-btn').forEach((btn) => btn.addEventListener('click', async () => deleteAnalysis(btn.dataset.symbol)));
  analysisTableBody.querySelectorAll('.symbol-link').forEach((btn) => btn.addEventListener('click', async () => loadAnalysisDetail(btn.dataset.symbol)));
  analysisTableBody.querySelectorAll('.analysis-row-select').forEach((checkbox) => {
    checkbox.addEventListener('change', () => {
      const symbol = checkbox.dataset.symbol;
      if (checkbox.checked) selectedAnalysisSymbols.add(symbol);
      else selectedAnalysisSymbols.delete(symbol);
      syncSelectAllCheckbox();
    });
  });
  syncSelectAllCheckbox();
}

function syncSelectAllCheckbox() {
  const selectable = getFilteredAnalysisItems().map((item) => item.symbol);
  if (!selectable.length) {
    analysisSelectAllEl.checked = false;
    return;
  }
  analysisSelectAllEl.checked = selectable.every((symbol) => selectedAnalysisSymbols.has(symbol));
}

function showAnalysisList() { analysisListView.classList.remove('hidden'); analysisDetailView.classList.add('hidden'); }
function setView(targetView) {
  menuItems.forEach((item) => item.classList.toggle('active', item.dataset.view === targetView));
  views.forEach((view) => view.classList.toggle('active', view.id === targetView));
  if (targetView === 'analysis') { showAnalysisList(); loadAnalysis(); }
  if (targetView === 'positions') loadPositions();
  if (targetView === 'prompt') loadPromptConfiguration();
  if (targetView === 'configuration') loadGeneralConfiguration();
}
menuItems.forEach((item) => item.addEventListener('click', () => setView(item.dataset.view)));


function getEffectiveBusinessModel() {
  const businessModelEdit = analysisDetailState?.saved_business_model_edit;
  if (businessModelEdit && Number(businessModelEdit.based_on_version_id) === Number(analysisDetailState.version.id)) {
    return businessModelEdit.business_model || '';
  }
  return analysisDetailState?.version?.business_model || '';
}

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
    const effectiveBusinessModel = getEffectiveBusinessModel();
  const businessModelSection = isEditingBusinessModel
    ? `<div class="business-model-editor"><label><strong>Business Model:</strong></label><textarea id="analysis-business-model-input" class="analysis-business-model-input" rows="5">${effectiveBusinessModel}</textarea><div class="table-actions"><button id="analysis-business-model-save-btn">Save</button><button id="analysis-business-model-cancel-btn">Cancel</button></div></div>`
    : `<div class="business-model-editor"><p><strong>Business Model:</strong> ${effectiveBusinessModel || 'N/A'}</p><button id="analysis-business-model-edit-btn">Edit Business Model</button></div>`;
  analysisSummary.innerHTML = `<div class="summary-grid"><div class="summary-item"><div class="label">Symbol</div><div class="value">${item.symbol}</div></div><div class="summary-item"><div class="label">Company Name</div><div class="value">${item.company_name || 'N/A'}</div></div><div class="summary-item"><div class="label">Current Price</div><div class="value">${formatCurrencyValue(item.current_price, 'USD')}</div></div><div class="summary-item"><div class="label">Expected Price</div><div class="value">${formatCurrencyValue(item.expected_price, 'USD')}</div></div><div class="summary-item"><div class="label">Upside</div><div class="value ${valueClass(item.upside)}">${formatPercent(item.upside)}</div></div><div class="summary-item"><div class="label">Confidence</div><div class="value">${formatConfidencePair(item.bullish_confidence, item.bearish_confidence)}</div></div></div>${businessModelSection}<p><strong>Business Summary:</strong> ${item.business_summary || 'N/A'}</p><p><strong>Assumptions:</strong> ${item.assumptions || 'N/A'}</p>`;
  analysisSummary.classList.remove('hidden');

  analysisScenariosBody.innerHTML = '';
  (item.scenarios || []).forEach((scenario) => {
    const row = document.createElement('tr');
    row.innerHTML = `<td>${scenario.scenario_name}</td><td>${formatCurrencyValue(scenario.price_low, 'USD')}</td><td>${formatCurrencyValue(scenario.price_high, 'USD')}</td><td>${formatPercent(scenario.cagr_low)}</td><td>${formatPercent(scenario.cagr_high)}</td><td>${formatPercent((scenario.probability || 0) * 100)}</td>`;
    analysisScenariosBody.appendChild(row);
  });

  renderVariablesTable();
  renderVersionControls();
  analysisRerunBtn.disabled = false;

  const passes = item.scenario_passes || [];
  const passLines = passes.map((p) => `Pass ${p.pass_index}: status=${p.validation_status}${p.is_outlier ? ' outlier=true' : ''}${p.rejection_reason ? ` reason=${p.rejection_reason}` : ''}${typeof p.quality_score === 'number' ? ` score=${p.quality_score.toFixed(2)}` : ''}`);
  analysisScenarioInfoText.textContent = `Prompt used to build scenarios:\n${item.scenario_prompt || 'N/A'}\n\nScenario build passes:\n${passLines.length ? passLines.join('\n') : 'No pass details available.'}`;
}

function renderVariablesTable() {
  const hasSavedEditsForVersion = analysisDetailState.saved_key_variable_edits?.based_on_version_id === analysisDetailState.version.id;
  const variables = hasSavedEditsForVersion
    ? analysisDetailState.saved_key_variable_edits.key_variables
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
  isEditingBusinessModel = false;

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

async function saveEditedBusinessModel() {
  const symbol = analysisDetailState.symbol;
  const versionId = analysisDetailState.version.id;
  const businessModel = document.getElementById('analysis-business-model-input')?.value?.trim() || '';
  if (!businessModel) {
    analysisDetailStatus.textContent = 'Business model cannot be empty.';
    analysisDetailStatus.className = 'status error';
    return;
  }

  analysisDetailStatus.textContent = 'Saving business model edit…';
  analysisDetailStatus.className = 'status';
  try {
    const response = await fetch(`/api/analysis/${encodeURIComponent(symbol)}/business-model`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ version_id: versionId, business_model: businessModel }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(extractErrorMessage(payload, 'Unable to save business model'));
    analysisDetailState = payload.analysis;
    isEditingBusinessModel = false;
    renderAnalysisDetail();
    analysisDetailStatus.textContent = 'Business model edit saved.';
  } catch (error) {
    analysisDetailStatus.textContent = `Error: ${error.message}`;
    analysisDetailStatus.className = 'status error';
  }
}

function cancelEditedBusinessModel() {
  isEditingBusinessModel = false;
  renderAnalysisDetail();
  analysisDetailStatus.textContent = 'Business model editing canceled.';
  analysisDetailStatus.className = 'status';
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
    isEditingBusinessModel = false;
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
    isEditingBusinessModel = false;
    renderAnalysisDetail();
    loadAnalysis();
    analysisDetailStatus.textContent = 'Scenarios re-run and new version created.';
  } catch (error) {
    analysisDetailStatus.textContent = `Error: ${error.message}`;
    analysisDetailStatus.className = 'status error';
  }
}

async function loadPositions() {
  positionsStatusEl.textContent = 'Loading positions…';
  positionsStatusEl.className = 'status';
  positionsTable.classList.add('hidden');

  try {
    const response = await fetch('/api/positions');
    const payload = await response.json();
    if (!response.ok) throw new Error(extractErrorMessage(payload, 'Request failed'));

    latestPositions = payload.positions || [];
    saveCachedPositions(latestPositions);

    if (!latestPositions.length) {
      positionsTableBody.innerHTML = '';
      positionsStatusEl.textContent = 'No positions found.';
      return;
    }

    updateSortHeaderState();
    renderPositions();
    positionsStatusEl.textContent = `Loaded ${latestPositions.length} position(s).`;
    positionsTable.classList.remove('hidden');
  } catch (error) {
    if (latestPositions.length) {
      updateSortHeaderState();
      renderPositions();
      positionsTable.classList.remove('hidden');
      positionsStatusEl.textContent = `Warning: ${error.message} Showing latest loaded positions.`;
      positionsStatusEl.className = 'status error';
      return;
    }

    positionsStatusEl.textContent = `Error: ${error.message}`;
    positionsStatusEl.className = 'status error';
  }
}

async function loadAnalysis() {
  analysisStatusEl.textContent = 'Loading analysis…'; analysisStatusEl.className = 'status'; analysisTable.classList.add('hidden');
  try {
    const [analysisResponse, positionsResponse] = await Promise.all([
      fetch('/api/analysis'),
      fetch('/api/positions'),
    ]);
    const analysisPayload = await analysisResponse.json();
    const positionsPayload = await positionsResponse.json();
    if (!analysisResponse.ok) throw new Error(extractErrorMessage(analysisPayload, 'Request failed'));
    latestPositions = positionsResponse.ok ? (positionsPayload.positions || []) : latestPositions;
    if (positionsResponse.ok) saveCachedPositions(latestPositions);

    latestAnalysis = enrichAnalysisWithPortfolioStatus(analysisPayload.analysis || []);
    analysisTableBody.innerHTML = '';
    selectedAnalysisSymbols = new Set([...selectedAnalysisSymbols].filter((symbol) => latestAnalysis.some((item) => item.symbol === symbol)));
    if (!latestAnalysis.length) { analysisStatusEl.textContent = 'Analysis is empty.'; syncSelectAllCheckbox(); return; }
    updateAnalysisSortHeaderState();
    renderAnalysisList();
    analysisStatusEl.textContent = `Loaded ${latestAnalysis.length} analysis symbol(s).`;
    analysisTable.classList.remove('hidden');
  } catch (error) { analysisStatusEl.textContent = `Error: ${error.message}`; analysisStatusEl.className = 'status error'; }
}

async function rerunSelectedSymbolsScenarios() {
  const symbols = [...selectedAnalysisSymbols];
  if (!symbols.length) {
    analysisStatusEl.textContent = 'Select at least one symbol first.';
    analysisStatusEl.className = 'status error';
    return;
  }

  analysisStatusEl.textContent = `Preparing scenario rerun for ${symbols.length} symbol(s)…`;
  analysisStatusEl.className = 'status';
  try {
    const scenarioPassCount = await getScenarioPassCountForStatus();
    let okCount = 0;
    let failCount = 0;
    for (const symbol of symbols) {
      analysisStatusEl.textContent = buildScenarioStatusMessage(symbol, scenarioPassCount);
      try {
        const detailResponse = await fetch(`/api/analysis/${encodeURIComponent(symbol)}`);
        const detailPayload = await detailResponse.json();
        if (!detailResponse.ok) throw new Error(extractErrorMessage(detailPayload, 'Unable to load symbol detail'));
        const versionId = detailPayload.analysis?.selected_version_id;
        if (!versionId) throw new Error('Missing version id');

        const rerunResponse = await fetch(`/api/analysis/${encodeURIComponent(symbol)}/rerun-scenarios`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ version_id: versionId }),
        });
        const rerunPayload = await rerunResponse.json();
        if (!rerunResponse.ok) throw new Error(extractErrorMessage(rerunPayload, 'Unable to re-run scenarios'));
        okCount += 1;
      } catch (error) {
        console.error(`Failed rerun for ${symbol}:`, error);
        failCount += 1;
      }
    }

    await loadAnalysis();
    analysisStatusEl.textContent = failCount ? `Re-ran ${okCount} symbol(s), ${failCount} failed.` : `Re-ran scenarios for ${okCount} symbol(s).`;
    analysisStatusEl.className = failCount ? 'status error' : 'status';
  } catch (error) {
    analysisStatusEl.textContent = `Error: ${error.message}`;
    analysisStatusEl.className = 'status error';
  }
}

async function addAnalysisSymbol() {
  const symbol = analysisSymbolInput.value.trim().toUpperCase(); if (!symbol) return;
  analysisStatusEl.className = 'status';
  const scenarioPassCount = await getScenarioPassCountForStatus();
  analysisStatusEl.textContent = buildScenarioStatusMessage(symbol, scenarioPassCount);
  try { const response = await fetch('/api/analysis', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ symbol }) });
    const payload = await response.json(); if (!response.ok) throw new Error(extractErrorMessage(payload, 'Unable to add analysis'));
    analysisSymbolInput.value = ''; await loadAnalysis();
    analysisStatusEl.textContent = `Analysis completed for ${symbol}.`;
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

async function refreshAnalysisPrices() {
  analysisStatusEl.textContent = 'Updating current prices…'; analysisStatusEl.className = 'status';
  try {
    const response = await fetch('/api/analysis/refresh-prices', { method: 'POST' });
    const payload = await response.json();
    if (!response.ok) throw new Error(extractErrorMessage(payload, 'Unable to refresh analysis prices'));
    latestAnalysis = enrichAnalysisWithPortfolioStatus(payload.analysis || []);
    updateAnalysisSortHeaderState();
    renderAnalysisList();
    analysisTable.classList.toggle('hidden', latestAnalysis.length === 0);
    analysisStatusEl.textContent = `Updated ${payload.updated || 0} symbol(s), skipped ${payload.skipped || 0}.`;
  } catch (error) {
    analysisStatusEl.textContent = `Error: ${error.message}`;
    analysisStatusEl.className = 'status error';
  }
}

async function deleteAnalysis(symbol) {
  analysisStatusEl.textContent = `Deleting ${symbol}…`; analysisStatusEl.className = 'status';
  try { const response = await fetch(`/api/analysis/${encodeURIComponent(symbol)}`, { method: 'DELETE' }); const payload = await response.json();
    if (!response.ok) throw new Error(extractErrorMessage(payload, 'Unable to delete')); await loadAnalysis();
  } catch (error) { analysisStatusEl.textContent = `Error: ${error.message}`; analysisStatusEl.className = 'status error'; }
}

async function loadPromptConfiguration() {
  promptStatusEl.textContent = 'Loading prompt configuration…';
  promptStatusEl.className = 'status';
  try { const response = await fetch('/api/configuration/prompts'); const payload = await response.json(); if (!response.ok) throw new Error(extractErrorMessage(payload, 'Unable to load prompt configuration'));
    const templates = payload.templates || {}; const sources = payload.sources || {};
    promptBusinessModelEl.value = templates.analysis_prompt_business_model || '';
    promptKeyVariablesEl.value = templates.analysis_prompt_key_variables || '';
    promptScenariosEl.value = templates.analysis_prompt_scenarios || '';
    promptStatusEl.textContent = `Loaded prompt templates (business=${sources.analysis_prompt_business_model || 'default'}, key=${sources.analysis_prompt_key_variables || 'default'}, scenarios=${sources.analysis_prompt_scenarios || 'default'}).`;
  } catch (error) { promptStatusEl.textContent = `Error: ${error.message}`; promptStatusEl.className = 'status error'; }
}

async function savePromptConfiguration() {
  promptStatusEl.textContent = 'Saving prompts…'; promptStatusEl.className = 'status';
  try { const response = await fetch('/api/configuration/prompts', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ templates: { analysis_prompt_business_model: promptBusinessModelEl.value, analysis_prompt_key_variables: promptKeyVariablesEl.value, analysis_prompt_scenarios: promptScenariosEl.value } }) });
    const payload = await response.json(); if (!response.ok) throw new Error(extractErrorMessage(payload, 'Unable to save prompts')); promptStatusEl.textContent = 'Prompts saved.';
  } catch (error) { promptStatusEl.textContent = `Error: ${error.message}`; promptStatusEl.className = 'status error'; }
}

async function resetPromptConfiguration() {
  promptStatusEl.textContent = 'Restoring default prompts…'; promptStatusEl.className = 'status';
  try { const response = await fetch('/api/configuration/prompts/reset', { method: 'POST' }); const payload = await response.json(); if (!response.ok) throw new Error(extractErrorMessage(payload, 'Unable to reset prompts'));
    const templates = payload.templates || {}; promptBusinessModelEl.value = templates.analysis_prompt_business_model || ''; promptKeyVariablesEl.value = templates.analysis_prompt_key_variables || ''; promptScenariosEl.value = templates.analysis_prompt_scenarios || '';
    promptStatusEl.textContent = 'Default prompts restored.';
  } catch (error) { promptStatusEl.textContent = `Error: ${error.message}`; promptStatusEl.className = 'status error'; }
}

async function previewPromptConfiguration() {
  const symbol = promptPreviewSymbolInput.value.trim().toUpperCase(); if (!symbol) { promptPreviewOutput.textContent = 'Enter a symbol to preview.'; return; }
  promptPreviewOutput.textContent = 'Rendering preview…';
  try { const response = await fetch('/api/configuration/prompts/preview', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ symbol }) });
    const payload = await response.json(); if (!response.ok) throw new Error(extractErrorMessage(payload, 'Unable to preview prompt'));
    const rendered = payload.rendered_prompts || {}; promptPreviewOutput.textContent = `Symbol: ${payload.symbol}
Price: ${payload.price}

[Business Model Prompt]
${rendered.analysis_prompt_business_model || ''}

[Key Variables Prompt]
${rendered.analysis_prompt_key_variables || ''}

[Scenarios Prompt]
${rendered.analysis_prompt_scenarios || ''}`;
  } catch (error) { promptPreviewOutput.textContent = `Error: ${error.message}`; }
}

async function loadGeneralConfiguration() {
  configurationStatusEl.textContent = 'Loading configuration…'; configurationStatusEl.className = 'status';
  try { const response = await fetch('/api/configuration/general'); const payload = await response.json(); if (!response.ok) throw new Error(extractErrorMessage(payload, 'Unable to load configuration'));
    const settings = payload.settings || {};
    configIbPriceWaitSecondsEl.value = settings.ib_price_wait_seconds ?? 5;
    configScenarioMultiPassEnabledEl.checked = Boolean(settings.scenario_multi_pass_enabled);
    configScenarioPassCountEl.value = settings.scenario_pass_count || 1;
    configurationStatusEl.textContent = 'Configuration loaded.';
  } catch (error) { configurationStatusEl.textContent = `Error: ${error.message}`; configurationStatusEl.className = 'status error'; }
}

async function saveGeneralConfiguration() {
  const waitSeconds = Number(configIbPriceWaitSecondsEl.value);
  const passCount = Number(configScenarioPassCountEl.value);
  if (!Number.isFinite(waitSeconds) || waitSeconds < 1 || waitSeconds > 30) {
    configurationStatusEl.textContent = 'Error: Price wait time must be between 1 and 30 seconds.';
    configurationStatusEl.className = 'status error';
    return;
  }
  if (!Number.isInteger(passCount) || passCount < 1 || passCount > 10) {
    configurationStatusEl.textContent = 'Error: Scenario pass count must be an integer between 1 and 10.';
    configurationStatusEl.className = 'status error';
    return;
  }

  configurationStatusEl.textContent = 'Saving configuration…'; configurationStatusEl.className = 'status';
  try { const response = await fetch('/api/configuration/general', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ settings: { ib_price_wait_seconds: waitSeconds, scenario_multi_pass_enabled: configScenarioMultiPassEnabledEl.checked, scenario_pass_count: passCount } }) });
    const payload = await response.json(); if (!response.ok) throw new Error(extractErrorMessage(payload, 'Unable to save configuration')); configurationStatusEl.textContent = 'Configuration saved.';
  } catch (error) { configurationStatusEl.textContent = `Error: ${error.message}`; configurationStatusEl.className = 'status error'; }
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
analysisPortfolioFilterEl.addEventListener('change', () => {
  portfolioFilter = analysisPortfolioFilterEl.value || 'all';
  renderAnalysisList();
});
analysisSelectAllEl.addEventListener('change', () => {
  const visibleItems = getFilteredAnalysisItems();
  if (analysisSelectAllEl.checked) visibleItems.forEach((item) => selectedAnalysisSymbols.add(item.symbol));
  else visibleItems.forEach((item) => selectedAnalysisSymbols.delete(item.symbol));
  renderAnalysisList();
});

refreshBtn.addEventListener('click', loadPositions);
analysisAddBtn.addEventListener('click', addAnalysisSymbol);
analysisImportBtn.addEventListener('click', importAnalysisFromPositions);
analysisRefreshPricesBtn.addEventListener('click', refreshAnalysisPrices);
analysisRerunSelectedBtn.addEventListener('click', rerunSelectedSymbolsScenarios);
analysisSymbolInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') addAnalysisSymbol(); });
analysisBackBtn.addEventListener('click', showAnalysisList);
analysisScenarioInfoBtn.addEventListener('click', () => analysisScenarioInfoModal.classList.remove('hidden'));
analysisScenarioInfoCloseBtn.addEventListener('click', () => analysisScenarioInfoModal.classList.add('hidden'));
analysisSummary.addEventListener('click', (event) => {
  const target = event.target;
  if (!(target instanceof HTMLElement)) return;
  if (target.id === 'analysis-business-model-edit-btn') {
    isEditingBusinessModel = true;
    renderAnalysisDetail();
    return;
  }
  if (target.id === 'analysis-business-model-save-btn') {
    saveEditedBusinessModel();
    return;
  }
  if (target.id === 'analysis-business-model-cancel-btn') {
    cancelEditedBusinessModel();
  }
});
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

promptSaveBtn.addEventListener('click', savePromptConfiguration);
promptResetBtn.addEventListener('click', resetPromptConfiguration);
promptPreviewBtn.addEventListener('click', previewPromptConfiguration);
promptPreviewSymbolInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') previewPromptConfiguration(); });
configSaveBtn.addEventListener('click', saveGeneralConfiguration);

updateSortHeaderState();
updateAnalysisSortHeaderState();
setView('analysis');
