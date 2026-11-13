import sys,json,sqlite3,pathlib,hashlib,re,time,zipfile,io,os
from datetime import datetime
from zoneinfo import ZoneInfo
ROOT=pathlib.Path(__file__).parent
os.umask(0o077)
DB=sqlite3.connect(os.environ.get('JARVIS_DB',str(ROOT/'data/brain.sqlite')),timeout=30)
DB.row_factory=sqlite3.Row
DB.execute('PRAGMA journal_mode=WAL')
DB.executescript('''CREATE TABLE IF NOT EXISTS docs(id TEXT PRIMARY KEY,title TEXT NOT NULL,body TEXT NOT NULL,kind TEXT NOT NULL,topic TEXT NOT NULL,status TEXT NOT NULL,source TEXT NOT NULL,updated REAL NOT NULL,fingerprint TEXT);
CREATE VIRTUAL TABLE IF NOT EXISTS search USING fts5(id UNINDEXED,title,body,tokenize='unicode61 remove_diacritics 2');
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT);
CREATE TABLE IF NOT EXISTS conversation_sessions(id TEXT PRIMARY KEY,space TEXT NOT NULL,channel TEXT NOT NULL,created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS conversation_turns(session_id TEXT NOT NULL,turn INTEGER NOT NULL,revision INTEGER NOT NULL,user TEXT NOT NULL,assistant TEXT NOT NULL,status TEXT NOT NULL,updated REAL NOT NULL,PRIMARY KEY(session_id,turn));
''')
SPACES={'member1':'Member 1','member2':'Member 2','member3':'Member 3','member4':'Member 4','shared':'Shared'}
DB.execute('BEGIN IMMEDIATE')
if 'space' not in {row[1] for row in DB.execute('PRAGMA table_info(docs)')}:
 DB.execute("ALTER TABLE docs ADD COLUMN space TEXT NOT NULL DEFAULT 'member1'")
 DB.execute('CREATE INDEX idx_docs_space_updated ON docs(space,updated)')
DB.commit()
def space_id(value):
 if not isinstance(value,str) or value not in SPACES:raise ValueError('Espace inconnu.')
 return value
TOPICS={'Intelligence artificielle':['codex','chatgpt','jarvis','ollama','intelligence artificielle',' llm',' gpt'], 'Maison & énergie':['maison','énergie','home assistant','influx','solaire','pompe','aquarium','frigo','proxmox','adguard','tailscale'], 'Création & projets':['site','wordpress','brasskapelos','bandsync','github','gateway','application','plugin'], 'Exploration':['astro','seestar','télescope','ciel','voyage'], 'Apprentissage':['allemand','conjugaison','verbes','école','apprendre']}
def clean(s):
 s=str(s)
 s=re.sub(r'(?im)^.*(?:password|mot de passe|passwd|api[_ -]?key|access[_ -]?token|refresh[_ -]?token|gateway[_ -]?token|authorization|bearer\s|oauth|BEGIN .*PRIVATE KEY).*$','[Information sensible masquée]',s)
 s=re.sub(r'AIza[0-9A-Za-z_-]{20,}','[secret masqué]',s)
 s=re.sub(r'\b(?:sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9_]+|eyJ[A-Za-z0-9_.-]{20,})\b','[secret masqué]',s)
 s=re.sub(r'(?<![\w/])[A-Za-z0-9_+/=-]{48,}(?![\w/])','[identifiant masqué]',s)
 return s.strip()
def topic(text):
 t=text.lower();scores={k:sum(t.count(w) for w in v) for k,v in TOPICS.items()};return max(scores,key=scores.get) if max(scores.values()) else 'Idées libres'
def put(d):
 d['title']=clean(d['title'])[:180] or 'Sans titre';d['body']=clean(d['body'])[:250000];d['topic']=d.get('topic') or topic(d['title']+' '+d['body'][:10000])
 old=DB.execute('SELECT fingerprint,space FROM docs WHERE id=?',(d['id'],)).fetchone()
 if old and old[0]==d.get('fingerprint') and d.get('fingerprint'):return False
 DB.execute('INSERT OR REPLACE INTO docs(id,title,body,kind,topic,status,source,updated,fingerprint,space) VALUES(?,?,?,?,?,?,?,?,?,?)',(d['id'],d['title'],d['body'],d['kind'],d['topic'],d.get('status','Source'),d['source'],d.get('updated',time.time()),d.get('fingerprint'),old['space'] if old else d.get('space','member1')))
 DB.execute('DELETE FROM search WHERE id=?',(d['id'],));DB.execute('INSERT INTO search VALUES(?,?,?)',(d['id'],d['title'],d['body']));return True
