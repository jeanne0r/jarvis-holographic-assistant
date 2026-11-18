"""Opt-in composition of the existing bridge, Windows client and model gate.

No SSH, process execution, Windows startup or new canonical store in the worker.
The separate, approved lifecycle supplies short-lived observations and tunnels.
"""
import argparse
import fcntl
from contextlib import closing
import hashlib
import io
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import threading
import time

from ..store import Memory, Principal, SECRET
from ..api import server
from ..phase2 import budgets
from ..phase2.bridge import Bridge
from ..phase2.hermes import HermesRuns
from ..phase2.http_bridge import dispatch
from ..phase2.local_model import ModelConfig, PrivateHTTP, Busy, gpu_available
from ..phase3.model_gate import Gate, server as model_server, vram_available, counting_resident
from ..phase3.lab import OWNER
from ..phase6d import heartbeat
from ..phase6d.database import migrate as migrate_operational
from ..phase6d.evidence import ObservedTools, metadata
from .interactive import OBJECTIVE, BUDGET, LOCK
from .worker import tick as existing_tick

WORKER = 'windows-hermes'
TOOLS = ['memory.search', 'sources.read', 'report']
MODEL = 'qwen3.5:4b'
DIGEST = 'd8b0f5e9760cd1682034f292d7ef72ec46f432149be0df7574bf2d6e92e38c04'
TEXT_PREFIX = 'Demande explicite utilisateur (données et outils synthétiques seulement) : '
READ_TOOLS = {'memory.audit', 'memory.knowledge', 'memory.search', 'memory.history', 'memory.project',
              'memory.experiences', 'memory.contradictions', 'skill.get',
              'source.ha.states', 'source.ha.history', 'source.influx.entities', 'source.influx.series'}


def definition(objective):
    return dict(objective=objective, trigger='jarvis-experimental', priority=1,
                memory_context=[], plan=['retrieve', 'report'], allowed_tools=list(TOOLS), budget=dict(BUDGET))


def options(cfg):
    value = cfg.get('operations', {})
    if not isinstance(value, dict) or set(value) - {'admissionEnabled', 'textEnabled', 'workerEnabled', 'voiceEnabled', 'runtime'}:
        raise ValueError('Explicit operational flags only')
    for field in ['admissionEnabled', 'textEnabled', 'workerEnabled', 'voiceEnabled']:
        if type(value.get(field, False)) is not bool:
            raise ValueError('Boolean server flags required')
    if value.get('textEnabled') and not value.get('admissionEnabled'):
        raise ValueError('Text requires human admission')
    return value


