"""Durable technical run ledger. No automatic adoption of historical jobs."""
import hashlib,json,sqlite3,time,uuid
from pathlib import Path
from ...store import snapshot
class Jobs:
 def __init__(self,path):
    self.db=sqlite3.connect(path);self.db.row_factory=sqlite3.Row
    if self.db.execute("SELECT 1 FROM sqlite_master WHERE name='jobs'").fetchone() and not self.db.execute("SELECT 1 FROM sqlite_master WHERE name='job_events'").fetchone():snapshot(path,str(path)+'.before-job-events-'+uuid.uuid4().hex)
    self.db.executescript('CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,owner TEXT NOT NULL,project TEXT NOT NULL,key TEXT NOT NULL,fingerprint TEXT NOT NULL,payload TEXT NOT NULL,state TEXT NOT NULL,result TEXT,created REAL NOT NULL,UNIQUE(owner,key));')
    self.db.executescript("""CREATE TABLE IF NOT EXISTS job_events(seq INTEGER PRIMARY KEY AUTOINCREMENT,job TEXT NOT NULL,owner TEXT NOT NULL,state TEXT NOT NULL,created REAL NOT NULL);
CREATE TRIGGER IF NOT EXISTS job_admission AFTER INSERT ON jobs BEGIN INSERT INTO job_events(job,owner,state,created) VALUES(new.id,new.owner,new.state,unixepoch()); END;
CREATE TRIGGER IF NOT EXISTS job_transition AFTER UPDATE OF state ON jobs WHEN old.state!=new.state BEGIN INSERT INTO job_events(job,owner,state,created) VALUES(new.id,new.owner,new.state,unixepoch()); END;
CREATE TRIGGER IF NOT EXISTS job_events_no_update BEFORE UPDATE ON job_events BEGIN SELECT RAISE(ABORT,'immutable event'); END;
CREATE TRIGGER IF NOT EXISTS job_events_no_delete BEFORE DELETE ON job_events BEGIN SELECT RAISE(ABORT,'immutable event'); END;""")
    with self.db:self.db.execute("UPDATE jobs SET state='uncertain' WHERE state IN ('running','cancel_requested')")
 def admit(self,owner,project,key,payload):
    if not isinstance(key,str) or not 1<=len(key)<=120:raise ValueError('Idempotency key')
    raw=json.dumps(payload,sort_keys=True,ensure_ascii=False,allow_nan=False);fp=hashlib.sha256((project+'\n'+raw).encode()).hexdigest()
    if len(raw.encode())>32000:raise ValueError('Payload bound')
    with self.db:
        old=self.db.execute('SELECT id,fingerprint FROM jobs WHERE owner=? AND key=?',(owner,key)).fetchone()
        if old:
            if old['fingerprint']!=fp:raise ValueError('Idempotency conflict')
            return old['id']
        job=str(uuid.uuid4());self.db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?)',(job,owner,project,key,fp,raw,'queued',None,time.time()));return job
 def get(self,owner,job):
    row=self.db.execute('SELECT * FROM jobs WHERE id=? AND owner=?',(job,owner)).fetchone()
    if not row:raise PermissionError('Job owner denied')
    return {**dict(row),'events':[{'seq':r['seq'],'data':{'type':'status','status':r['state']},'created':r['created']} for r in self.db.execute('SELECT * FROM job_events WHERE job=? AND owner=? ORDER BY seq LIMIT 200',(job,owner))]}
 def list(self,owner,projects):return [dict(r) for r in self.db.execute('SELECT * FROM jobs WHERE owner=? ORDER BY created DESC LIMIT 100',(owner,)) if r['project'] in projects]
 def cancel(self,owner,job):
    row=self.get(owner,job)
    if row['state']=='queued':
        with self.db:self.db.execute("UPDATE jobs SET state='cancelled' WHERE id=? AND state='queued'",(job,))
    elif row['state']=='running':
        with self.db:self.db.execute("UPDATE jobs SET state='cancel_requested' WHERE id=?",(job,))
    return self.get(owner,job)
 def close(self):self.db.close()
