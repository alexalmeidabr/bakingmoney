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

function formatNumber(value) {
  if (typeof value !== 'number') {
    return value;
  }
  return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
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
        <td>${formatNumber(position.quantity ?? '')}</td>
        <td>${formatNumber(position.avgCost ?? '')}</td>
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