class Controller:
    """One serial owner; persistent bridge leases and unknown states remain authoritative."""
    def __init__(self, path, cfg, *, client=None, upstream=None, clock=time.time, endpoint_probe=None, mission_id=None, searcher=None, sources=None):
        self.path, self.cfg, self.clock = Path(path), cfg, clock
        self.flags = options(cfg)
        runtime = self.flags.get('runtime', {})
        self.enabled = self.flags.get('workerEnabled', False)
        if self.enabled and (set(runtime) != {'hermesToken', 'modelToken', 'memoryToken', 'supervisorToken', 'expiresAt', 'maxMissions'}
                or type(runtime['expiresAt']) not in (int, float) or not math.isfinite(runtime['expiresAt'])
                or not self.clock() < runtime['expiresAt'] <= self.clock() + 300
                or runtime['maxMissions'] != 1):
            raise PermissionError('Approved five-minute, single-mission worker window required')
        if self.enabled:
            secrets = [runtime.get(k) for k in ['hermesToken', 'modelToken', 'memoryToken', 'supervisorToken']]
            if any(not isinstance(s, str) or not 32 <= len(s) <= 256 for s in secrets) or len(set(secrets + [cfg['bridgeToken']])) != 5:
                raise PermissionError('Distinct private service identities required')
        self.runtime = runtime
        self.p = Principal(OWNER, frozenset({'private'}), frozenset({'reader', 'proposer', 'mission_writer',
            'mission_worker', 'budget_admin', 'metered_caller', 'worker_supervisor', 'worker_reporter', 'evidence_writer'}), 'operational-controller')
        self.client = client or (HermesRuns(PrivateHTTP('http://127.0.0.1:8643', runtime['hermesToken']), MODEL, allow_live=True) if self.enabled else None)
        self.endpoint_probe = endpoint_probe or (lambda: bool(self.client.http('GET', '/v1/models', timeout=2).get('data')))
        self.searcher=searcher
        self.resident_note = None
        self.busy_reason = None   # 18.11 diagnosis: why the GPU was last judged busy (journaled on change)
        self.busy_wait = 30   # seconds a model turn may wait for a GPU observation that passes the thresholds
        self.sources=sources or {}
        self.target_mission=mission_id
        self.last_status = None
        outer = self
        raw_client = self.client
        class TrackedClient:
            def __getattr__(self, key): return getattr(raw_client, key)
            def status(self, run_id):
                outer.last_status = raw_client.status(run_id)
                return outer.last_status
        if self.client: self.client = TrackedClient()
        self.upstream = upstream or PrivateHTTP('http://127.0.0.1:11435')
        self.config = ModelConfig(MODEL, DIGEST, context_tokens=64000, max_output_tokens=768,
            timeout_seconds=60, min_free_mib=8500, think=False)
        self.cfg = self.config
        self.gate = None
        self.active = None
        self.bound = None
        self.sample = None
        self.sample_changed = threading.Condition()
        self.last_inference_ended = None
        self.lock = threading.Lock()
        with closing(Memory(self.path)) as memory:
            # Reuse the existing additive migration and its verified snapshot.
            migrate_operational(memory)
            self.epoch = heartbeat.register(memory, self.p, WORKER, self.p.actor)
            self.window_key = 'operational-window-' + str(runtime.get('expiresAt', 'disabled'))
            prior = memory.db.execute('SELECT mission_id FROM p2_events WHERE event_key=? LIMIT 1', (self.window_key,)).fetchone()
            if prior: self.bound = prior[0]
            # Never resume an earlier process's ambiguous submission/run.
            with memory.db:
                for row in memory.db.execute("SELECT o.mission_id FROM p2_outbox o JOIN mm_missions m ON m.id=o.mission_id WHERE m.owner=? AND o.state IN ('submitting','submitted','cancel_requested')", (OWNER,)).fetchall():
                    memory.db.execute("UPDATE p2_outbox SET state='unknown',lease_until=0 WHERE mission_id=?", (row[0],))
                    memory.db.execute("UPDATE mm_missions SET state='paused' WHERE id=?", (row[0],))
                    Bridge(memory, self.p).event(row[0], 'operational-restart-uncertain', 'reconciliation_required', {'automatic_replay': False})

    def note_busy(self, reason, sample):
        # Numbers only (no names, paths or content): which threshold failed, and by how much.
        g = sample if isinstance(sample, dict) else {}
        num = lambda v: round(v, 1) if type(v) in (int, float) and math.isfinite(v) else None
        text = '%s (free_mib %s, utilization %s, miner %s, age_s %s, resident %s)' % (reason, num(g.get('free_mib')), num(g.get('utilization')),
               g.get('miner_running') if type(g.get('miner_running')) is bool else None, num(self.clock() - g['observed_at']) if type(g.get('observed_at')) in (int, float) else None, self.resident_note)
        if text != self.busy_reason:
            print(json.dumps({'event': 'gpu-busy', 'reason': text}), flush=True)
        self.busy_reason = text

    def telemetry(self):
        if not self.sample:
            raise Busy('Supervisor unavailable')
        sample = self.own_model(self.sample)
        vram_available(sample, 8500, now=self.clock())
        return sample

    def own_model(self, sample):
        adjusted, self.resident_note = counting_resident(sample, self.upstream, self.config.model, self.config.digest, 8500)
        return adjusted

    def observe(self, memory, principal, data):
        principal.require('worker_reporter')
        if principal.actor != 'operational-supervisor' or principal.name != OWNER:
            raise PermissionError('Supervisor identity required')
        if set(data) != {'epoch', 'sequence', 'endpoint_ready', 'gpu'} or type(data['endpoint_ready']) is not bool:
            raise ValueError('Observation contract')
        sample = data['gpu']
        state = 'offline'
        if data['endpoint_ready']:
            try:
                vram_available(self.own_model(sample), 8500, now=self.clock())
                state = 'ready' if self.endpoint_probe() is True else 'offline'
            except Busy as e:
                state = 'gpu_busy'; self.note_busy(str(e), sample)
            except Exception: state = 'offline'
        if state != 'gpu_busy': self.busy_reason = None
        heartbeat.observe(memory, self.p, WORKER, data['epoch'], data['sequence'], state, now=self.clock())
        with self.sample_changed:
            self.sample = sample
            self.sample_changed.notify_all()
        return self.availability(memory)

    def availability(self, memory):
        value = heartbeat.status(memory, self.p, WORKER, now=self.clock(), ttl=10)
        enabled = self.enabled and self.clock() < self.runtime['expiresAt']
        target=self.bound or self.target_mission
        mission = Bridge(memory, self.p).get(target) if target else None
        return {**value, 'dispatch_allowed': enabled and value['dispatch_allowed'] and (self.bound is None or self.active is not None),
                'window_open': enabled, 'one_mission': True, 'automatic_replay': False,
                'executions_started': int(self.bound is not None), 'mission_state': mission['state'] if mission else None}

    def step(self):
        if not self.lock.acquire(blocking=False):
            return
        try:
            with closing(Memory(self.path)) as memory:
                if not self.enabled:
                    self.gate = None
                    return
                bridge = Bridge(memory, self.p)
                if self.clock() >= self.runtime['expiresAt']:
                    self.gate = None
                    if self.active:
                        bridge.cancel(self.active)
                        info = existing_tick(memory, self.p, self.active, self.client, self.telemetry, endpoint_ready=False, approved=True)
                        if info['state'] in {'cancelled', 'failed', 'completed'}: self.active = None
                    return
                if self.active is None:
                    if self.bound is not None or not self.availability(memory)['dispatch_allowed']:
                        return
                    # Any unresolved older run blocks new execution, even if a user
                    # cancels or a second controller is accidentally started.
                    if memory.db.execute("SELECT 1 FROM p2_outbox WHERE state='unknown' LIMIT 1").fetchone():
                        return
                    row = memory.db.execute("SELECT o.mission_id FROM p2_outbox o JOIN mm_missions m ON m.id=o.mission_id WHERE m.owner=? AND m.scope='private' AND o.state='ready' AND m.state='queued' AND (? IS NULL OR m.id=?) ORDER BY m.created LIMIT 1", (OWNER,self.target_mission,self.target_mission)).fetchone()
                    if not row:
                        return
                    self.telemetry()
                    self.active = self.bound = row[0]
                    with memory.db: bridge.event(self.active, self.window_key, 'execution_window_bound', {'max_missions': 1})
                    bid = budgets.create(memory, self.p, token_limit=98304)
                    self.gate = Gate(memory, self.p, bid, self.active, self.config, self.upstream, self.telemetry,
                                     max_calls=6, seconds=min(180, self.runtime['expiresAt'] - self.clock()))
                info = bridge.get(self.active)
                # Cancellation/polling remains possible if the GPU is now occupied.
                ready = self.availability(memory)['dispatch_allowed']
                info = existing_tick(memory, self.p, self.active, self.client, self.telemetry, endpoint_ready=ready, approved=True)
                if info['state'] in {'completed', 'failed', 'cancelled'} and self.last_status:
                    output = str(self.last_status.get('output', ''))
                    if 8000 < len(output) <= 32000 and not SECRET.search(output):
                        parts = [output[i:i+1000] for i in range(0, len(output), 1000)]
                        with memory.db:
                            for i, part in enumerate(parts): bridge.event(self.active, 'full-output-'+str(i), 'result_part', {'index': i, 'output': part})
                            bridge.event(self.active, 'full-output-manifest', 'result_complete', {'parts': len(parts), 'sha256': hashlib.sha256(output.encode()).hexdigest()})
                    elif len(output) > 32000:
                        with memory.db: bridge.event(self.active, 'full-output-limit', 'output_limit', {'reason': 'Native output exceeds 32000 characters; terminal preview only'})
                if info['dispatch_state'] == 'unknown' or info['state'] in {'completed', 'failed', 'cancelled', 'awaiting_approval'}:
                    if info['dispatch_state'] == 'unknown':
                        with memory.db: memory.db.execute("UPDATE mm_missions SET state='paused' WHERE id=?", (self.active,))
                    self.gate = None
                    self.active = None
        finally:
            self.lock.release()

    def call(self, body):
        # Do not mistake a snapshot taken during our preceding inference for
        # current idle capacity. Wait for the independent observer; never relax
        # mining/utilization/VRAM thresholds or perform another model call.
        deadline = time.monotonic() + 3
        with self.sample_changed:
            while self.last_inference_ended is not None and (not self.sample or self.sample.get('observed_at', 0) < self.last_inference_ended):
                remaining = deadline - time.monotonic()
                if remaining <= 0: raise Busy('Fresh post-inference observation required')
                self.sample_changed.wait(remaining)
        # Prod 17.11 (mission 88b5bd9b): the first observation after an inference can still show
        # the GPU busy (model being unloaded); refusing at once failed the whole mission. Wait,
        # bounded, for an observation that passes the SAME thresholds; never relax them.
        until = time.monotonic() + self.busy_wait
        while True:
            if self.gate is None: raise PermissionError('No approved active mission (no gate)')
            state = self.availability_for_call()
            if state['dispatch_allowed']: break
            remaining = until - time.monotonic()
            if remaining <= 0:
                raise PermissionError('No approved active mission (worker %s, fresh %s, waited %ss%s)' % (state.get('state'), state.get('fresh'), self.busy_wait,
                                      ', busy: ' + self.busy_reason if self.busy_reason else ''))
            with self.sample_changed: self.sample_changed.wait(min(remaining, 1))
        try: return self.gate.call(body)
        finally: self.last_inference_ended = self.clock()

    def availability_for_call(self):
        with closing(Memory(self.path)) as memory:
            return self.availability(memory)


