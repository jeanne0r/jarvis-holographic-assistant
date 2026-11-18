"""Additive laboratory metadata only; canonical facts retain their original schema."""
import time
import json
import os
from pathlib import Path
from ..store import snapshot, digest, uid

DDL = '''
CREATE TABLE IF NOT EXISTS p5_schema(version INTEGER PRIMARY KEY, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS p5_index_ack(collection TEXT, artifact TEXT, point_id TEXT, payload_hash TEXT,
 PRIMARY KEY(collection,artifact,point_id));
CREATE TABLE IF NOT EXISTS p5_visibility(memory_id TEXT PRIMARY KEY REFERENCES mm_memories(id), hidden INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS p5_visibility_audit(id TEXT PRIMARY KEY, owner TEXT, scope TEXT, event_key TEXT,
 memory_id TEXT, hidden INTEGER, actor TEXT, reason TEXT, created REAL, UNIQUE(owner,scope,event_key));
'''


def migrate(memory):
    if memory.db.execute("SELECT 1 FROM sqlite_master WHERE name='p5_schema'").fetchone():
        if memory.db.execute('SELECT version FROM p5_schema').fetchone()[0] != 1: raise ValueError('Schema version')
        return {'changed': False}
    backup = snapshot(memory.path, memory.path.with_name(memory.path.name+'.before-phase5-'+uid()))
    fd=os.open(backup['path']+'.manifest.json',os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,'w') as manifest:json.dump(backup,manifest)
    memory.db.executescript('BEGIN IMMEDIATE;'+DDL+'INSERT INTO p5_schema VALUES(1,'+str(time.time())+');COMMIT;')
    return {'changed': True, 'backup': backup}


def require(memory):
    if memory.db.execute('SELECT version FROM p5_schema').fetchone()[0] != 1: raise ValueError('Explicit migration required')


def hidden_ids(memory):
    require(memory)
    return {r[0] for r in memory.db.execute('SELECT memory_id FROM p5_visibility WHERE hidden=1')}


def visibility(memory, principal, memory_id, *, hidden, reason, key):
    principal.require('reviewer'); require(memory)
    row = memory._row(principal, memory_id)
    if row['owner'] != principal.name: raise PermissionError('Owner required')
    if type(hidden) is not bool or not isinstance(reason,str) or not 1<=len(reason)<=200 or not isinstance(key,str) or not 1<=len(key)<=200:
        raise ValueError('Bounded visibility change required')
    from ..store import SECRET
    if SECRET.search(reason): raise ValueError('Sensitive reason rejected')
    with memory.db:
        memory.db.execute('BEGIN IMMEDIATE')
        old = memory.db.execute('SELECT memory_id,hidden,reason FROM p5_visibility_audit WHERE owner=? AND scope=? AND event_key=?', (row['owner'],row['scope'],key)).fetchone()
        if old:
            if tuple(old)!=(memory_id,int(hidden),reason): raise ValueError('Idempotency conflict')
            return
        memory.db.execute('INSERT INTO p5_visibility_audit VALUES(?,?,?,?,?,?,?,?,?)',
            (uid(),row['owner'],row['scope'],key,memory_id,int(hidden),principal.actor,reason,time.time()))
        memory.db.execute('INSERT INTO p5_visibility VALUES(?,?) ON CONFLICT(memory_id) DO UPDATE SET hidden=excluded.hidden',(memory_id,int(hidden)))
