"""Optional: the reader against a REAL local InfluxDB 3 Core (dev only). Skipped unless
INFLUX3_URL and INFLUX3_TOKEN_FILE (JSON {"token": ...}, 0600) point at a disposable instance
holding the HA-shaped fixture (tables mL / switch.vsv_pump, database homeassistant)."""
import json, os, unittest
from .readers import Influx, Http, SourceUnavailable

URL, TOKEN = os.environ.get('INFLUX3_URL'), os.environ.get('INFLUX3_TOKEN_FILE')


@unittest.skipUnless(URL and TOKEN, 'no local InfluxDB 3')
class Live(unittest.TestCase):
    def setUp(self):
        token = json.load(open(TOKEN))['token']
        self.i = Influx(Http(URL, {'Authorization': 'Bearer ' + token}), ['homeassistant'])

    def test_entities_and_series(self):
        e = self.i.entities('vsv')
        self.assertIn({'entity': 'vsv_dosage', 'table': 'mL'}, e['items'])
        s = self.i.series('sensor.vsv_dosage', 2, 360)
        self.assertEqual((s['kind'], s['table']), ('numeric', 'mL')); self.assertGreater(s['count'], 3)
        self.assertEqual(self.i.series('sensor.does_not_exist', 2)['count'], 0)
        self.assertEqual(self.i.series('switch.vsv_pump', 2, 360)['table'], 'switch.vsv_pump')

    def test_wrong_database_or_token_is_unavailable(self):
        bad = Influx(Http(URL, {'Authorization': 'Bearer nope'}), ['homeassistant'])
        with self.assertRaises(SourceUnavailable): bad.entities()
        other = Influx(Http(URL, {'Authorization': 'Bearer ' + json.load(open(TOKEN))['token']}), ['nodb'])
        with self.assertRaises(SourceUnavailable): other.entities()


if __name__ == '__main__':
    unittest.main()
