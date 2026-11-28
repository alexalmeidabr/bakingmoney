const assert = require('node:assert/strict');
const test = require('node:test');

const {
  createController,
  normalizeScreen,
} = require('./static/navigation_history.js');

class MemoryHistory {
  constructor(entries = [{ state: null }], index = entries.length - 1) {
    this.entries = entries.map((entry) => ({ state: entry.state ?? null }));
    this.index = index;
    this.pushCount = 0;
    this.replaceCount = 0;
    this.goCalls = [];
    this.listeners = new Set();
  }

  get state() { return this.entries[this.index]?.state ?? null; }
  get length() { return this.entries.length; }

  addEventListener(type, listener) {
    if (type === 'popstate') this.listeners.add(listener);
  }

  pushState(state) {
    this.entries.splice(this.index + 1, Infinity, { state });
    this.index += 1;
    this.pushCount += 1;
  }

  replaceState(state) {
    this.entries[this.index] = { state };
    this.replaceCount += 1;
  }

  go(delta) {
    this.goCalls.push(delta);
    const nextIndex = this.index + delta;
    if (nextIndex < 0 || nextIndex >= this.entries.length || nextIndex === this.index) return;
    this.index = nextIndex;
    const event = { state: this.state };
    queueMicrotask(() => this.listeners.forEach((listener) => listener(event)));
  }

  back() { this.go(-1); }
  forward() { this.go(1); }
}

function applicationEntry(sequence, screen) {
  return { state: { bakingMoneyNavigation: 1, sequence, screen } };
}

async function settle() {
  for (let index = 0; index < 8; index += 1) await new Promise((resolve) => setImmediate(resolve));
}

function harness({ entries, index, canLeave = () => true } = {}) {
  const history = new MemoryHistory(entries, index);
  const rendered = [];
  const controller = createController({
    history,
    eventTarget: history,
    render: async (screen) => { rendered.push(screen); return true; },
    canLeave,
    fallbackScreen: { view: 'analysis' },
  });
  return { history, rendered, controller };
}

test('normalizes every supported main and nested application screen', () => {
  for (const view of ['analysis', 'positions', 'action-plan', 'action-plan-simulator', 'earnings-review', 'alerts', 'prompt', 'configuration', 'backup']) {
    assert.deepEqual(normalizeScreen({ view }), { view });
  }
  assert.deepEqual(normalizeScreen({ view: 'analysis', detail: { kind: 'analysis', symbol: 'nvda' } }),
    { view: 'analysis', detail: { kind: 'analysis', symbol: 'NVDA' } });
  assert.deepEqual(normalizeScreen({ view: 'positions', detail: { kind: 'analysis', symbol: 'nvda' } }),
    { view: 'positions', detail: { kind: 'analysis', symbol: 'NVDA' } });
  assert.deepEqual(normalizeScreen({ view: 'action-plan', detail: { kind: 'action', symbol: 'msft' } }),
    { view: 'action-plan', detail: { kind: 'action', symbol: 'MSFT' } });
  assert.deepEqual(normalizeScreen({ view: 'action-plan-simulator', detail: { kind: 'analysis', symbol: 'msft' } }),
    { view: 'action-plan-simulator', detail: { kind: 'analysis', symbol: 'MSFT' } });
  assert.deepEqual(normalizeScreen({ view: 'alerts', detail: { kind: 'alert', alertId: 17 } }),
    { view: 'alerts', detail: { kind: 'alert', alertId: '17' } });
  assert.deepEqual(normalizeScreen({ view: 'earnings-review', detail: { kind: 'earnings-symbol', symbol: 'amd' } }),
    { view: 'earnings-review', detail: { kind: 'earnings-symbol', symbol: 'AMD' } });
  assert.deepEqual(normalizeScreen({ view: 'earnings-review', detail: { kind: 'earnings-review', symbol: 'amd', reviewId: 9 } }),
    { view: 'earnings-review', detail: { kind: 'earnings-review', symbol: 'AMD', reviewId: 9 } });
  assert.equal(normalizeScreen({ view: 'backup', detail: { kind: 'alert', alertId: 1 } }), null);
  assert.equal(normalizeScreen({ view: 'unknown' }), null);
});

test('initializes a missing or invalid entry with Analysis using replaceState', async () => {
  const h = harness();
  assert.equal(await h.controller.initialize(), true);
  assert.deepEqual(h.rendered, [{ view: 'analysis' }]);
  assert.equal(h.history.replaceCount, 1);
  assert.equal(h.history.pushCount, 0);
  assert.deepEqual(h.history.state, {
    bakingMoneyNavigation: 1,
    sequence: 0,
    screen: { view: 'analysis' },
  });
});

test('restores a valid reload entry without replacing or pushing it', async () => {
  const screen = { view: 'alerts', detail: { kind: 'alert', alertId: '42' } };
  const h = harness({ entries: [applicationEntry(3, screen)] });
  assert.equal(await h.controller.initialize(), true);
  assert.deepEqual(h.rendered, [screen]);
  assert.equal(h.history.replaceCount, 0);
  assert.equal(h.history.pushCount, 0);
  assert.equal(h.controller.currentSequence(), 3);
});

test('navigates across three screens and restores them with Back and Forward', async () => {
  const h = harness();
  await h.controller.initialize();
  await h.controller.navigate({ view: 'positions' });
  await h.controller.navigate({ view: 'action-plan' });
  assert.equal(h.history.pushCount, 2);
  assert.equal(h.controller.currentSequence(), 2);

  h.history.back();
  await settle();
  assert.deepEqual(h.controller.currentScreen(), { view: 'positions' });
  h.history.back();
  await settle();
  assert.deepEqual(h.controller.currentScreen(), { view: 'analysis' });
  h.history.forward();
  await settle();
  h.history.forward();
  await settle();
  assert.deepEqual(h.controller.currentScreen(), { view: 'action-plan' });
  assert.equal(h.history.pushCount, 2, 'popstate restoration must not push');
});

