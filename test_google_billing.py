import datetime as dt
from types import SimpleNamespace
from zoneinfo import ZoneInfo
import unittest
from unittest.mock import patch

import google_billing_sync as billing

NOW = dt.datetime(2026, 11, 11, 12, tzinfo=dt.timezone.utc)


class BillingTests(unittest.TestCase):
    def setUp(self):
        scoped=patch.multiple(billing,PROJECT='example-project',ACCOUNT='000000-000000-000000',ZONE=ZoneInfo('Europe/Zurich'))
        scoped.start();self.addCleanup(scoped.stop)

    def test_nested_export_rows(self):
        fields = [
            {'name': 'cost', 'type': 'FLOAT'},
            {'name': 'project', 'type': 'RECORD', 'fields': [{'name': 'id', 'type': 'STRING'}]},
            {'name': 'credits', 'type': 'RECORD', 'mode': 'REPEATED', 'fields': [{'name': 'amount', 'type': 'FLOAT'}]},
        ]
        row = {'f': [{'v': '0.12'}, {'v': {'f': [{'v': billing.PROJECT}]}}, {'v': [{'v': {'f': [{'v': '-0.02'}]}}]}]}
        decoded = billing.decode_row(fields, row)
        self.assertEqual(decoded, {'cost': '0.12', 'project': {'id': billing.PROJECT}, 'credits': [{'amount': '-0.02'}]})
        with self.assertRaises(ValueError):
            billing.decode_row(fields, {'f': []})

    def test_net_costs_currencies_and_project_scope(self):
        base = {'project': {'id': billing.PROJECT}, 'usage_start_time': str(NOW.timestamp()), 'cost': '0.12', 'currency': 'USD', 'credits': [{'amount': '-0.02'}]}
        rows = [base, {**base, 'currency': 'CHF'}, {**base, 'project': {'id': 'another-project'}, 'cost': '1000'}]
        result = billing.aggregate(rows, NOW)
        self.assertEqual(result['matchedRows'], 2)
        self.assertEqual(result['today'], [{'currency': 'CHF', 'amount': .1}, {'currency': 'USD', 'amount': .1}])
        self.assertEqual(len(result['periods']), 2)
        self.assertEqual(result['periods'][0]['amount'], .1)

    def test_wallet_classification_distinguishes_gemini_from_other_services(self):
        base = {'project': {'id': billing.PROJECT}, 'usage_start_time': str(NOW.timestamp()), 'cost': '0.12', 'currency': 'CHF'}
        result = billing.aggregate([{**base, 'service': {'id': billing.GEMINI_API_SERVICE}}, {**base, 'service': {'id': 'bigquery'}}], NOW)
        self.assertEqual(sorted(row['walletEligible'] for row in result['periods']), [False, True])

    def test_zurich_day_and_no_false_zero_for_missing_today(self):
        before = NOW - dt.timedelta(days=1)
        row = {'project': {'id': billing.PROJECT}, 'usage_start_time': str(before.timestamp()), 'cost': '1', 'currency': 'USD'}
        self.assertEqual(billing.aggregate([row], NOW)['today'], [])
        midnight = dt.datetime(2026, 11, 10, 23, 30, tzinfo=dt.timezone.utc)
        row['usage_start_time'] = str(midnight.timestamp())
        self.assertEqual(billing.aggregate([row], NOW)['today'], [{'currency': 'USD', 'amount': 1}])

    def test_google_table_missing_waits_without_amount(self):
        with patch('google_billing_sync.subprocess.run', return_value=SimpleNamespace(returncode=0, stdout='fake-test-token')), \
             patch('google_billing_sync.get', side_effect=billing.GoogleError(404, [])), \
             patch('google_billing_sync.Path.exists', return_value=True):
            result = billing.sync()
        self.assertEqual(result['state'], 'pending_export')
        self.assertEqual(result['today'], [])
        self.assertFalse(result['officialBalanceConnected'])

    def test_changing_table_never_publishes_partial_cost(self):
        schema = [{'name': name, 'type': 'STRING'} for name in ['project', 'cost', 'currency', 'usage_start_time']]
        values = [
            {'tables': [{'tableReference': {'tableId': 'gcp_billing_export_v1_' + billing.ACCOUNT.replace('-', '_')}}]},
            {'schema': {'fields': schema}, 'numRows': '0', 'lastModifiedTime': '1'},
            {'rows': []},
            {'numRows': '1', 'lastModifiedTime': '2'},
        ]
        with patch('google_billing_sync.subprocess.run', return_value=SimpleNamespace(returncode=0, stdout='fake-test-token')), \
             patch('google_billing_sync.get', side_effect=values), \
             patch('google_billing_sync.Path.exists', return_value=True):
            result = billing.sync()
        self.assertEqual(result['state'], 'export_updating')
        self.assertEqual(result['today'], [])


if __name__ == '__main__':
    unittest.main()
