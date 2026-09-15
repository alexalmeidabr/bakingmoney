(function initializePortfolioAccountSelector(root) {
  const STORAGE_KEY = 'bakingmoney.portfolioAccountId';

  function normalizeAccountId(value) {
    const text = String(value ?? '').trim();
    return text || null;
  }

  function getAccountLabel(account) {
    const displayName = String(account?.display_name ?? '').trim();
    if (displayName) return displayName;
    return String(account?.masked_account_id ?? '').trim() || 'Unknown account';
  }

  function getAccountOptionLabel(account) {
    const label = getAccountLabel(account);
    return account?.portfolio_data_available === false
      ? `${label} - portfolio data unavailable`
      : label;
  }

  function resolveInitialPortfolioAccount(accounts, savedAccountId) {
    const normalizedAccounts = Array.isArray(accounts) ? accounts : [];
    const saved = normalizeAccountId(savedAccountId);
    if (!normalizedAccounts.length) {
      return { selectedAccountId: null, shouldClearSaved: Boolean(saved), shouldSaveSelection: false };
    }

    if (saved && normalizedAccounts.some((account) => normalizeAccountId(account?.account_id) === saved)) {
      return { selectedAccountId: saved, shouldClearSaved: false, shouldSaveSelection: false };
    }

    if (saved) {
      const fallback = resolveInitialPortfolioAccount(normalizedAccounts, null);
      return {
        selectedAccountId: fallback.selectedAccountId,
        shouldClearSaved: true,
        shouldSaveSelection: fallback.shouldSaveSelection,
      };
    }

    if (normalizedAccounts.length === 1) {
      return {
        selectedAccountId: normalizeAccountId(normalizedAccounts[0]?.account_id),
        shouldClearSaved: false,
        shouldSaveSelection: true,
      };
    }

    const readyAccounts = normalizedAccounts.filter((account) => account?.portfolio_data_available === true);
    if (readyAccounts.length === 1) {
      return {
        selectedAccountId: normalizeAccountId(readyAccounts[0]?.account_id),
        shouldClearSaved: false,
        shouldSaveSelection: true,
      };
    }

    return { selectedAccountId: null, shouldClearSaved: false, shouldSaveSelection: false };
  }

  function isPortfolioAccountScopedUrl(url) {
    const parsed = new URL(url, 'http://bakingmoney.local');
    return parsed.pathname === '/api/positions'
      || parsed.pathname === '/api/action-plan'
      || parsed.pathname.startsWith('/api/action-plan/');
  }

  function withPortfolioAccount(url, accountId) {
    const selected = normalizeAccountId(accountId);
    if (!selected) return url;
    const parsed = new URL(url, 'http://bakingmoney.local');
    if (!isPortfolioAccountScopedUrl(url)) return url;
    parsed.searchParams.set('account_id', selected);
    return `${parsed.pathname}${parsed.search}${parsed.hash}`;
  }

  const api = {
    STORAGE_KEY,
    getAccountLabel,
    getAccountOptionLabel,
    isPortfolioAccountScopedUrl,
    normalizeAccountId,
    resolveInitialPortfolioAccount,
    withPortfolioAccount,
  };

  root.PortfolioAccountSelector = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
}(typeof globalThis !== 'undefined' ? globalThis : this));
