"""B preparation only. No Windows, GPU or network calls."""
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from memory_manager.store import Memory,Principal
from memory_manager.phase2 import database,budgets
from memory_manager.phase4.allowance import consume
from . import native_lab


class NativePreparation(unittest.TestCase):
    def test_fresh_fixture_preserves_correction_and_never_starts_runtime(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(native_lab.lab,'ROOT',Path(tmp)),patch.object(native_lab,'native_run') as start:
            path=Path(tmp)/'data/phase5/fresh';manifest=native_lab.prepare(path)
            with self.assertRaises(FileExistsError):native_lab.prepare(path)
            m=Memory(path/'memory.sqlite')
            try:
                history=m.history(native_lab.lab.HOST,manifest['memory']['configuration_memory_id'])
                self.assertEqual(len(history),3);self.assertEqual(history[-1]['content']['capacities_kg'],[1,1,1,1])
            finally:m.close()
            start.assert_not_called()
    def test_incompatible_shared_quota_is_rejected_before_any_windows_probe(self):
        from scripts import pilot_phase5_windows
        with patch('sys.argv',['pilot','--approved-b','--private-state','unused','--artifact','unused']),patch.object(pilot_phase5_windows.lifecycle,'probe') as probe:
            with self.assertRaisesRegex(PermissionError,'64,000'):
                pilot_phase5_windows.main()
            probe.assert_not_called()
        self.assertEqual(native_lab.check_token_limit(98304),98304)
        for value in (50000,98305,True):
            with self.assertRaises(PermissionError):native_lab.check_token_limit(value)

    def test_archive_attestation_checks_actual_files_and_manifest(self):
        import hashlib
        from .source_attestation import verify, PIN
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);file=root/'agent.py';file.write_text('reviewed source')
            manifest=json.dumps({'commit':PIN,'files':[{'path':'agent.py','sha256':hashlib.sha256(file.read_bytes()).hexdigest()}]}).encode()
            sha=hashlib.sha256(manifest).hexdigest()
            self.assertEqual(verify(root,manifest,expected_sha=sha)['source_files_verified'],1)
            file.write_text('changed')
            with self.assertRaises(PermissionError):verify(root,manifest,expected_sha=sha)
            with self.assertRaises(PermissionError):verify(root,manifest,expected_sha='0'*64)

    def test_new_approval_is_private_unconsumed_and_twenty_minutes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'window.json';value={'started_at':100,'expires_at':1300,'closed':False,'calls':0,'missions':0,'limits':{'calls':16,'missions':3}}
            path.write_text(json.dumps(value));path.chmod(0o600);native_lab.check_window(path,now=150)
            value['calls']=1;path.write_text(json.dumps(value))
            with self.assertRaises(PermissionError):native_lab.check_window(path,now=150)
            value['calls']=False;path.write_text(json.dumps(value))
            with self.assertRaises(PermissionError):native_lab.check_window(path,now=150)
            value['calls']=0;path.write_text(json.dumps(value));path.chmod(0o644)
            with self.assertRaises(PermissionError):native_lab.check_window(path,now=150)
    def test_monthly_boundary_cannot_renew_shared_pilot_budget(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'window.json'
            start=datetime(2026,11,30,23,55,tzinfo=ZoneInfo('Europe/Zurich')).timestamp()
            value={'started_at':start,'expires_at':start+1200,'closed':False,'calls':0,'missions':0,'limits':{'calls':16,'missions':3}}
            path.write_text(json.dumps(value));path.chmod(0o600)
            with self.assertRaises(PermissionError):native_lab.check_window(path,now=start+1)

    def test_persistent_caps_can_only_be_narrowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'window.json';value={'started_at':100,'expires_at':1300,'closed':False,'calls':15,'missions':2,'limits':{'calls':16,'missions':3}}
            path.write_text(json.dumps(value));path.chmod(0o600)
            self.assertEqual(consume(path,'calls',now=150)['calls'],16)
            with self.assertRaises(PermissionError):consume(path,'calls',now=150)
            self.assertEqual(consume(path,'missions',now=150)['missions'],3)
            with self.assertRaises(PermissionError):consume(path,'missions',now=150)
            value['limits']['calls']=25;path.write_text(json.dumps(value))
            with self.assertRaises(PermissionError):consume(path,'calls',now=150)
    def test_shared_budget_cannot_be_renewed_by_another_mission(self):
        with tempfile.TemporaryDirectory() as tmp:
            m=Memory(Path(tmp)/'memory.sqlite',create=True);database.migrate(m)
            p=Principal('synthetic',frozenset({'private'}),frozenset({'budget_admin','metered_caller'}))
            try:
                bid=budgets.create(m,p,token_limit=50000)
                budgets.reserve(m,p,bid,'mission-one','local',tokens=40000)
                with self.assertRaises(PermissionError):budgets.reserve(m,p,bid,'mission-two','local',tokens=10001)
                with self.assertRaises(PermissionError):budgets.reserve(m,p,bid,'mission-two','paid',tokens=1,remote_micros=1)
            finally:m.close()


if __name__=='__main__':unittest.main()