def messages(path):
 out=[];fallback=[];sid=path.stem;stamp=path.stat().st_mtime
 with path.open(errors='replace') as f:
  for line in f:
   try:r=json.loads(line)
   except:continue
   p=r.get('payload',{})
   if r.get('type')=='session_meta':
    sid=p.get('id') or p.get('session_id') or sid
    # Child-agent transcripts are not conversations with the user.
    if isinstance(p.get('source'),dict) and 'subagent' in p['source']:return sid,[]
   if r.get('type')=='response_item' and p.get('type')=='message' and p.get('role') in ('user','assistant'):
    if p.get('role')=='assistant' and p.get('phase') not in (None,'final'):continue
    txt='\n'.join(x.get('text','') for x in p.get('content',[]) if isinstance(x,dict))
    txt=re.sub(r'<(recommended_plugins|environment_context|permissions instructions|skills_instructions|app_context|user_instructions)\b[^>]*>.*?</\1>', '', txt, flags=re.S).strip()
    if txt.startswith('# Files mentioned by the user'):
     txt=re.sub(r'^# Files mentioned by the user.*?(?=\n(?:## User|# User|<user)|\Z)', '', txt, flags=re.S).strip()
    if not txt or any(x in txt[:500] for x in ('<environment_context>','# AGENTS.md','<permissions instructions>','<INSTRUCTIONS>','<subagent_notification>')):continue
    out.append(('Toi' if p['role']=='user' else 'Codex',clean(txt)))
   elif r.get('type')=='event_msg' and p.get('type') in ('user_message','agent_message'):
    txt=p.get('message','')
    if isinstance(txt,str) and not any(x in txt[:500] for x in ('<environment_context>','# AGENTS.md','<INSTRUCTIONS>')):fallback.append(('Toi' if p['type']=='user_message' else 'Codex',clean(txt)))
 return sid,out or fallback
def sync():
 count=0;failed=0
 for p in pathlib.Path(os.environ.get('JARVIS_MEMORY_DIR',str(ROOT/'memory'))).glob('*.md'):
  raw=p.read_text();fp=hashlib.sha256(raw.encode()).hexdigest()
  for i,part in enumerate(re.split(r'(?m)(?=^## )',raw)):
   if len(part.strip())<50:continue
   title=part.splitlines()[0].lstrip('# ').strip()
   count+=put(dict(id='memory:'+p.stem+':'+str(i),title=title,body=part,kind='Mémoire',status='Note de référence',source='_memory/'+p.name,updated=p.stat().st_mtime,fingerprint=fp+':'+str(i)))
 for base in (('sessions','archived_sessions') if os.environ.get('JARVIS_IMPORT_CODEX_SESSIONS')=='true' else ()):
  for p in pathlib.Path(os.environ.get('CODEX_HOME',str(pathlib.Path.home()/'.codex')),base).rglob('*.jsonl'):
   st=p.stat();fp=f'v3:{st.st_size}:{st.st_mtime_ns}';key='file:'+str(p)
   old=DB.execute('SELECT value FROM meta WHERE key=?',(key,)).fetchone()
   if old and old[0]==fp:continue
   try:
    sid,msg=messages(p)
    if msg:
     candidates=[line.strip() for who,text in msg if who=='Toi' for line in text.splitlines() if len(line.strip())>8 and not line.lstrip().startswith(('<','#','/','-','```','file:'))]
     title=(candidates[0] if candidates else 'Conversation Codex · '+time.strftime('%d.%m.%Y',time.localtime(st.st_mtime)))[:120]
     count+=put(dict(id='codex:'+sid,title=title,body='\n\n'.join(w+': '+s for w,s in msg),kind='Codex',source='Codex local · '+sid,status='Conversation',updated=st.st_mtime,fingerprint=fp))
    DB.execute('INSERT OR REPLACE INTO meta VALUES(?,?)',(key,fp))
   except Exception:failed+=1
 DB.execute('INSERT OR REPLACE INTO meta VALUES(?,?)',('last_sync',str(time.time())))
 DB.commit();return dict(changed=count,failed=failed)
