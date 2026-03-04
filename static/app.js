const menuItems = document.querySelectorAll('.menu-item');
const views = document.querySelectorAll('.view');

const positionsStatusEl = document.getElementById('status');
const positionsTable = document.getElementById('positions-table');
const positionsTableBody = positionsTable.querySelector('tbody');
const refreshBtn = document.getElementById('refresh-btn');

const watchlistStatusEl = document.getElementById('watchlist-status');
const watchlistTable = document.getElementById('watchlist-table');
const watchlistTableBody = watchlistTable.querySelector('tbody');
const watchlistSymbolInput = document.getElementById('watchlist-symbol-input');
const addSymbolBtn = document.getElementById('add-symbol-btn');
const addPositionsBtn = document.getElementById('add-positions-btn');

function formatNumber(value, digits = 2) {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return 'N/A';
  }
  return value.toLocaleString(undefined, { maximumFractionDigits: digits });
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
    positionsTableBody.innerHTML = '';

    if (positions.length === 0) {
      positionsStatusEl.textContent = 'No positions found.';
      return;
    }

    positions.forEach((position) => {
      const row = document.createElement('tr');
      row.innerHTML = `
        <td>${position.symbol ?? ''}</td>
        <td>${formatNumber(position.position, 4)}</td>
        <td>${formatNumber(position.avgCost)}</td>
        <td>${position.currency ?? ''}</td>
      `;
      positionsTableBody.appendChild(row);
    });

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
        <td title="${item.warning || ''}">${formatNumber(item.price)}</td>
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

refreshBtn.addEventListener('click', loadPositions);
addSymbolBtn.addEventListener('click', addSymbol);
addPositionsBtn.addEventListener('click', importFromPositions);
watchlistSymbolInput.addEventListener('keydown', (event) => {
  if (event.key === 'Enter') {
    addSymbol();
  }
});

loadPositions();
