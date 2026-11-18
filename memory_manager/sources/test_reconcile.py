"""Uncertain mission: closed as failed, queue released, event appended, nothing replayed or deleted."""
import importlib.util, json, sqlite3, tempfile, time, unittest
from contextlib import closing
from pathlib import Path

from memory_manager.store import Memory, Principal
from memory_manager.phase2 import database
from memory_manager.phase3.lab import OWNER
from memory_manager.phase6.demand_queue import Queue, migrate
from memory_manager.phase6.operational import definition, TEXT_PREFIX
from memory_manager.phase6d.database import migrate as migrate_6d

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('reconcile', ROOT / 'ops/demand-simple/reconcile.py')
rc = importlib.util.module_from_spec(spec); spec.loader.exec_module(rc)


class Reconcile(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.db = Path(self.tmp.name) / 'm.sqlite'
        with closing(Memory(self.db, create=True)) as m:
            database.migrate(m); migrate(m); migrate_6d(m)
            host = Principal(OWNER, frozenset({'private'}), frozenset({'reader', 'mission_writer', 'mission_worker'}), 'host')
            panel = Principal(OWNER, frozenset({'private'}), frozenset({'reader', 'mission_writer'}), 'interactive-panel')
            sup = Principal(OWNER, frozenset({'private'}), frozenset({'queue_supervisor'}), 'on-demand-supervisor')
            q = Queue(m, host, accepting=True, execution=True)
            self.mid = q.admit(panel, 'k', {'scope': 'private', 'definition': definition(TEXT_PREFIX + 'VSV ?')})['mission_id']
            self.other = q.admit(panel, 'k2', {'scope': 'private', 'definition': definition(TEXT_PREFIX + 'Autre ?')})['mission_id']
            q.quarantine(self.mid)                                   # as prod 17.11 (0d1c6c51)
            self.assertIsNone(q.peek(sup))                           # the queue is blocked
            self.q, self.sup, self.m = q, sup, m
            self.events_before = m.db.execute('SELECT count(*) FROM p2_events').fetchone()[0]

    def tearDown(self):
        self.tmp.cleanup()

    def test_check_lists_and_close_releases_without_replay(self):
        found = rc.uncertain(self.db)
        self.assertEqual([u['mission_id'] for u in found], [self.mid]); self.assertEqual(found[0]['confirm_word'], 'FERMER-' + self.mid[:8])
        out = rc.close(self.db, self.mid)
        self.assertEqual(out['previous']['mission_state'], 'paused')
        self.assertEqual(rc.uncertain(self.db), [])
        with closing(Memory(self.db)) as m:
            self.assertEqual(m.db.execute('SELECT state FROM mm_missions WHERE id=?', (self.mid,)).fetchone()[0], 'failed')
            ev = m.db.execute("SELECT kind,data FROM p2_events WHERE mission_id=? ORDER BY seq DESC LIMIT 1", (self.mid,)).fetchone()
            self.assertEqual(ev[0], 'reconciliation_closed'); self.assertFalse(json.loads(ev[1])['automatic_replay'])
            self.assertEqual(m.db.execute('SELECT count(*) FROM p2_events').fetchone()[0], self.events_before + 1)
            host = Principal(OWNER, frozenset({'private'}), frozenset({'reader', 'mission_writer', 'mission_worker'}), 'host')
            self.assertEqual(Queue(m, host, accepting=True, execution=True).peek(self.sup)['mission_id'], self.other)   # queue unblocked
            self.assertEqual(m.db.execute('SELECT state FROM p2_outbox WHERE mission_id=?', (self.mid,)).fetchone()[0], 'failed')
        with self.assertRaisesRegex(PermissionError, 'not uncertain'): rc.close(self.db, self.mid)
        with self.assertRaises(KeyError): rc.close(self.db, 'nope')


if __name__ == '__main__':
    unittest.main()
