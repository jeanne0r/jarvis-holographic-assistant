"""Hybrid document retrieval; source SQLite validates every vector hit."""
import json,pathlib,re,sqlite3,sys,unicodedata,time
from client import call
from documents import ROOT,version

def search(data):
 query=data.get('query','');space=data.get('space','user');common=data.get('include_common',False)
 if not isinstance(query,str) or not 1<=len(query.strip())<=2000 or space not in ['user','amelie','malik','theo','commun']:raise ValueError('Recherche invalide.')
 spaces=list(set([space]+(['commun'] if common else [])))
 db=sqlite3.connect('file:'+str(ROOT/'data/brain.sqlite')+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
 scores={};source={};snippets={};semantic=False
 words=[w for w in re.findall(r'\w+',query.lower()) if w not in {'le','la','les','de','du','des','un','une','est','et','que','qui','quoi','comment','ce','je','tu','il','on','nous','dans','pour','sur','au','aux','en','a','l','d','se','peux','mon','ma','mes'}][:20]
 if words:
  sql="SELECT d.* FROM search JOIN docs d ON d.id=search.id WHERE search MATCH ? AND (d.status != 'Conversation partielle' OR d.updated < ?) AND d.space IN ("+','.join('?' for _ in spaces)+') ORDER BY bm25(search) LIMIT 15'
  rows=db.execute(sql,[' OR '.join('"'+w+'"' for w in words),time.time()-60,*spaces]).fetchall()
  for rank,r in enumerate(rows):
   key='brain:'+r['id'];scores[key]=1/(60+rank);source[key]=dict(r)
   body=r['body'];pos=next((m.start() for w in words if (m:=re.search(re.escape(w),body,re.I))),0);start=max(0,pos-300);snippets[key]=[body[start:start+4000]]
 # Structured facts remain searchable directly in SQLite when Qdrant is offline.
 path=ROOT/'data/voice-memory.sqlite'
 if path.exists() and words:
  facts=sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True);facts.row_factory=sqlite3.Row
  normalized=lambda text:unicodedata.normalize('NFD',text.lower()).encode('ascii','ignore').decode()
  for r in facts.execute('SELECT * FROM facts WHERE space IN ('+','.join('?' for _ in spaces)+')',spaces):
   name=normalized(r['label']);text=normalized(r['label']+' '+r['fact'])
   matches=sum(normalized(w) in text for w in words)
   if matches < min(2,len(words)):continue
   key='voice:'+r['space']+':'+r['key']
   body=r['fact']+(' Entité : '+r['entity_id'] if r['entity_id'] else '')+(' Pièce : '+r['area'] if r['area'] else '')
   scores[key]=1/25 if all(w in normalized(query) for w in r['key'].split()) else 1/65
   source[key]={'id':key,'title':r['label'],'body':body,'source':'Souvenir vocal explicite','space':r['space']};snippets[key]=[body]
  facts.close()
 try:
  hits=call('/search',{'query':query,'space':space,'include_common':common,'limit':24},timeout=8)['hits'];seen=set()
  for hit in hits:
   if hit.get('space') not in spaces:continue
   key=hit['doc_id'];row=None
   if key.startswith('brain:'):
    r=db.execute('SELECT * FROM docs WHERE id=? AND space IN ('+','.join('?' for _ in spaces)+')',[key[6:],*spaces]).fetchone()
    if r:row=dict(r)
    if not row or (row.get('status')=='Conversation partielle' and row.get('updated',0)>time.time()-60) or version(row['title'][:200],row['body'])!=hit['version']:continue
   elif key.startswith('voice:'):
    path=ROOT/'data/voice-memory.sqlite';found=None
    if path.exists():
     owner,memory_key=key[6:].split(':',1)
     facts=sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True);facts.row_factory=sqlite3.Row
     r=facts.execute('SELECT * FROM facts WHERE space=? AND key=?',(owner,memory_key)).fetchone();facts.close()
     if r and r['space'] in spaces:
      text=r['fact']+(' Entité : '+r['entity_id'] if r['entity_id'] else '')+(' Pièce : '+r['area'] if r['area'] else '')
      found={'title':r['label'],'text':text,'version':version(r['label'],text),'space':r['space']}
    if not found or found['version']!=hit['version']:continue
    row={'id':key,'title':found['title'],'body':found['text'],'source':'Souvenir vocal explicite','space':found['space']}
   else:continue
   semantic=True
   if key not in seen:
    scores[key]=scores.get(key,0)+1/(60+len(seen));seen.add(key)
   source[key]=row
   snippets.setdefault(key,[])
   if hit['text'] not in snippets[key]:snippets[key].insert(0,hit['text'])
 except Exception:pass
 chosen=sorted(scores,key=scores.get,reverse=True)[:5]
 return {'semantic':semantic,'sources':[{'id':source[k]['id'],'title':source[k]['title'],'body':'\n[…]\n'.join(snippets[k])[:6000],'source':source[k]['source']} for k in chosen]}
if __name__=='__main__':
 try:print(json.dumps({'ok':True,'data':search(json.load(sys.stdin))}))
 except Exception:print(json.dumps({'ok':False,'error':'Recherche des souvenirs indisponible.'}))
