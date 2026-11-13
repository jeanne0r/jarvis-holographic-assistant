"""Explicit voice facts and grounded user corrections. No audio, transcript or credentials."""
import json, os, pathlib, re, sqlite3, sys, time, unicodedata
os.umask(0o077)
SPACES={'member1','member2','member3','member4','shared'}
def norm(s):
 words=re.sub(r'[^a-z0-9]+',' ',unicodedata.normalize('NFD',s.lower()).encode('ascii','ignore').decode()).split()
 return ' '.join(w for w in words if w not in {'de','du','des','le','la','les','l','d'})
def main(action,data):
 space=data.get('space','member1')
 if space not in SPACES:raise ValueError('Espace inconnu.')
 path=os.environ.get('JARVIS_VOICE_MEMORY_DB',str(pathlib.Path(__file__).parent/'data/voice-memory.sqlite'))
 db=sqlite3.connect(path,timeout=10);db.row_factory=sqlite3.Row
 db.execute('PRAGMA journal_mode=WAL')
 db.execute('CREATE TABLE IF NOT EXISTS facts(space TEXT NOT NULL,key TEXT NOT NULL,label TEXT NOT NULL,fact TEXT NOT NULL,entity_id TEXT,area TEXT,updated REAL NOT NULL,PRIMARY KEY(space,key))')
 db.execute('CREATE TABLE IF NOT EXISTS correction_events(id INTEGER PRIMARY KEY AUTOINCREMENT,space TEXT NOT NULL,key TEXT NOT NULL,kind TEXT NOT NULL,previous_fact TEXT,new_fact TEXT NOT NULL,evidence TEXT NOT NULL,updated REAL NOT NULL)')
 # Canonicalize older keys so article/accent variants correct the same fact.
 with db:
  for old in db.execute('SELECT * FROM facts ORDER BY updated').fetchall():
   canonical=norm(old['label'])
   if canonical and canonical!=old['key']:
    db.execute('DELETE FROM facts WHERE space=? AND key=?',(old['space'],old['key']))
    current=db.execute('SELECT updated FROM facts WHERE space=? AND key=?',(old['space'],canonical)).fetchone()
    if not current or current[0]<=old['updated']:db.execute('INSERT OR REPLACE INTO facts VALUES(?,?,?,?,?,?,?)',(old['space'],canonical,old['label'],old['fact'],old['entity_id'],old['area'],old['updated']))
 if action=='list':
  rows=db.execute('SELECT * FROM facts WHERE space IN (?,?) ORDER BY updated DESC',(space,'shared')).fetchall()
  out=[]
  for r in rows:
   item=dict(r);event=db.execute('SELECT kind FROM correction_events WHERE space=? AND key=? ORDER BY id DESC LIMIT 1',(r['space'],r['key'])).fetchone()
   if event:item.update(origin='correction utilisateur',correctionKind=event['kind'])
   out.append(item)
  return out
 label=data.get('key','')
 if not isinstance(label,str) or not 1<=len(label.strip())<=120:raise ValueError('Nom de souvenir invalide.')
 key=norm(label)
 if not key:raise ValueError('Nom de souvenir invalide.')
 if action=='forget':
  with db:
   count=db.execute('DELETE FROM facts WHERE space=? AND key=?',(space,key)).rowcount
   db.execute('DELETE FROM correction_events WHERE space=? AND key=?',(space,key))
  return {'forgotten':bool(count),'key':key,'space':space}
 if action not in ('save','save_correction'):raise ValueError('Action inconnue.')
 fact=data.get('fact','');entity=data.get('entity_id') or None;area=data.get('area') or None
 if not isinstance(fact,str) or not 1<=len(fact.strip())<=800:raise ValueError('Souvenir trop long ou vide.')
 if entity and (not isinstance(entity,str) or not re.fullmatch(r'[a-z_]+\.[a-z0-9_]+',entity)):raise ValueError('Entité invalide.')
 if area and (not isinstance(area,str) or len(area)>100):raise ValueError('Pièce invalide.')
 if re.search(r'password|mot de passe|api[_ -]?key|access[_ -]?token|refresh[_ -]?token|bearer\s|oauth|private.key|\b(?:sk-|ghp_|AIza)[A-Za-z0-9_-]{12,}|eyJ[A-Za-z0-9_.-]{20,}',label+' '+fact,re.I):raise ValueError('Les secrets ne peuvent pas être mémorisés.')
 if db.execute('SELECT count(*) FROM facts WHERE space=?',(space,)).fetchone()[0]>=64 and not db.execute('SELECT 1 FROM facts WHERE space=? AND key=?',(space,key)).fetchone():raise ValueError('Mémoire pleine : oublier un ancien souvenir avant d’en ajouter un.')
 if action=='save_correction':
  evidence=data.get('evidence','');kind=data.get('kind')
  if kind not in ('identity','preference','rule') or not isinstance(evidence,str) or not 8<=len(evidence)<=400:raise ValueError('Preuve de correction invalide.')
  if re.search(r'password|mot de passe|api[_ -]?key|access[_ -]?token|refresh[_ -]?token|bearer\s|oauth|private.key|\b(?:sk-|ghp_|AIza)[A-Za-z0-9_-]{12,}|eyJ[A-Za-z0-9_.-]{20,}',evidence,re.I):raise ValueError('Les secrets ne peuvent pas être mémorisés.')
 with db:
  old=db.execute('SELECT fact FROM facts WHERE space=? AND key=?',(space,key)).fetchone()
  db.execute('INSERT OR REPLACE INTO facts VALUES(?,?,?,?,?,?,?)',(space,key,label.strip(),fact.strip(),entity,area,time.time()))
  if action=='save_correction':
   db.execute('INSERT INTO correction_events(space,key,kind,previous_fact,new_fact,evidence,updated) VALUES(?,?,?,?,?,?,?)',(space,key,kind,old['fact'] if old else None,fact.strip(),evidence,time.time()))
   db.execute('DELETE FROM correction_events WHERE id NOT IN (SELECT id FROM correction_events ORDER BY id DESC LIMIT 512)')
  else:db.execute('DELETE FROM correction_events WHERE space=? AND key=?',(space,key))
 return {'saved':True,**dict(db.execute('SELECT * FROM facts WHERE space=? AND key=?',(space,key)).fetchone())}
try:
 result=main(sys.argv[1],json.load(sys.stdin));print(json.dumps({'ok':True,'data':result}))
except Exception as e:
 print(json.dumps({'ok':False,'error':str(e) if isinstance(e,ValueError) else 'Mémoire persistante indisponible.'}))
