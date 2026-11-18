"""Restoration acceptance tests with SQLite in memory; no services or network."""
import copy
import importlib.util
from pathlib import Path
import sqlite3
from types import SimpleNamespace
import unittest
from ..store import Principal
from ..phase6d import heartbeat

path=Path(__file__).resolve().parents[2]/'ops/pilot-network/restore-readonly-pilot.py'
spec=importlib.util.spec_from_file_location('readonly_restore',path)
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)

class RestoreTests(unittest.TestCase):
    def sample(self):
        with sqlite3.connect(':memory:') as db:
            db.executescript(heartbeat.SCHEMA)
            m=SimpleNamespace(db=db)
            p=Principal('phase3-synthetic',frozenset({'private'}),frozenset({'worker_supervisor'}),'operational-controller')
            def snapshot():
                return {'p6d_workers':[repr(row) for row in db.execute('SELECT * FROM p6d_workers')], 'mm_missions':['unchanged']}
            heartbeat.register(m,p,'windows-hermes',p.actor)
            before=snapshot()
            heartbeat.register(m,p,'windows-hermes',p.actor)
            return before,snapshot()

    def test_actual_heartbeat_register_transition(self):
        r.validate_restart_tables(*self.sample())

    def test_canonical_and_schema_changes_refused(self):
        before,after=self.sample()
        for candidate in ({**after,'mm_missions':['modified']},{**after,'unexpected':[]}):
            with self.assertRaises(PermissionError):r.validate_restart_tables(before,candidate)

    def test_identity_observation_and_stale_epoch_refused(self):
        import ast
        before,after=self.sample()
        for column,value in [(0,'other-worker'),(1,'other-owner'),(2,'other-reporter'),
                             (3,ast.literal_eval(before['p6d_workers'][0])[3]),
                             (3,'invalid'),(4,1),(5,123),(6,'ready')]:
            changed=list(ast.literal_eval(after['p6d_workers'][0]));changed[column]=value
            with self.subTest(column=column):
                with self.assertRaises((PermissionError,ValueError)):
                    r.validate_restart_tables(before,{**after,'p6d_workers':[repr(tuple(changed))]})

    def test_missing_or_additional_worker_refused(self):
        before,after=self.sample()
        for rows in ([],after['p6d_workers']*2):
            with self.assertRaises(PermissionError):r.validate_restart_tables(before,{**after,'p6d_workers':rows})
