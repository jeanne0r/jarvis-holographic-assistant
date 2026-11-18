"""SQLite canonical prototype; stdlib only, no model, HA, shell or network calls.

Principal and source channels are supplied by a trusted host, never by retrieved
content. The HTTP surface only submits inferred proposals. See security doc.
"""
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import time
import uuid

TYPES = {'identity', 'knowledge', 'episode', 'project', 'skill', 'lesson'}
ACCEPTED = {'observed', 'user_confirmed', 'verified'}
STATUSES = ACCEPTED | {'inferred', 'disputed', 'superseded'}
SECRET = re.compile(r'password|mot de passe|api[_ -]?key|access[_ -]?token|refresh[_ -]?token|bearer\s|BEGIN .*PRIVATE KEY|\b(?:sk-|gh[pousr]_|AIza)[A-Za-z0-9_-]{12,}|https?://[^/\s:]+:[^/\s]+@', re.I)


def encode(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(',', ':'))


def digest(value):
    return hashlib.sha256(encode(value).encode()).hexdigest()


def uid():
    return str(uuid.uuid4())


@dataclass(frozen=True)
class Principal:
    name: str
    scopes: frozenset
    roles: frozenset = frozenset({'reader', 'proposer'})
    actor_id: str = ''

    @property
    def actor(self):
        return self.actor_id or self.name

    def require(self, role):
        if role not in self.roles:
            raise PermissionError('Capability denied')


