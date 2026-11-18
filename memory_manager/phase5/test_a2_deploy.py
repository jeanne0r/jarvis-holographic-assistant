"""A2 preparation tests do not access CT205 or start services."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

p=Path(__file__).resolve().parents[2]/'ops'/'phase5-a2-deploy.py'
spec=importlib.util.spec_from_file_location('a2',p);a2=importlib.util.module_from_spec(spec);spec.loader.exec_module(a2)


class A2Safety(unittest.TestCase):
    def test_approval_before_reading_bundle_or_machine(self):
        with patch('sys.argv',['deploy']),patch.object(a2,'available') as machine:
            with self.assertRaises(PermissionError):a2.main()
            machine.assert_not_called()
    def test_save_permissions_and_exclusive(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'public.py';a2.save(p,'# source',0o644)
            self.assertEqual(p.stat().st_mode&0o777,0o644)
            with self.assertRaises(FileExistsError):a2.save(p,'replace')
            private=Path(tmp)/'private.json';a2.save(private,{'synthetic':True})
            self.assertEqual(private.stat().st_mode&0o777,0o600)
    def test_watchdog_and_asgi_preflight_compile(self):
        compile(a2.WATCHDOG,'watchdog','exec');compile(a2.ASGI_CHECK,'asgi-check','exec')
        self.assertIn("'no_model_instance_created':True",a2.ASGI_CHECK)
        self.assertNotIn('pip install',a2.WATCHDOG)
        self.assertIn("'experimental_enabled':False",a2.WATCHDOG)
    def test_hash_compatible_with_canonical_pipeline(self):
        from memory_manager.store import digest
        self.assertEqual(a2.digest({'fr':'mémoire','a':1}),digest({'fr':'mémoire','a':1}))


if __name__=='__main__':unittest.main()
