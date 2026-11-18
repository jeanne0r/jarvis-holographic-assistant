"""Approved Windows-native synthetic pilot, retaining all canonical services on Proxmox.

Invoked inside the existing owned Ollama pilot lifecycle. No deployment,
production database, remote provider or shell command from a model is accepted.
"""
import json
import os
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
from ..phase3 import lab
from ..phase3.mcp import READ, SOURCES
from ..phase3.model_gate import Gate, server as model_server


from .windows import tunnel as private_tunnel
from .allowance import consume
import base64

IDENTITY = Path(os.environ['JARVIS_HERMES_IDENTITY']) if os.environ.get('JARVIS_HERMES_IDENTITY') else lab.ROOT / 'data/phase4/controller-identity'

def ssh_script(script, timeout=20):
    command = ['ssh', '-i', str(IDENTITY/'id_ed25519'), '-o', 'UserKnownHostsFile='+str(IDENTITY/'known_hosts'),
               '-o','IdentitiesOnly=yes','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','hermeslab@192.0.2.96',
               'powershell.exe -NoProfile -NonInteractive -EncodedCommand '+base64.b64encode(
                   ("$ErrorActionPreference='Stop';"+script).encode('utf-16le')).decode()]
    return subprocess.run(command,capture_output=True,timeout=timeout)

def validate_advertised_tools(body, *, skill_mode=False):
    # Use the same host-owned capability set as the controlled MCP. Maintaining
    # another hand-copied list previously rejected the new knowledge reader.
    names=READ | SOURCES | ({'jarvis_skill_propose'} if skill_mode else set())
    allowed={'mcp__jarvis__'+name for name in names}
    if any(tool.get('function',{}).get('name') not in allowed for tool in body.get('tools',[])):
        raise PermissionError('Unexpected runtime tool')


class Runtime:
    def __init__(self):self.process=None;self.trial_id=None;self.reports=[]
    def start(self,skill=False):
        if self.process is not None:raise RuntimeError('Stop owned runtime first')
        self.trial_id=uuid.uuid4().hex
        command=['ssh','-i',str(IDENTITY/'id_ed25519'),'-o','UserKnownHostsFile='+str(IDENTITY/'known_hosts'),
            '-o','IdentitiesOnly=yes','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','hermeslab@192.0.2.96',
            'C:\\JarvisHermesLab\\runtime\\Scripts\\python.exe -I C:\\JarvisHermesLab\\app\\ops\\phase4-run-hermes-windows.py --approved --trial-id '+self.trial_id+(' --skill-candidate' if skill else '')]
        self.process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    def stop(self):
        if self.process is None:return
        result=ssh_script("[IO.File]::WriteAllText('C:\\JarvisHermesLab\\runs\\"+self.trial_id+"\\stop.requested','operator stop')")
        if result.returncode:raise RuntimeError('Owned runtime stop request failed')
        try:out,err=self.process.communicate(timeout=15)
        except subprocess.TimeoutExpired:raise RuntimeError('Owned supervisor did not stop; wait for its 300s TTL')
        # Child logs can be present; retain them privately, never include credentials in public evidence.
        folder=lab.ROOT/'data/phase4';(folder/('runtime-'+self.trial_id+'.log')).write_bytes(out+b'\n'+err)
        r=ssh_script("Get-Content -LiteralPath 'C:\\JarvisHermesLab\\runs\\"+self.trial_id+"\\supervisor-result.json' -Raw")
        if r.returncode:raise RuntimeError('Owned supervisor report missing')
        report=json.loads(r.stdout.decode('utf-8-sig'));report['trial_id']=self.trial_id;self.reports.append(report)
        if not report.get('owned_process_stopped_after_close'):raise RuntimeError('Owned process did not stop')
        self.process=None

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


