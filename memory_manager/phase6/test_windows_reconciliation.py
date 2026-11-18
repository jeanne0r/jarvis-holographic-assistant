"""Version-specific attestations; no runtime, model or production writes."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import types
import unittest
from unittest.mock import patch

from memory_manager.phase4 import windows
from scripts import pilot_phase6b_panel as checks


class WindowsReconciliation(unittest.TestCase):
    def setUp(self):
        self.raw=(checks.ROOT/'docs/HERMES_OPERATIONAL_WINDOWS_BINDINGS.json').read_bytes()
        self.manifest=json.loads(self.raw)
        self.names=tuple(self.manifest['host_files'])
        self.remote={str(checks.PureWindowsPath('C:/JarvisHermesLab/app')/name):value
                     for name,value in self.manifest['windows_files'].items()}

    def test_git_provenance_and_only_host_port_delta(self):
        name='memory_manager/phase4/windows.py'
        def revision(ref):
            return subprocess.check_output(['git','show',ref+':'+name],cwd=checks.ROOT)
        previous=revision(self.manifest['windows_git_commit'])
        self.assertEqual(self.manifest['windows_files'][name],hashlib.sha256(previous).hexdigest())
        self.assertEqual((checks.ROOT/name).read_bytes(),revision(self.manifest['host_git_commit']))
        old=types.ModuleType('previous_windows');old.__package__='memory_manager.phase4'
        exec(compile(previous,'verified-git-windows','exec'),old.__dict__)
        for skills in [False,True]:
            self.assertEqual(old.profile(skill_candidate=skills),windows.profile(skill_candidate=skills))
        args=dict(key='fixture-key',known_hosts='fixture-known-hosts')
        baseline=old.tunnel(**args)
        self.assertEqual(baseline,windows.tunnel(**args))
        current=windows.tunnel(**args,memory_port=8797)
        self.assertEqual([(a,b) for a,b in zip(baseline,current) if a!=b],
            [('127.0.0.1:8792:127.0.0.1:8792','127.0.0.1:8792:127.0.0.1:8797')])
        for port in [0,22,8787,11434]:
            with self.assertRaises(ValueError):windows.tunnel(**args,memory_port=port)

    def test_exact_windows_bindings_pass_and_unknown_drift_is_refused(self):
        with patch.object(checks.lifecycle,'probe',return_value=self.remote):
            self.assertEqual(self.manifest['windows_files'],checks.check_windows_patch(operational=True))
        name='memory_manager/phase4/windows.py'
        changed={**self.remote,str(checks.PureWindowsPath('C:/JarvisHermesLab/app')/name):'0'*64}
        with patch.object(checks.lifecycle,'probe',return_value=changed):
            with self.assertRaises(PermissionError):checks.check_windows_patch(operational=True)

    def test_historical_strict_default_is_preserved(self):
        with patch.object(checks.lifecycle,'probe',return_value=self.remote):
            with self.assertRaises(PermissionError):checks.check_windows_patch()

    def test_host_drift_and_manifest_drift_are_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'docs').mkdir()
            binding=root/'docs/HERMES_OPERATIONAL_WINDOWS_BINDINGS.json';binding.write_bytes(self.raw)
            for name in self.names:
                target=root/name;target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes((checks.ROOT/name).read_bytes())
            with patch.object(checks,'ROOT',root):
                checks.application_bindings(self.names,operational=True)
                target=root/'memory_manager/phase4/windows.py';target.write_bytes(target.read_bytes()+b'\n# drift\n')
                with self.assertRaises(PermissionError):checks.application_bindings(self.names,operational=True)
                binding.write_bytes(self.raw+b' ')
                with self.assertRaises(PermissionError):checks.application_bindings(self.names,operational=True)

    def test_old_evidence_and_reconciled_supervisor_are_exact(self):
        for name,value in self.manifest['historical_evidence'].items():
            self.assertEqual(value,hashlib.sha256((checks.ROOT/name).read_bytes()).hexdigest())
        original=(checks.ROOT/'docs/HERMES_OPERATIONAL_MANIFEST.json').read_bytes()
        self.assertEqual(self.manifest['base_manifest_sha256'],hashlib.sha256(original).hexdigest())
        effective=json.loads((checks.ROOT/'docs/HERMES_OPERATIONAL_RECONCILED_MANIFEST.json').read_bytes())
        self.assertEqual({'scripts/pilot_phase6b_panel.py','scripts/run_interactive_hermes.py'},set(effective['source_changes']))
        for name,value in effective['supervisor_sources'].items():
            self.assertEqual(value,hashlib.sha256((checks.ROOT/name).read_bytes()).hexdigest())


if __name__=='__main__':unittest.main()
