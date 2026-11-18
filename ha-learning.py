"""Scoped HA lookup hints. Metadata only; no readings, transcripts or credentials."""
import hashlib,json,os,re,sqlite3,sys,time
from pathlib import Path
os.umask(0o077)
path=Path(os.environ.get('JARVIS_HA_LEARNING_DB',str(Path(__file__).parent/'data'/'ha-learning.sqlite')))
path.parent.mkdir(parents=True,exist_ok=True)
db=sqlite3.connect(path,timeout=3)
db.execute('CREATE TABLE IF NOT EXISTS hints (key TEXT PRIMARY KEY, space TEXT NOT NULL, query TEXT NOT NULL, filters TEXT NOT NULL, entities TEXT NOT NULL, uses INTEGER NOT NULL, updated REAL NOT NULL)')
a=json.load(sys.stdin);space=a.get('space','user')
if space not in ('user','amelie','malik','theo','commun'):raise ValueError('Espace inconnu')
action=sys.argv[1]
if action=='list':
 rows=db.execute('SELECT key,query,filters,entities,uses,updated FROM hints WHERE space=? AND updated>? ORDER BY updated DESC LIMIT 256',(space,time.time()-30*86400)).fetchall()
 result=[dict(key='ha-lookup:'+k,status='provisoire',query=q,filters=json.loads(f),entities=json.loads(e),observations=n,updatedAt=t) for k,q,f,e,n,t in rows]
elif action=='save':
 count=0
 for row in a.get('rows',[])[:8]:
  q=row.get('query','').strip()
  if not q or len(q)>160 or re.search(r'https?://|@|[A-Za-z0-9_-]{40}',q):continue
  filters={k:str(v)[:100] for k,v in row.get('filters',{}).items() if k in ('domain','device_class','area','protocol')}
  entities=[]
  for e in row.get('entities',[])[:5]:
   if not re.fullmatch(r'[a-z_]+\.[a-z0-9_]+',e.get('entity_id','')):continue
   entities.append({k:str(e.get(k,''))[:160] for k in ('entity_id','name','unit','device_class')})
  if not entities:continue
  filters=json.dumps(filters,sort_keys=True);key=hashlib.sha256((space+'\n'+q.casefold()+'\n'+filters).encode()).hexdigest()[:24]
  db.execute('INSERT INTO hints VALUES(?,?,?,?,?,1,?) ON CONFLICT(key) DO UPDATE SET entities=excluded.entities,uses=hints.uses+1,updated=excluded.updated',(key,space,q,filters,json.dumps(entities),time.time()));count+=1
 db.execute('DELETE FROM hints WHERE space=? AND key NOT IN (SELECT key FROM hints WHERE space=? ORDER BY updated DESC LIMIT 256)',(space,space));db.commit();result={'saved':count}
elif action=='forget':
 key=a.get('key','').removeprefix('ha-lookup:');db.execute('DELETE FROM hints WHERE space=? AND key=?',(space,key));db.commit();result={'forgotten':True}
else:raise ValueError('Action inconnue')
print(json.dumps(result))
