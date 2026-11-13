// Reproducible screenshots with synthetic data; no portfolio database or TWS access.
const fs = require('node:fs');
const http = require('node:http');
const os = require('node:os');
const path = require('node:path');
const { spawn } = require('node:child_process');
const { setTimeout: delay } = require('node:timers/promises');

const root = path.resolve(__dirname, '..');
const output = path.join(root, 'docs', 'screenshots');
const chromePath = process.env.CHROME_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const mime = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.svg': 'image/svg+xml', '.png': 'image/png' };

const baseline = {
  symbol: 'NVDA', company_name: 'NVIDIA', action: 'Add', desired_action: 'Add', rating: 'Buy',
  current_price: 100, expected_price: 160, expected_cagr: 18, upside: 60,
  current_position_market_value: 0, current_position_weight: 0, target_gap_amount: 5000,
  action_amount: 5000, action_amount_label: 'Buy $5,000', suggested_share_count: 50,
  funding_status: 'Funded', target_weight_low: 4, target_weight_mid: 5, target_weight_high: 6,
  linear_target_weight_low: 4, linear_target_weight_mid: 5, linear_target_weight_high: 6,
  position_gap_to_mid: 5, linear_allocation_score: 8.4, core_confidence_diff: 6,
  core_bullish_confidence: 8, core_bearish_confidence: 2, potential_confidence_diff: 4,
  potential_bullish_confidence: 7, potential_bearish_confidence: 3,
  executable_action_amount: 5000, owned_share_quantity: 0,
};
const second = { ...baseline, symbol: 'META', company_name: 'Meta Platforms', action: 'Trim',
  desired_action: 'Trim', rating: 'Hold', current_price: 650, expected_price: 800,
  current_position_market_value: 13000, current_position_weight: 13,
  target_gap_amount: 3000, action_amount: 3000, action_amount_label: 'Sell $3,000',
  suggested_share_count: 4, executable_action_amount: 2600, target_weight_mid: 10,
  linear_target_weight_mid: 10, position_gap_to_mid: -3, linear_allocation_score: 6.1 };
const manual = [
  { ...baseline, action: 'Watch', recommended_action: 'Add', suggested_share_count: 0,
    executable_action: 'Watch', executable_action_amount: 0, manual_trigger_status: 'waiting',
    manual_trigger_price: 80, manual_trigger_direction: 'at_or_below', manual_verified_price: 100,
    manual_verified_quote_at: new Date().toISOString(), manual_verified_quote_expires_at: new Date(Date.now() + 300000).toISOString(),
    planned_action_amount: 5000, planned_share_count: 50, reserve_enabled: true,
    reserve_percentage: 60, planned_purchase_amount_at_trigger: 5000, requested_reservation: 3000,
    fulfilled_reservation: 2200, unfulfilled_reservation: 800,
    fulfilled_reservation_from_current_cash_like: 1200, fulfilled_reservation_from_projected_proceeds: 1000,
    funding_status: 'Manual trigger waiting' },
  { ...second, action: 'Hold', recommended_action: 'Trim', suggested_share_count: 0,
    executable_action: 'Hold', executable_action_amount: 0, manual_trigger_status: 'waiting',
    manual_trigger_price: 700, manual_trigger_direction: 'at_or_above', manual_verified_price: 650,
    manual_verified_quote_at: new Date().toISOString(), manual_verified_quote_expires_at: new Date(Date.now() + 300000).toISOString(),
    planned_action_amount: 3000, planned_share_count: 4, reserve_enabled: false,
    reserve_percentage: 0, requested_reservation: 0, fulfilled_reservation: 0,
    funding_status: 'Manual trigger waiting' },
];
const summary = {
  portfolio_opportunity_score: 0.7, dynamic_reserve_pct: 15, maximum_deployable_equity_pct: 85,
  reserve_benchmark_yield: 4, target_reserve_amount: 15000, current_cash_unallocated: 20000,
  reserve_excess: 5000, reserve_scale_factor: 1, linear_allocated_target_total: 80,
  current_equity_allocation: 60, cash_available_for_linear_buys: 7600,
  available_buy_budget: 7600, total_add_demand: 5000, funded_add_amount: 5000,
  unfunded_add_demand: 0, eligible_stock_count: 2, capped_stock_count: 0,
};
const manualSummary = { ...summary, available_buy_budget_before_manual_reservations: 5000,
  requested_reservations: 3000, fulfilled_reservations: 2200, unfulfilled_reservations: 800,
  fulfilled_reservations_from_current_cash_like: 1200, fulfilled_reservations_from_projected_proceeds: 1000,
  available_buy_budget: 2800, cash_available_for_linear_buys: 2800, funded_add_amount: 0,
  remaining_buy_budget: 2800, executable_sell_trim_proceeds: 0 };
const payload = { linear_action_plan: [baseline, second], summary: { linear_summary: summary },
  manual_execution: { linear_action_plan: manual, summary: manualSummary } };

