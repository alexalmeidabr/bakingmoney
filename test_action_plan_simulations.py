import copy
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

import web_server as app
import test_multi_account_action_plan as account_fixtures


class SimulationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db_path = os.path.join(self.temp.name, 'sim.db')
        patch = mock.patch.object(app, 'DB_PATH', self.db_path)
        patch.start()
        self.addCleanup(patch.stop)
        app.init_db()
        self.conn = app.get_db_connection()
        self.addCleanup(lambda: self.conn.close())
        self.fixture = account_fixtures.MultiAccountActionPlanIsolationTests()
        self.fixture.save_settings(self.conn)
        for account in ('A', 'B'):
            self.fixture.save_state(self.conn, account, positions=[
                account_fixtures.position('NVDA', 10, 1000), account_fixtures.position('SGOV', 20, 2000),
            ], portfolio_value=10000, actual_cash=1000)
        self.analysis = mock.patch.object(app, 'list_analysis_symbols', return_value=self.fixture.analysis_items())
        self.analysis.start()
        self.addCleanup(self.analysis.stop)

    def create(self, **overrides):
        return app.create_action_plan_simulation(self.conn, 'A', {
            'name': 'Additional Investment', 'additional_cash_usd': 20000, **overrides,
        })

    def test_crud_duplicate_account_isolation_and_trigger_independence(self):
        app.save_manual_execution_trigger(self.conn, 'A', 'NVDA', {'buy_trigger_price': 80})
        simulation = self.create()
        sid = simulation['id']
        self.assertEqual(len(app.list_action_plan_simulations(self.conn, 'A')), 1)
        self.assertEqual(app.list_action_plan_simulations(self.conn, 'B'), [])
        self.assertEqual(app.list_simulation_triggers(self.conn, 'A', sid)[0]['buy_trigger_price'], 80)
        app.save_manual_execution_trigger(self.conn, 'A', 'NVDA', {'buy_trigger_price': 90})
        self.assertEqual(app.list_simulation_triggers(self.conn, 'A', sid)[0]['buy_trigger_price'], 80)
        app.save_simulation_trigger(self.conn, 'A', sid, 'NVDA', {'buy_trigger_price': 70})
        duplicate = app.duplicate_action_plan_simulation(self.conn, 'A', sid, {})
        self.assertNotEqual(duplicate['name'], simulation['name'])
        self.assertEqual(duplicate['additional_cash_usd'], 20000)
        self.assertEqual(app.list_simulation_triggers(self.conn, 'A', duplicate['id'])[0]['buy_trigger_price'], 70)
        app.delete_simulation_trigger(self.conn, 'A', sid, 'NVDA')
        self.assertEqual(app.list_simulation_triggers(self.conn, 'A', sid), [])
        self.assertEqual(app.get_manual_execution_trigger(self.conn, 'A', 'NVDA')['buy_trigger_price'], 90)
        changed = app.update_action_plan_simulation(self.conn, 'A', sid, {'name': 'Renamed', 'additional_cash_usd': 30000})
        self.assertEqual((changed['name'], changed['additional_cash_usd']), ('Renamed', 30000))
        with self.assertRaises(app.PortfolioAccountResolutionError):
            app.get_action_plan_simulation(self.conn, 'B', sid)
        app.delete_action_plan_simulation(self.conn, 'A', sid)
        self.assertEqual(app.list_simulation_triggers(self.conn, 'A', duplicate['id'])[0]['buy_trigger_price'], 70)
        self.assertEqual(app.get_manual_execution_trigger(self.conn, 'A', 'NVDA')['buy_trigger_price'], 90)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM action_plan_simulation_triggers WHERE simulation_id=?', (sid,)).fetchone()[0], 0)

    def test_empty_collection_never_falls_back_to_actual(self):
        app.save_manual_execution_trigger(self.conn, 'A', 'NVDA', {'buy_trigger_price': 80})
        simulation = self.create(copy_current_triggers=False)
        self.assertEqual(app.list_simulation_triggers(self.conn, 'A', simulation['id']), [])
        plan = app.build_simulation_action_plan(self.conn, 'A', simulation['id'])
        self.assertTrue(all(row['manual_trigger_status'] == 'no_manual_trigger' for row in plan['manual_execution']['linear_action_plan']))

    def test_both_workspaces_use_previous_session_prices_without_expiry(self):
        import action_plan_prices
        old = '2025-01-01T12:00:00+00:00'
        with self.conn:
            action_plan_prices.persist_observation(self.conn, 'A', 'MSFT', {
                'symbol': 'MSFT', 'price': 75, 'price_source': 'delayed_last', 'observed_at': old,
            })
        app.save_manual_execution_trigger(self.conn, 'A', 'MSFT', {'buy_trigger_price': 80})
        simulation = self.create(additional_cash_usd=0)
        actual = app.build_action_plan(self.conn, 'A', include_manual_execution=True)
        simulated = app.build_simulation_action_plan(self.conn, 'A', simulation['id'])
        self.assertEqual(actual['manual_execution'], simulated['manual_execution'])
        row = next(r for r in actual['manual_execution']['linear_action_plan'] if r['symbol'] == 'MSFT')
        self.assertEqual(row['manual_trigger_status'], 'eligible')
        self.assertEqual(row['manual_verified_price'], 75)
        self.assertEqual(row['current_price'], 75)
        self.assertEqual(row['manual_verified_quote_at'], old)
        self.assertEqual(row['manual_verified_market_observed_at'], old)
        self.assertIsNone(row['manual_verified_retrieved_at'])
        self.assertEqual(row['manual_verified_quote_time_kind'], 'market_observation')
        self.assertIsNone(row['manual_verified_quote_expires_at'])
        self.assertFalse(row['manual_trigger_blocked'])
        self.assertIn('Delayed', row['manual_price_verification_reason'])

    def test_owned_action_plan_uses_only_its_persisted_contract_observation(self):
        import action_plan_prices
        app.save_positions_cache(self.conn, [{
            'symbol': 'NVDA', 'position': 10, 'avgCost': 50, 'contract_key': 'conid:111',
            'price': None, 'price_status': 'unavailable',
        }], account_id='A')
        with self.conn:
            action_plan_prices.persist_observation(self.conn, 'A', 'NVDA', {
                'symbol': 'NVDA', 'contract_key': 'conid:111', 'price': 80,
                'price_source': 'last', 'market_observed_at': '2026-11-21T10:00:00+00:00',
            })
            action_plan_prices.persist_observation(self.conn, 'A', 'NVDA', {
                'symbol': 'NVDA', 'contract_key': 'conid:222', 'price': 200,
                'price_source': 'last', 'market_observed_at': '2026-11-22T10:00:00+00:00',
            })
        plan = app.build_action_plan(self.conn, 'A')
        row = next(item for item in plan['linear_action_plan'] if item['symbol'] == 'NVDA')
        self.assertEqual(80, row['current_price'])

    def test_unowned_contract_selection_controls_trigger_and_sizing_in_both_workspaces(self):
        import action_plan_prices
        app.save_manual_execution_trigger(self.conn, 'A', 'MSFT', {'buy_trigger_price': 80})
        simulation = self.create(additional_cash_usd=0)
        with self.conn:
            action_plan_prices.persist_observation(self.conn, 'A', 'MSFT', {
                'symbol': 'MSFT', 'contract_key': 'conid:111', 'security_type': 'STK',
                'currency': 'USD', 'price': 75, 'price_source': 'last',
                'market_observed_at': '2026-11-21T10:00:00+00:00',
            })
            action_plan_prices.persist_observation(self.conn, 'A', 'MSFT', {
                'symbol': 'MSFT', 'contract_key': 'conid:222', 'security_type': 'STK',
                'currency': 'USD', 'price': 50, 'price_source': 'last',
                'market_observed_at': '2026-11-22T10:00:00+00:00',
            })

        ambiguous = app.build_action_plan(self.conn, 'A', include_manual_execution=True)
        ambiguous_row = next(row for row in ambiguous['manual_execution']['linear_action_plan']
                             if row['symbol'] == 'MSFT')
        self.assertEqual((100, 'waiting'),
                         (ambiguous_row['current_price'], ambiguous_row['manual_trigger_status']))
        self.assertIn('multiple contract', ambiguous_row['price_warning'].lower())

        with self.conn:
            action_plan_prices.save_contract_selection(
                self.conn, 'A', 'MSFT', 'conid:111', 'STK', 'USD',
                '2026-11-22T11:00:00+00:00',
            )
        actual = app.build_action_plan(self.conn, 'A', include_manual_execution=True)
        simulated = app.build_simulation_action_plan(self.conn, 'A', simulation['id'])
        actual_row = next(row for row in actual['manual_execution']['linear_action_plan']
                          if row['symbol'] == 'MSFT')
        simulated_row = next(row for row in simulated['manual_execution']['linear_action_plan']
                             if row['symbol'] == 'MSFT')
        self.assertEqual((75, 'eligible'),
                         (actual_row['current_price'], actual_row['manual_trigger_status']))
        self.assertEqual(actual_row['current_price'], simulated_row['current_price'])
        self.assertEqual(actual_row['manual_trigger_status'], simulated_row['manual_trigger_status'])
        self.assertEqual(actual_row['suggested_share_count'], simulated_row['suggested_share_count'])

    def test_position_refresh_preserves_delayed_and_frozen_provenance(self):
        import action_plan_prices
        contract = SimpleNamespace(symbol='NVDA', conId=123, currency='USD')
        position = SimpleNamespace(contract=contract, position=10, avgCost=50)
        for data_type, label, source in ((2, 'Frozen', 'frozen'), (3, 'Delayed', 'delayed'),
                                         (4, 'Delayed-frozen', 'delayed_frozen')):
            with self.subTest(data_type=data_type):
                ticker = SimpleNamespace(marketDataType=data_type, marketPrice=lambda: 100,
                                         close=99, prevClose=99, last=100)
                rows = app._build_live_position_rows([position], {'conid:123': ticker}, app.utc_now_iso())
                self.assertIn(source, rows[0]['price_source'])
                self.assertIn(label, rows[0]['price_warning'])
                app.save_positions_cache(self.conn, rows, account_id='A')
                selected = action_plan_prices.resolve_price(app.load_positions_cache(self.conn, 'A')[0], {})
                self.assertIn(source, selected['price_source'])
                self.assertIn(label, selected['price_warning'])

    def test_validation_and_ambiguous_accounts(self):
        for payload in ({'name': ''}, {'name': ' '}, {'name': True}, {'name': 'x' * 201},
                        {'additional_cash_usd': -1}, {'additional_cash_usd': True},
                        {'additional_cash_usd': '100'}, {'additional_cash_usd': float('nan')},
                        {'additional_cash_usd': float('inf')}, {'additional_cash_usd': 1e16},
                        {'additional_cash_usd': 10**400},
                        {'copy_current_triggers': 'yes'}, {'unexpected': 1}):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                self.create(**payload)
        with self.assertRaises(app.PortfolioAccountResolutionError):
            app.list_action_plan_simulations(self.conn, None)
        for sid in (0, -1, 'bad', True):
            with self.subTest(sid=sid), self.assertRaises(ValueError):
                app.get_action_plan_simulation(self.conn, 'A', sid)

    def test_legacy_account_reconciliation_preserves_simulations_and_prices(self):
        import action_plan_prices
        with self.conn:
            self.conn.execute('DELETE FROM positions_cache')
            self.conn.execute('DELETE FROM portfolio_summary_cache')
            self.conn.execute('DELETE FROM ib_accounts')
        app.upsert_ib_account(self.conn, app.LEGACY_IB_ACCOUNT_ID)
        self.conn.commit()
        simulation = app.create_action_plan_simulation(self.conn, app.LEGACY_IB_ACCOUNT_ID, {'name': 'Legacy'})
        app.save_simulation_trigger(self.conn, app.LEGACY_IB_ACCOUNT_ID, simulation['id'], 'NVDA', {'buy_trigger_price': 80})
        with self.conn:
            action_plan_prices.persist_observation(self.conn, app.LEGACY_IB_ACCOUNT_ID, 'NVDA', {'price': 70})
        self.assertTrue(app.reconcile_legacy_account_to_real_account(self.conn, 'REAL'))
        self.assertEqual(app.get_action_plan_simulation(self.conn, 'REAL', simulation['id'])['name'], 'Legacy')
        self.assertEqual(app.list_simulation_triggers(self.conn, 'REAL', simulation['id'])[0]['buy_trigger_price'], 80)
        self.assertEqual(action_plan_prices.load_observations(self.conn, 'REAL')['NVDA'][0]['price'], 70)

    def test_zero_cash_exact_parity_and_cash_invariants_without_cache_writes(self):
        app.save_manual_execution_trigger(self.conn, 'A', 'NVDA', {'buy_trigger_price': 80, 'reserve_enabled': True, 'reserve_percentage': 60})
        simulation = self.create(additional_cash_usd=0)
        sid = simulation['id']
        actual = app.build_action_plan(self.conn, 'A', include_manual_execution=True)
        zero = app.build_simulation_action_plan(self.conn, 'A', sid)
        self.assertEqual({k: v for k, v in zero.items() if k != 'simulation'}, actual)
        positions = copy.deepcopy(app.load_positions_cache(self.conn, 'A'))
        summary = copy.deepcopy(app.load_portfolio_summary_cache(self.conn, 'A'))
        app.update_action_plan_simulation(self.conn, 'A', sid, {'additional_cash_usd': 20000})
        simulated = app.build_simulation_action_plan(self.conn, 'A', sid)
        for key in ('portfolio_value_used', 'total_portfolio_value', 'actual_cash', 'cash_like_available'):
            self.assertEqual(simulated['summary'][key], actual['summary'][key] + 20000, key)
        self.assertEqual(simulated['summary']['cash_equivalent_value'], 2000)
        for before, after in zip(actual['linear_action_plan'], simulated['linear_action_plan']):
            for key in ('owned_share_quantity', 'current_price', 'linear_allocation_score', 'target_weight_mid'):
                self.assertEqual(before[key], after[key], key)
            self.assertAlmostEqual(after['current_position_weight'], before['current_position_weight'] / 3)
        linear = simulated['summary']['linear_summary']
        base_linear = actual['summary']['linear_summary']
        self.assertAlmostEqual(linear['target_reserve_amount'], base_linear['target_reserve_amount'] * 3)
        self.assertGreater(linear['available_buy_budget'], base_linear['available_buy_budget'])
        self.assertEqual(app.load_positions_cache(self.conn, 'A'), positions)
        self.assertEqual(app.load_portfolio_summary_cache(self.conn, 'A'), summary)

    def test_positions_plus_cash_fallback_counts_cash_equivalents_once(self):
        app.save_portfolio_summary_cache(self.conn, {'base_currency': 'USD', 'actual_cash': 1000}, account_id='A')
        simulation = self.create()
        plan = app.build_simulation_action_plan(self.conn, 'A', simulation['id'])
        self.assertEqual(plan['summary']['portfolio_value_source'], 'positions_plus_cash')
        self.assertEqual(plan['summary']['portfolio_value_used'], 24000)
        self.assertEqual(plan['summary']['actual_cash'], 21000)
        self.assertEqual(plan['summary']['cash_like_available'], 23000)
        self.assertEqual(plan['summary']['cash_equivalent_value'], 2000)

    def test_competing_waiting_reservations_protect_reserve_and_use_simulated_targets(self):
        for symbol in ('NVDA', 'MSFT'):
            app.save_manual_execution_trigger(self.conn, 'A', symbol, {
                'buy_trigger_price': 80, 'reserve_enabled': True, 'reserve_percentage': 100,
            })
        simulation = self.create(additional_cash_usd=1000)
        plan = app.build_simulation_action_plan(self.conn, 'A', simulation['id'])
        rows = plan['manual_execution']['linear_action_plan']
        summary = plan['manual_execution']['summary']
        waiting = [row for row in rows if row['manual_trigger_status'] == 'waiting']
        self.assertEqual(len(waiting), 2)
        for row in waiting:
            target = 11000 * row['target_weight_mid'] / 100
            gap = max(0, target - row['owned_share_quantity'] * 80)
            self.assertAlmostEqual(row['requested_reservation'], app.whole_shares_for_amount(gap, 80) * 80)
            self.assertEqual(row['suggested_share_count'], 0)
        self.assertAlmostEqual(summary['requested_reservations'], sum(r['requested_reservation'] for r in rows))
        self.assertLessEqual(summary['fulfilled_reservations'], summary['available_buy_budget_before_manual_reservations'])
        self.assertGreaterEqual(summary['available_buy_budget'], 0)
        self.assertLessEqual(summary['fulfilled_reservations'] + summary['available_buy_budget'],
                             max(0, 4000 - summary['target_reserve_amount']) + 1e-6)

    def test_creation_rolls_back_if_copying_triggers_fails(self):
        app.save_manual_execution_trigger(self.conn, 'A', 'NVDA', {'buy_trigger_price': 80})
        self.conn.execute("CREATE TRIGGER reject_sim_trigger BEFORE INSERT ON action_plan_simulation_triggers BEGIN SELECT RAISE(ABORT, 'copy failed'); END")
        self.conn.commit()
        with self.assertRaises(app.sqlite3.IntegrityError):
            self.create()
        self.assertEqual(app.list_action_plan_simulations(self.conn, 'A'), [])

    def test_reopening_uses_latest_portfolio_and_survives_restart_and_backup(self):
        simulation = self.create()
        app.save_simulation_trigger(self.conn, 'A', simulation['id'], 'NVDA', {'buy_trigger_price': 75})
        self.fixture.save_state(self.conn, 'A', positions=[account_fixtures.position('NVDA', 30, 3000)], portfolio_value=15000, actual_cash=4000)
        self.assertEqual(app.build_simulation_action_plan(self.conn, 'A', simulation['id'])['summary']['portfolio_value_used'], 35000)
        backup = os.path.join(self.temp.name, 'backup.db')
        app._create_db_backup_snapshot(self.db_path, backup)
        app._validate_backup_db_file(backup)
        with mock.patch.object(app, 'DB_PATH', backup):
            app.init_db()
            conn = app.get_db_connection()
            try:
                self.assertEqual(app.get_action_plan_simulation(conn, 'A', simulation['id'])['additional_cash_usd'], 20000)
                self.assertEqual(app.list_simulation_triggers(conn, 'A', simulation['id'])[0]['buy_trigger_price'], 75)
            finally:
                conn.close()
        self.conn.execute('DROP TABLE action_plan_simulation_triggers')
        self.conn.execute('DROP TABLE action_plan_simulations')
        self.conn.commit()
        app.init_db()
        self.assertEqual(app.list_action_plan_simulations(self.conn, 'A'), [])
        self.assertEqual(app.load_positions_cache(self.conn, 'A')[0]['position'], 30)

    def test_api_routes_crud_triggers_calculation_and_errors(self):
        class Capture(app.BakingMoneyHandler):
            body = None

            def _read_json_body(self):
                return self.body

            def _send_json(self, payload, status=200):
                self.payload, self.status = payload, status

        handler = Capture.__new__(Capture)

        def request(method, path, body=None, account='A'):
            handler.path = path + ('&' if '?' in path else '?') + 'account_id=' + account
            handler.body = body
            getattr(handler, 'do_' + method)()
            return handler.status, handler.payload

        status, payload = request('POST', '/api/action-plan-simulations', {'name': 'API', 'additional_cash_usd': 20000})
        self.assertEqual(status, 201)
        sid = payload['simulation']['id']
        path = f'/api/action-plan-simulations/{sid}'
        self.assertEqual(request('GET', '/api/action-plan-simulations')[1]['simulations'][0]['id'], sid)
        self.assertEqual(request('GET', path)[1]['simulation']['name'], 'API')
        self.assertEqual(request('GET', path, account='B')[0], 404)
        self.assertEqual(request('PUT', path, {'name': 'New', 'additional_cash_usd': 30000})[1]['simulation']['name'], 'New')
        self.assertEqual(request('PUT', path, {'additional_cash_usd': True})[0], 400)
        trigger_path = path + '/triggers/NVDA'
        self.assertEqual(request('PUT', trigger_path, {'buy_trigger_price': 90})[1]['trigger']['buy_trigger_price'], 90)
        self.assertEqual(request('GET', trigger_path)[1]['trigger']['symbol'], 'NVDA')
        self.assertEqual(len(request('GET', path + '/triggers')[1]['triggers']), 1)
        self.assertEqual(request('GET', trigger_path, account='B')[0], 404)
        self.assertEqual(request('PUT', trigger_path, {'reserve_percentage': 101})[0], 400)
        plan_status, plan = request('GET', path + '/action-plan?execution_modes=both')
        self.assertEqual(plan_status, 200)
        self.assertEqual(plan['summary']['portfolio_value_used'], 40000)
        self.assertIn('manual_execution', plan)
        with mock.patch.object(app, 'get_analysis_detail', return_value=None):
            status, detail = request('GET', path + '/action-plan/NVDA?execution_modes=both')
            self.assertEqual(status, 200)
            self.assertEqual(detail['action_detail']['total_portfolio_value'], 40000)
            self.assertIn('manual_execution_detail', detail)
            self.assertEqual(request('GET', path + '/action-plan/UNKNOWN')[0], 404)
        self.assertEqual(request('GET', path + '/action-plan?execution_modes=bad')[0], 400)
        self.assertEqual(request('POST', path + '/duplicate', {})[0], 201)
        self.assertEqual(request('DELETE', trigger_path)[1], {'deleted': True})
        self.assertEqual(request('GET', trigger_path)[0], 404)
        self.assertEqual(request('DELETE', path)[1], {'deleted': True})
        self.assertEqual(request('GET', path)[0], 404)
        self.assertEqual(request('GET', '/api/action-plan-simulations/bad')[0], 400)
        self.assertEqual(request('GET', '/api/action-plan-simulations/999999999')[0], 404)


if __name__ == '__main__':
    unittest.main()
