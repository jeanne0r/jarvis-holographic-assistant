"""Durable, expiring supervisor observations; never starts Windows or mining."""
import math,time
from ..store import uid
SCHEMA='''CREATE TABLE IF NOT EXISTS p6d_workers(worker TEXT PRIMARY KEY,owner TEXT NOT NULL,reporter TEXT NOT NULL,epoch TEXT NOT NULL,sequence INTEGER NOT NULL,seen REAL,state TEXT NOT NULL);'''
def register(memory,principal,worker,reporter):
 principal.require('worker_supervisor')
 if not all(isinstance(x,str) and 1<=len(x)<=128 for x in [worker,reporter]):raise ValueError('Worker identities required')
 old=memory.db.execute('SELECT owner FROM p6d_workers WHERE worker=?',(worker,)).fetchone()
 if old and old[0]!=principal.name:raise PermissionError('Worker owner denied')
 epoch=uid()
 with memory.db:memory.db.execute('INSERT INTO p6d_workers VALUES(?,?,?,?,?,?,?) ON CONFLICT(worker) DO UPDATE SET reporter=excluded.reporter,epoch=excluded.epoch,sequence=0,seen=NULL,state=excluded.state',(worker,principal.name,reporter,epoch,0,None,'unknown'))
 return epoch

def observe(memory,principal,worker,epoch,sequence,state,*,now=None):
 principal.require('worker_reporter');now=time.time() if now is None else now
 if type(now) not in (float,int) or not math.isfinite(now) or type(sequence) is not int or sequence<1 or state not in {'ready','offline','gpu_busy','uncertain'}:raise ValueError('Invalid observation')
 with memory.db:
    row=memory.db.execute('SELECT * FROM p6d_workers WHERE worker=?',(worker,)).fetchone()
    if not row or row['owner']!=principal.name or row['reporter']!=principal.actor or row['epoch']!=epoch:raise PermissionError('Reporter binding denied')
    if sequence<=row['sequence'] or (row['seen'] is not None and now<row['seen']):raise ValueError('Replayed or backward heartbeat')
    memory.db.execute('UPDATE p6d_workers SET sequence=?,seen=?,state=? WHERE worker=?',(sequence,now,state,worker))

def status(memory,principal,worker,*,now=None,ttl=30):
 principal.require('reader');now=time.time() if now is None else now
 if type(ttl) not in (int,float) or not 1<=ttl<=60:raise ValueError('Bounded TTL')
 row=memory.db.execute('SELECT * FROM p6d_workers WHERE worker=? AND owner=?',(worker,principal.name)).fetchone()
 if not row:raise PermissionError('Worker visibility denied')
 fresh=row['seen'] is not None and 0<=now-row['seen']<ttl
 return {'worker':worker,'last_seen':row['seen'],'fresh':fresh,'state':row['state'] if fresh else 'unknown','dispatch_allowed':fresh and row['state']=='ready','automatic_replay':False}
