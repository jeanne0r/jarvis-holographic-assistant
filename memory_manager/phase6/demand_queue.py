"""Durable scheduling metadata over the existing mission/outbox source of truth."""
import json,time,uuid,os,fcntl,sqlite3
from contextlib import contextmanager
from ..store import snapshot,encode,digest
from ..phase2.bridge import Bridge
from ..phase3.lab import OWNER
from .operational import definition,OBJECTIVE,TEXT_PREFIX

SCHEMA='''CREATE TABLE IF NOT EXISTS p6q_jobs(mission_id TEXT PRIMARY KEY REFERENCES mm_missions(id),expires REAL NOT NULL,next_check REAL NOT NULL DEFAULT 0,reason TEXT NOT NULL DEFAULT 'waiting',lease TEXT UNIQUE,lease_until REAL,leased_at REAL,attempts INTEGER NOT NULL DEFAULT 0,cleanup_ok INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS p6q_keys(owner TEXT NOT NULL,scope TEXT NOT NULL,key TEXT NOT NULL,mission_id TEXT NOT NULL REFERENCES mm_missions(id),fingerprint TEXT NOT NULL,PRIMARY KEY(owner,scope,key));'''
REASONS={'waiting','windows_offline','gpu_busy','miner_active','insufficient_vram','maintenance','preflight_failed','uncertain','quota','expired','stopped','ready'}
TERMINAL={'completed','failed','cancelled'}

def migrate(memory):
    if len(memory.db.execute("SELECT name FROM sqlite_master WHERE name IN ('p6q_jobs','p6q_keys')").fetchall())==2:return False
    backup=memory.path.with_name(memory.path.name+'.before-demand-'+str(time.time_ns()))
    snapshot(memory.path,backup)
    memory.db.executescript('BEGIN IMMEDIATE;'+SCHEMA+'COMMIT;')
    return True

