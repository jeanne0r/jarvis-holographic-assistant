"""DoseLab removal: fresh database, same schema/owner/mode, lab copies deleted, blockers enforced."""
import importlib.util, json, os, sqlite3, tempfile, unittest
from pathlib import Path
from contextlib import closing

from memory_manager.store import Memory
from memory_manager.phase2 import database
from memory_manager.phase3.lab import seed
from memory_manager.phase5 import database as p5
from memory_manager.phase6.demand_queue import migrate
from memory_manager.phase6d.database import migrate as migrate_6d

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('reset_memory', ROOT / 'ops/demand-simple/reset_memory.py')
reset = importlib.util.module_from_spec(spec); spec.loader.exec_module(reset)


class Reset(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.state = Path(self.tmp.name) / 'state'; self.state.mkdir(mode=0o700)
        self.backups = Path(self.tmp.name) / 'backups'; (self.backups / 'simple-x').mkdir(parents=True)
        db = self.state / 'memory.sqlite'
        with closing(Memory(db, create=True)) as m:
            database.migrate(m); p5.migrate(m); seed(m); migrate(m); migrate_6d(m)
        for name in ['memory.backup.sqlite', 'restore-check.sqlite']: (self.state / name).write_bytes(db.read_bytes())
        (self.backups / 'simple-x/memory.sqlite').write_bytes(b'x')
        (self.state / 'config.json').write_text('{}')
        self.before = reset.tables(db)

    def tearDown(self):
        self.tmp.cleanup()

    def run_apply(self, **kw):
        return reset.apply(kw.pop('confirm', reset.WORD), state=self.state, app=ROOT, roots=[self.backups], unit_state=kw.pop('unit', 'inactive'))

    def test_check_lists_without_touching(self):
        out = reset.check(self.state, [self.backups], unit_state='inactive')
        self.assertTrue(out['passed']); self.assertGreater(out['rows']['mm_events'], 0)
        self.assertIn('synthetic://doselab', out['provenance'])
        self.assertTrue(any(p.endswith('memory.backup.sqlite') for p in out['deleted_with_it']))
        self.assertEqual(out['copies_elsewhere_not_deleted'], [str(self.backups / 'simple-x/memory.sqlite')])
        self.assertTrue((self.state / 'memory.backup.sqlite').exists())

    def test_apply_replaces_with_empty_same_schema(self):
        os.chmod(self.state / 'memory.sqlite', 0o600)
        out = self.run_apply()
        self.assertTrue(out['passed'], out); self.assertEqual(out['mm_events'], 0)
        db = self.state / 'memory.sqlite'
        self.assertTrue(set(self.before) <= set(reset.tables(db)))
        self.assertEqual(db.stat().st_mode & 0o777, 0o600)
        self.assertEqual(sorted(p.name for p in self.state.iterdir()), ['config.json', 'memory.sqlite'])
        self.assertTrue((self.backups / 'simple-x/memory.sqlite').exists())      # listed only, never deleted
        with closing(Memory(db)) as m:                                             # usable by the service: same migrations are no-ops
            self.assertFalse(migrate(m)); self.assertEqual(migrate_6d(m), {'changed': False})
            self.assertEqual(m.db.execute('SELECT count(*) FROM mm_missions').fetchone()[0], 0)

    def test_release_without_phase5_drops_only_unused_tables(self):
        import shutil
        app = Path(self.tmp.name) / 'opt'                       # prod 17.11: the installed release has no phase5
        shutil.copytree(ROOT / 'memory_manager', app / 'memory_manager', ignore=shutil.ignore_patterns('__pycache__', 'test_*', 'phase5', 'phase5c'))
        shutil.copytree(ROOT / 'scripts', app / 'scripts', ignore=shutil.ignore_patterns('__pycache__', 'test_*'))
        self.assertTrue(any(t.startswith('p5_') for t in self.before))
        out = reset.apply(reset.WORD, state=self.state, app=app, roots=[self.backups], unit_state='inactive')
        self.assertTrue(out['passed'], out)
        self.assertTrue(out['dropped_unused_tables']) ; self.assertTrue(all(t.startswith('p5_') for t in out['dropped_unused_tables']))
        self.assertEqual(sorted(p.name for p in self.state.iterdir()), ['config.json', 'memory.sqlite'])

    def test_table_used_by_release_is_never_dropped(self):
        import shutil
        app = Path(self.tmp.name) / 'opt'
        shutil.copytree(ROOT / 'memory_manager', app / 'memory_manager', ignore=shutil.ignore_patterns('__pycache__', 'test_*', 'phase5', 'phase5c'))
        (app / 'memory_manager/uses_p5.py').write_text("SQL='SELECT * FROM p5_visibility'\n")
        with self.assertRaisesRegex(RuntimeError, 'used by the installed release: .*p5_visibility'):
            reset.apply(reset.WORD, state=self.state, app=app, roots=[self.backups], unit_state='inactive')
        self.assertTrue((self.state / 'memory.backup.sqlite').exists())          # nothing deleted
        self.assertEqual(reset.tables(self.state / 'memory.sqlite'), self.before)
        self.assertEqual(sorted(p.name for p in self.state.iterdir() if p.name.startswith('.')), [])

    def test_blockers(self):
        with self.assertRaises(PermissionError): self.run_apply(confirm='oui')
        with self.assertRaises(PermissionError): self.run_apply(unit='active')
        with closing(sqlite3.connect(self.state / 'memory.sqlite')) as db, db:
            db.execute("INSERT INTO p2_outbox(mission_id,creator,payload,state,created,updated) SELECT id,'x','{}','unknown',0,0 FROM mm_missions LIMIT 1") \
                if db.execute('SELECT count(*) FROM mm_missions').fetchone()[0] else None
            db.execute('PRAGMA foreign_keys=OFF')
            db.execute("INSERT INTO p6q_jobs(mission_id,expires,lease) VALUES('m',0,'lease')")
        with self.assertRaisesRegex(PermissionError, 'uncertain'): self.run_apply()
        self.assertTrue((self.state / 'memory.backup.sqlite').exists())


if __name__ == '__main__':
    unittest.main()
