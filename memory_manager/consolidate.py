"""Bounded deterministic simulation. Suggestions never rewrite accepted facts."""
import json
import time
from .store import encode, uid


def enqueue(memory, principal, kind, key, *, scope='private', max_seconds=2, max_attempts=3):
    principal.require('consolidator')
    memory.access(principal, principal.name, scope)
    if kind not in {'nightly', 'weekly'} or not 0 < max_seconds <= 30 or not 1 <= max_attempts <= 5:
        raise ValueError('Invalid consolidation limits')
    if not isinstance(key, str) or not 1 <= len(key) <= 200:
        raise ValueError('Invalid event key')
    items = [r for r in memory.current(principal) if r['scope'] == scope and r['owner'] == principal.name]
    if len(items) > 10000:
        raise ValueError('Partition the consolidation into bounded jobs')
    with memory.db:
        prior = memory.db.execute('SELECT * FROM mm_jobs WHERE owner=? AND scope=? AND kind=? AND event_key=?',
                                  (principal.name, scope, kind, key)).fetchone()
        if prior:
            if prior['max_seconds'] != max_seconds or prior['max_attempts'] != max_attempts:
                raise ValueError('Job key reused with different limits')
            return prior['id']
        job_id, now = uid(), time.time()
        memory.db.execute('INSERT INTO mm_jobs(id,owner,scope,kind,event_key,state,items,max_attempts,max_seconds,created,updated) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                          (job_id, principal.name, scope, kind, key, 'queued', encode(items), max_attempts, max_seconds, now, now))
        return job_id


def job(memory, principal, job_id):
    row = memory.db.execute('SELECT * FROM mm_jobs WHERE id=?', (job_id,)).fetchone()
    if not row:
        raise KeyError('Unknown consolidation')
    memory.access(principal, row['owner'], row['scope'])
    if row['owner'] != principal.name:
        raise PermissionError('Job owner required')
    return dict(row)


def tick(memory, principal, job_id, *, max_items=50, interrupt=None):
    principal.require('consolidator')
    if not 1 <= max_items <= 100:
        raise ValueError('Invalid batch size')
    initial = job(memory, principal, job_id)
    deadline = time.monotonic() + initial['max_seconds']
    processed = 0
    while processed < max_items and time.monotonic() < deadline:
        try:
            with memory.db:
                # Each item and its cursor commit together; no external side effect.
                memory.db.execute('BEGIN IMMEDIATE')
                state = job(memory, principal, job_id)
                if state['state'] in {'completed', 'cancelled', 'paused', 'failed'}:
                    return state
                items, results = json.loads(state['items']), json.loads(state['result'])
                cursor = state['cursor']
                if cursor >= len(items):
                    memory.db.execute("UPDATE mm_jobs SET state='completed',updated=? WHERE id=?", (time.time(), job_id))
                    return job(memory, principal, job_id)
                item = items[cursor]
                suggestions = []
                if item['contradictions']:
                    suggestions.append({'kind': 'contradiction', 'memory_id': item['memory_id'], 'peers': item['contradictions']})
                duplicates = [r['memory_id'] for r in items[:cursor] if r['type'] == item['type'] and r['subject'] == item['subject'] and r['content'] == item['content']]
                if duplicates:
                    suggestions.append({'kind': 'deduplicate_proposal', 'memory_id': item['memory_id'], 'peers': duplicates})
                if state['kind'] == 'weekly' and item['type'] in {'episode', 'lesson'}:
                    related = [r for r in items if r['subject'] == item['subject'] and r['type'] == 'episode']
                    successes = sum(r['content'].get('outcome') == 'success' for r in related)
                    failures = sum(r['content'].get('outcome') == 'failure' for r in related)
                    suggestions.append({'kind': 'skill_proposal', 'memory_id': item['memory_id'],
                                        'subject': item['subject'], 'successes': successes, 'failures': failures,
                                        'success_rate': successes / (successes + failures) if successes + failures else None,
                                        'requires_tests_and_review': True})
                results.extend(suggestions)
                memory.db.execute("UPDATE mm_jobs SET cursor=?,state=?,result=?,updated=? WHERE id=?",
                                  (cursor + 1, 'completed' if cursor + 1 == len(items) else 'running', encode(results), time.time(), job_id))
                if interrupt:
                    interrupt(cursor)  # Test seam: kill/raise before commit, cursor must roll back.
            processed += 1
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            with memory.db:
                memory.db.execute("UPDATE mm_jobs SET attempts=attempts+1,state=CASE WHEN attempts+1>=max_attempts THEN 'failed' ELSE 'queued' END,updated=? WHERE id=?", (time.time(), job_id))
            raise
    return job(memory, principal, job_id)


def control(memory, principal, job_id, action):
    principal.require('consolidator')
    with memory.db:
        memory.db.execute('BEGIN IMMEDIATE')
        state = job(memory, principal, job_id)
        if state['state'] in {'completed', 'cancelled', 'failed'}:
            raise ValueError('Terminal job')
        if action not in {'pause', 'resume', 'cancel'}:
            raise ValueError('Invalid control')
        memory.db.execute('UPDATE mm_jobs SET state=?,updated=? WHERE id=?',
                          ({'pause': 'paused', 'resume': 'queued', 'cancel': 'cancelled'}[action], time.time(), job_id))


def plan_index(memory, principal):
    """Rebuildable export only. Never calls the existing /index or /prune."""
    principal.require('indexer')
    return [{'memory_id': r['memory_id'], 'revision': r['id'], 'owner': r['owner'], 'scope': r['scope'],
             'text': r['subject'] + '\n' + encode(r['content']), 'model_dimensions': 384}
            for r in memory.current(principal) if r['effective_status'] in {'verified', 'user_confirmed'}]
