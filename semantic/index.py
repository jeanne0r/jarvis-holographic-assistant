"""Incremental, resumable index; recent Jarvis exchanges get priority."""
import fcntl,json,pathlib,sqlite3,time,os
os.umask(0o077)
from client import call
from documents import documents,ROOT
lock=(ROOT/'data/semantic-index.lock').open('w')
try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError:raise SystemExit(0)
state=sqlite3.connect(ROOT/'data/semantic-index.sqlite')
state.execute('CREATE TABLE IF NOT EXISTS indexed(doc_id TEXT PRIMARY KEY,version TEXT NOT NULL,updated REAL NOT NULL)')
status=ROOT/'data/semantic-index-status.json'
def report(**data):
 temp=status.with_suffix('.tmp');temp.write_text(json.dumps({'checkedAt':time.time(),**data}));temp.chmod(0o600);temp.replace(status)
try:
 health=call('/health')
 if not health['points']:
  with state:state.execute('DELETE FROM indexed')
 docs=list(documents());total=len(docs);changed=0
 def process(doc):
  global changed
  old=state.execute('SELECT version FROM indexed WHERE doc_id=?',(doc['doc_id'],)).fetchone()
  if not old or old[0]!=doc['version']:
   call('/index',doc,timeout=300);changed+=1
   with state:state.execute('INSERT OR REPLACE INTO indexed VALUES(?,?,?)',(doc['doc_id'],doc['version'],time.time()))
 # Refresh newly completed conversations during the initial full index too.
 refreshed=0
 for i,doc in enumerate(docs):
  if time.monotonic()-refreshed>20:
   recent=[d for d in documents() if d['doc_id'].startswith(('brain:jarvis:','voice:'))]
   for fresh in recent:process(fresh)
   refreshed=time.monotonic()
  process(doc)
  report(state='indexing',done=i+1,total=total,changed=changed,model=health['model'])
 current_docs=list(documents())
 for doc in current_docs:process(doc)
 current={d['doc_id'] for d in current_docs}
 # Re-read IDs before pruning: additions made during the pass must survive.
 keep={d['doc_id'] for d in documents()}
 call('/prune',{'ids':list(keep)},timeout=90)
 with state:
  for row in state.execute('SELECT doc_id FROM indexed').fetchall():
   if row[0] not in keep:state.execute('DELETE FROM indexed WHERE doc_id=?',row)
 health=call('/health');report(state='ready',done=len(current_docs),total=len(current_docs),changed=changed,points=health['points'],model=health['model'])
 print(json.dumps({'state':'ready','documents':len(current_docs),'changed':changed,'points':health['points']}))
except Exception:
 report(state='error',message='Indexation interrompue ; reprise automatique au prochain passage.')
 print('Indexation interrompue ; reprise automatique.');raise SystemExit(1)
