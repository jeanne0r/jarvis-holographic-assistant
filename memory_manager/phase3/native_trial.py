"""Two synthetic native Hermes runs on the approved, isolated lab VM.

Invoked inside the existing owned Ollama pilot lifecycle. No deployment,
production database, remote provider or shell command from a model is accepted.
"""
import json
import hashlib
from pathlib import Path
import shlex
import subprocess
import threading
import time
import urllib.request
import uuid

from ..api import server as memory_server
from ..store import Memory, Principal
from ..phase2 import budgets
from ..phase2.bridge import Bridge
from ..phase2.hermes import HermesRuns
from ..phase2.http_bridge import dispatch
from ..phase2.local_model import PrivateHTTP
from ..phase2.memory_tools import MemoryTools
from . import lab
from .model_gate import Gate, server as model_server


def ssh(arguments, **kwargs):
    provision = lab.ROOT / 'data/phase3/provision'
    command = ['ssh', '-i', str(provision / 'lab-admin'), '-o', 'UserKnownHostsFile=' + str(provision / 'known_hosts'),
               '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=4',
               'user@192.0.2.241', shlex.join(arguments)]
    return subprocess.run(command, capture_output=True, text=True, timeout=kwargs.pop('timeout', 20), **kwargs)


def runtime(skill=False):
    expected = json.loads((lab.ROOT / 'data/phase3/provision/network-report.json').read_text())
    actual = ssh(['sudo', '-n', 'nft', '-j', 'list', 'table', 'inet', 'jarvis_phase3'])
    boot = ssh(['cat', '/proc/sys/kernel/random/boot_id'])
    if (not expected['passed'] or actual.returncode or boot.returncode
            or hashlib.sha256(actual.stdout.encode()).hexdigest() != expected['nft_sha256']
            or boot.stdout.strip() != expected['boot_id']):
        raise PermissionError('Fresh matching network isolation required before runtime startup')
    trial_id = uuid.uuid4().hex
    home = lab.trial_home(lab.ROOT / 'data/phase3/prepared', trial_id)
    # mkdir is exclusive. An old native HOME is never reused or auto-resumed.
    prepare = ssh(['sudo', '-n', '/usr/bin/python3', '-c',
                   'import os; from pathlib import Path; p=Path(' + repr(str(home)) + '); '
                   'p.mkdir(mode=0o700); os.chown(p,1001,1001)'])
    if prepare.returncode:
        raise RuntimeError('Fresh native trial home could not be created')
    command = ['sudo', '-n', 'systemd-run', '--unit=jarvis-phase3-hermes', '--collect',
        '--property=User=hermeslab', '--property=Group=hermeslab', '--property=MemoryMax=2G',
        '--property=CPUQuota=100%', '--property=TasksMax=128', '--property=RuntimeMaxSec=300',
        '--property=NoNewPrivileges=yes', '--property=ProtectSystem=strict',
        '--property=ProtectHome=read-only', '--property=PrivateTmp=yes',
        '--property=ReadWritePaths=' + str(home),
        '/usr/bin/python3', str(lab.ROOT / 'ops/phase3-hermes-run.py'), '--approved', '--trial-id', trial_id]
    if skill:
        command.append('--skill-candidate')
    result = ssh(command)
    if result.returncode:
        raise RuntimeError('Isolated Hermes unit did not start: ' + result.stderr[:800])


def events_from_sse(text):
    """Hermes emits JSON event fields; standard named SSE events also work."""
    events = []
    for frame in text.replace('\r\n', '\n').split('\n\n'):
        name = next((line[7:] for line in frame.splitlines() if line.startswith('event: ')), None)
        data = '\n'.join(line[6:] for line in frame.splitlines() if line.startswith('data: '))
        if data:
            event = json.loads(data)
            if name:
                event.setdefault('event', name)
            events.append(event)
    return events


