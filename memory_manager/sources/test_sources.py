import json, os, tempfile, threading, unittest
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

from ..store import Memory, Principal
from .readers import HomeAssistant, Influx, Http, SourceUnavailable, summarize, influxql_string
from .tools import SourceTools

NOW = 1_763_380_800.0  # 2025-11-17T12:00Z
STATES = [
    {'entity_id': 'sensor.vsv_dosage', 'state': '41.5', 'last_changed': '2026-11-17T10:00:00+00:00',
     'attributes': {'friendly_name': 'VSV dosage', 'unit_of_measurement': 'mL', 'icon': 'mdi:x', 'secret_thing': 'zz'}},
    {'entity_id': 'switch.vsv_pump', 'state': 'off', 'last_changed': '2026-11-17T09:00:00+00:00', 'attributes': {'friendly_name': 'Pompe VSV'}},
    {'entity_id': 'camera.porte', 'state': 'idle', 'last_changed': '2026-11-17T09:00:00+00:00',
     'attributes': {'friendly_name': 'Porte', 'entity_picture': '/api/camera_proxy/camera.porte?token=abc', 'access_token': 'abcdefabcdef'}},
]
HISTORY = [[{'state': str(40 + i % 3), 'last_changed': '2026-11-17T0%d:00:00+00:00' % i} for i in range(6)] + [{'state': 'unavailable', 'last_changed': '2026-11-17T07:30:00+00:00'}]]
# Shapes observed on a local InfluxDB 3 Core 3.12.1 (/api/v3/query_influxql, format=json).
SERIES = [{'iox::measurement': 'mL', 'time': '2026-11-16T00:00:00', 'mean': 40.0}, {'iox::measurement': 'mL', 'time': '2026-11-16T01:00:00', 'mean': 38.5},
          {'iox::measurement': 'mL', 'time': '2026-11-16T02:00:00', 'mean': 36.0}]
TAGS = [{'iox::measurement': 'mL', 'key': 'entity_id', 'value': 'vsv_dosage'}, {'iox::measurement': '°C', 'key': 'entity_id', 'value': 'salon_temperature'}]


class Fake(BaseHTTPRequestHandler):
    seen = []
    def log_message(self, *a): pass
    def reply(self, code, raw, ctype='application/json', extra=None):
        self.send_response(code); self.send_header('Content-Type', ctype)
        for k, v in (extra or {}).items(): self.send_header(k, v)
        self.send_header('Content-Length', str(len(raw))); self.end_headers(); self.wfile.write(raw)
    def do_GET(self):
        u = urlsplit(self.path); Fake.seen.append(('GET', u.path, parse_qs(u.query, keep_blank_values=True), self.headers.get('Authorization')))
        if u.path == '/api/states': return self.reply(200, json.dumps(STATES).encode())
        if u.path.startswith('/api/history/period/'): return self.reply(200, json.dumps(HISTORY).encode())
        if u.path == '/redirect': return self.reply(302, b'', extra={'Location': '/api/services/switch/turn_on'})
        if u.path == '/api/v3/query_influxql':
            q = parse_qs(u.query)['q'][0]
            return self.reply(200, json.dumps(TAGS if q.startswith('SHOW TAG VALUES') else SERIES).encode())
        self.reply(404, b'{}')
    def do_POST(self):
        u = urlsplit(self.path); body = self.rfile.read(int(self.headers.get('Content-Length', 0))).decode()
        Fake.seen.append(('POST', u.path, parse_qs(u.query), body))
        self.reply(404, b'{}')


