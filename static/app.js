const menuItems = document.querySelectorAll('.menu-item');
const views = document.querySelectorAll('.view');

const positionsStatusEl = document.getElementById('status');
const positionsTable = document.getElementById('positions-table');
const positionsTableBody = positionsTable.querySelector('tbody');
const refreshBtn = document.getElementById('refresh-btn');
const positionSortHeaders = document.querySelectorAll('#positions-table th.sortable');

const watchlistStatusEl = document.getElementById('watchlist-status');
const watchlistTable = document.getElementById('watchlist-table');
const watchlistTableBody = watchlistTable.querySelector('tbody');
const watchlistSymbolInput = document.getElementById('watchlist-symbol-input');
const addSymbolBtn = document.getElementById('add-symbol-btn');
const addPositionsBtn = document.getElementById('add-positions-btn');

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

let latestPositions = [];
let positionSort = { key: 'symbol', direction: 'asc' };

let latestAnalysis = [];
let analysisSort = { key: 'symbol', direction: 'asc' };

function formatNumber(value, digits = 2) {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return 'N/A';
  }
  return value.toLocaleString(undefined, { maximumFractionDigits: digits });
}

function formatCurrencyValue(value, currency, digits = 2) {
  const formatted = formatNumber(value, digits);
  if (!currency) {
    return formatted;
  }
  return formatted === 'N/A' ? formatted : `${formatted} ${currency}`;
}

function formatPercent(value) {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return 'N/A';
  }
  return `${value.toFixed(2)}%`;
}

function valueClass(value) {
  if (typeof value !== 'number' || Number.isNaN(value) || value === 0) {
    return '';
  }
  return value > 0 ? 'pnl-positive' : 'pnl-negative';
}

function compareValues(left, right, direction = 'asc') {
  if (left == null && right == null) return 0;
  if (left == null) return 1;
  if (right == null) return -1;

  let result = 0;
  if (typeof left === 'number' && typeof right === 'number') {
    result = left - right;
  } else {
    result = String(left).localeCompare(String(right));
  }

  return direction === 'asc' ? result : -result;
}

function sortPositions(positions) {
  const { key, direction } = positionSort;
  return [...positions].sort((a, b) => compareValues(a[key], b[key], direction));
}

function sortAnalysis(items) {
  const { key, direction } = analysisSort;
  return [...items].sort((a, b) => compareValues(a[key], b[key], direction));
}

function updateSortHeaderState() {
  positionSortHeaders.forEach((header) => {
    const isActive = header.dataset.sortKey === positionSort.key;
    header.dataset.sortDirection = isActive ? positionSort.direction : '';
  });
}

function updateAnalysisSortHeaderState() {
  analysisSortHeaders.forEach((header) => {
    const isActive = header.dataset.sortKey === analysisSort.key;
    header.dataset.sortDirection = isActive ? analysisSort.direction : '';
  });
}

function renderPositions() {
  const sortedPositions = sortPositions(latestPositions);
  positionsTableBody.innerHTML = '';

  sortedPositions.forEach((position) => {
    const row = document.createElement('tr');
    row.innerHTML = `
      <td>${position.symbol ?? ''}</td>
      <td>${formatNumber(position.position, 4)}</td>
      <td>${formatCurrencyValue(position.price, position.currency)}</td>
      <td>${formatNumber(position.avgCost)}</td>
      <td class="${valueClass(position.changePercent)}">${formatPercent(position.changePercent)}</td>
      <td>${formatCurrencyValue(position.marketValue, position.currency)}</td>
      <td class="${valueClass(position.unrealizedPnL)}">${formatNumber(position.unrealizedPnL)}</td>
      <td class="${valueClass(position.dailyPnL)}">${formatNumber(position.dailyPnL)}</td>
    `;
    positionsTableBody.appendChild(row);
  });
}