def run(config, upstream, telemetry, *, skill_only=False):
    folder = lab.ROOT / 'data/phase3/prepared'
    network = json.loads((lab.ROOT / 'data/phase3/provision/network-report.json').read_text())
    if not network['passed']:
        raise PermissionError('Verified lab network isolation required')
    clients = json.loads((folder / 'clients.json').read_text())
    principal = Principal(lab.OWNER, frozenset({'private'}), frozenset({
        'reader', 'proposer', 'mission_writer', 'mission_worker', 'budget_admin', 'metered_caller'}), 'native-pilot-host')
    token = lambda name: (folder / name).read_text().strip()
    attempt = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
    report = {'attempt_id': attempt, 'hermes_runtime_tested': False, 'paid_api_calls': 0, 'missions': [], 'model_requests': []}
    active = [None]

    class Relay:
        cfg = config
        def call(self, body):
            row = {'at': time.time(), 'bytes': len(json.dumps(body).encode()),
                   'fields': sorted(body), 'tools': [t.get('function', {}).get('name') for t in body.get('tools', [])]}
            report['model_requests'].append(row)
            allowed = ['jarvis_memory_search', 'jarvis_memory_history', 'jarvis_memory_project',
                       'jarvis_memory_experiences', 'jarvis_memory_contradictions', 'jarvis_skill_get']
            if report['missions'] and report['missions'][-1]['skill_mode']:
                allowed.extend(['jarvis_skill_propose', 'jarvis_skill_get'])
            if any(name not in {'mcp__jarvis__' + t for t in allowed} for name in row['tools']):
                row['error'] = 'Unexpected runtime tool; no model dispatch'
                raise PermissionError('Unexpected runtime tool')
            if active[0] is None:
                raise PermissionError('No host-bound mission')
            try:
                result = active[0].call(body)
                row['usage'] = result['usage']
                row['finish_reason'] = result['choices'][0]['finish_reason']
                return result
            except Exception as exc:
                row['error'] = type(exc).__name__ + ': ' + str(exc)
                raise

    memory_http = memory_server(folder / 'memory.sqlite', clients, 8792, extension=dispatch)
    model_http = model_server(Relay(), token('model.token'), 11436)
    servers = [memory_http, model_http]
    for srv in servers:
        threading.Thread(target=srv.serve_forever, daemon=True).start()
    tunnel = None
    native = PrivateHTTP('http://127.0.0.1:8643', token('hermes.token'))
    simulator = PrivateHTTP('http://127.0.0.1:8792', token('bridge.token'))
    try:
        provision = lab.ROOT / 'data/phase3/provision'
        tunnel = subprocess.Popen(['ssh', '-i', str(provision / 'lab-admin'),
            '-o', 'UserKnownHostsFile=' + str(provision / 'known_hosts'), '-o', 'BatchMode=yes',
            '-o', 'StrictHostKeyChecking=yes', '-o', 'ExitOnForwardFailure=yes', '-N',
            '-R', '127.0.0.1:11436:127.0.0.1:11436', '-R', '127.0.0.1:8792:127.0.0.1:8792',
            '-L', '127.0.0.1:8643:127.0.0.1:8643', 'user@192.0.2.241'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1)
        if tunnel.poll() is not None:
            raise RuntimeError('Laboratory tunnel declined')
        manifest = json.loads((folder / 'manifest.json').read_text())
        for number, skill in ([(2, True), (3, True)] if skill_only else [(1, False), (2, True)]):
            retrieval = number == 3
            runtime(skill and not retrieval)
            for _ in range(75):
                try:
                    native('GET', '/v1/models', timeout=2)
                    report['hermes_runtime_tested'] = True
                    break
                except Exception:
                    time.sleep(1)
            else:
                raise RuntimeError('Native Hermes API unavailable')
            objective = ('Retrouve via jarvis_skill_get la compétence doselab_freshness version 1. '
                         'Rapporte son état candidate, son fingerprint et ses sources ; aucune proposition ou publication.'
                         if retrieval else manifest['mission_' + str(number)])
            definition = {'objective': objective, 'trigger': 'approved-synthetic-pilot',
                'priority': 1, 'memory_context': [], 'plan': ['Consult controlled memory tools', 'Report with provenance'],
                'allowed_tools': ['memory.search', 'report'],
                'budget': {'tokens': 0, 'cost_micros': 0, 'seconds': 180, 'attempts': 1,
                           'local_tokens': min(98304, config.context_tokens * 6)}}
            if skill and not retrieval:
                definition['allowed_tools'].append('memory.propose')
                definition['objective'] += (' Utilise jarvis_skill_propose avec spec contenant exactement name (doselab_freshness), '
                    'version (1), description, allowed_tools ([memory.search, report]), checks ([flow, freshness]); '
                    'sources contient uniquement memory_id, identifiant stable de l’expérience confirmée retrouvée. '
                    'N’utilise ni id (révision), ni source.ref dans sources. Aucune publication.')
            started = time.monotonic()
            admitted = simulator('POST', '/v1/missions', {'definition': definition},
                                 headers={'Idempotency-Key': 'native-hermes-' + attempt + '-' + str(number)})
            row = {'mission_id': admitted['mission_id'], 'admission_seconds': time.monotonic() - started,
                   'number': number, 'skill_mode': skill}
            report['missions'].append(row)
            memory = Memory(folder / 'memory.sqlite')
            try:
                bid = budgets.create(memory, principal, token_limit=definition['budget']['local_tokens'])
                active[0] = Gate(memory, principal, bid, row['mission_id'], config, upstream, telemetry)
                client = HermesRuns(native, config.model, allow_live=True)
                bridge = Bridge(memory, principal)
                while time.monotonic() - started < 185:
                    status = bridge.work(client, row['mission_id'])
                    if status['state'] in {'completed', 'failed', 'cancelled', 'paused', 'awaiting_approval'}:
                        break
                    time.sleep(1)
                row['bridge_status'] = bridge.get(row['mission_id'])
                row['events'] = bridge.events(row['mission_id'])
                rid = row['bridge_status']['upstream_id']
                row['native_status'] = client.status(rid) if rid else {}
                if rid and row['bridge_status']['state'] == 'completed':
                    request = urllib.request.Request('http://127.0.0.1:8643/v1/runs/' + rid + '/events',
                        headers={'Authorization': 'Bearer ' + token('hermes.token')})
                    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                    with opener.open(request, timeout=5) as response:
                        row['native_events_sse'] = response.read(256000).decode()
                    result = str(row['native_status'].get('output', ''))
                    row['experience_ids'] = MemoryTools(memory, principal, row['mission_id']).call('mission.result',
                        {'result': result, 'native_run_id': rid, 'model': config.model, 'digest': config.digest})
                row['usage'] = [dict(r) for r in memory.db.execute('SELECT * FROM p2_usage WHERE budget_id=?', (bid,))]
                row['skills'] = [dict(r) for r in memory.db.execute('SELECT name,version,state,sources FROM p2_skills')]
                row['active_skills'] = memory.db.execute('SELECT count(*) FROM p2_skill_active').fetchone()[0]
                if skill:
                    from ..phase2 import skill_registry
                    row['candidate_evaluations'] = []
                    for candidate in memory.db.execute('SELECT spec FROM p2_skills'):
                        spec = json.loads(candidate['spec'])
                        evaluation = skill_registry.assess(memory, principal, spec['name'], spec['version'])
                        try:
                            skill_registry.publish(memory, principal, spec['name'], spec['version'])
                        except PermissionError:
                            evaluation['agent_publication_denied'] = True
                        else:
                            evaluation['agent_publication_denied'] = False
                        row['candidate_evaluations'].append(evaluation)
                trace = row.get('native_events_sse', '')
                tool_events = [e for e in events_from_sse(trace) if e.get('event') == 'tool.completed']
                successful_tools = [str(e.get('tool', '')) for e in tool_events if not e.get('error')]
                row['successful_native_tools'] = successful_tools
                result = str(row.get('native_status', {}).get('output', ''))
                row['checks'] = {'native_completed': row['bridge_status']['state'] == 'completed',
                    'experience_recorded': bool(row.get('experience_ids')),
                    'no_remote_cost': all(u.get('actual_remote_micros', 0) == 0 for u in row['usage'])}
                if not skill:
                    row['checks'].update({
                        'native_search_called': any(t.endswith('jarvis_memory_search') for t in successful_tools),
                        'native_history_called': any(t.endswith('jarvis_memory_history') for t in successful_tools),
                        'current_source_cited': 'synthetic://doselab/correction' in result,
                        'old_source_cited': 'synthetic://doselab/old' in result})
                else:
                    expected_source = manifest['memory']['experience_memory_id']
                    row['checks'].update({
                        'native_skill_proposal_called': any(t.endswith('jarvis_skill_propose') for t in successful_tools),
                        'candidate_only': bool(row['skills']) and all(s['state'] == 'candidate' for s in row['skills']),
                        'confirmed_experience_linked': any(expected_source in s['sources'] for s in row['skills']),
                        'nothing_published': row['active_skills'] == 0,
                        'regression_evaluation_passed': bool(row['candidate_evaluations']) and all(e['passed'] for e in row['candidate_evaluations']),
                        'agent_publication_denied': bool(row['candidate_evaluations']) and all(e['agent_publication_denied'] for e in row['candidate_evaluations'])})
                    if retrieval:
                        row['checks'].pop('native_skill_proposal_called')
                        row['checks']['native_skill_lookup_after_restart'] = any(t.endswith('jarvis_skill_get') for t in successful_tools)
                        fingerprints = [r[0] for r in memory.db.execute('SELECT fingerprint FROM p2_skills')]
                        row['checks']['fingerprint_returned'] = bool(fingerprints) and all(f in result for f in fingerprints)
                row['passed'] = all(row['checks'].values())
            finally:
                memory.close()
                active[0] = None
                ssh(['sudo', '-n', 'systemctl', 'stop', 'jarvis-phase3-hermes.service'], timeout=30)
            if row['bridge_status']['state'] != 'completed':
                break
        report['passed'] = len(report['missions']) == 2 and all(r['passed'] for r in report['missions'])
        return report
    except Exception as exc:
        report.update(passed=False, error_class=type(exc).__name__, error=str(exc))
        return report
    finally:
        ssh(['sudo', '-n', 'systemctl', 'stop', 'jarvis-phase3-hermes.service'], timeout=30)
        if tunnel:
            tunnel.terminate()
            tunnel.wait(timeout=10)
        for srv in servers:
            srv.shutdown()
            srv.server_close()
