(function initializeActionPlanSorting(root) {
  function finiteNumber(value) {
    if (value == null || value === '' || typeof value === 'boolean') return null;
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  }

  function firstPresent(item, keys) {
    for (const key of keys) {
      const value = item?.[key];
      if (value != null && value !== '') return value;
    }
    return undefined;
  }

  function getTargetBandMidpoint(item) {
    if (!item) return null;

    const low = finiteNumber(firstPresent(item, ['linear_target_weight_low', 'target_weight_low', 'target_low', 'target_low_pct']));
    const high = finiteNumber(firstPresent(item, ['linear_target_weight_high', 'target_weight_high', 'target_high', 'target_high_pct']));
    if (low == null || high == null) return null;

    const midpointValue = firstPresent(item, [
      'linear_target_weight_mid',
      'target_weight_mid',
      'target_mid',
      'target_mid_pct',
      'target_band_mid',
    ]);
    return midpointValue === undefined ? (low + high) / 2 : finiteNumber(midpointValue);
  }

  function getLinearCagrValue(item) {
    if (!item) return null;
    if (Object.prototype.hasOwnProperty.call(item, 'expected_equity_cagr')) {
      return finiteNumber(item.expected_equity_cagr);
    }
    return finiteNumber(firstPresent(item, [
      'expected_cagr',
      'weighted_expected_cagr',
      'scenario_expected_cagr',
    ]));
  }

  function formatCagrPercent(value) {
    const number = finiteNumber(value);
    return number == null ? '—' : `${number.toFixed(1)}%`;
  }

  function compareDeterministicLabels(left, right) {
    const leftSymbol = String(left?.symbol ?? '').trim();
    const rightSymbol = String(right?.symbol ?? '').trim();
    const symbolDelta = leftSymbol.localeCompare(rightSymbol, undefined, { sensitivity: 'base' });
    if (symbolDelta !== 0) return symbolDelta;

    const leftCompany = String(left?.company_name ?? left?.company ?? left?.name ?? '').trim();
    const rightCompany = String(right?.company_name ?? right?.company ?? right?.name ?? '').trim();
    return leftCompany.localeCompare(rightCompany, undefined, { sensitivity: 'base' });
  }

  function compareNullableNumbers(left, right, direction = 'asc') {
    if (left == null && right == null) return 0;
    if (left == null) return 1;
    if (right == null) return -1;
    const multiplier = direction === 'desc' ? -1 : 1;
    return (left - right) * multiplier;
  }

  function sortRowsByNumericValue(items, options) {
    const {
      direction = 'asc',
      getValue,
      getSecondaryValue = null,
      secondaryDirection = 'asc',
    } = options;
    return items.map((item, index) => ({ item, index })).sort((left, right) => {
      const primaryDelta = compareNullableNumbers(getValue(left.item), getValue(right.item), direction);
      if (primaryDelta !== 0) return primaryDelta;
      if (getSecondaryValue) {
        const secondaryDelta = compareNullableNumbers(
          getSecondaryValue(left.item),
          getSecondaryValue(right.item),
          secondaryDirection,
        );
        if (secondaryDelta !== 0) return secondaryDelta;
      }
      const labelDelta = compareDeterministicLabels(left.item, right.item);
      return labelDelta !== 0 ? labelDelta : left.index - right.index;
    }).map((entry) => entry.item);
  }

  const api = {
    finiteNumber,
    formatCagrPercent,
    getLinearCagrValue,
    getTargetBandMidpoint,
    compareDeterministicLabels,
    compareNullableNumbers,
    sortRowsByNumericValue,
  };
  root.ActionPlanSorting = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
}(typeof globalThis !== 'undefined' ? globalThis : this));