def snapshot(source, destination):
    """WAL-consistent backup, exclusive destination, integrity and hash evidence."""
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if source == destination:
        raise ValueError('Backup must be separate')
    fd = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True) as src:
        with sqlite3.connect(destination) as dst:
            src.backup(dst)
            if dst.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError('Backup integrity failed')
            tables = [r[0] for r in dst.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    return {'path': str(destination), 'sha256': hashlib.sha256(destination.read_bytes()).hexdigest(),
            'integrity': 'ok', 'tables': sorted(tables)}


class Memory:
    def __init__(self, path, *, create=False):
        self.path = Path(path).resolve()
        if create:
            # Never adopt an existing database (including an empty placeholder).
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
        if not self.path.is_file():
            raise ValueError('Explicit initialization required')
        self.db = sqlite3.connect(self.path.as_uri() + '?mode=rw', uri=True, timeout=5)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA foreign_keys=ON')
        if create:
            self.db.executescript(Path(__file__).with_name('schema.sql').read_text())
            with self.db:
                self.db.execute('INSERT INTO mm_schema VALUES(1,?)', (time.time(),))
        try:
            version = self.db.execute('SELECT max(version) FROM mm_schema').fetchone()[0]
        except sqlite3.Error:
            self.db.close()
            raise
        if version != 1:
            self.db.close()
            raise ValueError('Unsupported schema; explicit backed-up migration required')
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')

    def close(self):
        self.db.close()

    @staticmethod
    def access(principal, owner, scope):
        if scope not in principal.scopes or (scope == 'private' and owner != principal.name):
            raise PermissionError('Memory not accessible')

    def _row(self, principal, memory_id):
        row = self.db.execute('SELECT * FROM mm_memories WHERE id=?', (memory_id,)).fetchone()
        if not row:
            raise KeyError('Unknown memory')
        self.access(principal, row['owner'], row['scope'])
        return row

    def ingest(self, principal, key, source, candidates, *, scope='private'):
        """Atomic immediate consolidation of already-structured candidates.

        Arbitrary text extraction is deliberately not implemented. Untrusted
        callers cannot select a trusted channel or replace an active fact.
        """
        principal.require('proposer')
        self.access(principal, principal.name, scope)
        if not isinstance(key, str) or not 1 <= len(key) <= 200:
            raise ValueError('Invalid idempotency key')
        if not isinstance(candidates, list) or not 1 <= len(candidates) <= 32:
            raise ValueError('Bounded candidates required')
        if not isinstance(source, dict) or not {'kind', 'ref', 'observed_at'} <= source.keys():
            raise ValueError('Source reference and observation time required')
        if source['kind'] not in {'user', 'measurement', 'model', 'external', 'test'}:
            raise ValueError('Unknown source channel')
        if not isinstance(source['ref'], str) or not source['ref'] or len(source['ref']) > 1000:
            raise ValueError('Invalid source reference')
        observed = float(source['observed_at'])
        if not 0 <= observed <= time.time() + 300:
            raise ValueError('Invalid observation time')
        serialized = encode({'source': source, 'candidates': candidates})
        if len(serialized) > 64000:
            raise ValueError('Event too large')
        if SECRET.search(serialized):
            raise ValueError('Credentials must not enter memory')
        trusted = 'ingester' in principal.roles
        if not trusted and source['kind'] != 'external':
            raise PermissionError('Trusted source channel denied')
        fingerprint = digest({'source': source, 'candidates': candidates})
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            old = self.db.execute('SELECT * FROM mm_events WHERE owner=? AND scope=? AND event_key=?',
                                  (principal.name, scope, key)).fetchone()
            if old:
                if old['fingerprint'] != fingerprint:
                    raise ValueError('Idempotency key reused with different data')
                return [r[0] for r in self.db.execute('SELECT memory_id FROM mm_revisions WHERE event_id=? ORDER BY rowid', (old['id'],))]
            event_id = uid()
            self.db.execute('INSERT INTO mm_events VALUES(?,?,?,?,?,?,?)',
                            (event_id, principal.name, scope, key, fingerprint, encode(source), time.time()))
            result = []
            for c in candidates:
                if c.get('type') not in TYPES or not isinstance(c.get('content'), dict) or not c['content']:
                    raise ValueError('Typed structured content required')
                if any(not isinstance(c.get(k), str) or not 1 <= len(c[k]) <= 200 for k in ('subject', 'predicate')):
                    raise ValueError('Subject and predicate required')
                status = c.get('status', 'inferred')
                if status not in STATUSES - {'superseded'}:
                    raise ValueError('Invalid status')
                if status in ACCEPTED and not trusted:
                    raise PermissionError('Promotion denied')
                if status == 'user_confirmed' and source['kind'] != 'user':
                    raise PermissionError('User statement source required')
                if status == 'verified' and (source['kind'] not in {'measurement', 'test'} or 'validator' not in principal.roles or not source.get('evidence')):
                    raise PermissionError('Independent evidence required')
                if source['kind'] in {'model', 'external'} and status != 'inferred':
                    raise PermissionError('Untrusted data remains inference')
                memory_id, parent = c.get('correction_of') or uid(), None
                if c.get('correction_of'):
                    if not trusted or source['kind'] not in {'user', 'measurement', 'test'} or status not in ACCEPTED:
                        raise PermissionError('Correction requires trusted evidence')
                    previous = self._row(principal, memory_id)
                    if previous['owner'] != principal.name or previous['scope'] != scope:
                        raise PermissionError('Correction outside ownership')
                    parent = previous['current_revision']
                    if c.get('expected_revision') != parent:
                        raise ValueError('Stale correction; review current revision')
                    before = self.db.execute('SELECT * FROM mm_revisions WHERE id=?', (parent,)).fetchone()
                    if any(c[k] != before[k] for k in ('subject', 'predicate', 'type')):
                        raise ValueError('Correction cannot change memory identity')
                revision = uid()
                confidence = float(c.get('confidence', .5))
                if 'observed_at' in c and not trusted:
                    raise PermissionError('Per-candidate source time requires trusted ingress')
                candidate_observed = float(c.get('observed_at', observed))
                if not 0 <= candidate_observed <= observed:
                    raise ValueError('Candidate observation must belong to its source event')
                valid_from = float(c.get('valid_from', candidate_observed))
                valid_to = c.get('valid_to')
                if valid_to is not None:
                    valid_to = float(valid_to)
                if not 0 <= confidence <= 1 or not 0 <= valid_from < float('inf') or (valid_to is not None and not valid_from < valid_to < float('inf')):
                    raise ValueError('Invalid confidence or validity')
                if not parent:
                    self.db.execute('INSERT INTO mm_memories VALUES(?,?,?,?)', (memory_id, principal.name, scope, revision))
                self.db.execute('INSERT INTO mm_revisions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                                (revision, memory_id, parent, event_id, c['type'], c['subject'], c['predicate'], encode(c['content']),
                                 candidate_observed, valid_from, valid_to, confidence, status, time.time()))
                self.db.execute('UPDATE mm_memories SET current_revision=? WHERE id=?', (revision, memory_id))
                self.db.execute('INSERT INTO mm_fts VALUES(?,?,?)', (revision, c['subject'], encode(c['content'])))
                for relation in c.get('relations', []):
                    target = self._row(principal, relation['memory_id'])
                    if relation['kind'] not in {'supports', 'analogy', 'depends_on', 'corrects'}:
                        raise ValueError('Invalid relation')
                    # A shared item may not reveal a private item or another scope.
                    if target['scope'] != scope or (scope == 'private' and target['owner'] != principal.name):
                        raise PermissionError('Cross-scope relation denied')
                    self.db.execute('INSERT INTO mm_relations VALUES(?,?,?)', (revision, target['current_revision'], relation['kind']))
                self.db.execute('INSERT INTO mm_audit(actor,action,memory_id,before_revision,after_revision,event_id,created) VALUES(?,?,?,?,?,?,?)',
                                (principal.name, 'correct' if parent else 'observe', memory_id, parent, revision, event_id, time.time()))
                result.append(memory_id)
            return result

    def current(self, principal, *, at=None):
        principal.require('reader')
        at = time.time() if at is None else at
        scopes = sorted(principal.scopes)
        if not scopes:
            return []
        rows = self.db.execute('''SELECT r.*,m.owner,m.scope,e.source FROM mm_memories m
          JOIN mm_revisions r ON r.id=m.current_revision JOIN mm_events e ON e.id=r.event_id
          WHERE m.scope IN (''' + ','.join('?' for _ in scopes) + ''')
          AND (m.scope!='private' OR m.owner=?) AND r.valid_from<=? AND (r.valid_to IS NULL OR r.valid_to>?)''',
                               (*scopes, principal.name, at, at)).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item['content'], item['source'] = json.loads(item['content']), json.loads(item['source'])
            item['relations'] = [dict(r) for r in self.db.execute('SELECT kind,target FROM mm_relations WHERE source=?', (item['id'],))]
            item['contradictions'] = []
            result.append(item)
        for item in result:
            for other in result:
                if (item['id'] != other['id'] and item['subject'] == other['subject'] and item['predicate'] == other['predicate']
                        and item['content'] != other['content'] and item['status'] in ACCEPTED and other['status'] in ACCEPTED):
                    item['contradictions'].append(other['memory_id'])
            item['effective_status'] = 'disputed' if item['contradictions'] else item['status']
        return result

    def history(self, principal, memory_id):
        principal.require('reader')
        memory = self._row(principal, memory_id)
        rows = [dict(r) for r in self.db.execute('''SELECT r.*,e.source FROM mm_revisions r JOIN mm_events e ON e.id=r.event_id
                 WHERE memory_id=? ORDER BY r.rowid''', (memory_id,))]
        for row in rows:
            row['content'], row['source'] = json.loads(row['content']), json.loads(row['source'])
            row['effective_status'] = row['status'] if row['id'] == memory['current_revision'] else 'superseded'
        return rows

    def search(self, principal, query, *, vector_hits=(), memory_type=None, subject=None, at=None, limit=10, exclude_ids=()):
        if not isinstance(query, str) or len(query) > 2000 or not 1 <= limit <= 50:
            raise ValueError('Invalid query or limit')
        rows = {r['memory_id']: r for r in self.current(principal, at=at)
                if r['memory_id'] not in exclude_ids and (memory_type is None or r['type'] == memory_type) and (subject is None or r['subject'] == subject)}
        scores = {}
        words = re.findall(r'\w+', query)[:20]
        if words:
            match = ' OR '.join('"' + w + '"' for w in words)
            # No limit before ACL/version filtering; no restricted hit can displace an authorized hit.
            scopes = sorted(principal.scopes)
            sql = '''SELECT f.revision FROM mm_fts f JOIN mm_memories m ON m.current_revision=f.revision
                     WHERE mm_fts MATCH ? AND (m.scope!='private' OR m.owner=?)
                     AND m.scope IN (''' + ','.join('?' for _ in scopes) + ') ORDER BY bm25(mm_fts)'
            for rank, hit in enumerate(self.db.execute(sql, (match, principal.name, *scopes))):
                for mid, row in rows.items():
                    if row['id'] == hit['revision']:
                        scores[mid] = 1 / (60 + rank)
        for rank, hit in enumerate(list(vector_hits)[:100]):
            mid = hit.get('memory_id')
            if mid in rows and rows[mid]['id'] == hit.get('revision'):
                scores[mid] = scores.get(mid, 0) + 1 / (60 + rank)
        if not words and not vector_hits:
            scores = {mid: 0 for mid in rows}
        priority = {'verified': 4, 'user_confirmed': 3, 'observed': 2, 'disputed': 1, 'inferred': 0}
        chosen = sorted(scores, key=lambda mid: (priority.get(rows[mid]['effective_status'], 0), scores[mid], rows[mid]['observed']), reverse=True)[:limit]
        return [{**rows[mid], 'score': scores[mid], 'usage': 'analogy_only' if rows[mid]['type'] == 'episode' else 'attributed_knowledge'} for mid in chosen]

    def undo(self, principal, memory_id, *, expected_revision, key):
        """Compensating revision; no deletion, no promotion beyond prior evidence."""
        principal.require('reviewer')
        history = self.history(principal, memory_id)
        if len(history) < 2 or history[-1]['id'] != expected_revision:
            raise ValueError('Nothing to undo or stale revision')
        old = history[-2]
        candidate = {k: old[k] for k in ('type', 'subject', 'predicate', 'content', 'status', 'confidence', 'valid_from', 'valid_to')}
        candidate.update(correction_of=memory_id, expected_revision=expected_revision)
        return self.ingest(principal, key, {**old['source'], 'undo_of': expected_revision}, [candidate], scope=self._row(principal, memory_id)['scope'])