function renderAnalysisList() {
  const sortedItems = sortAnalysis(latestAnalysis);
  analysisTableBody.innerHTML = '';

  sortedItems.forEach((item) => {
    const row = document.createElement('tr');
    row.innerHTML = `
      <td><button class="symbol-link" data-symbol="${item.symbol}">${item.symbol}</button></td>
      <td>${formatCurrencyValue(item.expected_price, 'USD')}</td>
      <td class="${valueClass(item.upside)}">${formatPercent(item.upside)}</td>
      <td>${formatNumber(item.overall_confidence, 2)}</td>
      <td><button class="remove-btn" data-symbol="${item.symbol}">Delete</button></td>
    `;
    analysisTableBody.appendChild(row);
  });

  analysisTableBody.querySelectorAll('.remove-btn').forEach((button) => {
    button.addEventListener('click', async () => {
      await deleteAnalysis(button.dataset.symbol);
    });
  });

  analysisTableBody.querySelectorAll('.symbol-link').forEach((button) => {
    button.addEventListener('click', async () => {
      await loadAnalysisDetail(button.dataset.symbol);
    });
  });
}

function setView(targetView) {
  menuItems.forEach((item) => {
    item.classList.toggle('active', item.dataset.view === targetView);
  });

  views.forEach((view) => {
    view.classList.toggle('active', view.id === targetView);
  });

  if (targetView === 'watchlist') {
    loadWatchlist();
  }
  if (targetView === 'analysis') {
    showAnalysisList();
    loadAnalysis();
  }
}

function showAnalysisList() {
  analysisListView.classList.remove('hidden');
  analysisDetailView.classList.add('hidden');
}

menuItems.forEach((item) => {
  item.addEventListener('click', () => {
    setView(item.dataset.view);
  });
});

async function loadPositions() {
  positionsStatusEl.textContent = 'Loading positions…';
  positionsStatusEl.className = 'status';
  positionsTable.classList.add('hidden');

  try {
    const response = await fetch('/api/positions');
    const payload = await response.json();

    if (!response.ok) {
      throw new Error(payload.error || payload.details || 'Request failed');
    }

    const positions = payload.positions || [];
    latestPositions = positions;

    if (positions.length === 0) {
      positionsTableBody.innerHTML = '';
      positionsStatusEl.textContent = 'No positions found.';
      return;
    }

    updateSortHeaderState();
    renderPositions();

    positionsStatusEl.textContent = `Loaded ${positions.length} position(s).`;
    positionsTable.classList.remove('hidden');
  } catch (error) {
    positionsStatusEl.textContent = `Error: ${error.message}`;
    positionsStatusEl.className = 'status error';
  }
}

async function loadWatchlist() {
  watchlistStatusEl.textContent = 'Loading watchlist…';
  watchlistStatusEl.className = 'status';
  watchlistTable.classList.add('hidden');

  try {
    const response = await fetch('/api/watchlist');
    const payload = await response.json();

    if (!response.ok) {
      throw new Error(payload.error || payload.details || 'Request failed');
    }

    const items = payload.watchlist || [];
    watchlistTableBody.innerHTML = '';

    if (items.length === 0) {
      watchlistStatusEl.textContent = 'Watchlist is empty.';
      return;
    }

    items.forEach((item) => {
      const row = document.createElement('tr');
      row.innerHTML = `
        <td>${item.symbol ?? ''}</td>
        <td title="${item.warning || ''}">${formatCurrencyValue(item.price, 'USD')}</td>
        <td>${formatNumber(item.pe)}</td>
        <td>${formatNumber(item.forwardPe)}</td>
        <td><button class="remove-btn" data-symbol="${item.symbol}">Remove</button></td>
      `;
      watchlistTableBody.appendChild(row);
    });

    watchlistTableBody.querySelectorAll('.remove-btn').forEach((button) => {
      button.addEventListener('click', async () => {
        const symbol = button.dataset.symbol;
        await removeSymbol(symbol);
      });
    });

    const missingPriceWarnings = items.filter((item) => item.warning).length;
    watchlistStatusEl.textContent = `Loaded ${items.length} watchlist item(s).${missingPriceWarnings ? ` ${missingPriceWarnings} missing price(s): delayed/unavailable.` : ''}`;
    watchlistTable.classList.remove('hidden');
  } catch (error) {
    watchlistStatusEl.textContent = `Error: ${error.message}`;
    watchlistStatusEl.className = 'status error';
  }
}

