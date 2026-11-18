"""Candidate process -> real HTTP protocols -> fake native Hermes/Ollama.
All data synthetic, all listeners loopback; never contacts Windows or a GPU.
"""
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import socket
import shutil
import subprocess
import tempfile
import threading
import time
import unittest
import urllib.request

from scripts.prepare_operational_hermes import prepare, ROOT
from scripts.prepare_interactive_pilot import prepare as state_prepare
from memory_manager.phase6.operational import DIGEST
from memory_manager.phase2.local_model import PrivateHTTP
from memory_manager.phase3.mcp import dispatch as mcp_dispatch
from memory_manager.store import Memory


class OperationalRuntimeTests(unittest.TestCase):
    def test_browser_to_candidate_worker_memory_gate_and_result(self):
        self.run_case()

    def test_text_deployed_auth_and_runtime(self):
        self.run_case(text=True)

    def run_case(self, *, text=False):
        children = []; servers = []; creates = []; models = []; reads = []
        for port in [8643, 11435, 11436]:
            with socket.socket() as s:
                s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
                s.bind(('127.0.0.1', port))  # Never adopt a live endpoint.
        def free():
            with socket.socket() as s: s.bind(('127.0.0.1', 0)); return s.getsockname()[1]
        public, front, bridge = free(), free(), free()
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        env = {'PATH': os.environ['PATH'], 'LANG': 'C.UTF-8', 'PYTHONDONTWRITEBYTECODE': '1'}
        def start(command, cwd):
            p = subprocess.Popen(command, cwd=cwd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE); children.append(p)
            return p
        def ready(p, url):
            for _ in range(100):
                if p.poll() is not None: raise AssertionError(p.stderr.read().decode())
                try:
                    with opener.open(url, timeout=.3): return
                except Exception: time.sleep(.1)
            raise AssertionError('Runtime candidate not ready')
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp); candidate = tmp/'candidate'
            if text:
                # Exact installed code, not the optional SSO worktree modules.
                from scripts.prepare_text_missions import prepare as text_prepare
                candidate.mkdir();shutil.copytree('/opt/jarvis-hermes-pilot',candidate/'pilot-release')
                text_prepare(candidate/'frontend')
                for name in ['index.html','hermes-embedded.css']:
                    shutil.copyfile(Path('/home/user/gateway/public/jarvis')/name,candidate/'frontend'/name)
            else: prepare(candidate)
            state = tmp/'state'; cfg = state_prepare(state, front=front, bridge=bridge, fixture=True)
            origin = 'http://127.0.0.1:'+str(public)
            cfg.update(embeddedPanel={'enabled': True, 'origin': origin}, operations={'admissionEnabled': True, 'textEnabled': text, 'workerEnabled': True, 'voiceEnabled': False,
                'runtime': {'hermesToken': 'H'*43, 'modelToken': 'M'*43, 'memoryToken': 'R'*43, 'supervisorToken': 'S'*43, 'expiresAt': time.time()+295, 'maxMissions': 1}})
            (state/'config.json').write_text(json.dumps(cfg))
            native_memory = PrivateHTTP('http://127.0.0.1:'+str(bridge), 'R'*43)
            gate = PrivateHTTP('http://127.0.0.1:11436', 'M'*43)
            output = 'Quatre cellules identiques de 1 kg. Sources : synthetic://doselab/correction ; ancienne configuration : synthetic://doselab/old.'
            class Fake(BaseHTTPRequestHandler):
                def log_message(self, *_): pass
                def reply(self, value):
                    raw = json.dumps(value).encode(); self.send_response(200); self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(raw))); self.end_headers(); self.wfile.write(raw)
                def do_GET(self):
                    if self.server.server_port == 11435:
                        assert self.path == '/api/tags'; return self.reply({'models': [{'name': 'qwen3.5:4b', 'digest': DIGEST}]})
                    assert self.headers['Authorization'] == 'Bearer '+'H'*43
                    if self.path == '/v1/models': return self.reply({'data': [{'id': 'qwen3.5:4b'}]})
                    assert self.path == '/v1/runs/native-1'
                    memory = mcp_dispatch({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'jarvis_memory_knowledge', 'arguments': {'q': 'DoseLab'}}}, native_memory)
                    assert 'error' not in memory; reads.append(memory)
                    result = gate('POST', '/v1/chat/completions', {'model': 'qwen3.5:4b', 'messages': [{'role': 'user', 'content': 'DoseLab : consulte les sources synthétiques.'}]})
                    return self.reply({'status': 'completed', 'output': result['choices'][0]['message']['content']})
                def do_POST(self):
                    body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                    if self.server.server_port == 11435:
                        assert self.path == '/api/chat'; models.append(body)
                        return self.reply({'done': True, 'done_reason': 'stop', 'prompt_eval_count': 50, 'eval_count': 40, 'message': {'content': output}})
                    assert self.headers['Authorization'] == 'Bearer '+'H'*43 and self.path == '/v1/runs'
                    assert body['model'] == 'qwen3.5:4b'; creates.append(body)
                    self.reply({'run_id': 'native-1'})
            observer = PrivateHTTP('http://127.0.0.1:'+str(bridge), 'S'*43); halt = threading.Event()
            try:
                for port in [8643, 11435]:
                    srv = ThreadingHTTPServer(('127.0.0.1', port), Fake); servers.append(srv); threading.Thread(target=srv.serve_forever, daemon=True).start()
                private = start(['/usr/bin/python3', '-m', 'memory_manager.phase6.interactive', '--config', str(state/'config.json')], candidate/'pilot-release'); ready(private, cfg['origin']+'/api/health')
                epoch = observer('GET', '/v1/workers/windows-hermes/epoch')['epoch']
                def heartbeat():
                    sequence = 0
                    while not halt.is_set():
                        sequence += 1
                        observer('POST', '/v1/workers/windows-hermes/observe', {'epoch': epoch, 'sequence': sequence, 'endpoint_ready': True, 'gpu': {'observed_at': time.time(), 'free_mib': 10000, 'utilization': 0, 'miner_running': False}})
                        halt.wait(.5)
                reporter = threading.Thread(target=heartbeat, daemon=True); reporter.start()
                flag = tmp/'switch.json'; flag.write_text('{"enabled":true,"admissionEnabled":true}'); flag.chmod(0o600)
                ui_cfg = tmp/'ui.json'; ui_cfg.write_text(json.dumps({'origin': origin, 'upstreamPort': front, 'frontend': str(candidate/'frontend'), 'sourcePublic': '/home/user/workspace/jarvis/public', 'operationalAssets': True, 'switchFile': str(flag)}))
                ui = start(['node', 'ops/embedded-ui-lab.mjs', str(ui_cfg)], ROOT); ready(ui, origin+'/jarvis/')
                browser = subprocess.run(['node', 'test_hermes_text_browser.cjs' if text else 'test_hermes_operational_browser.cjs', str(ui_cfg), str(state/'operator.token'), '--runtime'], cwd=ROOT, env=env, capture_output=True, text=True, timeout=45)
                self.assertEqual(browser.returncode, 0, browser.stdout+browser.stderr)
                self.assertEqual(len(creates), 1); self.assertEqual(len(models), 1); self.assertEqual(len(reads), 1)
                if text:
                    with closing(Memory(state/'memory.sqlite')) as memory:
                        row=memory.db.execute('SELECT definition FROM mm_missions').fetchone()
                        mission=json.loads(row[0])
                        self.assertIn('Évalue « DoseLab » : Ω et µg',mission['objective'])
                        self.assertEqual(mission['allowed_tools'],['memory.search','report'])
                        self.assertEqual(mission['memory_context'],[])
                        self.assertEqual(mission['budget']['cost_micros'],0)
                with closing(Memory(state/'memory.sqlite')) as memory:
                    self.assertEqual(memory.db.execute("SELECT count(*) FROM mm_missions WHERE state='completed'").fetchone()[0], 1)
                    self.assertEqual(memory.db.execute('SELECT count(*) FROM p2_usage').fetchone()[0], 1)
                    self.assertEqual(memory.db.execute('SELECT sum(actual_remote_micros) FROM p2_usage').fetchone()[0], 0)
                print(browser.stdout.strip())
            finally:
                halt.set()
                if 'reporter' in locals(): reporter.join(timeout=3)
                for p in children:
                    if p.poll() is None: p.terminate(); p.wait(timeout=10)
                    p.stderr.close()
                for srv in servers: srv.shutdown(); srv.server_close()


if __name__ == '__main__': unittest.main()