def run(config, upstream, telemetry, *, skill_only=False, folder=None, memory_extension=dispatch,
        local_token_limit=98304, shared_budget=False, skill_evaluator=None,
        mission_numbers=None, required_search_tool='jarvis_memory_search'):
    numbers = tuple(mission_numbers) if mission_numbers is not None else ((2,3) if skill_only else (1,2,3))
    if not numbers or any(type(n) is not int or n not in (1,2,3) for n in numbers) or tuple(sorted(set(numbers))) != numbers:
        raise ValueError('Bounded ordered mission subset required')
    if required_search_tool not in {'jarvis_memory_search','jarvis_memory_knowledge'}:
        raise ValueError('Host-selected read tool required')
    legacy = lab.ROOT / 'data/phase3/windows-20261114'
    if type(local_token_limit) is not int or not 1 <= local_token_limit <= 98304 or type(shared_budget) is not bool:
        raise ValueError('Host-owned bounded local budget required')
    experimental = folder is not None
    folder = Path(folder).resolve() if experimental else legacy
    if experimental and not folder.is_relative_to((lab.ROOT/'data/phase5').resolve()):
        raise PermissionError('New phase5 laboratory required')
    credentials = legacy if experimental else folder
    window = folder/'window.json' if experimental else lab.ROOT/'data/phase4/window.json'
    if experimental:
        import stat,os
        info=window.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or info.st_uid!=os.getuid():
            raise PermissionError('Private owned phase5 approval required')
    runtime_owner = Runtime()
    if not json.loads((lab.ROOT/'data/phase4/admission.json').read_text()).get('passed'):
        raise PermissionError('Actual Windows prechecks required')
    clients = json.loads((credentials / 'clients.json').read_text())
    principal = Principal(lab.OWNER, frozenset({'private'}), frozenset({
        'reader', 'proposer', 'mission_writer', 'mission_worker', 'budget_admin', 'metered_caller'}), 'native-pilot-host')
    token = lambda name: (credentials / name).read_text().strip()
    attempt = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
    report = {'attempt_id': attempt, 'hermes_runtime_tested': False, 'paid_api_calls': 0, 'missions': [], 'model_requests': []}
    active = [None]
    allowance=json.loads(window.read_text())
    window_remaining=allowance['expires_at']-time.time()-30
    if window_remaining<60 or allowance.get('closed',False) is not False or allowance['missions']>=4:
        raise PermissionError('Approved pilot window closed, exhausted or insufficient')
    deadline=time.monotonic()+min(1500,window_remaining)
    total_calls=[0]

    class Relay:
        cfg = config
        def call(self, body):
            if time.monotonic()>=deadline or total_calls[0]>=24:raise PermissionError('Pilot duration/call cap reached')
            consume(window,'calls')
            total_calls[0]+=1
            row = {'at': time.time(), 'bytes': len(json.dumps(body).encode()),
                   'fields': sorted(body), 'tools': [t.get('function', {}).get('name') for t in body.get('tools', [])]}
            report['model_requests'].append(row)
            try:
                validate_advertised_tools(body,skill_mode=bool(report['missions'] and report['missions'][-1]['skill_mode']))
            except PermissionError:
                row['error'] = 'Unexpected runtime tool; no model dispatch'
                raise
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

    memory_http = memory_server(folder / 'memory.sqlite', clients, 8792, extension=memory_extension)
    model_http = model_server(Relay(), token('model.token'), 11436)
    servers = [memory_http, model_http]
    for srv in servers:
        threading.Thread(target=srv.serve_forever, daemon=True).start()
    tunnel = None
    native = PrivateHTTP('http://127.0.0.1:8643', token('hermes.token'))
    simulator = PrivateHTTP('http://127.0.0.1:8792', token('bridge.token'))
    try:
        tunnel_args=private_tunnel(key=IDENTITY/'id_ed25519',known_hosts=IDENTITY/'known_hosts')
        tunnel = subprocess.Popen(tunnel_args,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        time.sleep(1)
        if tunnel.poll() is not None:
            raise RuntimeError('Laboratory tunnel declined')
        manifest = json.loads((folder / 'manifest.json').read_text())
        shared_bid = None
        for number in numbers:
            skill = number != 1
            retrieval = number == 3
            if time.monotonic()>=deadline:raise TimeoutError("Pilot window expired")
            runtime_owner.start(skill and not retrieval)
            for _ in range(75):
                if runtime_owner.process.poll() is not None:raise RuntimeError('Owned Hermes supervisor exited; refuse ambiguous listener')
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
            if experimental and retrieval:
                objective += (' Consulte aussi jarvis_memory_experiences pour retrouver le résultat synthétique '
                              'd’une mission précédente (source mission://), en distinguant récit de mission et fait vérifié.')
            definition = {'objective': objective, 'trigger': 'approved-synthetic-pilot',
                'priority': 1, 'memory_context': [], 'plan': ['Consult controlled memory tools', 'Report with provenance'],
                'allowed_tools': ['memory.search', 'report'],
                'budget': {'tokens': 0, 'cost_micros': 0, 'seconds': 180, 'attempts': 1,
                           'local_tokens': min(local_token_limit, config.context_tokens * 6)}}
            if skill and not retrieval:
                definition['allowed_tools'].append('memory.propose')
                definition['objective'] += (' Utilise jarvis_skill_propose avec spec contenant exactement name (doselab_freshness), '
                    'version (1), description, allowed_tools ([memory.search, report]), checks ([flow, freshness]); '
                    'sources contient uniquement memory_id, identifiant stable de l’expérience confirmée retrouvée. '
                    'N’utilise ni id (révision), ni source.ref dans sources. Aucune publication.')
            consume(window,'missions')
            remaining=int(deadline-time.monotonic())
            if remaining<60:raise PermissionError('Insufficient remaining pilot window')
            definition['budget']['seconds']=min(180,remaining)
            started = time.monotonic()
            admitted = simulator('POST', '/v1/missions', {'definition': definition},
                                 headers={'Idempotency-Key': 'native-hermes-' + attempt + '-' + str(number)})
            row = {'mission_id': admitted['mission_id'], 'admission_seconds': time.monotonic() - started,
                   'number': number, 'skill_mode': skill}
            report['missions'].append(row)
            memory = Memory(folder / 'memory.sqlite')
            try:
                bid = shared_bid if shared_budget and shared_bid else budgets.create(memory, principal, token_limit=definition['budget']['local_tokens'])
                if shared_budget: shared_bid=bid
                active[0] = Gate(memory, principal, bid, row['mission_id'], config, upstream, telemetry, seconds=definition['budget']['seconds'])
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
                row['usage'] = [dict(r) for r in memory.db.execute('SELECT * FROM p2_usage WHERE budget_id=? AND mission_id=?', (bid,row['mission_id']))]
                row['skills'] = [dict(r) for r in memory.db.execute('SELECT name,version,state,sources FROM p2_skills')]
                row['active_skills'] = memory.db.execute('SELECT count(*) FROM p2_skill_active').fetchone()[0]
                if skill:
                    from ..phase2 import skill_registry
                    row['candidate_evaluations'] = []
                    for candidate in memory.db.execute('SELECT spec FROM p2_skills'):
                        spec = json.loads(candidate['spec'])
                        evaluation = skill_registry.assess(memory, principal, spec['name'], spec['version'])
                        if skill_evaluator:
                            evaluation['extended']=skill_evaluator(spec)
                            evaluation['passed']=evaluation['passed'] and evaluation['extended']['passed']
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
                        'native_search_called': any(t.endswith(required_search_tool) for t in successful_tools),
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
                runtime_owner.stop()
            if row['bridge_status']['state'] != 'completed':
                break
        report['passed'] = len(report['missions']) == len(numbers) and all(r['passed'] for r in report['missions'])
        return report
    except Exception as exc:
        report.update(passed=False, error_class=type(exc).__name__, error=str(exc))
        return report
    finally:
        try:
            runtime_owner.stop()
        except Exception as exc:
            report['passed']=False
            report['runtime_cleanup_error']=type(exc).__name__
        finally:
            report['runtime_supervisors']=runtime_owner.reports
            try:
                if tunnel:
                    tunnel.terminate()
                    tunnel.wait(timeout=10)
            finally:
                for srv in servers:
                    srv.shutdown()
                    srv.server_close()
