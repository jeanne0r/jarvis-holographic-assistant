"""Private storage RPC. Caller credentials bind subject; policy rechecked per action.
No imports of the live backend, shell, network client, scheduler or production data.
"""
import hashlib,json,os,pathlib,secrets,sqlite3,time,uuid
from .persistence import Persistence

class Storage:
 def __init__(self,repository,policy,*,staging,json_files=None,project_roots=None,sync_sources=None,index_reader=None):
  self.repo,self.policy=repository,policy;self.index_reader=index_reader
  self.staging=pathlib.Path(staging).resolve(strict=True)
  self.json_files=json_files or {};self.project_roots=project_roots or {};self.sync_sources=sync_sources or {};self.uploads={}
 def grant(self,subject,permission,space=None):
  g=self.policy.get(subject,{})
  if permission not in g.get('permissions',[]) or space is not None and space not in g.get('spaces',[]):raise PermissionError('Storage authority')
  if permission=='storage.write' and space is not None and space not in g.get('write_spaces',[]):raise PermissionError('Storage write space')
  return g
 def owned(self,subject,kind,key,write=False):
  row=self.repo.metadata(kind,key)
  g=self.grant(subject,'storage.write' if write else 'storage.read',row['space'] if row else '')
  if not row or row.get('deleted') or row['owner']!=subject and row['space'] not in g.get('common_write' if write else 'common_read',[]):raise PermissionError('Storage resource')
  if row.get('project') and row['project'] not in g.get('project_write' if write else 'project_read',[]):raise PermissionError('Storage project')
  return row
 def file(self,key):
  p=pathlib.Path(self.json_files[key])
  if not p.is_absolute() or any(x.is_symlink() for x in [p,*p.parents]):raise PermissionError('JSON symlink')
  return p
 def read_json(self,key):
  p=self.file(key)
  if p.stat().st_size>8*1024**2:raise ValueError('JSON bound')
  return json.loads(p.read_text())
 def write_json(self,key,value):
  p=self.file(key);tmp=p.with_name(p.name+'.'+secrets.token_hex(12)+'.tmp')
  # Keep recoverable original bytes; no overwrite of old backups.
  backup=p.with_name(p.name+'.before-'+uuid.uuid4().hex)
  raw=p.read_bytes();fd=os.open(backup,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
  with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
  if hashlib.sha256(backup.read_bytes()).digest()!=hashlib.sha256(raw).digest():raise IOError('JSON backup verification')
  try:
   with tmp.open('x',encoding='utf8') as f:os.chmod(tmp,0o600);json.dump(value,f,ensure_ascii=False);f.flush();os.fsync(f.fileno())
   os.replace(tmp,p)
   fd=os.open(p.parent,os.O_DIRECTORY);os.fsync(fd);os.close(fd)
  finally:tmp.unlink(missing_ok=True)
 def call(self,service,method,a):
  if service!='gateway-storage' or set(a)-{'subject','space','kind','id','query','data','guard','action','project','upload','chunk','offset','size'}:raise PermissionError('Storage protocol')
  subject=a['subject'];space=a.get('space');g=self.grant(subject,'storage.read' if method in ('metadata','list','get','facts','chat.read','projects.list','json.read','fact.metadata','tasks.list','fridge.list','map') else 'storage.write',space)
  kind=a.get('kind');key=a.get('id')
  if method=='metadata':
   try:return self.owned(subject,kind,key)
   except PermissionError:return None
  if method=='list':
   query=a.get('query',{});spaces=[space] if space else g['spaces'];rows=[]
   if kind=='memory':return [r for r in self.repo.facts(subject,spaces) if r['owner']==subject or r['space'] in g.get('common_read',[])]
   if kind!='document':raise ValueError('Native kind')
   for target in spaces:rows.extend(self.repo.list(kind,{'spaces':[target],'owner':subject,'projects':g.get('project_read',[]),'q':query.get('q','')}))
   return [r for r in rows if r['owner']==subject or r['space'] in g.get('common_read',[])]
  if method=='get':self.owned(subject,kind,key);return self.repo.get(kind,key)
  if method=='create':
   d=a['data'];self.grant(subject,'storage.write',d['space'])
   if d.get('project') and d['project'] not in g.get('project_write',[]):raise PermissionError('Project write')
   if kind=='memory':return self.repo.fact_write(subject,d['space'],d)
   return self.repo.create(kind,{**d,'owner':subject})
  if method=='mutate':
   meta=self.owned(subject,kind,key,True);d=a['data']
   if kind=='memory':
    target,label=json.loads(key);return self.repo.fact_write(subject,target,{'key':label},forget=True)
   self.grant(subject,'storage.write',d.get('target'))
   guard=a['guard']
   if guard.get('expectedOwner')!=meta['owner'] or guard.get('expectedVersion')!=meta['version']:raise PermissionError('Version changed')
   return self.repo.mutate(kind,key,d,guard)
  if method=='facts':return [r for r in self.repo.facts(subject,[space]+(['commun'] if space!='commun' and 'commun' in g.get('common_read',[]) else [])) if r['owner']==subject or r['space'] in g.get('common_read',[])]
  if method=='fact.metadata':
   key=json.dumps([space,self.repo.norm(a['data']['key'])],ensure_ascii=False)
   try:return self.owned(subject,'memory',key)
   except PermissionError:return None
  if method in ('fact.save','fact.forget'):return self.repo.fact_write(subject,space,a['data'],forget=method.endswith('forget'))
  if method=='conversation.record':return self.repo.record(subject,space,a['data'])
  if method=='map':
   from .projection import memory_map
   return memory_map(self,subject,space,a.get('offset'),self.index_reader)
  if method=='projects.list':return sorted(g.get('project_read',[]))
  if method.startswith('chat.'):
   project=a['project'];write=method=='chat.clear'
   if project not in g.get('project_write' if write else 'project_read',[]):raise PermissionError('Chat project')
   # Original gateway chats/<project>.json remains canonical. No shadow history.
   account='chat:'+project;self.owned(subject,'service-account',account,write)
   rows=self.read_json(account)
   if not isinstance(rows,list):raise ValueError('Historical chat format')
   if write:self.write_json(account,[]);return []
   return rows
  if method=='json.read':
   self.owned(subject,'service-account',key);value=self.read_json(key)
   if isinstance(value,list):
    # Resource lists are scoped before return, unknown item owners never adopted.
    selected=[]
    for item in value:
     try:self.owned(subject,kind,str(item['id']));selected.append(item)
     except (PermissionError,KeyError,TypeError):continue
    return selected
   return value
  if method in ('tasks.list','fridge.list','map'):
   account=a['id'];self.owned(subject,'service-account',account);value=self.read_json(account)
   rows=value if method=='tasks.list' else value['items'];kind='task' if method=='tasks.list' else 'fridge-item'
   visible=[]
   for item in rows:
    try:self.owned(subject,kind,str(item['id']));visible.append(item)
    except (PermissionError,KeyError,TypeError):continue
   if kind=='task':return {'tasks':visible}
   ids={str(item['id']) for item in visible};barcodes={item.get('barcode') for item in visible}
   return {'items':visible,'events':[e for e in value.get('events',[]) if str(e.get('itemId')) in ids], 'products':{k:v for k,v in value.get('products',{}).items() if k in barcodes}}
  if method=='tasks.change':
   account=a['id'];self.owned(subject,'service-account',account,True);rows=self.read_json(account);d=a['data'];action=a['action']
   if not isinstance(rows,list):raise ValueError('Tasks format')
   if action=='POST':
    title=d.get('title','').strip();person=d.get('person','commun');due=d.get('due')
    if not title or len(title)>180 or person not in ('user','amelie','malik','theo','commun') or due and not __import__('re').fullmatch(r'\d{4}-\d{2}-\d{2}',due):raise ValueError('Task format')
    # Person is a display/assignment field, never an owner or a grant.
    item={'id':str(uuid.uuid4()),'title':title,'person':person,'due':due or None,'done':False,'createdAt':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()}
    self.repo.claim('task',item['id'],subject,space,approved=True);rows.append(item)
   elif action in ('PATCH','DELETE'):
    self.owned(subject,'task',d.get('id'),True);index=next(i for i,item in enumerate(rows) if item['id']==d['id']);item=rows[index]
    if action=='DELETE':rows.pop(index)
    else:
     if type(d.get('done'))!=bool:raise ValueError('Task state')
     item['done']=d['done'];item['completedAt']=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat() if d['done'] else None
   else:raise ValueError('Task action')
   self.write_json(account,rows);return {'task':item}
  if method=='upload.begin':
   size=a['size']
   if type(size)!=int or not 1<=size<=3*1024**3 or len(self.uploads)>=4:raise ValueError('Upload bound')
   token=uuid.uuid4().hex;p=self.staging/(token+'.upload');fd=os.open(p,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
   self.uploads[token]={'subject':subject,'space':space,'size':size,'offset':0,'created':time.monotonic()};return {'upload':token}
  if method.startswith('upload.'):
   token=a['upload'];u=self.uploads.get(token)
   if not u or u['subject']!=subject or u['space']!=space:raise PermissionError('Upload owner')
   p=self.staging/(token+'.upload')
   if method=='upload.abort':p.unlink(missing_ok=True);del self.uploads[token];return {'aborted':True}
   if time.monotonic()-u['created']>900:raise TimeoutError('Upload expired; abort required')
   if method=='upload.chunk':
    import base64
    chunk=base64.b64decode(a['chunk'],validate=True)
    if len(chunk)>32768 or a['offset']!=u['offset'] or u['offset']+len(chunk)>u['size']:raise ValueError('Upload sequence')
    with p.open('ab') as f:f.write(chunk)
    u['offset']+=len(chunk);return {'offset':u['offset']}
   if method=='upload.finish':
    if u['offset']!=u['size']:raise ValueError('Incomplete upload')
    try:return self.repo.ingest(subject,space,p)
    finally:p.unlink(missing_ok=True);del self.uploads[token]
   raise ValueError('Upload action')
  if method=='sync':
   results=[]
   for path in self.sync_sources.get(subject,{}).get(space,[]):
    p=pathlib.Path(path)
    if any(x.is_symlink() for x in [p,*p.parents]) or not p.is_file() or p.stat().st_size>64*1024**2:raise PermissionError('Sync source boundary')
    results.append(self.repo.ingest(subject,space,p,sync=True))
   return {'changed':sum(r['changed'] for r in results),'failed':0}
  raise PermissionError('Unknown storage operation')
