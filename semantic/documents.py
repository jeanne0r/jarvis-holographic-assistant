import hashlib,pathlib,sqlite3,os,time
ROOT=pathlib.Path(os.environ.get('JARVIS_SEMANTIC_ROOT',str(pathlib.Path(__file__).resolve().parent.parent)))

def version(title,text):return hashlib.sha256((title+'\n'+text).encode()).hexdigest()
def documents():
 db=sqlite3.connect('file:'+str(ROOT/'data/brain.sqlite')+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
 for row in db.execute("SELECT id,space,title,body,source FROM docs WHERE status != 'Conversation partielle' OR updated < ?",(time.time()-60,)):
  d=dict(row);yield {'doc_id':'brain:'+d['id'],'space':d['space'],'title':d['title'][:200],'text':d['body'],'source':d['source'][:300],'version':version(d['title'][:200],d['body'])}
 db.close()
 path=ROOT/'data/voice-memory.sqlite'
 if path.exists():
  db=sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
  for r in db.execute('SELECT * FROM facts'):
   d=dict(r);text=d['fact']+(' Entité : '+d['entity_id'] if d['entity_id'] else '')+(' Pièce : '+d['area'] if d['area'] else '')
   yield {'doc_id':'voice:'+d['space']+':'+d['key'],'space':d['space'],'title':d['label'],'text':text,'source':'Souvenir vocal explicite','version':version(d['label'],text)}
  db.close()