async function loadAnalysis() {
  analysisStatusEl.textContent = 'Loading analysis…';
  analysisStatusEl.className = 'status';
  analysisTable.classList.add('hidden');

  try {
    const response = await fetch('/api/analysis');
    const payload = await response.json();

    if (!response.ok) {
      throw new Error(payload.error || payload.details || 'Request failed');
    }

    latestAnalysis = payload.analysis || [];
    if (latestAnalysis.length === 0) {
      analysisStatusEl.textContent = 'Analysis is empty.';
      analysisTableBody.innerHTML = '';
      return;
    }

    updateAnalysisSortHeaderState();
    renderAnalysisList();
    analysisStatusEl.textContent = `Loaded ${latestAnalysis.length} analysis symbol(s).`;
    analysisTable.classList.remove('hidden');
  } catch (error) {
    analysisStatusEl.textContent = `Error: ${error.message}`;
    analysisStatusEl.className = 'status error';
  }
}

async function addSymbol() {
  const symbol = watchlistSymbolInput.value.trim().toUpperCase();
  if (!symbol) {
    return;
  }

  watchlistStatusEl.textContent = 'Adding symbol…';

  try {
    const response = await fetch('/api/watchlist', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbol }),
    });

    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || payload.details || 'Unable to add symbol');
    }

    watchlistSymbolInput.value = '';
    await loadWatchlist();
  } catch (error) {
    watchlistStatusEl.textContent = `Error: ${error.message}`;
    watchlistStatusEl.className = 'status error';
  }
}

async function addAnalysisSymbol() {
  const symbol = analysisSymbolInput.value.trim().toUpperCase();
  if (!symbol) return;

  analysisStatusEl.textContent = `Analyzing ${symbol}…`;
  analysisStatusEl.className = 'status';

  try {
    const response = await fetch('/api/analysis', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbol }),
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || payload.details || 'Unable to add analysis');
    }

    analysisSymbolInput.value = '';
    await loadAnalysis();
  } catch (error) {
    analysisStatusEl.textContent = `Error: ${error.message}`;
    analysisStatusEl.className = 'status error';
  }
}

async function importAnalysisFromPositions() {
  analysisStatusEl.textContent = 'Importing from positions…';
  analysisStatusEl.className = 'status';

  try {
    const response = await fetch('/api/analysis/import-from-positions', { method: 'POST' });
    const payload = await response.json();
    if (!response.ok && response.status !== 207) {
      throw new Error(payload.error || payload.details || 'Unable to import analysis');
    }

    await loadAnalysis();
    if (payload.failures && payload.failures.length) {
      analysisStatusEl.textContent = `Imported ${payload.importedSymbols.length} symbol(s), ${payload.failures.length} failed.`;
      analysisStatusEl.className = 'status error';
    }
  } catch (error) {
    analysisStatusEl.textContent = `Error: ${error.message}`;
    analysisStatusEl.className = 'status error';
  }
}

async function loadAnalysisDetail(symbol) {
  analysisDetailStatus.textContent = `Loading ${symbol} detail…`;
  analysisDetailStatus.className = 'status';
  analysisSummary.classList.add('hidden');

  analysisListView.classList.add('hidden');
  analysisDetailView.classList.remove('hidden');

  try {
    const response = await fetch(`/api/analysis/${encodeURIComponent(symbol)}`);
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || payload.details || 'Unable to load details');
    }

    const item = payload.analysis;
    analysisDetailTitle.textContent = `Analysis: ${item.symbol}`;
    analysisSummary.innerHTML = `
      <div class="summary-grid">
        <div class="summary-item"><div class="label">Symbol</div><div class="value">${item.symbol}</div></div>
        <div class="summary-item"><div class="label">Current Price</div><div class="value">${formatCurrencyValue(item.current_price, 'USD')}</div></div>
        <div class="summary-item"><div class="label">Expected Price</div><div class="value">${formatCurrencyValue(item.expected_price, 'USD')}</div></div>
        <div class="summary-item"><div class="label">Upside</div><div class="value ${valueClass(item.upside)}">${formatPercent(item.upside)}</div></div>
        <div class="summary-item"><div class="label">Confidence Level</div><div class="value">${formatNumber(item.overall_confidence, 2)}</div></div>
      </div>
      <p><strong>Assumptions:</strong> ${item.assumptions || 'N/A'}</p>
    `;
    analysisSummary.classList.remove('hidden');

    analysisScenariosBody.innerHTML = '';
    (item.scenarios || []).forEach((scenario) => {
      const row = document.createElement('tr');
      row.innerHTML = `
        <td>${scenario.scenario_name}</td>
        <td>${formatCurrencyValue(scenario.price_low, 'USD')}</td>
        <td>${formatCurrencyValue(scenario.price_high, 'USD')}</td>
        <td>${formatPercent(scenario.cagr_low)}</td>
        <td>${formatPercent(scenario.cagr_high)}</td>
        <td>${formatPercent((scenario.probability || 0) * 100)}</td>
      `;
      analysisScenariosBody.appendChild(row);
    });

    analysisVariablesBody.innerHTML = '';
    (item.key_variables || []).forEach((variable) => {
      const row = document.createElement('tr');
      row.innerHTML = `
        <td>${variable.variable_text}</td>
        <td>${variable.variable_type}</td>
        <td>${formatNumber(variable.confidence, 2)}</td>
        <td>${formatNumber(variable.importance, 2)}</td>
      `;
      analysisVariablesBody.appendChild(row);
    });

    analysisDetailStatus.textContent = `Loaded ${item.symbol} detail.`;
  } catch (error) {
    analysisDetailStatus.textContent = `Error: ${error.message}`;
    analysisDetailStatus.className = 'status error';
  }
}