class Sources(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Fake)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = 'http://127.0.0.1:%d' % cls.server.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close()

    def setUp(self):
        Fake.seen.clear()
        self.ha = HomeAssistant(Http(self.base, {'Authorization': 'Bearer HA-TOKEN-SHOULD-NOT-LEAK'}))
        self.influx = Influx(Http(self.base, {'Authorization': 'Bearer INFLUX-ADMIN'}), ['homeassistant'])
        self.dir = tempfile.TemporaryDirectory(); self.db = Path(self.dir.name) / 'm.sqlite'
        Memory(self.db, create=True).close()

    def tearDown(self):
        self.dir.cleanup()

    def test_ha_states_keeps_only_safe_attributes(self):
        out = self.ha.states(query='vsv')
        self.assertEqual([r['entity_id'] for r in out['items']], ['sensor.vsv_dosage', 'switch.vsv_pump'])
        self.assertEqual(out['items'][0]['unit_of_measurement'], 'mL')
        self.assertNotIn('secret_thing', out['items'][0]); self.assertNotIn('icon', out['items'][0])
        cam = self.ha.states(domain='camera')['items'][0]
        self.assertNotIn('entity_picture', cam); self.assertNotIn('access_token', cam)
        self.assertEqual({(m, p) for m, p, *_ in Fake.seen}, {('GET', '/api/states')})

    def test_ha_history_is_one_get_and_summarized(self):
        out = self.ha.history('sensor.vsv_dosage', 24, now=NOW)
        self.assertEqual(out['kind'], 'numeric'); self.assertEqual(out['count'], 7); self.assertEqual(out['unavailable'], 1)
        self.assertEqual((out['min'], out['max']), (40.0, 42.0))
        (method, path, query, auth), = Fake.seen
        self.assertEqual(method, 'GET'); self.assertTrue(path.startswith('/api/history/period/'))
        self.assertEqual(query['filter_entity_id'], ['sensor.vsv_dosage']); self.assertIn('no_attributes', query)

    def test_entity_and_bounds_validation(self):
        for bad in ['sensor.vsv/../../api/services', 'switch.x?y', '../api', 'sensor.', 'SENSOR.x', 42]:
            with self.assertRaises(ValueError): self.ha.history(bad, 24)
        for hours in [0, 24 * 32, 1.5, True]:
            with self.assertRaises(ValueError): self.ha.history('sensor.vsv_dosage', hours)
        self.assertEqual(Fake.seen, [])

    def test_http_has_no_write_method_and_follows_no_redirect(self):
        http = Http(self.base, {})
        for method in ['PUT', 'DELETE', 'PATCH']:
            with self.assertRaises(PermissionError): http(method, '/api/states')
        with self.assertRaises(SourceUnavailable): http('GET', '/redirect')
        self.assertEqual([p for _, p, *_ in Fake.seen], ['/redirect'])
        for bad in ['http://u:p@h', 'ftp://h', 'http://h/api', 'http://h?x=1']:
            with self.assertRaises(ValueError): Http(bad, {})

    def test_error_never_echoes_token(self):
        http = Http('http://127.0.0.1:9', {'Authorization': 'Bearer HA-TOKEN-SHOULD-NOT-LEAK'}, timeout=1)
        with self.assertRaises(SourceUnavailable) as e: HomeAssistant(http).states()
        self.assertNotIn('TOKEN', str(e.exception))

    def test_influx_series_is_one_get_with_built_influxql(self):
        out = self.influx.series('sensor.vsv_dosage', 30, 60, now=NOW)
        self.assertEqual((out['count'], out['min'], out['last_value'], out['table']), (3, 36.0, 36.0, 'mL'))
        (method, path, query, auth), = Fake.seen
        self.assertEqual((method, path, query['db'], query['format']), ('GET', '/api/v3/query_influxql', ['homeassistant'], ['json']))
        self.assertEqual(query['q'][0], 'SELECT mean("value") FROM /.*/ WHERE "entity_id" = \'vsv_dosage\' AND "domain" = \'sensor\' '
                                        'AND time > now() - 30d GROUP BY time(60m) fill(none)')
        self.assertEqual(influxql_string("a'b\\c"), "'a\\'b\\\\c'")
        self.assertEqual(self.influx.series('sensor.vsv_dosage', 3660, 1)['window_minutes'], 1055)   # bounded to 5000 points
        with self.assertRaises(PermissionError): self.influx.series('sensor.vsv_dosage', 3, database='_internal')
        with self.assertRaises(ValueError): self.influx.series("sensor.vsv' OR 1=1", 3)

    def test_influx_entities(self):
        out = self.influx.entities('vsv')
        self.assertEqual(out['items'], [{'entity': 'vsv_dosage', 'table': 'mL'}])
        self.assertEqual(Fake.seen[0][2]['q'], ['SHOW TAG VALUES WITH KEY = "entity_id"'])

    def test_summary_of_states(self):
        out = summarize([(NOW, 'on'), (NOW + 60, 'off'), (NOW + 120, 'on')])
        self.assertEqual(out['kind'], 'states'); self.assertEqual(out['states'], {'on': 2, 'off': 1})

    def test_tool_records_citable_observed_measurement(self):
        with closing(Memory(self.db)) as m:
            tools = SourceTools(m, 'user', {'ha': self.ha, 'influx': self.influx}, clock=lambda: NOW)
            rows = tools.call('source.ha.history', {'entity_id': 'sensor.vsv_dosage', 'hours': 24})
            ref = rows[0]['source']['ref']
            self.assertEqual(ref, 'ha://sensor.vsv_dosage/history/24h@20251117T1200Z')
            reader = Principal('user', frozenset({'private'}), frozenset({'reader'}))
            hist = m.history(reader, rows[0]['memory_id'])
            self.assertEqual((hist[0]['id'], hist[0]['status'], hist[0]['source']['kind']), (rows[0]['revision_id'], 'observed', 'measurement'))
            self.assertEqual(hist[0]['source']['ref'], ref)
            self.assertNotIn('TOKEN', json.dumps(hist))
            rows = tools.call('source.influx.series', {'entity_id': 'sensor.vsv_dosage', 'days': 30})
            self.assertEqual(rows[0]['source']['ref'], 'influx://homeassistant/sensor.vsv_dosage/30d/60m@20251117T1200Z')
            with self.assertRaises(ValueError): tools.call('source.influx.series', {'entity_id': 'sensor.vsv_dosage', 'days': 3, 'bucket': 'x'})

    def test_tool_refuses_unknown_fields_tools_and_sources(self):
        with closing(Memory(self.db)) as m:
            tools = SourceTools(m, 'user', {'ha': self.ha})
            self.assertEqual(tools.available(), ['source.ha.history', 'source.ha.states'])
            with self.assertRaises(ValueError): tools.call('source.ha.history', {'entity_id': 'sensor.vsv_dosage', 'hours': 2, 'url': 'x'})
            with self.assertRaises(ValueError): tools.call('source.ha.history', {'entity_id': 'sensor.vsv_dosage'})
            with self.assertRaises(PermissionError): tools.call('source.ha.call_service', {})
            with self.assertRaises(PermissionError): tools.call('source.influx.series', {'entity_id': 'sensor.x', 'days': 1})
            self.assertEqual(m.db.execute('SELECT count(*) FROM mm_events').fetchone()[0], 0)
        self.assertFalse(any(m == 'POST' for m, *_ in Fake.seen))

    def test_every_request_is_a_get_on_two_read_paths(self):
        self.ha.states(); self.ha.history('sensor.vsv_dosage', 2); self.influx.entities(); self.influx.series('sensor.vsv_dosage', 2)
        self.assertEqual({(m, p if not p.startswith('/api/history/period/') else '/api/history/period/') for m, p, *_ in Fake.seen},
                         {('GET', '/api/states'), ('GET', '/api/history/period/'), ('GET', '/api/v3/query_influxql')})


if __name__ == '__main__':
    unittest.main()