def listing(q='',space='member1'):
 if q.strip():
  words=re.findall(r'\w+',q,re.UNICODE)[:20]
  if not words:return []
  match=' OR '.join('"'+w+'"' for w in words)
  rows=DB.execute('SELECT d.id,d.title,d.kind,d.topic,d.status,d.source,d.updated,substr(d.body,1,240) AS preview FROM search JOIN docs d ON d.id=search.id WHERE search MATCH ? AND d.space=? ORDER BY bm25(search) LIMIT 500',(match,space)).fetchall()
 else:rows=DB.execute('SELECT id,title,kind,topic,status,source,updated,substr(body,1,240) AS preview FROM docs WHERE space=? ORDER BY updated DESC LIMIT 1200',(space,)).fetchall()
 return [dict(r) for r in rows]
def import_one(c,space):
 if not isinstance(c,dict) or not isinstance(c.get('mapping'),dict):return 0
 mapping=c['mapping'];items=[];seen=set();cur=c.get('current_node')
 while cur and cur in mapping and cur not in seen:
  seen.add(cur);items.append(mapping[cur]);cur=mapping[cur].get('parent')
 items=list(reversed(items)) if items else list(mapping.values());msg=[]
 for n in items:
  m=n.get('message') or {};role=m.get('author',{}).get('role')
  if role not in ('user','assistant'):continue
  parts=m.get('content',{}).get('parts',[]);txt='\n'.join(p for p in parts if isinstance(p,str))
  if txt:msg.append(('Toi' if role=='user' else 'ChatGPT')+': '+txt)
 cid=str(c.get('id') or c.get('conversation_id') or hashlib.sha256(json.dumps(c,sort_keys=True).encode()).hexdigest());text='\n\n'.join(msg)
 if not text:return 0
 return int(put(dict(id=('chatgpt:' if space=='member1' else 'chatgpt:'+space+':')+cid,space=space,title=c.get('title') or 'Discussion ChatGPT',body=text,kind='ChatGPT',status='Conversation',source='Export ChatGPT · '+cid,updated=float(c.get('update_time') or c.get('create_time') or time.time()),fingerprint=hashlib.sha256(text.encode()).hexdigest())))
def import_iter(chats,space):
 total=0;since_commit=0
 for c in chats:
  total+=import_one(c,space);since_commit+=1
  if since_commit>=50:DB.commit();since_commit=0
 DB.commit();return total
def iter_json_array(stream,initial):
 decoder=json.JSONDecoder();buf=initial;pos=0
 def refill():
  nonlocal buf,pos
  chunk=stream.read(1024*1024)
  if not chunk:return False
  buf=buf[pos:]+chunk;pos=0;return True
 while True:
  while pos>=len(buf):
   if not refill():raise ValueError('JSON de conversations incomplet.')
  if buf[pos].isspace():pos+=1;continue
  if buf[pos]!='[':raise ValueError('Format de conversations non reconnu.')
  pos+=1;break
 first=True
 while True:
  while True:
   while pos>=len(buf):
    if not refill():raise ValueError('JSON de conversations incomplet.')
   if buf[pos].isspace():pos+=1;continue
   break
  if buf[pos]==']':return
  if not first:
   if buf[pos]!=',':raise ValueError('JSON de conversations invalide.')
   pos+=1
   while True:
    while pos>=len(buf):
     if not refill():raise ValueError('JSON de conversations incomplet.')
    if buf[pos].isspace():pos+=1;continue
    break
  while True:
   try:item,end=decoder.raw_decode(buf,pos);break
   except json.JSONDecodeError:
    if not refill():raise ValueError('JSON de conversations invalide.')
  yield item;pos=end;first=False