async function deleteAnalysis(symbol) {
  analysisStatusEl.textContent = `Deleting ${symbol}…`;
  analysisStatusEl.className = 'status';

  try {
    const response = await fetch(`/api/analysis/${encodeURIComponent(symbol)}`, { method: 'DELETE' });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || payload.details || 'Unable to delete');
    }
    await loadAnalysis();
  } catch (error) {
    analysisStatusEl.textContent = `Error: ${error.message}`;
    analysisStatusEl.className = 'status error';
  }
}

async function removeSymbol(symbol) {
  watchlistStatusEl.textContent = `Removing ${symbol}…`;

  try {
    const response = await fetch(`/api/watchlist/${encodeURIComponent(symbol)}`, {
      method: 'DELETE',
    });

    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || payload.details || 'Unable to remove symbol');
    }

    await loadWatchlist();
  } catch (error) {
    watchlistStatusEl.textContent = `Error: ${error.message}`;
    watchlistStatusEl.className = 'status error';
  }
}

async function importFromPositions() {
  watchlistStatusEl.textContent = 'Adding symbols from positions…';

  try {
    const response = await fetch('/api/watchlist/import-positions', {
      method: 'POST',
    });

    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || payload.details || 'Unable to import positions');
    }

    await loadWatchlist();
  } catch (error) {
    watchlistStatusEl.textContent = `Error: ${error.message}`;
    watchlistStatusEl.className = 'status error';
  }
}

positionSortHeaders.forEach((header) => {
  header.addEventListener('click', () => {
    const { sortKey } = header.dataset;
    if (!sortKey) return;

    if (positionSort.key === sortKey) {
      positionSort.direction = positionSort.direction === 'asc' ? 'desc' : 'asc';
    } else {
      positionSort = { key: sortKey, direction: 'asc' };
    }

    updateSortHeaderState();
    renderPositions();
  });
});

analysisSortHeaders.forEach((header) => {
  header.addEventListener('click', () => {
    const { sortKey } = header.dataset;
    if (!sortKey) return;

    if (analysisSort.key === sortKey) {
      analysisSort.direction = analysisSort.direction === 'asc' ? 'desc' : 'asc';
    } else {
      analysisSort = { key: sortKey, direction: 'asc' };
    }

    updateAnalysisSortHeaderState();
    renderAnalysisList();
  });
});

refreshBtn.addEventListener('click', loadPositions);
addSymbolBtn.addEventListener('click', addSymbol);
addPositionsBtn.addEventListener('click', importFromPositions);
watchlistSymbolInput.addEventListener('keydown', (event) => {
  if (event.key === 'Enter') {
    addSymbol();
  }
});
analysisAddBtn.addEventListener('click', addAnalysisSymbol);
analysisImportBtn.addEventListener('click', importAnalysisFromPositions);
analysisSymbolInput.addEventListener('keydown', (event) => {
  if (event.key === 'Enter') {
    addAnalysisSymbol();
  }
});
analysisBackBtn.addEventListener('click', showAnalysisList);

updateSortHeaderState();
updateAnalysisSortHeaderState();
loadPositions();
