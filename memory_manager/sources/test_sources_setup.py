"""Operator setup: hidden tokens only in sources.json (0600), literal LAN IPs, drop-in content."""
import importlib.util, json, os, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('sources_setup', ROOT / 'ops/demand-simple/sources_setup.py')
ss = importlib.util.module_from_spec(spec); spec.loader.exec_module(ss)


class Setup(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp()); os.chmod(self.d, 0o700)
        self.addCleanup(lambda: __import__('shutil').rmtree(self.d))

    def answers(self, *values):
        it = iter(values); return lambda prompt: next(it)

    def test_config_written_private_and_ips_extracted(self):
        cfg = ss.ask_config(self.answers('o', '', 'o', 'http://192.0.2.40:8181', 'homeassistant'),
                            secret=lambda prompt: 'TOKEN-' + ('HA' if 'HA' in prompt else 'INFLUX'))
        self.assertEqual(cfg['homeAssistant']['url'], 'http://192.0.2.215:8123')
        self.assertEqual(ss.validate(cfg), ['192.0.2.215', '192.0.2.40'])
        ss.write_private(self.d / 'sources.json', cfg, self.d)
        self.assertEqual((self.d / 'sources.json').stat().st_mode & 0o777, 0o600)
        self.assertEqual(ss.load_config(self.d), cfg)
        os.chmod(self.d / 'sources.json', 0o644)
        with self.assertRaises(PermissionError): ss.load_config(self.d)

    def test_refuses_names_public_and_loopback(self):
        for url in ['http://homeassistant.local:8123', 'http://8.8.8.8:8086', 'http://127.0.0.1:8086']:
            with self.assertRaises(ValueError): ss.literal_ip(url)
        with self.assertRaises(ValueError):
            ss.ask_config(self.answers('o', '', 'n'), secret=lambda p: '')

    def test_dropin_only_allows_listed_ips(self):
        out = ss.network(['192.0.2.215', '192.0.2.40'], self.d / 'unit.d/real-sources.conf', reload=False)
        text = Path(out['dropin']).read_text()
        self.assertIn('[Service]\nIPAddressAllow=192.0.2.215/32 192.0.2.40/32\n', text)
        self.assertNotIn('IPAddressDeny', text)          # additive: the unit's deny-all stays


if __name__ == '__main__':
    unittest.main()
