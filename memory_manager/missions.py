"""Persistent mission registry, not an autonomous command executor."""
import json
import time
from .store import encode, uid

TRANSITIONS = {
    'queued': {'planning', 'paused', 'cancelled'},
    'planning': {'running', 'awaiting_approval', 'failed', 'paused', 'cancelled'},
    'running': {'testing', 'awaiting_approval', 'failed', 'paused', 'cancelled'},
    'testing': {'completed', 'running', 'awaiting_approval', 'failed', 'paused', 'cancelled'},
    'awaiting_approval': {'queued', 'cancelled', 'paused'},
    'paused': {'queued', 'cancelled'},
    'completed': set(), 'failed': set(), 'cancelled': set(),
}


def create(memory, principal, key, definition, scope='private'):
    principal.require('mission_writer')
    memory.access(principal, principal.name, scope)
    required = {'objective', 'trigger', 'priority', 'memory_context', 'plan', 'allowed_tools', 'budget'}
    if not isinstance(definition, dict) or not required <= definition.keys() or not 1 <= len(key) <= 200 or len(encode(definition)) > 16000:
        raise ValueError('Complete bounded mission required')
    # Deliberately non-executing capabilities. A future broker owns broader grants.
    if set(definition['allowed_tools']) - {'memory.search', 'memory.propose', 'sources.read', 'report'}:
        raise PermissionError('Experimental mission tool denied')
    budget = definition['budget']
    if not isinstance(budget, dict) or budget.get('tokens') != 0 or budget.get('cost_micros') != 0 or not 0 < budget.get('seconds', 0) <= 300 or not 1 <= budget.get('attempts', 0) <= 3:
        raise ValueError('Prototype permits only bounded zero-cost missions')
    with memory.db:
        memory.db.execute('BEGIN IMMEDIATE')
        row = memory.db.execute('SELECT * FROM mm_missions WHERE owner=? AND scope=? AND event_key=?', (principal.name, scope, key)).fetchone()
        if row:
            if row['definition'] != encode(definition):
                raise ValueError('Mission key reused')
            return row['id']
        mid, now = uid(), time.time()
        memory.db.execute('INSERT INTO mm_missions VALUES(?,?,?,?,?,?,?,?)', (mid, principal.name, scope, key, 'queued', encode(definition), now, now))
        memory.db.execute('INSERT INTO mm_mission_events(mission_id,state,actor,evidence,created) VALUES(?,?,?,?,?)', (mid, 'queued', principal.name, '{}', now))
        return mid


def get(memory, principal, mid):
    principal.require('reader')
    row = memory.db.execute('SELECT * FROM mm_missions WHERE id=?', (mid,)).fetchone()
    if not row:
        raise KeyError('Unknown mission')
    memory.access(principal, row['owner'], row['scope'])
    result = dict(row)
    result['definition'] = json.loads(result['definition'])
    result['events'] = [dict(r) for r in memory.db.execute('SELECT * FROM mm_mission_events WHERE mission_id=? ORDER BY seq', (mid,))]
    return result


def transition(memory, principal, mid, expected_state, state, evidence=None):
    principal.require('mission_writer')
    with memory.db:
        memory.db.execute('BEGIN IMMEDIATE')
        mission = get(memory, principal, mid)
        if mission['owner'] != principal.name:
            raise PermissionError('Mission owner required')
        if mission['state'] != expected_state or state not in TRANSITIONS[expected_state]:
            raise ValueError('Stale or invalid transition')
        if state == 'queued' and any(e['state'] == 'awaiting_approval' for e in mission['events']):
            # Approval cannot be manufactured by a worker transition.
            raise PermissionError('Approval broker not implemented; keep awaiting approval')
        if state == 'completed' and not evidence:
            raise ValueError('Completion requires evidence')
        if len(encode(evidence or {})) > 8000:
            raise ValueError('Evidence too large')
        now = time.time()
        memory.db.execute('UPDATE mm_missions SET state=?,updated=? WHERE id=?', (state, now, mid))
        memory.db.execute('INSERT INTO mm_mission_events(mission_id,state,actor,evidence,created) VALUES(?,?,?,?,?)',
                          (mid, state, principal.name, encode(evidence or {}), now))
    return get(memory, principal, mid)