def extension(controller, flags):
    def handle(memory, principal, request, url, query):
        path, method = url.path, request.command
        if path == '/v1/workers/windows-hermes/status' and method == 'GET':
            principal.require('reader')
            if principal.name != OWNER: raise PermissionError('Worker owner denied')
            return 200, controller.availability(memory), 'application/json'
        if path == '/v1/workers/windows-hermes/epoch' and method == 'GET':
            principal.require('worker_reporter')
            return 200, {'epoch': controller.epoch, 'expires_at': controller.runtime.get('expiresAt'), 'owned_model_gate_port': 11436 if controller.enabled else None}, 'application/json'
        if path == '/v1/workers/windows-hermes/observe' and method == 'POST':
            principal.require('worker_reporter')
            size = int(request.headers.get('Content-Length', '0'))
            if request.headers.get('Transfer-Encoding') or not 0 < size <= 2048: raise ValueError('Observation limit')
            return 200, controller.observe(memory, principal, json.loads(request.rfile.read(size))), 'application/json'
        if principal.actor == 'operational-supervisor':
            raise PermissionError('Supervisor observes only')
        if principal.actor == 'hermes-memory':
            if controller.active is None: raise PermissionError('No host-bound active memory context')
            observed = ObservedTools(memory, controller.p, principal, controller.active,searcher=controller.searcher,sources=controller.sources)
            if path in {'/v1/search', '/v1/history'} and method == 'GET':
                name = 'memory.search' if path.endswith('search') else 'memory.history'
                if set(query) != ({'q'} if name == 'memory.search' else {'memory_id'}): raise ValueError('Read fields')
                rows, receipt = observed.call(name, query)
                return 200, {'items': rows, 'receipt_id': receipt}, 'application/json'
            if path == '/v1/tools/call' and method == 'POST':
                size = int(request.headers.get('Content-Length', '0'))
                if request.headers.get('Transfer-Encoding') or not 0 < size <= 8000: raise ValueError('Tool limit')
                raw = request.rfile.read(size); data = json.loads(raw)
                if data.get('name') not in READ_TOOLS: raise PermissionError('Read-only MCP')
                if set(data) != {'name', 'arguments'}: raise ValueError('Read-only tool envelope')
                result, receipt = observed.call(data['name'], data['arguments'])
                return 200, {'result': result, 'receipt_id': receipt}, 'application/json'
            raise PermissionError('Memory runtime cannot operate missions')
        if path == '/v1/health' and method == 'GET':
            return 200, {'ready': True, 'synthetic_only': True, 'dispatch_enabled': controller.enabled}, 'application/json'
        if path.startswith('/v1/missions/') and path.endswith('/canonical') and method == 'GET':
            mid = path.split('/')[3]; Bridge(memory, principal).get(mid)
            if query: raise ValueError('No model-selected metadata')
            receipts = [r[0] for r in memory.db.execute('SELECT id FROM p6d_receipts WHERE mission_id=? ORDER BY created DESC,id LIMIT 20', (mid,))]
            if not receipts: return 403, {'error': 'No authenticated read receipts'}, 'application/json'
            return 200, {'projection': metadata(memory, controller.p, mid, receipts), 'validation': 'unreviewed'}, 'application/json'
        if not path.startswith('/v1/missions') or '/approvals' in path or path.endswith(('/result', '/canonical')):
            raise PermissionError('Operation not commissioned')
        if path == '/v1/missions' and method == 'POST':
            principal.require('mission_writer')
            if not flags.get('admissionEnabled', False): raise PermissionError('Admission disabled')
            if controller.enabled and controller.clock() >= controller.runtime['expiresAt']: raise PermissionError('Admission window closed')
            size = int(request.headers.get('Content-Length', '0'))
            if request.headers.get('Transfer-Encoding') or not 0 < size <= 8000: raise ValueError('Admission limit')
            raw = request.rfile.read(size); data = json.loads(raw)
            objective = data.get('definition', {}).get('objective')
            text = isinstance(objective, str) and objective.startswith(TEXT_PREFIX) and 1 <= len(objective[len(TEXT_PREFIX):]) <= 2000
            if objective != OBJECTIVE and not (flags.get('textEnabled', False) and text): raise PermissionError('Template or explicit bounded text only')
            if data != {'scope': 'private', 'definition': definition(objective)}: raise PermissionError('Server-selected grants and budget required')
            request.rfile = io.BytesIO(raw)
            with LOCK:
                prior = memory.db.execute('SELECT id FROM mm_missions WHERE owner=? AND scope=? AND event_key=?', (principal.name, 'private', request.headers.get('Idempotency-Key', ''))).fetchone()
                if not prior and memory.db.execute("SELECT 1 FROM mm_missions WHERE owner=? AND scope='private' AND state NOT IN ('completed','failed','cancelled') LIMIT 1", (principal.name,)).fetchone():
                    return 409, {'error': 'Une mission est déjà active ou incertaine.'}, 'application/json'
                return dispatch(memory, principal, request, url, query)
        return dispatch(memory, principal, request, url, query)
    return handle