def import_stream(stream,space,max_object=400*1024*1024):
 first=stream.read(1)
 while first and first.isspace():first=stream.read(1)
 if first=='[':return import_iter(iter_json_array(stream,first),space)
 if first!='{':raise ValueError('Format de conversations non reconnu.')
 raw=(first+stream.read(max_object+1)).encode('utf-8')
 if len(raw)>max_object:raise ValueError('Fichier JSON enveloppé trop volumineux ; importe le ZIP ChatGPT complet.')
 chats=json.loads(raw)
 if isinstance(chats,dict):chats=chats.get('conversations',[chats] if 'mapping' in chats else [])
 if not isinstance(chats,list):raise ValueError('Format de conversations non reconnu.')
 return import_iter(chats,space)
def import_zip_file(path,space):
 with zipfile.ZipFile(path) as archive:
  files=[item for item in archive.infolist() if re.match(r'^conversations(?:[-_]?[0-9]+)?\.json$',pathlib.PurePosixPath(item.filename).name)]
  if not files:raise ValueError('Aucun fichier conversations.json dans cet export.')
  if sum(item.file_size for item in files)>8*1024*1024*1024:raise ValueError('Les conversations décompressées dépassent 8 Go.')
  total=0
  for item in files:
   with archive.open(item) as binary:
    total+=import_stream(io.TextIOWrapper(binary,encoding='utf-8'),space)
  return {'imported':total}
def import_export_file(path,space):
 with open(path,'rb') as source:signature=source.read(2)
 if signature==b'PK':return import_zip_file(path,space)
 with open(path,encoding='utf-8-sig') as source:return {'imported':import_stream(source,space)}
def import_chats(raw,space='member1'):
 if raw[:2]==b'PK':
  path=ROOT/'data'/'import-buffer.zip';path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
  try:return import_zip_file(path,space)
  finally:path.unlink(missing_ok=True)
 return {'imported':import_stream(io.StringIO(raw.decode('utf-8-sig')),space)}
def conversation_session(a):
 sid=a.get('id');space=space_id(a.get('space','member1'));channel=a.get('channel')
 if not isinstance(sid,str) or not re.fullmatch(r'[0-9a-fA-F-]{36}',sid) or channel not in ('written','voice'):raise ValueError('Conversation invalide.')
 old=DB.execute('SELECT * FROM conversation_sessions WHERE id=?',(sid,)).fetchone()
 if old and (old['space']!=space or old['channel']!=channel):raise ValueError('Cette conversation appartient à un autre espace.')
 DB.execute('INSERT OR IGNORE INTO conversation_sessions VALUES(?,?,?,?)',(sid,space,channel,time.time()));DB.commit()
 return {'id':sid,'space':space,'channel':channel}
def conversation_record(a):
 sid=a.get('id');channel=a.get('channel');space=space_id(a.get('space','member1'))
 if not isinstance(sid,str) or not re.fullmatch(r'[0-9a-fA-F-]{36}',sid) or channel not in ('written','voice'):raise ValueError('Conversation invalide.')
 session=DB.execute('SELECT * FROM conversation_sessions WHERE id=?',(sid,)).fetchone()
 if channel=='voice':
  if not session or session['channel']!='voice':raise ValueError('Session vocale inconnue.')
  space=session['space']
 elif not session:
  conversation_session({'id':sid,'space':space,'channel':channel})
  session=DB.execute('SELECT * FROM conversation_sessions WHERE id=?',(sid,)).fetchone()
 if session and (session['space']!=space or session['channel']!=channel):raise ValueError('Cette conversation appartient à un autre espace.')
 turn=a.get('turn');revision=a.get('revision');status=a.get('status','partial')
 if type(turn)!=int or not 0<=turn<=99999 or type(revision)!=int or not 1<=revision<=100000 or status not in ('partial','complete','interrupted','continued'):raise ValueError('Numéro de message invalide.')
 user=a.get('user','');assistant=a.get('assistant','')
 if not isinstance(user,str) or not isinstance(assistant,str) or len(user)+len(assistant)>40000:raise ValueError('Échange trop volumineux.')
 user=clean(user);assistant=clean(assistant)
 if not user and not assistant:return {'saved':True,'empty':True}
 DB.execute('BEGIN IMMEDIATE')
 old=DB.execute('SELECT * FROM conversation_turns WHERE session_id=? AND turn=?',(sid,turn)).fetchone()
 if old and old['revision']>=revision:
  DB.commit();return {'saved':True,'duplicate':True,'revision':old['revision']}
 now=time.time()
 DB.execute('INSERT OR REPLACE INTO conversation_turns VALUES(?,?,?,?,?,?,?)',(sid,turn,revision,user,assistant,status,now))
 stamp=datetime.fromtimestamp(session['created'] if session else now,ZoneInfo('Europe/Zurich')).strftime('%d.%m.%Y %H:%M')
 label='vocal' if channel=='voice' else 'écrit'
 text='Échange '+label+' Jarvis · '+stamp+' · tour '+str(turn+1)+'\n\n'
 if user:text+='Toi : '+user+'\n\n'
 if assistant:text+='Jarvis : '+assistant+'\n\n'
 if status=='interrupted':text+='[Réponse interrompue : le texte généré peut ne pas avoir été entièrement entendu.]'
 elif status=='partial':text+='[Transcription ou réponse partielle.]'
 elif status=='continued':text+='[Suite dans le tour suivant.]'
 doc_id='jarvis:'+sid+':'+str(turn)
 put(dict(id=doc_id,space=space,title=('Jarvis '+label+' · '+(user or assistant)[:110]),body=text,kind='Jarvis',status='Conversation partielle' if status=='partial' else 'Conversation',source='Jarvis '+label+' · '+stamp,updated=now))
 DB.commit();return {'saved':True,'id':doc_id,'revision':revision,'space':space}
