"""Real sources through the existing mission chain: admission, envelope, MCP proxy, receipts, quality."""
import json, tempfile, time, unittest
from contextlib import closing
from pathlib import Path

from memory_manager.store import Memory, Principal
from memory_manager.phase3.lab import OWNER, seed
from memory_manager.phase2 import database
from memory_manager.phase2.bridge import LEGACY_TEXT_PREFIX, REAL_TEXT_PREFIX
from memory_manager.phase6.operational import definition, TEXT_PREFIX
from memory_manager.phase6.demand_queue import Queue, migrate, report_quality
from memory_manager.phase6d.database import migrate as migrate_6d
from memory_manager.phase6d.evidence import ObservedTools, metadata
from memory_manager.sources.tools import SourceTools
from scripts.text_mission_window import result_provenance


class FakeHA:
    calls = []
    def states(self, query='', domain='', limit=40):
        FakeHA.calls.append(('states', query)); return {'matched': 1, 'items': [{'entity_id': 'sensor.vsv_dosage', 'state': '38'}], 'truncated': False}
    def history(self, entity_id, hours, now=None):
        FakeHA.calls.append(('history', entity_id, hours))
        return {'entity_id': entity_id, 'kind': 'numeric', 'count': 3, 'min': 36.0, 'max': 40.0, 'series': [['2026-11-17T00:00:00Z', 36.0]]}


def legacy(text):
    return dict(definition(text), allowed_tools=['memory.search', 'report'])


class Chain(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); path = Path(self.tmp.name) / 'm.sqlite'
        self.m = Memory(path, create=True); database.migrate(self.m); seed(self.m); migrate(self.m); migrate_6d(self.m)
        roles = frozenset({'reader', 'mission_writer', 'mission_worker', 'evidence_writer'})
        self.host = Principal(OWNER, frozenset({'private'}), roles, 'host')
        self.panel = Principal(OWNER, frozenset({'private'}), frozenset({'reader', 'mission_writer'}), 'interactive-panel')
        self.hermes = Principal(OWNER, frozenset({'private'}), frozenset({'reader'}), 'hermes-memory')
        self.q = Queue(self.m, self.host, accepting=True, execution=True)

    def tearDown(self):
        self.m.close(); self.tmp.cleanup()

    def admit(self, key, d):
        return self.q.admit(self.panel, key, {'scope': 'private', 'definition': d})['mission_id']

    def test_gateway_legacy_grants_are_upgraded_server_side(self):
        text = TEXT_PREFIX + 'Dois-je recalibrer le VSV ?'
        mid = self.admit('k1', legacy(text))
        stored = json.loads(self.m.db.execute('SELECT definition FROM mm_missions WHERE id=?', (mid,)).fetchone()[0])
        self.assertEqual(stored['allowed_tools'], ['memory.search', 'sources.read', 'report'])
        self.assertEqual(stored['objective'], text)                       # stored request unchanged
        self.assertEqual(self.admit('k2', definition(text)), mid)        # same intent, either form → same mission
        bad = legacy(text); bad['allowed_tools'] = ['memory.search', 'report', 'shell']
        with self.assertRaises(PermissionError): self.admit('k3', bad)
        bad = definition(text); bad['budget'] = dict(bad['budget'], seconds=300)
        with self.assertRaises(PermissionError): self.admit('k4', bad)

    def test_model_sees_real_data_prefix_not_synthetic(self):
        self.assertEqual(TEXT_PREFIX, LEGACY_TEXT_PREFIX)
        mid = self.admit('k1', legacy(TEXT_PREFIX + 'VSV ?'))
        payload = json.loads(self.m.db.execute('SELECT payload FROM p2_outbox WHERE mission_id=?', (mid,)).fetchone()[0])
        self.assertEqual(payload['objective'], REAL_TEXT_PREFIX + 'VSV ?')
        self.assertIn('ha://', payload['tool_policy']); self.assertIn('earlier answers, not evidence', payload['tool_policy'])

    def receipt_for(self, mid):
        tools = ObservedTools(self.m, self.host, self.hermes, mid, sources={'ha': FakeHA()})
        rows, receipt = tools.call('source.ha.history', {'entity_id': 'sensor.vsv_dosage', 'hours': 48})
        return rows[0]['source']['ref'], receipt

    def test_source_read_is_receipted_and_projected(self):
        mid = self.admit('k1', legacy(TEXT_PREFIX + 'VSV ?'))
        ref, receipt = self.receipt_for(mid)
        self.assertTrue(ref.startswith('ha://sensor.vsv_dosage/history/48h@'))
        proj = metadata(self.m, self.host, mid, [receipt])
        self.assertEqual([i['source_ref'] for i in proj['items']], [ref])
        self.assertEqual(report_quality(proj, 'Sous-dosage. Source : `%s`' % ref, self.m.db, result_provenance), (True, [], False))
        self.assertEqual(report_quality(proj, 'Sous-dosage, sans source.', self.m.db, result_provenance), (False, [], False))

    def test_forged_measurement_ref_is_refused(self):
        forged = {'origin': 'sqlite', 'selection_origin': 'authenticated_host_tool_receipts', 'items': [{'source_ref': 'ha://sensor.x/history/1h@20261117T0000Z'}]}
        with self.assertRaisesRegex(PermissionError, 'Unverified measurement source'):
            report_quality(forged, 'ha://sensor.x/history/1h@20261117T0000Z', self.m.db, result_provenance)

    def test_unconfigured_source_and_write_tools_denied(self):
        mid = self.admit('k1', legacy(TEXT_PREFIX + 'VSV ?'))
        tools = ObservedTools(self.m, self.host, self.hermes, mid, sources={})
        with self.assertRaises(PermissionError): tools.call('source.ha.history', {'entity_id': 'sensor.vsv_dosage', 'hours': 1})
        with self.assertRaises(PermissionError): tools.call('source.ha.call_service', {})


