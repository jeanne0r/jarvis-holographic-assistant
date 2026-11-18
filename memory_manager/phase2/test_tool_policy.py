"""Prod 16.11: grant names were shown to the model as `allowed_tools`; it called `report`
(not an advertised tool) and the gate refused 403. The model-facing envelope now says
grants are permissions; enforcement still comes from the stored definition."""
import json, tempfile, time, unittest
from pathlib import Path
from ..store import Memory, SECRET
from . import budgets, database
from .bridge import Bridge, TOOL_POLICY
from .test_integration import WORKER


class ToolPolicyEnvelope(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='jarvis2-toolpolicy-')
        self.m = Memory(Path(self.tmp.name) / 'memory.sqlite', create=True); database.migrate(self.m)
        budgets.create(self.m, WORKER, token_limit=32768)

    def tearDown(self):
        self.m.close(); self.tmp.cleanup()

    def test_model_never_sees_grants_as_tool_names(self):
        grants = ['memory.search', 'report']
        definition = {'objective': 'Synthetic DoseLab question', 'trigger': 'synthetic', 'priority': 1, 'memory_context': [],
                      'plan': ['retrieve', 'report'], 'allowed_tools': grants,
                      'budget': {'tokens': 0, 'cost_micros': 0, 'seconds': 120, 'attempts': 1}}
        mid = Bridge(self.m, WORKER).submit('m-' + str(time.time_ns()), definition)
        payload = json.loads(self.m.db.execute('SELECT payload FROM p2_outbox WHERE mission_id=?', (mid,)).fetchone()[0])
        self.assertNotIn('allowed_tools', payload)
        self.assertEqual(payload['mission_grants'], grants)
        self.assertEqual(payload['tool_policy'], TOOL_POLICY)
        self.assertIn('There is no `report` tool', TOOL_POLICY)
        self.assertIn('source.ref verbatim', TOOL_POLICY); self.assertIn('memory_id is not a', TOOL_POLICY)  # prod 17.11
        self.assertIn('report_contract', payload)                       # report requirements unchanged
        self.assertIsNone(SECRET.search(TOOL_POLICY))                   # never trips the admission filter
        # Enforcement source is unchanged: the stored definition keeps its grants.
        stored = json.loads(self.m.db.execute('SELECT definition FROM mm_missions WHERE id=?', (mid,)).fetchone()[0])
        self.assertEqual(stored['allowed_tools'], grants)


if __name__ == '__main__':
    unittest.main()
