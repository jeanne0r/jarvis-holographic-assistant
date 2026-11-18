"""Prod 16.11: the gate turned every PermissionError into a bare 403 with no trace.
The client still learns nothing more; the journal now names the reason (and tool)."""
import contextlib, io, json, threading, types, unittest, urllib.error, urllib.request
from .model_gate import server

TOKEN = 'synthetic-token-with-at-least-32-characters'


class GateJournal(unittest.TestCase):
    def post(self, reason):
        def call(body): raise PermissionError(reason)
        gate = types.SimpleNamespace(call=call, cfg=types.SimpleNamespace(model='fixture:4b', context_tokens=4096))
        srv = server(gate, TOKEN); threading.Thread(target=srv.serve_forever, daemon=True).start()
        url = 'http://127.0.0.1:%d/v1/chat/completions' % srv.server_address[1]
        req = urllib.request.Request(url, data=b'{"model":"fixture:4b","messages":[]}',
                                     headers={'Authorization': 'Bearer ' + TOKEN, 'Content-Type': 'application/json'})
        out = io.StringIO()
        try:
            with contextlib.redirect_stdout(out), self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(req, timeout=3)
            body = json.loads(ctx.exception.read())
        finally:
            srv.shutdown(); srv.server_close()
        return ctx.exception.code, body, [json.loads(l) for l in out.getvalue().splitlines() if l.startswith('{')]

    def test_refusal_reason_and_tool_journaled_client_sees_generic_403(self):
        code, body, lines = self.post('Unadvertised model tool denied: report')
        self.assertEqual((code, body), (403, {'error': 'Pilot quota or mission denied'}))
        self.assertEqual(lines, [{'event': 'model-gate-refused', 'reason': 'Unadvertised model tool denied: report'}])

    def test_sensitive_looking_reason_is_never_journaled(self):
        code, _, lines = self.post('Unadvertised model tool denied: get_api_key')
        self.assertEqual(code, 403); self.assertEqual(lines, [{'event': 'model-gate-refused', 'reason': '[filtered]'}])


if __name__ == '__main__':
    unittest.main()


class ResidentModel(unittest.TestCase):
    """18.11 ebd39223: Kryptex ~1.1 GB + our loaded model ~5.8 GB left 3.3 GB free and the check refused.
    Our own resident model's VRAM counts as available to it; anything else does not."""
    def ps(self, rows=None, fail=False):
        def transport(method, path, body=None, timeout=5):
            if fail: raise OSError('tunnel down')
            assert (method, path) == ('GET', '/api/ps'); return {'models': rows or []}
        return transport

    def test_own_model_counted_others_not_with_notes(self):
        from .model_gate import counting_resident, vram_available
        from ..phase2.local_model import Busy
        sample = {'observed_at': 1000, 'miner_running': True, 'utilization': 100, 'free_mib': 3281}
        ours = {'name': 'qwen3.5:4b', 'digest': 'd1', 'size_vram': 5959 * 1024 * 1024}
        s, note = counting_resident(sample, self.ps([ours]), 'qwen3.5:4b', 'd1', 8500)
        self.assertEqual(s['free_mib'], 3281 + 5959); vram_available(s, 8500, now=1001); self.assertEqual(note, 'own model resident, 5959 MiB')
        self.assertEqual(sample['free_mib'], 3281)
        for rows, want in (([dict(ours, digest='other')], 'not resident (ps: qwen3.5:4b / other'), ([], 'not resident (ps: - / -)')):
            s, note = counting_resident(sample, self.ps(rows), 'qwen3.5:4b', 'd1', 8500)
            self.assertTrue(note.startswith(want), note)
            with self.assertRaises(Busy): vram_available(s, 8500, now=1001)
        s, note = counting_resident(sample, self.ps(fail=True), 'qwen3.5:4b', 'd1', 8500)
        self.assertEqual(note, 'ps-error OSError, 0 MiB')
        self.assertEqual(counting_resident(dict(sample, free_mib=9000), self.ps(fail=True), 'q', 'd', 8500)[1], None)   # enough: no call
        self.assertEqual(counting_resident(dict(sample, free_mib=float('nan')), self.ps([ours]), 'qwen3.5:4b', 'd1', 8500)[1], None)