def run(config):
    """Existing private service topology; no provider process can be started here."""
    from .interactive import ROOT
    path = Path(config)
    st = path.lstat()
    if path.is_symlink() or st.st_uid != os.getuid() or st.st_mode & 0o077 or st.st_size > 131072:
        raise PermissionError('Private owned config required')
    cfg = json.loads(path.read_text()); folder = path.parent.resolve(); flags = options(cfg)
    if cfg.get('onDemand') is not None:
        from .demand_service import run as demand_run
        return demand_run(config)
    if cfg.get('syntheticOnly') is not True or cfg.get('dispatchEnabled') is not False or cfg.get('missionLimits') != {'calls': 6, 'tokens': 98304, 'seconds': 240, 'attempts': 1, 'remoteCostChf': 0}:
        raise PermissionError('Existing synthetic profile and quotas required')
    if any(type(cfg.get(k)) is not int or not 1024 <= cfg[k] <= 65535 for k in ('frontPort', 'bridgePort')) or cfg['frontPort'] == cfg['bridgePort'] or cfg.get('origin') != 'http://127.0.0.1:' + str(cfg['frontPort']):
        raise PermissionError('Existing loopback topology required')
    dbpath = folder / 'memory.sqlite'
    if dbpath.is_symlink() or dbpath.stat().st_uid != os.getuid() or dbpath.stat().st_mode & 0o077 or folder.stat().st_mode & 0o077:
        raise PermissionError('Private synthetic SQLite only')
    lockfd = os.open(folder / 'worker.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    fcntl.flock(lockfd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    with closing(Memory(dbpath)) as memory:
        if memory.db.execute("SELECT 1 FROM mm_memories WHERE owner!=? OR scope!='private' LIMIT 1", (OWNER,)).fetchone():
            raise PermissionError('Synthetic owner only')
        for row in memory.db.execute('SELECT source FROM mm_events'):
            if not json.loads(row[0]).get('ref', '').startswith(('synthetic://doselab/', 'mission://')):
                raise PermissionError('Synthetic provenance only')
    controller = Controller(dbpath, cfg)
    clients = {hashlib.sha256(cfg['bridgeToken'].encode()).hexdigest(): {'name': OWNER, 'scopes': ['private'], 'roles': ['reader', 'mission_writer'], 'actor_id': 'interactive-panel'}}
    if controller.enabled:
        for key, roles, actor in [('memoryToken', ['reader'], 'hermes-memory'), ('supervisorToken', ['worker_reporter'], 'operational-supervisor')]:
            clients[hashlib.sha256(controller.runtime[key].encode()).hexdigest()] = {'name': OWNER, 'scopes': ['private'], 'roles': roles, 'actor_id': actor}
    servers = [server(dbpath, clients, cfg['bridgePort'], extension=extension(controller, flags))]
    if controller.enabled: servers.append(model_server(controller, controller.runtime['modelToken'], 11436))
    # Model server advertises only the pinned local configuration.
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set()); signal.signal(signal.SIGINT, lambda *_: stop.set())
    child = None
    try:
        for srv in servers: threading.Thread(target=srv.serve_forever, daemon=True).start()
        child = subprocess.Popen(['node', str(ROOT / 'ops/pilot-embedded.mjs'), str(path.resolve())], cwd=ROOT,
            env={'PATH': os.environ['PATH'], 'LANG': 'C.UTF-8', 'HOME': str(folder / 'empty-home')})
        while not stop.wait(.25):
            if child.poll() is not None: raise RuntimeError('Panel exited; no automatic restart')
            try: controller.step()
            except Exception:
                controller.gate = None
                if controller.active:
                    with closing(Memory(dbpath)) as memory:
                        with memory.db:
                            memory.db.execute("UPDATE p2_outbox SET state='unknown' WHERE mission_id=?", (controller.active,))
                            memory.db.execute("UPDATE mm_missions SET state='paused' WHERE id=?", (controller.active,))
                            Bridge(memory, controller.p).event(controller.active, 'controller-error', 'reconciliation_required', {'automatic_replay': False})
                    controller.active = None
    finally:
        controller.gate = None
        if controller.active:
            with closing(Memory(dbpath)) as memory:
                bridge = Bridge(memory, controller.p); info = bridge.get(controller.active)
                bridge.cancel(controller.active)
                if info['upstream_id']:
                    try: controller.client.stop(info['upstream_id'])
                    except Exception: pass  # Native Job Object deadline remains independent.
        if child and child.poll() is None:
            child.terminate()
            try: child.wait(timeout=5)
            except subprocess.TimeoutExpired: child.kill(); child.wait()
        for srv in servers: srv.shutdown(); srv.server_close()
        os.close(lockfd)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--config', required=True)
    run(parser.parse_args().config)

