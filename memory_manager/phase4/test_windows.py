"""Linux-hosted synthetic tests of Windows preparation, not native Hermes proof."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from ..phase3 import lab
from ..store import Memory, Principal
from ..phase2.bridge import Bridge
from ..phase2.hermes import HermesRuns
from ..phase2.local_model import Unavailable
from ..phase2.test_integration import Endpoint
from . import windows, credentials, job
from .worker import tick


class Configuration(unittest.TestCase):
    def test_windows_profile_reuses_controlled_memory_and_64k_gate(self):
        cfg = windows.profile(skill_candidate=True)
        m = cfg['mcp_servers']['jarvis']
        self.assertEqual(m['command'], r'C:\JarvisHermesLab\runtime\Scripts\python.exe')
        self.assertEqual(m['args'][1], 'memory_manager.phase4.mcp')
        self.assertIn('--skill-candidate', m['args'])
        self.assertEqual(cfg['model']['context_length'], 64000)
        self.assertEqual(cfg['model']['base_url'], 'http://127.0.0.1:11436/v1')
        self.assertFalse(cfg['memory']['memory_enabled'])
        self.assertFalse(cfg['security']['allow_lazy_installs'])
        self.assertEqual(cfg['platform_toolsets']['api_server'], ['mcp-jarvis'])
        self.assertNotIn('/home/user', json.dumps(cfg))

    def test_tunnel_binds_all_apis_to_loopback_and_checks_host_key(self):
        args = windows.tunnel(key='private-key-path', known_hosts='pinned-hosts')
        self.assertIn('StrictHostKeyChecking=yes', args)
        self.assertIn('ForwardAgent=no', args)
        self.assertIn('127.0.0.1:11435:127.0.0.1:11434', args)
        self.assertIn('127.0.0.1:8792:127.0.0.1:8792', args)
        self.assertIn('127.0.0.1:11436:127.0.0.1:11436', args)
        self.assertNotIn('-g', args)
        with self.assertRaises(ValueError): windows.tunnel(key='k', known_hosts='h', host='8.8.8.8')
        with self.assertRaises(PermissionError): windows.tunnel(key='k', known_hosts='h', user='codexdiag')

    def test_old_or_escaping_windows_homes_are_rejected(self):
        self.assertEqual(windows.validate_home('C:/JarvisHermesLab/runs/' + 'a'*32).name, 'a'*32)
        for path in ('C:/Users/winuser', 'C:/JarvisHermesLab/runs/old', 'C:/JarvisHermesLab/runs/../identity'):
            with self.assertRaises(ValueError): windows.validate_home(path)

    def test_ntfs_acl_requires_protected_trusted_principals(self):
        good = {'current_sid': 'S-1-5-21-123', 'owner_sid': 'S-1-5-32-544', 'protected': True,
                'reparse': False, 'allow_sids': ['S-1-5-18', 'S-1-5-32-544', 'S-1-5-21-123']}
        credentials.check_acl(good)
        for change in ({'allow_sids': ['S-1-1-0']}, {'protected': False}, {'reparse': True}, {'owner_sid': 'unknown'}):
            with self.assertRaises(PermissionError): credentials.check_acl({**good, **change})

    def test_posix_token_protection_remains_enforced(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'token';p.write_text('x'*64);p.chmod(0o600)
            self.assertEqual(credentials.load_token(p), 'x'*64)
            p.chmod(0o644)
            with self.assertRaises(PermissionError): credentials.load_token(p)

    def test_windows_loader_uses_ntfs_attestation_instead_of_posix_mode(self):
        token=MagicMock();token.is_file.return_value=True;token.is_symlink.return_value=False
        token.read_text.return_value='x'*64
        acl={'protected':True,'reparse':False,'current_sid':'S-1-5-21-123',
             'owner_sid':'S-1-5-32-544','allow_sids':['S-1-5-21-123']}
        with patch.object(credentials,'Path',return_value=token), patch.object(credentials.os,'name','nt'), \
             patch.object(credentials,'windows_acl',return_value=acl) as inspect:
            self.assertEqual(credentials.load_token('fixed-path'),'x'*64)
            inspect.assert_called_once_with(token)
            token.stat.assert_not_called()


class NativeAPIBindingsSimulated(unittest.TestCase):
    def fake_api(self):
        api = MagicMock()
        api.CreateJobObjectW.return_value = 789
        api.SetInformationJobObject.return_value = 1
        def create(*args):
            p=args[-1]._obj;p.process=123;p.thread=456;p.pid=999
            return 1
        api.CreateProcessW.side_effect = create
        api.AssignProcessToJobObject.return_value = 1
        api.ResumeThread.return_value = 1
        api.WaitForSingleObject.return_value = 0
        def query(_h,_kind,pointer,*_):
            pointer._obj.PeakJobMemory=1024;return 1
        api.QueryInformationJobObject.side_effect=query
        def code(_h,pointer): pointer._obj.value=0;return 1
        api.GetExitCodeProcess.side_effect=code
        return api

    def test_child_is_assigned_suspended_before_it_can_run(self):
        api=self.fake_api()
        with patch.object(job.os,'name','nt'), patch.object(job.c,'WinDLL',return_value=api,create=True):
            result=job.supervise(['python.exe','-c','pass'],{'SystemRoot':'C:\\Windows'},'C:\\Windows')
        names=[c[0] for c in api.mock_calls]
        self.assertLess(names.index('AssignProcessToJobObject'),names.index('ResumeThread'))
        api.CloseHandle.assert_any_call(789)
        self.assertEqual(result['peak_job_memory_bytes'],1024)
        self.assertFalse(api.CreateProcessW.call_args.args[4])  # No handle inheritance.

    def test_failed_assignment_terminates_only_the_owned_suspended_child(self):
        api=self.fake_api();api.AssignProcessToJobObject.return_value=0
        with patch.object(job.os,'name','nt'), patch.object(job.c,'WinDLL',return_value=api,create=True), \
             patch.object(job.c,'get_last_error',return_value=5,create=True):
            with self.assertRaises(OSError):job.supervise(['python.exe'],{},'C:\\Windows')
        api.ResumeThread.assert_not_called()
        api.TerminateProcess.assert_called_once_with(123,1)
        api.CloseHandle.assert_any_call(789)


class WindowsBridgeContractSimulated(unittest.TestCase):
    def setUp(self):
        parent=lab.ROOT/'data/phase3';parent.mkdir(parents=True,exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(dir=parent)
        self.folder=Path(self.tmp.name)/'fixture';lab.prepare(self.folder)
        self.m=Memory(self.folder/'memory.sqlite')
        self.p=Principal(lab.OWNER,frozenset({'private'}),frozenset({'reader','mission_writer','mission_worker'}),'phase4-broker')
        self.ep=Endpoint();self.client=HermesRuns(self.ep.http,'fixture:4b',allow_live=True)
        self.mid=Bridge(self.m,self.p).submit('windows-fixture',{
            'objective':'Synthetic Windows Hermes mission','trigger':'test','priority':1,'memory_context':[],
            'plan':['read','report'],'allowed_tools':['memory.search','report'],
            'budget':{'tokens':0,'cost_micros':0,'seconds':120,'attempts':1}})
        self.gpu={'observed_at':__import__('time').time(),'miner_running':False,'free_mib':9200,'utilization':0}

    def tearDown(self):self.ep.close();self.m.close();self.tmp.cleanup()

    def test_offline_or_mining_mission_remains_durable_without_submission(self):
        status=tick(self.m,self.p,self.mid,self.client,lambda:self.gpu,endpoint_ready=False)
        self.assertEqual(status['dispatch_state'],'ready');self.assertEqual(self.ep.runs,{})
        self.gpu['miner_running']=True
        status=tick(self.m,self.p,self.mid,self.client,lambda:self.gpu,endpoint_ready=True)
        self.assertEqual(status['state'],'queued');self.assertEqual(self.ep.runs,{})
        self.m.close();self.m=Memory(self.folder/'memory.sqlite')
        self.assertEqual(Bridge(self.m,self.p).get(self.mid)['dispatch_state'],'ready')

    def test_interrupted_native_run_is_paused_and_never_blindly_resubmitted(self):
        tick(self.m,self.p,self.mid,self.client,lambda:self.gpu,endpoint_ready=True)
        self.ep.state='interrupted'
        status=tick(self.m,self.p,self.mid,self.client,lambda:self.gpu,endpoint_ready=True)
        self.assertEqual(status['state'],'paused');self.assertEqual(status['dispatch_state'],'unknown')
        count=len(self.ep.runs)
        self.m.close();self.m=Memory(self.folder/'memory.sqlite')
        tick(self.m,self.p,self.mid,self.client,lambda:self.gpu,endpoint_ready=True)
        self.assertEqual(len(self.ep.runs),count)

    def test_unavailable_client_cannot_trigger_paid_fallback(self):
        class Offline:
            def create(self,*_):raise Unavailable('offline')
        status=tick(self.m,self.p,self.mid,Offline(),lambda:self.gpu,endpoint_ready=True)
        self.assertEqual(status['dispatch_state'],'unknown')
        self.assertEqual(self.ep.runs,{})

    def test_queue_wait_does_not_consume_execution_time_or_reset_after_dispatch(self):
        with self.m.db:
            self.m.db.execute('UPDATE p2_outbox SET created=1 WHERE mission_id=?',(self.mid,))
            self.m.db.execute('UPDATE mm_missions SET created=1 WHERE id=?',(self.mid,))
        tick(self.m,self.p,self.mid,self.client,lambda:self.gpu,endpoint_ready=False)
        status=tick(self.m,self.p,self.mid,self.client,lambda:self.gpu,endpoint_ready=True)
        self.assertEqual(status['dispatch_state'],'submitted')
        before=self.m.db.execute("SELECT created FROM p2_events WHERE event_key='phase4-execution-started'").fetchone()[0]
        with self.m.db:
            self.m.db.execute("UPDATE p2_events SET created=? WHERE event_key='phase4-execution-started'",(before-300,))
        status=tick(self.m,self.p,self.mid,self.client,lambda:self.gpu,endpoint_ready=True)
        self.assertEqual(status['dispatch_state'],'cancelled')
        self.assertEqual(len(self.ep.runs),1)

    def test_reader_cannot_write_deferred_events(self):
        reader=Principal(lab.OWNER,frozenset({'private'}),frozenset({'reader'}),'reader')
        with self.assertRaises(PermissionError):
            tick(self.m,reader,self.mid,self.client,lambda:self.gpu,endpoint_ready=False)




class PilotAllowance(unittest.TestCase):
    def test_expiry_and_failed_dispatches_do_not_refund_allowance(self):
        from .allowance import consume
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'window.json'
            p.write_text(json.dumps({'started_at':100,'expires_at':200,'calls':23,'missions':3}));p.chmod(0o600)
            self.assertEqual(consume(p,'calls',now=150)['calls'],24)
            with self.assertRaises(PermissionError):consume(p,'calls',now=150)
            self.assertEqual(consume(p,'missions',now=150)['missions'],4)
            with self.assertRaises(PermissionError):consume(p,'missions',now=201)
            value=json.loads(p.read_text());value['closed']=True;p.write_text(json.dumps(value))
            with self.assertRaises(PermissionError):consume(p,'missions',now=151)

    def test_simultaneous_callers_cannot_exceed_shared_cap(self):
        from .allowance import consume
        from concurrent.futures import ThreadPoolExecutor
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'window.json';p.write_text(json.dumps({'started_at':100,'expires_at':200,'calls':22,'missions':0}));p.chmod(0o600)
            def attempt(_):
                try:consume(p,'calls',now=150);return True
                except PermissionError:return False
            with ThreadPoolExecutor(max_workers=8) as pool:self.assertEqual(sum(pool.map(attempt,range(8))),2)

    def test_public_or_corrupt_allowance_is_refused(self):
        from .allowance import consume
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'window.json';p.write_text('{}');p.chmod(0o644)
            with self.assertRaises(PermissionError):consume(p,'calls',now=150)
            p.chmod(0o600);p.write_text('{')
            with self.assertRaises(ValueError):consume(p,'calls',now=150)


class ClosedPilotStartup(unittest.TestCase):
    def test_closed_or_exhausted_window_never_starts_windows_process(self):
        import time
        from scripts import pilot_phase4_windows as pilot
        for closed,missions in [(True,0),(False,4)]:
            with self.subTest(closed=closed,missions=missions), tempfile.TemporaryDirectory() as directory:
                root=Path(directory);(root/'docs').mkdir();private=root/'data/phase4';private.mkdir(parents=True)
                (private/'admission.json').write_text('{"passed":true}')
                (private/'window.json').write_text(json.dumps({'expires_at':time.time()+1000,'closed':closed,'missions':missions}))
                sample={'available':True,'miner_running':False,'free_mib':9000,'utilization':0}
                with patch.object(pilot,'ROOT',root),patch.object(pilot,'collect',return_value=sample), \
                     patch.object(pilot,'probe',return_value={'listening':False}), \
                     patch.object(pilot.subprocess,'Popen') as start, \
                     patch('sys.argv',['pilot','--approved','--output','docs/refused.json']),patch('builtins.print'):
                    pilot.main()
                start.assert_not_called()
                result=json.loads((root/'docs/refused.json').read_text())
                self.assertFalse(result['passed']);self.assertEqual(result['error_class'],'PermissionError')

if __name__ == '__main__': unittest.main()
