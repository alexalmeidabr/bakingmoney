(function initializeEarningsCalendarDateFilters(globalScope) {
  function parseCalendarDate(value) {
    if (!value || typeof value !== 'string') return null;
    const match = value.match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (!match) return null;
    const year = Number(match[1]);
    const month = Number(match[2]);
    const day = Number(match[3]);
    const parsed = new Date(year, month - 1, day);
    if (Number.isNaN(parsed.getTime())) return null;
    if (parsed.getFullYear() !== year || parsed.getMonth() !== month - 1 || parsed.getDate() !== day) return null;
    parsed.setHours(0, 0, 0, 0);
    return parsed;
  }

  function normalizeLocalCalendarDate(value) {
    if (typeof value === 'string') return parseCalendarDate(value);
    if (!(value instanceof Date) || Number.isNaN(value.getTime())) return null;
    return new Date(value.getFullYear(), value.getMonth(), value.getDate());
  }

  function addCalendarDays(dateValue, days) {
    const normalized = normalizeLocalCalendarDate(dateValue);
    if (!normalized) return null;
    normalized.setDate(normalized.getDate() + days);
    normalized.setHours(0, 0, 0, 0);
    return normalized;
  }

  function getMondayWeekRange(referenceDate, weekOffset = 0) {
    const normalized = normalizeLocalCalendarDate(referenceDate);
    if (!normalized) return null;
    const daysSinceMonday = (normalized.getDay() + 6) % 7;
    const start = addCalendarDays(normalized, -daysSinceMonday + (weekOffset * 7));
    return { start, end: addCalendarDays(start, 6) };
  }

  function releaseDateMatchesEarningsCalendarDateFilters(releaseDateValue, todayValue, selectedDateFilters) {
    const releaseDate = parseCalendarDate(releaseDateValue);
    const today = normalizeLocalCalendarDate(todayValue);
    if (!releaseDate || !today || !selectedDateFilters || typeof selectedDateFilters.has !== 'function') return false;

    const releaseTime = releaseDate.getTime();
    const todayTime = today.getTime();
    const yesterday = addCalendarDays(today, -1);
    const tomorrow = addCalendarDays(today, 1);
    const currentWeek = getMondayWeekRange(today);
    const nextWeek = getMondayWeekRange(today, 1);

    if (selectedDateFilters.has('past') && releaseTime < todayTime) return true;
    if (selectedDateFilters.has('yesterday') && releaseTime === yesterday.getTime()) return true;
    if (selectedDateFilters.has('today') && releaseTime === todayTime) return true;
    if (selectedDateFilters.has('tomorrow') && releaseTime === tomorrow.getTime()) return true;
    if (selectedDateFilters.has('current_week') && releaseTime >= currentWeek.start.getTime() && releaseTime <= currentWeek.end.getTime()) return true;
    if (selectedDateFilters.has('next_week') && releaseTime >= nextWeek.start.getTime() && releaseTime <= nextWeek.end.getTime()) return true;
    if (selectedDateFilters.has('future') && releaseTime > todayTime) return true;
    return false;
  }

  function earningsCalendarItemMatchesFilters(item, filters = {}) {
    const {
      today,
      selectedDateFilters = new Set(),
      portfolioFilter = 'all',
      selectedFiscalYears = new Set(),
      availableYearCount = 0,
      selectedFiscalQuarters = new Set(),
      quarterOptionCount = 4,
    } = filters;
    if (portfolioFilter === 'in_portfolio' && !item.in_portfolio) return false;
    if (portfolioFilter === 'not_in_portfolio' && item.in_portfolio) return false;
    if (selectedDateFilters.size > 0 && !releaseDateMatchesEarningsCalendarDateFilters(item.release_date, today, selectedDateFilters)) return false;
    if (selectedFiscalYears.size > 0 && selectedFiscalYears.size < availableYearCount && !selectedFiscalYears.has(String(item.fiscal_year ?? ''))) return false;
    if (selectedFiscalQuarters.size > 0 && selectedFiscalQuarters.size < quarterOptionCount && !selectedFiscalQuarters.has(String(item.fiscal_quarter ?? ''))) return false;
    return true;
  }

  function earningsReleaseTimingPriority(value) {
    const normalized = String(value || '')
      .trim()
      .toLowerCase()
      .replace(/[_-]+/g, ' ')
      .replace(/\s+/g, ' ');
    if (normalized === 'before open' || normalized === 'bmo' || normalized === 'before market open') return 0;
    if (normalized === 'after close' || normalized === 'amc' || normalized === 'after market close') return 1;
    return 2;
  }

  function compareEarningsCalendarItems(leftItem, rightItem, dateDirection = 'asc') {
    const leftDate = parseCalendarDate(leftItem?.release_date);
    const rightDate = parseCalendarDate(rightItem?.release_date);
    if (!leftDate && !rightDate) {
      return String(leftItem?.symbol || '').localeCompare(String(rightItem?.symbol || ''))
        || String(leftItem?.company_name || '').localeCompare(String(rightItem?.company_name || ''));
    }
    if (!leftDate) return 1;
    if (!rightDate) return -1;

    const dateDelta = leftDate.getTime() - rightDate.getTime();
    if (dateDelta !== 0) return dateDirection === 'desc' ? -dateDelta : dateDelta;

    const timingDelta = earningsReleaseTimingPriority(leftItem?.release_timing)
      - earningsReleaseTimingPriority(rightItem?.release_timing);
    if (timingDelta !== 0) return timingDelta;

    return String(leftItem?.symbol || '').localeCompare(String(rightItem?.symbol || ''))
      || String(leftItem?.company_name || '').localeCompare(String(rightItem?.company_name || ''));
  }

  const api = {
    parseCalendarDate,
    normalizeLocalCalendarDate,
    addCalendarDays,
    getMondayWeekRange,
    releaseDateMatchesEarningsCalendarDateFilters,
    earningsCalendarItemMatchesFilters,
    earningsReleaseTimingPriority,
    compareEarningsCalendarItems,
  };

  globalScope.EarningsCalendarDateFilters = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
