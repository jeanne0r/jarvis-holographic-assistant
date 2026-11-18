"""Installer safeguards only: no sudo, service operation or production write."""
import importlib.util
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from scripts.prepare_interactive_pilot import prepare
from memory_manager.phase6.operational import Controller

PATH = Path(__file__).resolve().parents[2] / 'ops/pilot-network/install-operational-panel.py'
spec = importlib.util.spec_from_file_location('operational_install', PATH)
install = importlib.util.module_from_spec(spec)
spec.loader.exec_module(install)


class InstallSafeguards(unittest.TestCase):
    def cfg(self):
        return dict(syntheticOnly=True, dispatchEnabled=False, frontPort=8796,
            bridgePort=8797, origin='http://127.0.0.1:8796',
            missionLimits=dict(calls=6, tokens=98304, seconds=240, attempts=1, remoteCostChf=0),
            embeddedPanel=dict(enabled=True, origin=install.ORIGIN),
            expiresAt=(time.time()+100)*1000, bridgeToken='unused-fixture-token')

    def test_manifest_and_exact_three_targets_excludes_voice(self):
        # Deployment has legitimately changed the live preimages. Model their
        # BEFORE state in this unit test rather than depending on active files.
        reviewed=json.loads((install.SRC/'docs/HERMES_OPERATIONAL_MANIFEST.json').read_text())
        preimages={row['target']:row['before'] for row in reviewed['gateway_patch']}
        actual=install.verified
        def fixture_verified(path,expected,*args,**kwargs):
            if str(path) in preimages:
                self.assertEqual(preimages[str(path)],expected)
                return b'isolated-before-fixture'
            return actual(path,expected,*args,**kwargs)
        with patch.object(install,'verified',side_effect=fixture_verified):
            manifest, files, selected = install.candidate()
        self.assertEqual(67, len(files))
        self.assertEqual(set(install.CHANGED), {r['target'] for r in selected})
        self.assertTrue(all(not r['target'].endswith('app.js') for r in selected))
        with patch.object(install, 'MANIFEST_SHA', '0'*64):
            with self.assertRaises(PermissionError): install.candidate()

    def test_disabled_profile_preserves_existing_fields(self):
        cfg = self.cfg()
        result = install.configuration(cfg)
        self.assertEqual(install.OFF, result.pop('operations'))
        self.assertEqual(cfg, result)
        for key, value in [('dispatchEnabled', True), ('expiresAt', 0),
                           ('operations', {**install.OFF, 'workerEnabled': True}),
                           ('operations', {**install.OFF, 'runtime': {}})]:
            with self.subTest(key=key):
                with self.assertRaises(PermissionError): install.configuration({**cfg, key: value})

    def test_symlink_and_private_permissions_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)/'file'; p.write_text('fixture'); p.chmod(0o600)
            install.regular(p, private=True)
            link = Path(directory)/'link'; link.symlink_to(p)
            with self.assertRaises(PermissionError): install.regular(link)
            p.chmod(0o644)
            with self.assertRaises(PermissionError): install.regular(p, private=True)

    def test_nonroot_cannot_reach_any_preflight_or_mutation(self):
        with patch('sys.argv', [str(PATH), '--install-approved', '--voice-closed']), \
             patch.object(install.os, 'geteuid', return_value=1000), \
             patch.object(install, 'candidate') as preflight, \
             patch.object(install, 'command') as command:
            with self.assertRaises(PermissionError): install.main()
            preflight.assert_not_called(); command.assert_not_called()

    def test_snapshot_restore_and_disabled_migration_preserve_canonical_tables(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)/'fixture'
            prepare(folder, fixture=True)
            path = folder/'memory.sqlite'
            before = install.tables(path)
            install.validate_synthetic(path)
            raw = install.verified(install.SRC/'ops/pilot-network/deploy-private-embedded.py', install.HELPER_SHA)
            helper = install.load_module('snapshot_fixture', raw)
            helper.snapshot(path, folder/'backup.sqlite')
            helper.snapshot(folder/'backup.sqlite', folder/'restored.sqlite')
            self.assertEqual(before, install.tables(folder/'restored.sqlite'))
            controller = Controller(path, install.configuration(self.cfg()))
            self.assertFalse(controller.enabled)
            self.assertIsNone(controller.client)
            controller.step()
            after = install.tables(path)
            self.assertTrue(all(after.get(name) == rows for name, rows in before.items()))
            self.assertIn('p6d_workers', after)
            self.assertEqual(0, len(after['mm_missions']))

    def test_acceptance_uses_only_invalid_admission_probes(self):
        calls = []
        def fake(url, *, method='GET', body=None, headers=None):
            calls.append((url, method, body))
            cookie = (headers or {}).get('Cookie')
            if url.endswith('/session'):
                return 200, b'{}', {'Set-Cookie': 'JarvisHermesSession=fixture; Path='+install.PREFIX+'; HttpOnly; Secure; SameSite=Strict'}
            if body is not None or 'amelie' in url: return 403, b'{}', {}
            if not cookie: return 401, b'{}', {}
            if url.endswith('/hermes/config'):
                return 200, json.dumps(dict(enabled=False, textEnabled=False, voiceEnabled=False)).encode(), {}
            return 200, b'{}', {}
        with patch.object(install, 'connect', side_effect=fake):
            install.accept('http://127.0.0.1:8796', 'fixture-not-a-secret')
        attempts = [body for url, method, body in calls if '/hermes/missions?' in url and body]
        self.assertEqual([{'_probe': True}], attempts)
        self.assertEqual(1, sum(method == 'DELETE' for _, method, _ in calls))

    def test_resume_exact_checkpoint_and_unchanged_credentials_required(self):
        old = self.cfg()
        old['humanHash'] = install.sha(b'fixture')
        current = install.configuration(old)
        marker = dict(passed=False, status='in_progress', backup=str(install.FAILED_BACKUP))
        plan = dict(manifest_sha256=install.MANIFEST_SHA, max_gateway_restarts=1)
        args = [marker, plan, current, old, 'fixture', 'fixture', {'table': []}, {'table': []}, {'table': []}]
        self.assertEqual(current, install.resume_state(*args))
        for index, value in [(0, {**marker, 'passed': True}),
                             (1, {**plan, 'max_gateway_restarts': 2}),
                             (2, {**current, 'operations': {**install.OFF, 'workerEnabled': True}}),
                             (5, 'changed-fixture'), (6, {'table': ['new row']}),
                             (8, {'table': ['restore differs']})]:
            changed = list(args); changed[index] = value
            with self.subTest(index=index):
                with self.assertRaises(PermissionError): install.resume_state(*changed)

    def test_bpf_failure_prevents_gateway_restart_or_acceptance(self):
        from types import SimpleNamespace
        def denied():
            raise PermissionError('BPF denied fixture')
        with patch.object(install, 'accept') as accept, patch.object(install, 'user_command') as command:
            with self.assertRaises(PermissionError):
                install.finish_install(None, SimpleNamespace(supervised_start=denied),
                    {}, [], {}, {}, 'fixture', b'{}', None, 'fixture-pid', None)
            accept.assert_not_called()
            command.assert_not_called()

    def test_post_start_health_does_not_repeat_pre_maintenance_idle_gate(self):
        def show(*args):
            return 'active' if 'ActiveState' in args else '222'
        with patch.object(install,'user_command',side_effect=show), \
             patch.object(install,'connect',return_value=(200,b'{"ok":true}',{})), \
             patch.object(install,'idle',side_effect=AssertionError('pre-maintenance only')):
            self.assertEqual('222',install.gateway_alive('111'))
            with self.assertRaises(PermissionError): install.gateway_alive('222')

    def test_real_read_only_protocol_acceptance_via_relay_without_provider(self):
        import os
        import socket
        import subprocess
        def free():
            with socket.socket() as s:
                s.bind(('127.0.0.1',0));return s.getsockname()[1]
        ports=set()
        while len(ports)<3:ports.add(free())
        front,bridge,public=ports
        children=[]
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)/'state'
            cfg=prepare(folder,front=front,bridge=bridge,fixture=True)
            cfg.update(embeddedPanel={'enabled':True,'origin':install.ORIGIN},operations=dict(install.OFF))
            (folder/'config.json').write_text(json.dumps(cfg))
            switch=Path(directory)/'switch.json';switch.write_text('{"enabled":true}');switch.chmod(0o600)
            code="""import http from 'node:http';import {embeddedRelay} from './hermes-embedded-relay.mjs';const r=embeddedRelay({enabled:true,origin:process.argv[1],port:Number(process.argv[2]),switchFile:process.argv[3]});http.createServer((req,res)=>r(req,res,new URL(req.url,process.argv[1]))).listen(Number(process.argv[4]),'127.0.0.1');"""
            try:
                children.append(subprocess.Popen(['python3','-B','-m','memory_manager.phase6.interactive','--config',str(folder/'config.json')],cwd=install.BUNDLE/'pilot-release',stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL))
                for attempt in range(80):
                    try:
                        if install.connect(f'http://127.0.0.1:{front}/api/health')[0]==200:break
                    except OSError:time.sleep(.05)
                else:self.fail('Private fixture not ready')
                children.append(subprocess.Popen(['node','--input-type=module','-e',code,install.ORIGIN,str(front),str(switch),str(public)],cwd=install.SRC,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL))
                for attempt in range(80):
                    try:
                        if install.connect(f'http://127.0.0.1:{public}'+install.PREFIX+'/session')[0]==401:break
                    except OSError:time.sleep(.05)
                else:self.fail('Relay fixture not ready')
                human=(folder/'operator.token').read_text()
                install.accept(f'http://127.0.0.1:{front}',human)
                install.accept(f'http://127.0.0.1:{public}',human)
                self.assertEqual([],install.tables(folder/'memory.sqlite')['mm_missions'])
                self.assertEqual([],install.tables(folder/'memory.sqlite')['p2_usage'])
            finally:
                for child in reversed(children):
                    child.terminate();child.wait(timeout=10)


if __name__ == '__main__': unittest.main()
