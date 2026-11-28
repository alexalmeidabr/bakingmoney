(function exposeNavigation(root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.BakingMoneyNavigation = api;
}(typeof globalThis !== 'undefined' ? globalThis : this, function navigationFactory() {
  'use strict';

  const MAIN_VIEWS = new Set([
    'analysis', 'positions', 'action-plan', 'action-plan-simulator',
    'earnings-review', 'alerts', 'prompt', 'configuration', 'backup',
  ]);

  function normalizedSymbol(value) {
    const symbol = String(value || '').trim().toUpperCase();
    return symbol || null;
  }

  function normalizeScreen(value) {
    if (!value || typeof value !== 'object' || !MAIN_VIEWS.has(value.view)) return null;
    const screen = { view: value.view };
    if (value.view === 'action-plan-simulator' && value.simulationId != null) {
      const simulationId = String(value.simulationId).trim();
      if (!simulationId) return null;
      screen.simulationId = simulationId;
    }
    if (value.detail == null) return screen;
    const detail = value.detail;
    if (!detail || typeof detail !== 'object') return null;

    if (detail.kind === 'analysis') {
      if (!['analysis', 'positions', 'action-plan', 'action-plan-simulator', 'earnings-review'].includes(value.view)) return null;
      const symbol = normalizedSymbol(detail.symbol);
      if (!symbol) return null;
      screen.detail = { kind: 'analysis', symbol };
      if (detail.versionId != null && String(detail.versionId).trim()) screen.detail.versionId = String(detail.versionId);
      return screen;
    }
    if (detail.kind === 'action') {
      if (!['action-plan', 'action-plan-simulator'].includes(value.view)) return null;
      const symbol = normalizedSymbol(detail.symbol);
      if (!symbol) return null;
      screen.detail = { kind: 'action', symbol };
      return screen;
    }
    if (detail.kind === 'alert') {
      if (value.view !== 'alerts' || detail.alertId == null || !String(detail.alertId).trim()) return null;
      screen.detail = { kind: 'alert', alertId: String(detail.alertId) };
      return screen;
    }
    if (detail.kind === 'earnings-symbol') {
      if (value.view !== 'earnings-review') return null;
      const symbol = normalizedSymbol(detail.symbol);
      if (!symbol) return null;
      screen.detail = { kind: 'earnings-symbol', symbol };
      return screen;
    }
    if (detail.kind === 'earnings-review') {
      const symbol = normalizedSymbol(detail.symbol);
      const reviewId = Number(detail.reviewId);
      if (value.view !== 'earnings-review' || !symbol || !Number.isFinite(reviewId)) return null;
      screen.detail = { kind: 'earnings-review', symbol, reviewId };
      return screen;
    }
    return null;
  }

  function screensEqual(left, right) {
    return JSON.stringify(left) === JSON.stringify(right);
  }

  function parseEntry(value) {
    if (!value || value.bakingMoneyNavigation !== 1 || !Number.isInteger(value.sequence) || value.sequence < 0) return null;
    const screen = normalizeScreen(value.screen);
    return screen ? { sequence: value.sequence, screen } : null;
  }

  function createController({ history, eventTarget, render, canLeave = () => true, fallbackScreen = { view: 'analysis' } }) {
    let activeScreen = null;
    let activeSequence = null;
    let popQueue = Promise.resolve();
    let pendingScreen = null;
    let navigationRevision = 0;

    const entry = (sequence, screen) => ({ bakingMoneyNavigation: 1, sequence, screen });

    async function allowed(target) {
      return (await canLeave(activeScreen, target)) !== false;
    }

    async function apply(target, sequence) {
      const revision = ++navigationRevision;
      pendingScreen = target;
      const rendered = await render(target);
      if (revision !== navigationRevision) return null;
      pendingScreen = null;
      if (rendered === false) return false;
      activeScreen = target;
      activeSequence = sequence;
      return true;
    }

    async function onPopState(event) {
      const target = parseEntry(event.state);
      if (!target || (target.sequence === activeSequence && screensEqual(target.screen, activeScreen) && !pendingScreen)) return;
      if (!(await allowed(target.screen))) {
        const browserEntry = parseEntry(history.state);
        if (!browserEntry) return;
        const correction = activeSequence - browserEntry.sequence;
        if (correction) history.go(correction);
        return;
      }
      const applied = await apply(target.screen, target.sequence);
      if (applied === false) {
        const browserEntry = parseEntry(history.state);
        if (!browserEntry) return;
        const correction = activeSequence - browserEntry.sequence;
        if (correction) history.go(correction);
      }
    }

    eventTarget.addEventListener('popstate', (event) => {
      popQueue = popQueue.then(() => onPopState(event));
    });

    return {
      async initialize() {
        const restored = parseEntry(history.state);
        if (restored) return apply(restored.screen, restored.sequence);
        const initial = normalizeScreen(fallbackScreen) || { view: 'analysis' };
        if (!(await apply(initial, 0))) return false;
        history.replaceState(entry(0, initial), '');
        return true;
      },

      async navigate(value) {
        const target = normalizeScreen(value);
        if (!target) return false;
        const alreadyActive = screensEqual(target, activeScreen);
        if (alreadyActive && !pendingScreen) return true;
        if (!(await allowed(target))) return false;
        const nextSequence = alreadyActive ? activeSequence : (activeSequence ?? -1) + 1;
        const applied = await apply(target, nextSequence);
        if (applied !== true) return false;
        if (alreadyActive) return true;
        history.pushState(entry(nextSequence, target), '');
        return true;
      },

      async back(fallback = fallbackScreen) {
        if (activeSequence > 0) {
          history.back();
          return true;
        }
        return this.navigate(fallback);
      },
      currentScreen: () => activeScreen,
      currentSequence: () => activeSequence,
    };
  }

  return { createController, normalizeScreen };
}));
