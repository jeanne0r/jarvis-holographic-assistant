"""Synthetic fixtures and inert Hermes configuration; no provider/runtime import."""
import hashlib
import json
import os
from pathlib import Path
import secrets

from ..store import Memory, Principal
from ..phase2 import database
from ..phase2.hermes import HERMES_COMMIT

ROOT = Path(__file__).resolve().parents[2]
OWNER = 'phase3-synthetic'
HOST = Principal(OWNER, frozenset({'private'}),
                 frozenset({'reader', 'proposer', 'ingester', 'validator'}), 'fixture-host')
MODEL = 'qwen3.5:4b'


def trial_home(folder, trial_id):
    import re
    if not isinstance(trial_id, str) or not re.fullmatch('[0-9a-f]{32}', trial_id):
        raise ValueError('Fresh host-generated trial identifier required')
    return folder / ('hermes-home-trial-' + trial_id)


def seed(memory):
    old = {'type': 'knowledge', 'subject': 'DoseLab X4', 'predicate': 'load_cells',
           'content': {'capacities_kg': [1, 2, 5, 10]}, 'status': 'user_confirmed'}
    mid = memory.ingest(HOST, 'cells-old', {'kind': 'user', 'ref': 'synthetic://doselab/old',
                                         'observed_at': 1700000000}, [old])[0]
    original = memory.history(HOST, mid)[0]['id']
    memory.ingest(HOST, 'cells-correction', {'kind': 'user', 'ref': 'synthetic://doselab/correction',
                                          'observed_at': 1700000100},
                  [{**old, 'content': {'capacities_kg': [1, 1, 1, 1]},
                    'correction_of': mid, 'expected_revision': original}])
    episode = memory.ingest(HOST, 'experience', {'kind': 'user',
        'ref': 'synthetic://doselab/experience', 'observed_at': 1700000200}, [{
        'type': 'episode', 'subject': 'DoseLab X4', 'predicate': 'diagnostic_result',
        'content': {'result': 'Une procédure a échoué faute de contrôle de fraîcheur des mesures.',
                    'lesson': 'Vérifier la fraîcheur avant de produire un diagnostic ; demander une revue humaine sinon.'},
        'status': 'user_confirmed'}])[0]
    return {'configuration_memory_id': mid, 'experience_memory_id': episode,
            'current_revision': memory.history(HOST, mid)[-1]['id']}


def profile(lab, *, skill_candidate=False):
    """JSON is also YAML. This candidate must be checked by the real runtime."""
    result = {
        'model': {'default': MODEL, 'provider': 'custom',
                  'context_length': 64000,
                  'base_url': 'http://127.0.0.1:11436/v1', 'api_key': '${LAB_MODEL_TOKEN}'},
        'agent': {'max_turns': 6, 'api_max_retries': 0, 'auto_recovery_cycles': 0},
        'max_concurrent_sessions': 1,
        'memory': {'provider': 'none', 'memory_enabled': False,
                   'user_profile_enabled': False, 'nudge_interval': 0},
        'compression': {'enabled': False},
        'tools': {'tool_search': {'enabled': 'off'}},
        'auxiliary': {'background_review': {'enabled': False},
                      'title_generation': {'enabled': False, 'model_upgrade_enabled': False}},
        'platform_toolsets': {'cli': ['mcp-jarvis'], 'api_server': ['mcp-jarvis']},
        'platforms': {'api_server': {'enabled': True, 'extra': {'host': '127.0.0.1', 'port': 8643}}},
        'mcp_servers': {'jarvis': {'command': '/usr/bin/python3',
            'args': ['-m', 'memory_manager.phase3.mcp', '--token-file',
                     str(lab / 'memory.token'), '--port', '8792'],
            'env': {'PYTHONPATH': str(ROOT)}, 'sampling': {'enabled': False}}},
    }
    if skill_candidate:
        result['mcp_servers']['jarvis']['args'].append('--skill-candidate')
    return result


def prepare(destination):
    lab = Path(destination).resolve()
    allowed = (ROOT / 'data' / 'phase3').resolve()
    if not lab.is_relative_to(allowed) or lab == allowed:
        raise ValueError('Choose a new laboratory below worktree/data/phase3/')
    lab.mkdir(parents=True, mode=0o700, exist_ok=False)
    os.chmod(lab, 0o700)
    memory = Memory(lab / 'memory.sqlite', create=True)
    try:
        database.migrate(memory)
        ids = seed(memory)
    finally:
        memory.close()
    token = secrets.token_hex(32)
    bridge_token = secrets.token_hex(32)
    for name, value in [('memory.token', token), ('bridge.token', bridge_token), ('hermes.token', secrets.token_hex(32)),
                        ('model.token', secrets.token_hex(32))]:
        path = lab / name
        with open(path, 'x', opener=lambda p, flags: os.open(p, flags, 0o600)) as output:
            output.write(value + '\n')
    clients = {hashlib.sha256(token.encode()).hexdigest(): {
        'name': OWNER, 'scopes': ['private'], 'roles': ['reader', 'proposer'],
        'actor_id': 'hermes-phase3'}}
    clients[hashlib.sha256(bridge_token.encode()).hexdigest()] = {
        'name': OWNER, 'scopes': ['private'], 'roles': ['reader', 'mission_writer'],
        'actor_id': 'jarvis-simulator'}
    (lab / 'clients.json').write_text(json.dumps(clients, indent=2) + '\n')
    os.chmod(lab / 'clients.json', 0o600)
    (lab / 'config.yaml').write_text(json.dumps(profile(lab), indent=2) + '\n')
    manifest = {'synthetic_only': True, 'runtime_started': False, 'hermes_commit': HERMES_COMMIT,
                'memory': ids, 'model_proxy_port': 11436, 'model_proxy_required': True,
                'mission_1': 'Analyse DoseLab X4 : retrouve les cellules actuelles, les anciennes valeurs remplacées et cite les sources de chaque révision. Consulte réellement les outils mémoire.',
                'mission_2': 'Consulte l’expérience synthétique DoseLab X4 et propose une compétence candidate de diagnostic avec contrôle de fraîcheur et revue humaine. Ne la publie pas.'}
    (lab / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    return manifest
