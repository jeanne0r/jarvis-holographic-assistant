"""Installer tests on disposable files only. Never invokes root or a service."""
import importlib.util
import json
import os
import errno
import pwd
import socket
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from types import SimpleNamespace

FILE=Path(__file__).resolve().parents[2]/'ops/pilot-network/install-demand-queue.py'
spec=importlib.util.spec_from_file_location('queue_install',FILE)
install=importlib.util.module_from_spec(spec);spec.loader.exec_module(install)

class InstallTests(unittest.TestCase):
    def cfg(self):
        return {'operations':dict(install.OFF),'syntheticOnly':True,'dispatchEnabled':False,
                'frontPort':8796,'bridgePort':8797,'origin':'http://127.0.0.1:8796',
                'embeddedPanel':{'enabled':True,'origin':'https://192.0.2.16:8788'},
                'expiresAt':(time.time()+3600)*1000,'bridgeToken':'b'*48,'humanHash':'h'*64,
                'missionLimits':{'calls':6,'tokens':98304,'seconds':240,'attempts':1,'remoteCostChf':0}}
    def test_queue_only_profile_preserves_human_and_bridge(self):
        cfg=self.cfg();before=json.dumps(cfg,sort_keys=True)
        for accepting in [False,True]:
            new=install.profile(cfg,'s'*48,accepting)
            self.assertEqual(new['operations'],{**install.OFF,'admissionEnabled':accepting,'textEnabled':accepting})
            self.assertIs(new['onDemand']['executionEnabled'],False)
            self.assertIsNone(new['onDemand']['runtime'])
            self.assertEqual(new['humanHash'],cfg['humanHash']);self.assertEqual(new['bridgeToken'],cfg['bridgeToken'])
        self.assertEqual(json.dumps(cfg,sort_keys=True),before)
    def test_unsafe_profile_refused(self):
        for mutate in [lambda c:c.update(dispatchEnabled=True),lambda c:c['operations'].update(workerEnabled=True),
                       lambda c:c.update(expiresAt=0),lambda c:c['missionLimits'].update(remoteCostChf=1),
                       lambda c:c.update(onDemand={})]:
            cfg=self.cfg();mutate(cfg)
            with self.assertRaises(PermissionError):install.profile(cfg,'s'*48,False)
        with self.assertRaises(PermissionError):install.profile(self.cfg(),'b'*48,False)
    def test_atomic_regular_replacement_and_symlink_refusal(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'code';target.write_bytes(b'old');target.chmod(0o644)
            install.replace_code(target,b'new',os.getuid(),os.getgid())
            self.assertEqual(target.read_bytes(),b'new');self.assertEqual(target.stat().st_mode&0o777,0o644)
            link=Path(tmp)/'link';link.symlink_to(target)
            with self.assertRaises(PermissionError):install.replace_code(link,b'bad',os.getuid(),os.getgid())
            self.assertEqual(target.read_bytes(),b'new')
    def test_hash_and_private_mode_enforced(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'config';target.write_bytes(b'private');target.chmod(0o600)
            self.assertEqual(install.checked(target,install.sha(b'private'),os.getuid(),True),b'private')
            with self.assertRaises(PermissionError):install.checked(target,'0'*64)
            target.chmod(0o644)
            with self.assertRaises(PermissionError):install.checked(target,private=True)
    def test_observed_gateway_is_pinned_but_installation_stays_strict(self):
        owner=pwd.getpwuid(os.getuid())
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'server.js';target.write_bytes(b'existing');target.chmod(0o664)
            digest=install.sha(b'existing')
            with self.assertRaises(PermissionError):install.checked(target)
            with self.assertRaises(PermissionError):install.observed_gateway_file(target,digest,owner)
            with patch.object(install.grp,'getgrgid',return_value=SimpleNamespace(gr_mem=[])),patch.object(install.pwd,'getpwall',return_value=[owner]):
                before=target.stat()
                observed=install.observed_gateway_file(target,digest,owner,allow_group_write=True)
                self.assertEqual(observed,install.observed_gateway_file(target,digest,owner,allow_group_write=True))
                self.assertEqual(target.stat().st_mode,before.st_mode)
                with self.assertRaises(PermissionError):install.observed_gateway_file(target,'0'*64,owner,allow_group_write=True)
                target.chmod(0o666)
                with self.assertRaises(PermissionError):install.observed_gateway_file(target,digest,owner,allow_group_write=True)
            target.chmod(0o664)
            with patch.object(install.grp,'getgrgid',return_value=SimpleNamespace(gr_mem=['foreign'])),patch.object(install.pwd,'getpwall',return_value=[owner]):
                with self.assertRaises(PermissionError):install.observed_gateway_file(target,digest,owner,allow_group_write=True)
            target.unlink();target.symlink_to(Path(tmp)/'elsewhere')
            with self.assertRaises(PermissionError):install.observed_gateway_file(target,digest,owner,allow_group_write=True)
    def test_port_quiescence_waits_without_reusing_or_weakening_bind(self):
        now=[0.];calls=[]
        class Probe:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def bind(self,address):
                calls.append(address)
                if len(calls)==1:raise OSError(errno.EADDRINUSE,'still draining')
        def sleep(seconds):now[0]+=seconds
        with patch.object(Path,'read_text',return_value='header\n'):
            install.wait_private_ports(ports=(34567,),clock=lambda:now[0],sleep=sleep,socket_factory=Probe)
        self.assertEqual(calls,[('127.0.0.1',34567)]*2);self.assertEqual(now[0],.25)
    def test_actual_listener_is_never_stopped_or_adopted(self):
        with socket.socket() as listener:
            listener.bind(('127.0.0.1',0));listener.listen();port=listener.getsockname()[1]
            with self.assertRaises(PermissionError):install.wait_private_ports(ports=(port,))
            self.assertEqual(listener.getsockopt(socket.SOL_SOCKET,socket.SO_ACCEPTCONN),1)
    def test_busy_ports_expire_and_other_errors_fail_immediately(self):
        now=[0.]
        class Busy:
            code=errno.EADDRINUSE
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def bind(self,address):raise OSError(self.code,'refused')
        with patch.object(Path,'read_text',return_value='header\n'):
            with self.assertRaises(TimeoutError):install.wait_private_ports(seconds=.5,clock=lambda:now[0],sleep=lambda seconds:now.__setitem__(0,now[0]+seconds),socket_factory=Busy)
            Busy.code=errno.EACCES
            with self.assertRaises(PermissionError):install.wait_private_ports(socket_factory=Busy)
    def test_resume_preserves_all_existing_tables_and_requires_empty_queue(self):
        before={'mm_missions':['completed'],'mm_revisions':['original']}
        after={**before,'p6q_jobs':[],'p6q_keys':[]}
        install.validate_migrated_tables(before,after)
        for bad in [{**after,'mm_revisions':[]},{**after,'p6q_jobs':['a job']},{**after,'unexpected':[]}]:
            with self.assertRaises(PermissionError):install.validate_migrated_tables(before,bad)

if __name__=='__main__':unittest.main()
