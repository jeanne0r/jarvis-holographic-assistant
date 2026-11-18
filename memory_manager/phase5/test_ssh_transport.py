import unittest
from unittest.mock import patch
from .ssh_transport import CT205,REMOTE


class Capabilities(unittest.TestCase):
    def endpoint(self,service):return CT205(service,'/var/lib/jarvis-memory/phase5-a2/synthetic-test',identity='/synthetic/key',known_hosts='/synthetic/known_hosts')
    def test_production_paths_and_arbitrary_ports_denied_before_ssh(self):
        q=self.endpoint('qdrant')
        with patch('subprocess.run') as run:
            for method,path in [('GET','/collections/jarvis_memory_v1'),('POST','/collections/jarvis_memory_v1/points/delete'),('DELETE','/collections/jarvis_knowledge_experimental_v1'),('PUT','/collections/jarvis_knowledge_experimental_v1')]:
                with self.assertRaises(PermissionError):q(method,path)
            run.assert_not_called()
    def test_identity_and_deadline_are_host_configuration(self):
        with self.assertRaises(ValueError):CT205('embedding','/etc',identity='x',known_hosts='y')
        with self.assertRaises(ValueError):self.endpoint('qdrant')('GET','/collections/jarvis_knowledge_experimental_v1',timeout=100)
        compile(REMOTE,'private capability helper','exec')
    def test_ssh_pins_host_key_and_never_passes_tokens(self):
        import subprocess
        with patch('subprocess.run',return_value=subprocess.CompletedProcess([],0,'{"ok":true,"result":{"ready":true}}','')) as run:
            self.assertEqual(self.endpoint('qdrant')('GET','/collections/jarvis_knowledge_experimental_v1'),{'ready':True})
            cmd=run.call_args.args[0]
            self.assertIn('StrictHostKeyChecking=yes',cmd);self.assertIn('IdentitiesOnly=yes',cmd)
            self.assertNotIn('Bearer',run.call_args.kwargs['input'])


if __name__=='__main__':unittest.main()