test('repeated navigation between two screens records the real sequence', async () => {
  const h = harness();
  await h.controller.initialize();
  await h.controller.navigate({ view: 'positions' });
  await h.controller.navigate({ view: 'analysis' });
  await h.controller.navigate({ view: 'positions' });
  assert.deepEqual(h.history.entries.map((entry) => entry.state?.screen), [
    { view: 'analysis' }, { view: 'positions' }, { view: 'analysis' }, { view: 'positions' },
  ]);
  assert.deepEqual(h.history.entries.map((entry) => entry.state?.sequence), [0, 1, 2, 3]);
});

test('selecting the active screen does not render or add a duplicate entry', async () => {
  const h = harness();
  await h.controller.initialize();
  assert.equal(await h.controller.navigate({ view: 'analysis' }), true);
  assert.equal(h.history.pushCount, 0);
  assert.deepEqual(h.rendered, [{ view: 'analysis' }]);
});

test('nested entries restore the actual path instead of a predetermined parent', async () => {
  const h = harness();
  await h.controller.initialize();
  await h.controller.navigate({ view: 'positions' });
  await h.controller.navigate({ view: 'positions', detail: { kind: 'analysis', symbol: 'NVDA' } });
  await h.controller.navigate({ view: 'action-plan' });
  await h.controller.navigate({ view: 'action-plan', detail: { kind: 'action', symbol: 'MSFT' } });
  for (const expected of [
    { view: 'action-plan' },
    { view: 'positions', detail: { kind: 'analysis', symbol: 'NVDA' } },
    { view: 'positions' },
  ]) {
    h.history.back();
    await settle();
    assert.deepEqual(h.controller.currentScreen(), expected);
  }
});

test('rejecting Back compensates to the rendered browser entry', async () => {
  let permit = true;
  const h = harness({ canLeave: () => permit });
  await h.controller.initialize();
  await h.controller.navigate({ view: 'positions' });
  await h.controller.navigate({ view: 'action-plan-simulator' });
  permit = false;

  h.history.back();
  await settle();

  assert.equal(h.history.index, 2);
  assert.equal(h.history.state.sequence, 2);
  assert.deepEqual(h.controller.currentScreen(), { view: 'action-plan-simulator' });
  assert.deepEqual(h.history.goCalls.slice(-2), [-1, 1]);
});

test('rejecting Forward compensates to the rendered browser entry', async () => {
  let permit = true;
  const h = harness({ canLeave: () => permit });
  await h.controller.initialize();
  await h.controller.navigate({ view: 'positions' });
  await h.controller.navigate({ view: 'action-plan-simulator' });
  h.history.back();
  await settle();
  permit = false;

  h.history.forward();
  await settle();

  assert.equal(h.history.index, 1);
  assert.equal(h.history.state.sequence, 1);
  assert.deepEqual(h.controller.currentScreen(), { view: 'positions' });
  assert.deepEqual(h.history.goCalls.slice(-2), [1, -1]);
});

test('two rapid rejected Back traversals reconcile to one rendered entry', async () => {
  let permit = true;
  const h = harness({ canLeave: () => permit });
  await h.controller.initialize();
  await h.controller.navigate({ view: 'positions' });
  await h.controller.navigate({ view: 'action-plan-simulator' });
  permit = false;

  h.history.back();
  h.history.back();
  await settle();

  assert.equal(h.history.index, 2);
  assert.equal(h.history.state.sequence, 2);
  assert.equal(h.controller.currentSequence(), 2);
  assert.deepEqual(h.controller.currentScreen(), { view: 'action-plan-simulator' });
  assert.deepEqual(h.rendered, [
    { view: 'analysis' }, { view: 'positions' }, { view: 'action-plan-simulator' },
  ]);
});

test('internal Back traverses history when an earlier application entry exists', async () => {
  const h = harness();
  await h.controller.initialize();
  await h.controller.navigate({ view: 'positions' });
  await h.controller.navigate({ view: 'positions', detail: { kind: 'analysis', symbol: 'NVDA' } });

  assert.equal(await h.controller.back({ view: 'positions' }), true);
  await settle();

  assert.equal(h.history.index, 1);
  assert.deepEqual(h.controller.currentScreen(), { view: 'positions' });
  assert.equal(h.history.pushCount, 2);
});

test('internal Back at sequence zero navigates to its logical fallback', async () => {
  const detail = { view: 'alerts', detail: { kind: 'alert', alertId: '8' } };
  const h = harness({ entries: [applicationEntry(0, detail)] });
  await h.controller.initialize();

  assert.equal(await h.controller.back({ view: 'alerts' }), true);

  assert.deepEqual(h.controller.currentScreen(), { view: 'alerts' });
  assert.equal(h.history.pushCount, 1);
  assert.equal(h.history.state.sequence, 1);
});

test('browser Back beyond the first application entry remains outside BakingMoney', async () => {
  const h = harness({ entries: [{ state: null }, applicationEntry(0, { view: 'analysis' })], index: 1 });
  await h.controller.initialize();

  h.history.back();
  await settle();

  assert.equal(h.history.index, 0);
  assert.equal(h.history.state, null);
  assert.equal(h.history.replaceCount, 0);
  assert.deepEqual(h.history.goCalls, [-1]);
});