async function main() {
  fs.mkdirSync(output, { recursive: true });
  const server = http.createServer((request, response) => {
    const pathname = new URL(request.url, 'http://localhost').pathname;
    if (pathname.startsWith('/api/')) {
      response.setHeader('Content-Type', 'application/json');
      response.end(JSON.stringify(pathname === '/api/ib-accounts'
        ? { accounts: [{ account_id: 'U_DEMO', display_name: 'Demo Portfolio', portfolio_data_available: true }] }
        : pathname === '/api/analysis' ? { analysis: [] }
          : pathname.startsWith('/api/positions') ? { positions: [] } : {}));
      return;
    }
    const file = path.resolve(root, `.${pathname === '/' ? '/static/index.html' : pathname}`);
    if (!file.startsWith(root + path.sep) || !fs.existsSync(file) || !fs.statSync(file).isFile()) {
      response.writeHead(404).end(); return;
    }
    response.setHeader('Content-Type', mime[path.extname(file)] || 'application/octet-stream');
    fs.createReadStream(file).pipe(response);
  });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const sitePort = server.address().port;
  const chromePort = 19247;
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'bakingmoney-screenshot-'));
  const chrome = spawn(chromePath, [
    '--headless=new', '--no-first-run', '--no-default-browser-check', '--remote-allow-origins=*',
    `--remote-debugging-port=${chromePort}`, `--user-data-dir=${profile}`,
    '--window-size=1440,1200', 'about:blank',
  ], { stdio: 'ignore', windowsHide: true });
  let socket;
  try {
    let pages;
    for (let attempt = 0; attempt < 50; attempt += 1) {
      try { pages = await (await fetch(`http://127.0.0.1:${chromePort}/json/list`)).json(); break; }
      catch { await delay(200); }
    }
    if (!pages?.[0]?.webSocketDebuggerUrl) throw new Error('Chrome DevTools did not start');
    socket = new WebSocket(pages[0].webSocketDebuggerUrl);
    await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject; });
    let nextId = 0;
    const pending = new Map();
    socket.onmessage = ({ data }) => {
      const message = JSON.parse(data);
      if (!message.id) return;
      const waiter = pending.get(message.id);
      if (waiter) { pending.delete(message.id); message.error ? waiter.reject(new Error(message.error.message)) : waiter.resolve(message.result); }
    };
    const send = (method, params = {}) => new Promise((resolve, reject) => {
      const id = ++nextId;
      pending.set(id, { resolve, reject });
      socket.send(JSON.stringify({ id, method, params }));
    });
    const evaluate = async (expression) => {
      const result = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
      if (result.exceptionDetails) throw new Error(result.exceptionDetails.text + ': ' + (result.exceptionDetails.exception?.description || ''));
      return result.result?.value;
    };
    const screenshot = async (name) => {
      await evaluate('window.scrollTo(0, 0)');
      const result = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
      fs.writeFileSync(path.join(output, name), Buffer.from(result.data, 'base64'));
    };
    await send('Page.enable');
    await send('Runtime.enable');
    await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1200, deviceScaleFactor: 1, mobile: false });
    await send('Page.navigate', { url: `http://127.0.0.1:${sitePort}/` });
    for (let attempt = 0; attempt < 50; attempt += 1) {
      if (await evaluate('typeof renderActionPlan === "function"')) break;
      await delay(100);
    }
    await delay(400);
    await evaluate(`selectedPortfolioAccountId = 'U_DEMO'; latestActionPlanPayload = ${JSON.stringify(payload)}; setView('action-plan', {skipLoad:true}); renderActionPlan(); actionPlanStatusEl.textContent = 'Loaded 2 Linear Allocation rows.';`);
    if (!await evaluate('document.querySelectorAll("#action-plan-linear-actions-table tbody tr").length === 2')) throw new Error('Baseline table did not render');
    await screenshot('action-plan-without-triggers.png');
    await evaluate("setActionPlanExecutionMode('with')");
    if (!await evaluate('document.querySelector("#action-plan-linear-actions-table tbody").textContent.includes("Waiting")')) throw new Error('Manual table did not render');
    await screenshot('action-plan-with-triggers.png');
    await evaluate(`renderManualTriggerDetail('NVDA', {buy_trigger_price:80, sell_trigger_price:null, sell_trigger_direction:'at_or_above', reserve_enabled:true, reserve_percentage:60}); latestActionPlanDetailPayload = {action_detail:${JSON.stringify(baseline)}, manual_execution_detail:${JSON.stringify(manual[0])}}; renderSelectedActionPlanDetail(latestActionPlanDetailPayload);`);
    if (!await evaluate("document.querySelector('[data-trigger-field=\"buy_trigger_price\"]')?.value === '80'")) throw new Error('Editor did not render');
    await screenshot('manual-execution-trigger-editor.png');
    process.stdout.write(`Captured three screenshots in ${output}\n`);
  } finally {
    socket?.close();
    chrome.kill();
    server.close();
    await Promise.race([new Promise((resolve) => chrome.once('exit', resolve)), delay(2000)]);
    const resolvedProfile = fs.realpathSync(profile);
    const resolvedTemp = fs.realpathSync(os.tmpdir());
    if (resolvedProfile.startsWith(path.join(resolvedTemp, 'bakingmoney-screenshot-'))) {
      fs.rmSync(resolvedProfile, { recursive: true, force: true });
    }
  }
}

main().catch((error) => { process.stderr.write(`${error.stack}\n`); process.exitCode = 1; });
