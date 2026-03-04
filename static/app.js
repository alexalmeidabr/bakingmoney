const menuItems = document.querySelectorAll('.menu-item');
const views = document.querySelectorAll('.view');
const statusEl = document.getElementById('status');
const table = document.getElementById('positions-table');
const tableBody = table.querySelector('tbody');
const refreshBtn = document.getElementById('refresh-btn');

function switchView(targetView) {
  menuItems.forEach((item) => {
    item.classList.toggle('active', item.dataset.view === targetView);
  });

  views.forEach((view) => {
    view.classList.toggle('active', view.id === targetView);
  });
}

menuItems.forEach((item) => {
  item.addEventListener('click', () => {
    switchView(item.dataset.view);
  });
});

function formatNumber(value, digits = 2) {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return '—';
  }
  return value.toLocaleString(undefined, { maximumFractionDigits: digits });
}

function formatPercent(value) {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return '—';
  }
  return `${value.toFixed(2)}%`;
}

function pnlClass(value) {
  if (typeof value !== 'number' || Number.isNaN(value) || value === 0) {
    return '';
  }
  return value > 0 ? 'pnl-positive' : 'pnl-negative';
}

async function loadPositions() {
  statusEl.textContent = 'Loading positions…';
  statusEl.className = 'status';
  table.classList.add('hidden');

  try {
    const response = await fetch('/api/positions');
    const payload = await response.json();

    if (!response.ok) {
      throw new Error(payload.error || payload.details || 'Request failed');
    }

    const positions = payload.positions || [];
    tableBody.innerHTML = '';

    if (positions.length === 0) {
      statusEl.textContent = 'No positions found.';
      return;
    }

    positions.forEach((position) => {
      const row = document.createElement('tr');
      row.innerHTML = `
        <td>${position.symbol ?? ''}</td>
        <td>${formatNumber(position.position, 4)}</td>
        <td>${formatNumber(position.price)}</td>
        <td>${formatNumber(position.avgCost)}</td>
        <td class="${pnlClass(position.changePercent)}">${formatPercent(position.changePercent)}</td>
        <td>${formatNumber(position.marketValue)}</td>
        <td class="${pnlClass(position.unrealizedPnL)}">${formatNumber(position.unrealizedPnL)}</td>
        <td class="${pnlClass(position.dailyPnL)}">${formatNumber(position.dailyPnL)}</td>
        <td>${position.currency ?? ''}</td>
      `;
      tableBody.appendChild(row);
    });

    statusEl.textContent = `Loaded ${positions.length} position(s).`;
    table.classList.remove('hidden');
  } catch (error) {
    statusEl.textContent = `Error: ${error.message}`;
    statusEl.className = 'status error';
  }
}

refreshBtn.addEventListener('click', loadPositions);
loadPositions();
