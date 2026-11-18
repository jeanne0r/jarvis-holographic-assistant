"""Offline safety tests; importing the A1 runner never starts a process or network."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('qdrant_a1',Path(__file__).resolve().parents[2]/'ops'/'phase5-qdrant-a1.py')
a1=importlib.util.module_from_spec(spec);spec.loader.exec_module(a1)


class Safety(unittest.TestCase):
    def test_production_write_allowlist_and_port(self):
        with patch.object(a1.urllib.request,'build_opener') as network:
            for method,path in [('PUT','/collections/jarvis_memory_v1'),('POST','/collections/jarvis_memory_v1/points/delete'),('DELETE','/collections/jarvis_memory_v1'),('POST','/collections/jarvis_knowledge_experimental_v1/snapshots')]:
                with self.assertRaises(PermissionError):a1.api(6333,'fake',method,path)
            with self.assertRaises(PermissionError):a1.api(6334,'fake','GET','/')
            network.assert_not_called()
    def test_backup_is_private_exclusive_and_hash_verified(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'manifest.json';a1.save(path,{'synthetic':True})
            self.assertEqual(path.stat().st_mode&0o777,0o600)
            self.assertEqual(len(a1.sha(path)),64)
            with self.assertRaises(FileExistsError):a1.save(path,{})
    def test_resource_properties_are_explicit(self):
        command=a1.limits('synthetic-unit')
        for option in ['--property=MemoryMax=268435456','--property=CPUQuota=50%','--property=RuntimeMaxSec=600',
                       '--property=MemorySwapMax=0','--property=KillMode=control-group','--property=OOMPolicy=stop']:
            self.assertIn(option,command)
    def test_approval_checked_before_machine_access(self):
        with patch('sys.argv',['runner']),patch.object(a1,'memory_available') as memory:
            with self.assertRaises(PermissionError):a1.main()
            memory.assert_not_called()
    def test_yaml_config_and_private_network_are_explicit(self):
        text=a1.yaml_text({'service':{'host':'127.0.0.1','grpc_port':None,'http_port':16333}})
        self.assertIn('grpc_port: null',text);self.assertIn('host: "127.0.0.1"',text)
        self.assertIn('--property=PrivateNetwork=yes',a1.limits('synthetic-unit'))
    def test_redirect_is_denied(self):
        with self.assertRaises(PermissionError):a1.NoRedirect().redirect_request(None,None,None,None,None,None)


if __name__=='__main__':unittest.main()
