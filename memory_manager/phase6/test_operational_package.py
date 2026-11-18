"""Candidate release + actual UI/session/bridge SQLite. Runtime stays disabled."""
import hashlib
from contextlib import closing
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time
import unittest
import urllib.request
import urllib.error
from scripts.prepare_operational_hermes import prepare, ROOT
from scripts.prepare_interactive_pilot import prepare as state_prepare
from memory_manager.store import Memory


class OperationalPackageTests(unittest.TestCase):
    def test_packaged_ui_admission_cancel_restart_and_production_unchanged(self):
        inputs = [Path('/home/user/gateway/server.js'), Path('/home/user/gateway/public/jarvis/app.js'), Path('/home/user/gateway/data/hermes-panel-switch.json'), Path('/opt/jarvis-hermes-pilot/deployment-files.json')]
        before = {p: p.read_bytes() for p in inputs}
        children = []; opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        def free():
            with socket.socket() as s: s.bind(('127.0.0.1', 0)); return s.getsockname()[1]
        ports = set()
        while len(ports) < 3: ports.add(free())
        public, front, bridge = ports
        origin = 'http://127.0.0.1:'+str(public)
        env = {'PATH': os.environ['PATH'], 'LANG': 'C.UTF-8', 'PYTHONDONTWRITEBYTECODE': '1'}
        def start(command, cwd):
            p = subprocess.Popen(command, cwd=cwd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE); children.append(p); return p
        def ready(p, url):
            for _ in range(100):
                if p.poll() is not None: raise AssertionError(p.stderr.read().decode())
                try:
                    with opener.open(url, timeout=.3): return
                except Exception: time.sleep(.1)
            raise AssertionError('Candidate readiness failed')
        def stop(p):
            p.terminate(); p.wait(timeout=10); p.stderr.close(); children.remove(p); self.assertEqual(p.returncode, 0)
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp); candidate = tmp/'candidate'; prepare(candidate)
            state = tmp/'state'; cfg = state_prepare(state, front=front, bridge=bridge, fixture=True)
            cfg.update(embeddedPanel={'enabled': True, 'origin': origin}, operations={'admissionEnabled': True, 'textEnabled': True, 'workerEnabled': False, 'voiceEnabled': False})
            (state/'config.json').write_text(json.dumps(cfg))
            (tmp/'switch.json').write_text('{"enabled":true,"admissionEnabled":true}'); (tmp/'switch.json').chmod(0o600)
            (tmp/'ui.json').write_text(json.dumps({'origin': origin, 'upstreamPort': front, 'frontend': str(candidate/'frontend'), 'sourcePublic': '/home/user/workspace/jarvis/public', 'operationalAssets': True, 'switchFile': str(tmp/'switch.json')}))
            try:
                private = start(['/usr/bin/python3', '-m', 'memory_manager.phase6.interactive', '--config', str(state/'config.json')], candidate/'pilot-release')
                ready(private, cfg['origin']+'/api/health')
                ui = start(['node', 'ops/embedded-ui-lab.mjs', str(tmp/'ui.json')], ROOT); ready(ui, origin+'/jarvis/')
                browser = subprocess.run(['node', 'test_hermes_operational_browser.cjs', str(tmp/'ui.json'), str(state/'operator.token')], cwd=ROOT, env=env, capture_output=True, text=True, timeout=90)
                self.assertEqual(browser.returncode, 0, browser.stdout+browser.stderr); print(browser.stdout.strip())
                stop(private)
                private = start(['/usr/bin/python3', '-m', 'memory_manager.phase6.interactive', '--config', str(state/'config.json')], candidate/'pilot-release'); ready(private, cfg['origin']+'/api/health')
                with closing(Memory(state/'memory.sqlite')) as memory:
                    self.assertEqual(memory.db.execute("SELECT count(*) FROM mm_missions WHERE state='cancelled'").fetchone()[0], 4)
                    self.assertEqual(memory.db.execute('SELECT count(*) FROM p2_usage').fetchone()[0], 0)
                    self.assertEqual(memory.db.execute('SELECT count(*) FROM mm_missions').fetchone()[0], 4)
            finally:
                for child in list(children):
                    if child.poll() is None: stop(child)
                    else: child.stderr.close()
        for p, original in before.items(): self.assertEqual(p.read_bytes(), original)


if __name__ == '__main__': unittest.main()
