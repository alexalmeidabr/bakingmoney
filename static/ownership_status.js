(function initializeOwnershipStatus(globalScope) {
  function normalizeOwnershipStatus(value, portfolioDataAvailable = true) {
    if (portfolioDataAvailable !== true) return null;
    if (value === true) return true;
    if (value === false) return false;
    return null;
  }

  function ownershipMatchesPortfolioFilter(status, portfolioFilter = 'all') {
    if (portfolioFilter === 'in_portfolio') return status === true;
    if (portfolioFilter === 'not_in_portfolio') return status === false;
    return true;
  }

  function ownershipBadge(status) {
    if (status === true) return { className: 'badge-portfolio-in', label: 'In Portfolio' };
    if (status === false) return { className: 'badge-portfolio-out', label: 'Not in Portfolio' };
    return { className: 'badge-portfolio-unavailable', label: 'Portfolio unavailable' };
  }

  function ownershipText(status) {
    if (status === true) return 'Yes';
    if (status === false) return 'No';
    return 'Unavailable';
  }

  const api = {
    normalizeOwnershipStatus,
    ownershipMatchesPortfolioFilter,
    ownershipBadge,
    ownershipText,
  };

  globalScope.OwnershipStatus = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
