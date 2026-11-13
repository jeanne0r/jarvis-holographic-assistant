import datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from usage import Ledger, estimate, google_credit

NOW = dt.datetime(2026, 11, 11, 12, tzinfo=dt.timezone.utc)
EXAMPLE = {'promptTokenCount': 1000, 'responseTokenCount': 200,
           'promptTokensDetails': [{'modality': 'TEXT', 'tokenCount': 400}, {'modality': 'AUDIO', 'tokenCount': 600}],
           'responseTokensDetails': [{'modality': 'AUDIO', 'tokenCount': 200}], 'thoughtsTokenCount': 50}
COST = 400 * 750 + 600 * 3000 + 200 * 12000 + 50 * 4500


class UsageTests(unittest.TestCase):
    def setUp(self):
        scoped=patch('usage.ZONE',ZoneInfo('Europe/Zurich'));scoped.start();self.addCleanup(scoped.stop)
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).parent / 'data', prefix='usage-test-')
        self.path = Path(self.temp.name) / 'usage.sqlite'
        self.ledger = Ledger(self.path)
        self.sid = str(uuid4())
        self.ledger.session({'id': self.sid, 'model': 'models/gemini-3.8-live'}, NOW)

    def tearDown(self):
        self.ledger.db.close()
        self.temp.cleanup()

    def report(self, seq, now=NOW, usage=EXAMPLE):
        return self.ledger.report({'sessionId': self.sid, 'sequence': seq, 'usage': usage}, now)

    def test_modalities_thoughts_and_history(self):
        self.assertEqual(estimate(EXAMPLE)[0], COST)
        self.report(1)
        self.assertAlmostEqual(self.report(2)['todayUsd'], 2 * COST / 1e9)
        # Re-read prompt/context is billed again each turn, not delta-subtracted.
        larger = {**EXAMPLE, 'promptTokenCount': 1200}
        self.assertEqual(estimate(larger)[0], COST + 200 * 3000)

    def test_idempotent_persisted_reports(self):
        self.report(1)
        self.report(1)
        other = Ledger(self.path)
        self.assertEqual(other.summary(NOW)['reportsToday'], 1)
        self.assertAlmostEqual(other.summary(NOW)['todayUsd'], COST / 1e9)
        other.db.close()

    def test_local_day_and_midnight_retry(self):
        before = dt.datetime(2026, 11, 11, 22, 59, tzinfo=dt.timezone.utc)
        after = before + dt.timedelta(minutes=2)
        self.report(1, before)
        self.assertEqual(self.report(2, after)['day'], '2026-11-12')
        self.assertAlmostEqual(self.report(1, after)['todayUsd'], COST / 1e9)

    def test_balance_reconciliation_keeps_daily_costs(self):
        self.report(1)
        snapshot = self.ledger.balance({'amount': 15.99, 'currency': 'USD'}, NOW)
        self.assertEqual(snapshot['balance']['remaining'], 15.99)
        self.assertAlmostEqual(snapshot['todayUsd'], COST / 1e9)
        self.assertAlmostEqual(self.report(2)['balance']['remaining'], 15.99 - COST / 1e9)
        self.ledger.balance({'amount': 20, 'currency': 'USD'}, NOW)
        self.assertEqual(self.ledger.summary(NOW)['balance']['remaining'], 20)
        self.assertAlmostEqual(self.ledger.summary(NOW)['todayUsd'], 2 * COST / 1e9)

    def test_offline_reports_keep_their_original_day_and_balance(self):
        tomorrow = NOW + dt.timedelta(days=1)
        self.ledger.balance({'amount': 15.99, 'currency': 'USD'}, tomorrow)
        result = self.ledger.report({'sessionId': self.sid, 'sequence': 1, 'usage': EXAMPLE, 'occurredAt': NOW.isoformat()}, tomorrow)
        self.assertEqual(result['todayUsd'], 0)
        self.assertEqual(result['balance']['remaining'], 15.99)
        self.assertAlmostEqual(self.ledger.summary(NOW)['todayUsd'], COST / 1e9)

    def test_fx_never_subtracts_usd_directly_from_chf(self):
        with patch('usage.fx_quote', return_value=(.8, '2026-11-11')):
            self.ledger.balance({'amount': 15.99, 'currency': 'CHF'}, NOW)
        self.assertAlmostEqual(self.report(1)['balance']['remaining'], 15.99 - COST / 1e9 * .8)

    def test_validation_unknown_prices_and_no_false_zero(self):
        for bad in [-1, float('nan'), True, '100']:
            with self.assertRaises(ValueError):
                estimate({'promptTokenCount': bad})
        with self.assertRaises(ValueError):
            self.ledger.report({'sessionId': 'unknown', 'sequence': 1, 'usage': EXAMPLE}, NOW)
        with self.assertRaises(ValueError):
            estimate({**EXAMPLE, 'promptTokenCount': 1})
        self.ledger.balance({'amount': 15.99, 'currency': 'USD'}, NOW)
        self.ledger.db.execute('UPDATE sessions SET model=? WHERE id=?', ('unknown-model', self.sid))
        self.ledger.db.commit()
        summary = self.report(1)
        self.assertIsNone(summary['todayUsd'])
        self.assertIsNone(summary['balance']['remaining'])
        self.assertEqual(summary['unknownPriceReports'], 1)

    def test_google_balance_ignores_local_tokens_and_repeated_sync(self):
        pending = {'state': 'pending_export', 'today': []}
        with patch('usage.google_snapshot', return_value=pending):
            result = self.ledger.balance({'amount': 15.96, 'currency': 'CHF', 'deductionSource': 'google-export'}, NOW)
            self.assertEqual(result['balance']['remaining'], 15.96)
            self.assertEqual(result['balance']['status'], 'waiting_google')
            self.assertEqual(self.report(1)['balance']['remaining'], 15.96)
        snapshot = {'state': 'ready', 'checkedAt': (NOW + dt.timedelta(hours=2)).isoformat(),
                    'periods': [{'start': NOW.isoformat(), 'end': (NOW + dt.timedelta(hours=1)).isoformat(), 'amount': .25, 'currency': 'CHF', 'walletEligible': True}]}
        with patch('usage.google_snapshot', return_value=snapshot):
            a = self.ledger.summary(NOW + dt.timedelta(hours=2))
            b = self.ledger.summary(NOW + dt.timedelta(hours=2))
        self.assertEqual(a['balance']['remaining'], 15.71)
        self.assertEqual(b['balance']['remaining'], 15.71)
        self.assertNotIn('periods', a['google'])

    def test_google_wallet_excludes_postpaid_services_and_unknown_scope(self):
        base = {'amount': 15.96, 'currency': 'CHF', 'updatedAt': NOW.isoformat(), 'walletScope': 'gemini-api'}
        period = {'start': NOW.isoformat(), 'end': (NOW + dt.timedelta(hours=1)).isoformat(), 'amount': .25, 'currency': 'CHF', 'walletEligible': True}
        snapshot = {'checkedAt': NOW.isoformat(), 'periods': [period, {**period, 'amount': 100, 'walletEligible': False}]}
        self.assertEqual(google_credit(base, snapshot, {}, NOW)['remaining'], 15.71)
        snapshot['periods'].append({**period, 'walletEligible': None})
        self.assertIsNone(google_credit(base, snapshot, {}, NOW)['remaining'])

    def test_historical_export_does_not_claim_current_credit_is_calculated(self):
        base = {'amount': 15.96, 'currency': 'CHF', 'updatedAt': NOW.isoformat(), 'walletScope': 'gemini-api'}
        snapshot = {'state': 'awaiting_today', 'checkedAt': NOW.isoformat(), 'periods': [
            {'start': (NOW - dt.timedelta(days=30)).isoformat(), 'end': (NOW - dt.timedelta(days=29)).isoformat(),
             'amount': 10, 'currency': 'CHF', 'walletEligible': True}]}
        result = google_credit(base, snapshot, {}, NOW)
        self.assertEqual(result['remaining'], 15.96)
        self.assertEqual(result['status'], 'waiting_google')

    def test_google_backfill_overlap_and_corrections(self):
        reference = NOW + dt.timedelta(minutes=30)
        base = {'amount': 15.96, 'currency': 'CHF', 'updatedAt': reference.isoformat(), 'referenceAt': reference.isoformat()}
        snapshot = {'state': 'ready', 'checkedAt': (NOW + dt.timedelta(hours=2)).isoformat(), 'periods': [
            {'start': (NOW - dt.timedelta(hours=1)).isoformat(), 'end': NOW.isoformat(), 'amount': 100, 'currency': 'CHF'},
            {'start': NOW.isoformat(), 'end': (NOW + dt.timedelta(hours=1)).isoformat(), 'amount': .6, 'currency': 'CHF'},
            {'start': (NOW + dt.timedelta(hours=1)).isoformat(), 'end': (NOW + dt.timedelta(hours=2)).isoformat(), 'amount': .2, 'currency': 'CHF'},
        ]}
        result = google_credit(base, snapshot, {}, NOW + dt.timedelta(hours=2))
        self.assertEqual(result['deducted'], .5)
        self.assertEqual(result['remaining'], 15.46)
        self.assertTrue(result['prorated'])
        snapshot['periods'][-1]['amount'] = .1
        self.assertEqual(google_credit(base, snapshot, {}, NOW + dt.timedelta(hours=2))['remaining'], 15.56)

    def test_speech_models_have_separate_rates_and_unknown_usage(self):
        from usage import model_rates
        tts = model_rates('gemini-3.8-flash-lite-tts', NOW)
        self.assertEqual(tts['inputText'], 500)
        self.assertEqual(model_rates('gemini-3.5-flash-lite', NOW)['inputText'], 300)
        self.assertEqual(model_rates('gemini-3.5-flash-lite', NOW)['outputText'], 2500)
        self.assertEqual(tts['outputAudio'], 6000)
        self.assertEqual(model_rates('gemini-3.8-flash-lite-tts', NOW.replace(year=2027))['outputAudio'], 12000)
        self.assertEqual(model_rates('gemini-3.5-transcribe', NOW)['outputText'], 12000)
        sid = str(uuid4())
        self.ledger.session({'id':sid,'model':'gemini-3.8-flash-lite-tts'}, NOW)
        usage = {'promptTokenCount':5,'responseTokenCount':36,'promptTokensDetails':[{'modality':'TEXT','tokenCount':5}],'responseTokensDetails':[{'modality':'AUDIO','tokenCount':36}]}
        self.ledger.report({'sessionId':sid,'sequence':1,'usage':usage}, NOW)
        cost = self.ledger.db.execute('SELECT cost_nano FROM reports WHERE session_id=?', (sid,)).fetchone()[0]
        self.assertEqual(cost, 5*500+36*6000)
        self.ledger.report({'sessionId':sid,'sequence':2,'usage':{},'incomplete':True}, NOW)
        self.assertIsNone(self.ledger.summary(NOW)['todayUsd'])

    def test_google_error_keeps_last_deduction_and_checks_currency(self):
        base = {'amount': 15.96, 'currency': 'CHF', 'updatedAt': NOW.isoformat()}
        cached = {'state': 'ready', 'checkedAt': NOW.isoformat(), 'periods': [
            {'start': NOW.isoformat(), 'end': (NOW + dt.timedelta(hours=1)).isoformat(), 'amount': .25, 'currency': 'CHF'}]}
        result = google_credit(base, {'state': 'access_error'}, cached, NOW + dt.timedelta(hours=2))
        self.assertEqual(result['remaining'], 15.71)
        self.assertEqual(result['status'], 'stale')
        cached['periods'][0]['currency'] = 'USD'
        result = google_credit(base, cached, {}, NOW)
        self.assertIsNone(result['remaining'])
        self.assertEqual(result['status'], 'currency_mismatch')


if __name__ == '__main__':
    unittest.main()