@contextmanager
def admission_lock(memory):
    fd=os.open(memory.path.with_name(memory.path.name+'.queue-admit.lock'),os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    try:
        fcntl.flock(fd,fcntl.LOCK_EX)
        yield
    finally:os.close(fd)

def report_quality(projection,output,db,check):
    """Prod 17.11: a report written by a mission that later FAILED was among the sources read;
    the strict check refused the whole answer as 'not cited'. Each source still goes through the
    same strict check; an unverifiable mission report is declared (count), never hidden, never
    trusted, and citing one keeps quality False. Any other refusal still propagates."""
    # Real reads (ha://, influx://) are checked here, not by the pinned strict check: the ref must be
    # a host-ingested measurement event (sources/tools.py). mission:// reports remain earlier
    # answers: an answer citing only them is not a sourced answer.
    measured=[i for i in projection['items'] if i['source_ref'].startswith(MEASURED)]
    for item in measured:
        if not measurement_event(db,item['source_ref']):raise PermissionError('Unverified measurement source')
    cites_measured=any(i['source_ref'] in output for i in measured)
    projection=dict(projection,items=[i for i in projection['items'] if i not in measured])
    if not projection['items']:return bool(measured) and cites_measured,[],False
    unverified=[]
    for item in projection['items']:
        try:check(dict(projection,items=[item]),output,db)
        except PermissionError as e:
            if str(e)!='Unverified synthetic mission source':raise
            unverified.append(item['source_ref'])
    unverified=list(dict.fromkeys(unverified))
    verified=dict(projection,items=[i for i in projection['items'] if i['source_ref'] not in unverified])
    cites_unverified=any(r in output for r in unverified)
    strict=bool(verified['items']) and check(verified,output,db)[1] is True
    quality=(strict or cites_measured) and not cites_unverified
    return quality,unverified,cites_unverified

MEASURED=('ha://','influx://')
def measurement_event(db,ref):
    return any(json.loads(r[0]).get('ref')==ref and json.loads(r[0]).get('kind')=='measurement' for r in db.execute(
        "SELECT source FROM mm_events WHERE owner=? AND scope='private' AND event_key LIKE 'source-read-%'",(OWNER,)))

class Queue:
    def __init__(self,memory,host,*,accepting=False,execution=False,clock=time.time):
        if host.name!=OWNER or 'private' not in host.scopes:raise PermissionError('Synthetic host only')
        self.m,self.p,self.clock,self.accepting,self.execution=memory,host,clock,accepting is True,execution is True
    def supervisor(self,p):
        p.require('queue_supervisor')
        if p.name!=OWNER or p.actor!='on-demand-supervisor' or 'private' not in p.scopes:raise PermissionError('Independent queue supervisor only')
    def admit(self,p,key,data):
        p.require('mission_writer')
        if p.name!=OWNER or p.actor!='interactive-panel':raise PermissionError('Existing authenticated panel only')
        if not self.accepting:raise PermissionError('New requests suspended')
        if not isinstance(key,str) or not 1<=len(key)<=120:raise ValueError('Idempotency key required')
        d=data.get('definition',{}) if isinstance(data,dict) else {}
        if not isinstance(d,dict):raise PermissionError('Structured mission definition required')
        text=d.get('objective');valid=text==OBJECTIVE or isinstance(text,str) and text.startswith(TEXT_PREFIX) and 1<=len(text[len(TEXT_PREFIX):])<=2000
        # The gateway (unchanged until the routing step) still sends the former grants
        # [memory.search, report]. Grants stay server-selected: either exact form is
        # accepted and the stored definition always carries the current grants.
        legacy=dict(definition(text) if valid else {},allowed_tools=['memory.search','report'])
        if not valid or data not in ({'scope':'private','definition':definition(text)},{'scope':'private','definition':legacy}):raise PermissionError('Exact server grants/budget required')
        d=definition(text)
        # Serial admission uses the existing canonical submit transaction. An orphan
        # after a crash is never adopted or dispatched automatically.
        with admission_lock(self.m):
            fingerprint=digest(d)
            alias=self.m.db.execute('SELECT mission_id,fingerprint FROM p6q_keys WHERE owner=? AND scope=? AND key=?',(OWNER,'private',key)).fetchone()
            if alias:
                if alias['fingerprint']!=fingerprint:raise ValueError('Idempotency key reused with different content')
                mid=alias['mission_id']
                return {'mission_id':mid,'state':Bridge(self.m,p).get(mid)['state'],'accepted':True,'execution_started':False}
            # Exact same intent within its original 24h horizon returns the
            # existing record, even after reconnect/ack loss or completion.
            # This is not semantic deduplication, nor an automatic rerun.
            same=self.m.db.execute('SELECT m.id FROM mm_missions m JOIN p6q_jobs q ON q.mission_id=m.id WHERE m.owner=? AND m.scope=? AND m.definition=? AND q.expires>? ORDER BY m.created LIMIT 1',(OWNER,'private',encode(d),self.clock())).fetchone()
            if self.m.db.execute('SELECT count(*) FROM p6q_keys').fetchone()[0]>=10000:raise ValueError('Idempotency registry capacity reached')
            if same:
                mid=same[0]
                with self.m.db:self.m.db.execute('INSERT INTO p6q_keys VALUES(?,?,?,?,?)',(OWNER,'private',key,mid,fingerprint))
                return {'mission_id':mid,'state':Bridge(self.m,p).get(mid)['state'],'accepted':True,'execution_started':False}
            prior=self.m.db.execute('SELECT id FROM mm_missions WHERE owner=? AND scope=? AND event_key=?',(OWNER,'private',key)).fetchone()
            if not prior and self.m.db.execute('SELECT count(*) FROM mm_missions m JOIN p6q_jobs q ON q.mission_id=m.id WHERE m.created>=?',(self.clock()-86400,)).fetchone()[0]>=50:raise ValueError('Daily admission quota')
            if not prior and self.m.db.execute("SELECT count(*) FROM p6q_jobs q JOIN mm_missions m ON m.id=q.mission_id WHERE m.state NOT IN ('completed','failed','cancelled')").fetchone()[0]>=10:raise ValueError('Queue capacity reached')
            mid=Bridge(self.m,p).submit(key,d,'private')
            if prior and not self.m.db.execute('SELECT 1 FROM p6q_jobs WHERE mission_id=?',(mid,)).fetchone():raise PermissionError('Legacy mission cannot be adopted')
            self.m.db.execute('INSERT OR IGNORE INTO p6q_jobs(mission_id,expires) VALUES(?,?)',(mid,self.clock()+86400))
            Bridge(self.m,self.p).event(mid,'demand-admitted','queue_admission',{'synthetic_only':False,'real_sources':'read-only','ttl_seconds':86400,'tools':list(d['allowed_tools']),'remote_cost_chf':0})
            self.m.db.execute('INSERT INTO p6q_keys VALUES(?,?,?,?,?)',(OWNER,'private',key,mid,fingerprint))
            self.m.db.commit()
            return {'mission_id':mid,'state':Bridge(self.m,p).get(mid)['state'],'accepted':True,'execution_started':False}
    def expire(self):
        now=self.clock()
        rows=self.m.db.execute("SELECT q.* FROM p6q_jobs q JOIN mm_missions m ON m.id=q.mission_id WHERE q.lease IS NULL AND q.attempts=0 AND q.expires<=? AND m.state='queued'",(now,)).fetchall()
        for row in rows:
            Bridge(self.m,self.p).cancel(row['mission_id'])
            with self.m.db:
                self.m.db.execute("UPDATE p6q_jobs SET reason='expired' WHERE mission_id=?",(row['mission_id'],))
                Bridge(self.m,self.p).event(row['mission_id'],'demand-expired','queue_expired',{'automatic_execution':False})
    def quarantine(self,mid,reason='uncertain'):
        with self.m.db:
            state=Bridge(self.m,self.p).get(mid)['state']
            if state not in TERMINAL:
                self.m.db.execute("UPDATE mm_missions SET state='paused' WHERE id=?",(mid,))
                self.m.db.execute("UPDATE p2_outbox SET state='unknown',lease_until=0 WHERE mission_id=?",(mid,))
            self.m.db.execute("UPDATE p6q_jobs SET reason=?,cleanup_ok=0 WHERE mission_id=?",(reason,mid))
            Bridge(self.m,self.p).event(mid,'demand-quarantine','reconciliation_required',{'automatic_replay':False,'reason':reason})
    def recover(self):
        for row in self.m.db.execute('SELECT mission_id FROM p6q_jobs WHERE lease IS NOT NULL').fetchall():self.quarantine(row[0])
    def peek(self,p):
        self.supervisor(p);self.expire()
        if self.m.db.execute("SELECT 1 FROM p6q_jobs WHERE lease IS NOT NULL OR cleanup_ok=0 LIMIT 1").fetchone() or self.m.db.execute("SELECT 1 FROM p2_outbox WHERE state IN ('unknown','submitting','submitted','cancel_requested') LIMIT 1").fetchone():return None
        row=self.m.db.execute("SELECT q.mission_id,q.reason FROM p6q_jobs q JOIN mm_missions m ON m.id=q.mission_id JOIN p2_outbox o ON o.mission_id=m.id WHERE m.state='queued' AND o.state='ready' AND q.lease IS NULL AND q.attempts=0 AND q.next_check<=? ORDER BY m.created,m.id LIMIT 1",(self.clock(),)).fetchone()
        return dict(row) if row else None
    def defer(self,p,mid,reason):
        self.supervisor(p)
        if reason not in REASONS:raise ValueError('Bounded availability reason')
        with self.m.db:
            row=self.m.db.execute('SELECT * FROM p6q_jobs WHERE mission_id=?',(mid,)).fetchone()
            if not row or row['lease'] is not None:raise PermissionError('Unstarted queued job required')
            self.m.db.execute('UPDATE p6q_jobs SET reason=?,next_check=? WHERE mission_id=?',(reason,self.clock()+30,mid))
            Bridge(self.m,self.p).event(mid,'deferred-'+reason,'deferred',{'reason':reason,'retry_after_seconds':30})
    def reserve(self,p,mid):
        self.supervisor(p);self.expire()
        if not self.execution:raise PermissionError('Execution not commissioned')
        with self.m.db:
            self.m.db.execute('BEGIN IMMEDIATE')
            if self.m.db.execute("SELECT 1 FROM p6q_jobs WHERE lease IS NOT NULL OR cleanup_ok=0 LIMIT 1").fetchone():raise PermissionError('Existing or uncertain execution blocks dispatch')
            if self.m.db.execute("SELECT 1 FROM p2_outbox WHERE state IN ('unknown','submitted','submitting','cancel_requested') LIMIT 1").fetchone():raise PermissionError('Legacy/uncertain run requires review')
            if self.m.db.execute('SELECT count(*) FROM p6q_jobs WHERE leased_at>=?',(self.clock()-86400,)).fetchone()[0]>=12:raise PermissionError('Daily execution quota')
            row=self.m.db.execute('SELECT q.*,m.state,o.state AS dispatch_state FROM p6q_jobs q JOIN mm_missions m ON m.id=q.mission_id JOIN p2_outbox o ON o.mission_id=m.id WHERE q.mission_id=?',(mid,)).fetchone()
            if not row or row['state']!='queued' or row['dispatch_state']!='ready' or row['attempts']!=0 or row['next_check']>self.clock():raise PermissionError('Fresh unstarted job required')
            lease=uuid.uuid4().hex;end=self.clock()+300
            self.m.db.execute("UPDATE p6q_jobs SET lease=?,lease_until=?,leased_at=?,attempts=1,cleanup_ok=0,reason='ready' WHERE mission_id=?",(lease,end,self.clock(),mid))
            Bridge(self.m,self.p).event(mid,'demand-reserved','execution_reserved',{'seconds':300,'calls':6,'tokens':98304,'remote_cost_chf':0})
            return {'mission_id':mid,'lease':lease,'expires_at':end}
    def finish(self,p,lease,cleanup_ok):
        self.supervisor(p)
        row=self.m.db.execute('SELECT * FROM p6q_jobs WHERE lease=?',(lease,)).fetchone()
        if not row:raise PermissionError('Current lease required')
        state=Bridge(self.m,self.p).get(row['mission_id'])['state']
        if cleanup_ok is not True or state not in TERMINAL:
            self.quarantine(row['mission_id']);return {'quarantined':True}
        quality=False
        if state=='completed':
            try:
                from ..phase6d.evidence import metadata
                from scripts.text_mission_window import result_provenance
                receipts=[r[0] for r in self.m.db.execute('SELECT id FROM p6d_receipts WHERE mission_id=? ORDER BY created DESC LIMIT 20',(row['mission_id'],))]
                projection=metadata(self.m,self.p,row['mission_id'],receipts)
                event=self.m.db.execute("SELECT data FROM p2_events WHERE mission_id=? AND event_key='terminal'",(row['mission_id'],)).fetchone()
                output=json.loads(event[0]).get('output','') if event else ''
                quality,unverified,cites_unverified=report_quality(projection,output,self.m.db,result_provenance)
                measured=list(dict.fromkeys(i['source_ref'] for i in projection['items'] if i['source_ref'].startswith(('ha://','influx://'))))
            except (ValueError,KeyError,PermissionError,sqlite3.Error):quality,unverified,cites_unverified,measured,output=False,[],False,[],''
            with self.m.db:Bridge(self.m,self.p).event(row['mission_id'],'demand-report-quality','report_quality',{'model_cites_source_ref':quality,'fact_promotion':False,'model_output_modified':False,
                'unverified_mission_sources_read':len(unverified),'cites_unverified_source':cites_unverified,
                'measurements_read':len(measured),'cites_measurement':any(r in output for r in measured)})
        with self.m.db:
            self.m.db.execute("UPDATE p6q_jobs SET lease=NULL,cleanup_ok=1,reason='stopped' WHERE mission_id=?",(row['mission_id'],))
            Bridge(self.m,self.p).event(row['mission_id'],'demand-cleanup','owned_cleanup_confirmed',{'automatic_replay':False})
        return {'released':True,'state':state}
    def status(self):
        active=self.m.db.execute('SELECT q.mission_id,q.reason FROM p6q_jobs q WHERE lease IS NOT NULL OR cleanup_ok=0 LIMIT 1').fetchone()
        waiting=self.m.db.execute("SELECT q.reason FROM p6q_jobs q JOIN mm_missions m ON m.id=q.mission_id WHERE m.state='queued' ORDER BY m.created LIMIT 1").fetchone()
        return {'accepting':self.accepting,'execution_enabled':self.execution,'active':dict(active) if active else None,'reason':waiting[0] if waiting else 'waiting','automatic_replay':False}