class Withheld(unittest.TestCase):
    def test_category_names_the_kind_never_the_text(self):
        from memory_manager.phase2.bridge import withheld_category
        from memory_manager.store import SECRET
        for text, want in [('openai.AuthenticationError: Incorrect API key provided', 'api_key'), ('Authorization: Bearer abc', 'bearer'),
                           ('le mot de passe est', 'password'), ('https://u:p@host/x', 'url_credentials'), ('sk-abcdefghijklmnop', 'provider_key')]:
            self.assertEqual(withheld_category(SECRET.search(text).group(0)), want, text)


class Proxy(unittest.TestCase):
    """Windows-side MCP proxy: advertises the source tools, forwards them by their inner name only."""
    def test_list_and_forward(self):
        from memory_manager.phase3.mcp import dispatch, SOURCES
        sent = []
        def http(method, path, body=None, **kw):
            sent.append((method, path, body)); self.kw = kw; return {'result': [], 'receipt_id': 'r'}
        listed = dispatch({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'}, http)
        names = {t['name'] for t in listed['result']['tools']}
        self.assertTrue(SOURCES <= names)
        out = dispatch({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {'name': 'jarvis_ha_history', 'arguments': {'entity_id': 'sensor.vsv_dosage', 'hours': 24}}}, http)
        self.assertNotIn('error', out)
        self.assertEqual(sent[-1], ('POST', '/v1/tools/call', {'name': 'source.ha.history', 'arguments': {'entity_id': 'sensor.vsv_dosage', 'hours': 24}}))
        self.assertEqual(self.kw, {'timeout': 30})                      # prod 17.11: 5 s default lost a slow read
        bad = dispatch({'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {'name': 'jarvis_ha_history', 'arguments': {'entity_id': 'sensor.vsv_dosage', 'hours': 24, 'url': 'x'}}}, http)
        self.assertIn('error', bad); self.assertEqual(len(sent), 1)


if __name__ == '__main__':
    unittest.main()
