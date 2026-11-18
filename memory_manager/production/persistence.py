"""Bindings over existing formats, with ownership metadata in the same SQLite files.
Only explicitly configured copies are used by tests. Never infer historical owners.
Legacy parsers are compiled from named functions, without executing module startup.
"""
import ast,hashlib,io,json,os,pathlib,re,sqlite3,time,uuid,zipfile
from datetime import datetime
from zoneinfo import ZoneInfo
from ..phase6d.legacy_repository import LegacyRepository
from ..store import snapshot

ROOT=pathlib.Path(__file__).resolve().parents[2]
def functions(path,names,environment):
 tree=ast.parse(pathlib.Path(path).read_text())
 nodes=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.Assign)) and (getattr(n,'name',None) in names or isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='TOPICS' for t in n.targets))]
 if {n.name for n in nodes if isinstance(n,ast.FunctionDef)}!=set(names):raise ValueError('Legacy source contract changed')
 exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),environment)
 return environment

class TransactionDB:
 """Legacy helpers cannot commit or begin outside the host-owned transaction."""
 def __init__(self,db):self.db=db
 def execute(self,sql,params=()):
  if sql.strip().upper()=='BEGIN IMMEDIATE':return None
  return self.db.execute(sql,params)
 def commit(self):pass

class Persistence(LegacyRepository):
 def __init__(self,brain,voice):
  super().__init__(pathlib.Path(brain).resolve(strict=True))
  self.voice_path=pathlib.Path(voice).resolve(strict=True)
  self.voice=sqlite3.connect(self.voice_path);self.voice.row_factory=sqlite3.Row
  env=dict(json=json,pathlib=pathlib,hashlib=hashlib,re=re,time=time,os=os,datetime=datetime,ZoneInfo=ZoneInfo,zipfile=zipfile,io=io,DB=TransactionDB(self.db),SPACES={s:s for s in ['user','amelie','malik','theo','commun']})
  self.legacy=functions(ROOT/'store.py',{'clean','topic','put','messages','space_id','conversation_session','conversation_record','import_one','import_iter','iter_json_array','import_stream','import_zip_file','import_export_file'},env)
  # Enforce document ownership before the old upsert, and claim only newly created rows.
  self.raw_put=env['put'];env['put']=self._put
  import unicodedata
  self.norm=functions(ROOT/'voice-memory.py',{'norm'},dict(re=re,unicodedata=unicodedata))['norm']
  self.actor=None;self.space=None
 def migrate(self):
  result=super().migrate()
  if not self.db.execute("SELECT 1 FROM sqlite_master WHERE name='g_document_revisions'").fetchone():
   snapshot(self.path,str(self.path)+'.before-production-history-'+uuid.uuid4().hex)
   with self.db:
    self.db.execute('CREATE TABLE g_document_revisions(id INTEGER PRIMARY KEY,resource TEXT,owner TEXT,version INTEGER,previous TEXT,updated REAL)')
    self.db.execute('CREATE TABLE g_conversation_revisions(id INTEGER PRIMARY KEY,session_id TEXT,turn INTEGER,owner TEXT,revision INTEGER,previous TEXT,updated REAL)')
  if not self.voice.execute("SELECT 1 FROM sqlite_master WHERE name='g_fact_acl'").fetchone():
   snapshot(self.voice_path,str(self.voice_path)+'.before-fact-acl-'+uuid.uuid4().hex)
   with self.voice:
    self.voice.execute('CREATE TABLE g_fact_acl(space TEXT,key TEXT,owner TEXT NOT NULL,version INTEGER NOT NULL,status TEXT NOT NULL,deleted INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(space,key))')
    self.voice.execute('CREATE TABLE g_fact_revisions(id INTEGER PRIMARY KEY,space TEXT,key TEXT,owner TEXT,version INTEGER,action TEXT,previous TEXT,updated REAL)')
  return result
 def metadata(self,kind,key):
  if kind=='memory':
   space,key=json.loads(key)
   row=self.voice.execute('SELECT owner,space,version,status,deleted FROM g_fact_acl WHERE space=? AND key=?',(space,key)).fetchone()
   return dict(row) if row else None
  return super().metadata(kind,key)
 def _put(self,document):
  key=document['id'];old=self.db.execute('SELECT space FROM docs WHERE id=?',(key,)).fetchone();acl=super().metadata('document',key)
  if old and (not acl or acl['owner']!=self.actor or acl['space']!=self.space):raise PermissionError('Existing source not owned')
  document['space']=self.space
  if old and (not document.get('fingerprint') or self.db.execute('SELECT fingerprint FROM docs WHERE id=?',(key,)).fetchone()[0]!=document.get('fingerprint')):
   previous=self.db.execute('SELECT * FROM docs WHERE id=?',(key,)).fetchone()
   self.db.execute('INSERT INTO g_document_revisions(resource,owner,version,previous,updated) VALUES(?,?,?,?,?)',(key,self.actor,acl['version'],json.dumps(dict(previous),ensure_ascii=False),time.time()))
  changed=self.raw_put(document)
  if not old:self.db.execute('INSERT INTO g_resource_acl VALUES(?,?,?,?,?,1)',('document',key,self.actor,self.space,None))
  elif changed:self.db.execute("UPDATE g_resource_acl SET version=version+1 WHERE kind='document' AND id=?",(key,))
  return changed
 def record(self,subject,space,data):
  if data.get('space',space)!=space:raise PermissionError('Conversation space')
  sid=data.get('id');old=self.db.execute('SELECT space,channel FROM conversation_sessions WHERE id=?',(sid,)).fetchone()
  acl=super().metadata('conversation',sid)
  if old and (not acl or acl['owner']!=subject or old['space']!=space):raise PermissionError('Conversation owner')
  if not isinstance(sid,str) or not re.fullmatch('[a-fA-F0-9-]{36}',sid):raise ValueError('Session id')
  self.actor,self.space=subject,space
  try:
   self.db.execute('BEGIN IMMEDIATE')
   if not old:
    self.legacy['conversation_session']({**data,'space':space})
    self.db.execute('INSERT INTO g_resource_acl VALUES(?,?,?,?,?,1)',('conversation',sid,subject,space,None))
   previous=self.db.execute('SELECT * FROM conversation_turns WHERE session_id=? AND turn=?',(sid,data.get('turn'))).fetchone()
   if previous and type(data.get('revision'))==int and data['revision']>previous['revision']:
    self.db.execute('INSERT INTO g_conversation_revisions(session_id,turn,owner,revision,previous,updated) VALUES(?,?,?,?,?,?)',(sid,data['turn'],subject,previous['revision'],json.dumps(dict(previous),ensure_ascii=False),time.time()))
   result=self.legacy['conversation_record']({**data,'space':space,'expected_space':space})
   self.db.commit();return result
  except BaseException:self.db.rollback();raise
  finally:self.actor=self.space=None
 def ingest(self,subject,space,path,*,sync=False):
  self.actor,self.space=subject,space
  try:
   self.db.execute('BEGIN IMMEDIATE')
   if sync:
    path=pathlib.Path(path)
    if path.suffix=='.jsonl':
     sid,msg=self.legacy['messages'](path)
     count=self._put(dict(id='codex:'+sid,title=next((text[:120] for role,text in msg if role=='Toi'),'Conversation Codex'),body='\n\n'.join(w+': '+text for w,text in msg),kind='Codex',source='Codex local · '+sid,status='Conversation',updated=path.stat().st_mtime,fingerprint=hashlib.sha256(path.read_bytes()).hexdigest())) if msg else 0
    elif path.suffix=='.md':
     raw=path.read_text();count=0
     for i,part in enumerate(re.split(r'(?m)(?=^## )',raw)):
      if len(part.strip())>=50:count+=self._put(dict(id='memory:'+path.stem+':'+str(i),title=part.splitlines()[0].lstrip('# ').strip(),body=part,kind='Mémoire',status='Note de référence',source='_memory/'+path.name,updated=path.stat().st_mtime,fingerprint=hashlib.sha256(raw.encode()).hexdigest()+':'+str(i)))
    else:raise ValueError('Approved source format')
    result={'changed':int(count)}
   else:result=self.legacy['import_export_file'](path,space)
   self.db.commit();return result
  except BaseException:self.db.rollback();raise
  finally:self.actor=self.space=None
 def facts(self,subject,spaces,*,include_common=False):
  out=[]
  for space in spaces:
   for r in self.voice.execute("SELECT f.*,a.owner,a.version,a.status FROM facts f JOIN g_fact_acl a USING(space,key) WHERE f.space=? AND a.deleted=0 AND (a.owner=? OR f.space='commun') ORDER BY updated DESC",(space,subject)):
    item=dict(r);item['id']=json.dumps([space,item['key']],ensure_ascii=False);out.append(item)
  return out
 def fact_write(self,subject,space,data,*,forget=False):
  label=data.get('key','');fact=data.get('fact','')
  if not isinstance(label,str):raise ValueError('Fact label')
  key=self.norm(label)
  if not key or not isinstance(label,str) or len(label)>120 or not forget and (not isinstance(fact,str) or not 1<=len(fact.strip())<=800):raise ValueError('Fact schema')
  clean=self.legacy['clean']
  if clean(label)!=label.strip() or not forget and clean(fact)!=fact.strip():raise ValueError('Secret rejected')
  with self.voice:
   old=self.voice.execute('SELECT * FROM facts WHERE space=? AND key=?',(space,key)).fetchone()
   acl=self.voice.execute('SELECT * FROM g_fact_acl WHERE space=? AND key=?',(space,key)).fetchone()
   if old and (not acl or acl['owner']!=subject):raise PermissionError('Fact ownership')
   if forget and not old:raise PermissionError('Unknown fact')
   version=(acl['version'] if acl else 0)+1
   self.voice.execute('INSERT INTO g_fact_revisions(space,key,owner,version,action,previous,updated) VALUES(?,?,?,?,?,?,?)',(space,key,subject,version,'forget' if forget else 'proposal',json.dumps(dict(old),ensure_ascii=False) if old else None,time.time()))
   self.voice.execute('INSERT OR REPLACE INTO g_fact_acl VALUES(?,?,?,?,?,?)',(space,key,subject,version,'inferred',int(forget)))
   if not forget:
    entity=data.get('entity_id');area=data.get('area')
    if entity is not None and (not isinstance(entity,str) or not re.fullmatch(r'[a-z_]+\.[a-z0-9_]+',entity)):raise ValueError('Entity format')
    if area is not None and (not isinstance(area,str) or len(area)>100):raise ValueError('Area format')
    self.voice.execute('INSERT OR REPLACE INTO facts VALUES(?,?,?,?,?,?,?)',(space,key,label.strip(),fact.strip(),entity,area,time.time()))
    if data.get('evidence') is not None:
     evidence=data['evidence'];kind=data.get('kind')
     if kind not in ('identity','preference','rule') or not isinstance(evidence,str) or not 8<=len(evidence)<=400 or clean(evidence)!=evidence.strip():raise ValueError('Correction evidence')
     self.voice.execute('INSERT INTO correction_events(space,key,kind,previous_fact,new_fact,evidence,updated) VALUES(?,?,?,?,?,?,?)',(space,key,kind,old['fact'] if old else None,fact.strip(),evidence,time.time()))
  return {'forgotten':True,'key':key,'space':space} if forget else {'saved':True,'key':key,'fact':fact.strip(),'space':space,'owner':subject,'status':'inferred','version':version}
 def close(self):self.voice.close();super().close()
