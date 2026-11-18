"""Versioned declarative skills, fixed evaluations and human publication gate."""
import json
import math
import re
import time
from ..store import encode, digest, ACCEPTED, SECRET
from .validation import SKILL, validate

CASES = [
    ({'flow_lpm': 7, 'fresh': True}, 'report_only'),
    ({'flow_lpm': 2, 'fresh': True}, 'request_human_review'),
    ({'flow_lpm': 7, 'fresh': False}, 'request_human_review'),
]


def check(spec):
    # Validate types before set coercion: strings must never masquerade as lists.
    if isinstance(spec, dict) and isinstance(spec.get('allowed_tools'), list):
        if any(t not in ('memory.search', 'report') for t in spec['allowed_tools']):
            raise PermissionError('Skill cannot broaden permissions')
    validate(spec, SKILL)
    if set(spec) != {'name', 'version', 'description', 'allowed_tools', 'checks'} or not re.fullmatch(r'[a-z][a-z0-9_-]{2,63}', spec['name']) or type(spec['version']) is not int or spec['version'] < 1:
        raise ValueError('Skill identity')
    if set(spec['allowed_tools']) - {'memory.search', 'report'} or set(spec['checks']) - {'flow', 'freshness'} or not spec['checks'] or SECRET.search(encode(spec)):
        raise PermissionError('Skill cannot broaden permissions or introduce code')
    if len(encode(spec)) > 4000: raise ValueError('Skill limit')


def get(memory, principal, name, version, *, scope='private'):
    """Read canonical candidate/version, without granting execution or publication."""
    principal.require('reader')
    memory.access(principal, principal.name, scope)
    row = memory.db.execute('SELECT * FROM p2_skills WHERE owner=? AND scope=? AND name=? AND version=?',
                            (principal.name, scope, name, version)).fetchone()
    if not row:
        raise KeyError('Skill version unavailable')
    value = dict(row)
    for key in ('spec', 'sources', 'evaluation'):
        value[key] = json.loads(value[key]) if value[key] else None
    current = {r['memory_id']: r for r in memory.current(principal)}
    value['sources_current_accepted'] = all(
        ref['memory_id'] in current and current[ref['memory_id']]['id'] == ref['revision']
        and current[ref['memory_id']]['effective_status'] in ACCEPTED for ref in value['sources'])
    value['execution_authorized'] = False
    return value


def assess(memory, principal, name, version, *, scope='private'):
    """Persist fixed laboratory evaluation; never transition publication state."""
    principal.require('proposer')
    value = get(memory, principal, name, version, scope=scope)
    if value['state'] != 'candidate':
        raise ValueError('Candidate required')
    report = evaluate(value['spec'])
    with memory.db:
        memory.db.execute('UPDATE p2_skills SET evaluation=? WHERE owner=? AND scope=? AND name=? AND version=?',
                          (encode(report), principal.name, scope, name, version))
    return report


def apply(spec, sample):
    check(spec)
    # Pure recommendation on SYNTHETIC input, never a physical command.
    if 'freshness' in spec['checks'] and sample.get('fresh') is not True: return 'request_human_review'
    if 'flow' in spec['checks'] and (type(sample.get('flow_lpm')) not in (int, float) or not math.isfinite(sample['flow_lpm']) or sample['flow_lpm'] < 6): return 'request_human_review'
    return 'report_only'


def evaluate(spec):
    check(spec)
    results = [apply(spec, sample) == expected for sample, expected in CASES]
    return {'spec_hash': digest(spec), 'suite_hash': digest(CASES), 'results': results, 'passed': all(results), 'passed_count': sum(results), 'total': len(results)}


def propose(memory, principal, spec, sources, scope='private'):
    principal.require('proposer')
    memory.access(principal, principal.name, scope)
    check(spec)
    if not isinstance(sources, list) or not 1 <= len(sources) <= 16: raise ValueError('Experience sources required')
    references = []
    for mid in sources:
        row = memory._row(principal, mid)
        if row['scope'] != scope: raise PermissionError('Skill source scope mismatch')
        references.append({'memory_id': mid, 'revision': row['current_revision']})
    with memory.db:
        prior = memory.db.execute('SELECT * FROM p2_skills WHERE owner=? AND scope=? AND name=? AND version=?', (principal.name, scope, spec['name'], spec['version'])).fetchone()
        if prior:
            if prior['fingerprint'] != digest(spec) or prior['sources'] != encode(references): raise ValueError('Skill version is immutable')
        else:
            memory.db.execute('INSERT INTO p2_skills VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                              (principal.name, scope, spec['name'], spec['version'], encode(spec), digest(spec), encode(references), 'candidate', None, principal.actor, None))
    return {'name': spec['name'], 'version': spec['version'], 'state': 'candidate', 'fingerprint': digest(spec)}


def publish(memory, principal, name, version, *, scope='private', _action='publish'):
    principal.require('reviewer')
    memory.access(principal, principal.name, scope)
    key = (principal.name, scope, name, version)
    with memory.db:
        memory.db.execute('BEGIN IMMEDIATE')
        row = memory.db.execute('SELECT * FROM p2_skills WHERE owner=? AND scope=? AND name=? AND version=?', key).fetchone()
        if not row: raise KeyError('Skill version missing')
        if row['proposed_by'] == principal.actor: raise PermissionError('Independent publication identity required')
        spec = json.loads(row['spec'])
        report = evaluate(spec)
        current = {r['memory_id']: r for r in memory.current(principal)}
        if any(ref['memory_id'] not in current or current[ref['memory_id']]['id'] != ref['revision'] or current[ref['memory_id']]['effective_status'] not in ACCEPTED for ref in json.loads(row['sources'])):
            raise ValueError('Source no longer current and accepted')
        if not report['passed']: raise ValueError('Regression suite failed')
        previous = memory.db.execute('SELECT s.spec FROM p2_skill_active a JOIN p2_skills s USING(owner,scope,name,version) WHERE a.owner=? AND a.scope=? AND a.name=?', key[:3]).fetchone()
        if previous:
            baseline = evaluate(json.loads(previous[0]))
            if any(old and not new for old, new in zip(baseline['results'], report['results'])): raise ValueError('Skill regression')
            report['delta_passed'] = report['passed_count'] - baseline['passed_count']
        memory.db.execute("UPDATE p2_skills SET state='published',evaluation=?,published_by=? WHERE owner=? AND scope=? AND name=? AND version=?", (encode(report), principal.actor, *key))
        memory.db.execute('INSERT INTO p2_skill_active VALUES(?,?,?,?) ON CONFLICT(owner,scope,name) DO UPDATE SET version=excluded.version', key)
        memory.db.execute('INSERT INTO p2_skill_audit(owner,scope,name,version,action,actor,created) VALUES(?,?,?,?,?,?,?)', (*key, _action, principal.actor, time.time()))
    return report


def rollback(memory, principal, name, version, *, scope='private'):
    principal.require('reviewer')
    memory.access(principal, principal.name, scope)
    row = memory.db.execute("SELECT state FROM p2_skills WHERE owner=? AND scope=? AND name=? AND version=?", (principal.name, scope, name, version)).fetchone()
    if not row or row['state'] != 'published': raise ValueError('Only previously published versions can be restored')
    # Reevaluate fixed tests and source validity, never reactivate a failed procedure.
    return publish(memory, principal, name, version, scope=scope, _action='rollback')