def main():
 action=sys.argv[1]
 if action=='import':return import_chats(sys.stdin.buffer.read(),space_id(sys.argv[2] if len(sys.argv)>2 else 'member1'))
 a=json.load(sys.stdin) if not sys.stdin.isatty() else {}
 if action=='sync':return sync()
 if action=='conversation_session':return conversation_session(a)
 if action=='conversation_record':return conversation_record(a)
 if action=='import_path':
  staging=(ROOT/'data'/'import-staging').resolve();path=pathlib.Path(a.get('path','')).resolve()
  if path.parent!=staging or path.suffix!='.upload':raise ValueError('Fichier d’import invalide.')
  return import_export_file(path,space_id(a.get('space','member1')))
 space=space_id(a.get('space','member1'))
 if action=='list':
  return dict(docs=listing(a.get('q',''),space),total=DB.execute('SELECT count(*) FROM docs WHERE space=?',(space,)).fetchone()[0],counts={r[0]:r[1] for r in DB.execute('SELECT kind,count(*) FROM docs WHERE space=? GROUP BY kind',(space,))},lastSync=(DB.execute('SELECT value FROM meta WHERE key="last_sync"').fetchone() or [None])[0])
 if action=='get':
  row=DB.execute('SELECT * FROM docs WHERE id=? AND space=?',(a['id'],space)).fetchone();return dict(row) if row else None
 if action=='move':
  target=space_id(a.get('target'))
  changed=DB.execute('UPDATE docs SET space=? WHERE id=? AND space=?',(target,a.get('id'),space)).rowcount
  if not changed:raise ValueError('Souvenir introuvable dans cet espace.')
  DB.commit();return {'moved':True,'space':target}
 if action=='save':
  if not isinstance(a.get('title'),str) or not 1<=len(a['title'].strip())<=180 or not isinstance(a.get('body'),str) or not 1<=len(a['body'].strip())<=30000:raise ValueError('Ajoute un titre et un texte (30 000 caractères maximum).')
  if a.get('status') not in ('Idée','Décision','À explorer','Réalisé'):raise ValueError('Statut invalide.')
  d=dict(id='note:'+os.urandom(12).hex(),space=space,title=a['title'],body=a['body'],kind='Atelier',status=a['status'],source='Ajouté dans Jarvis',updated=time.time());put(d);DB.commit();return d
 raise ValueError('Action inconnue')
try:print(json.dumps({'ok':True,'data':main()},ensure_ascii=False))
except Exception as e:
 DB.rollback();print(json.dumps({'ok':False,'error':str(e) if isinstance(e,ValueError) else 'La mémoire est momentanément indisponible.'},ensure_ascii=False));sys.exit(1)
