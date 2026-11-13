"""Read-only paginated Qdrant points, validated against canonical SQLite, projected locally."""
import json,math,pathlib,sqlite3,sys,time,urllib.request,urllib.parse,socket,os
from documents import ROOT,documents
SPACES={'member1','member2','member3','member4','shared'}

def project(vectors,iterations=18):
 if not vectors:return []
 d=len(vectors[0]);n=len(vectors)
 if not d or d>2048 or any(len(v)!=d or not all(math.isfinite(x) for x in v) for v in vectors):raise ValueError('Vecteurs invalides.')
 mean=[sum(row[j] for row in vectors)/n for j in range(d)]
 rows=[[x-mean[j] for j,x in enumerate(row)] for row in vectors]
 axes=[]
 def unit(v):
  for axis in axes:
   dot=sum(a*b for a,b in zip(v,axis));v=[a-dot*b for a,b in zip(v,axis)]
  norm=math.sqrt(sum(x*x for x in v));return [x/norm for x in v] if norm>1e-10 else [0.]*d
 for k in range(3):
  w=unit([math.sin((j+1)*(k+1)*1.61803398875) for j in range(d)])
  for _ in range(iterations):
   scores=[sum(a*b for a,b in zip(row,w)) for row in rows];next_w=[0.]*d
   for row,score in zip(rows,scores):
    for j,value in enumerate(row):next_w[j]+=value*score
   w=unit(next_w)
  if w and w[max(range(d),key=lambda j:abs(w[j]))]<0:w=[-x for x in w]
  axes.append(w)
 coordinates=[[sum(a*b for a,b in zip(row,axis)) for axis in axes] for row in rows]
 scale=max((abs(v) for row in coordinates for v in row),default=1) or 1
 return [[round(v/scale,6) for v in row] for row in coordinates]

def fetch_sample(spaces,limit,offset=None):
 base=os.environ.get('QDRANT_URL','http://127.0.0.1:6333').rstrip('/')+'/collections/jarvis_memory_v1/points/'
 key=os.environ.get('QDRANT__SERVICE__API_KEY','')
 if not key:raise RuntimeError('Qdrant is not configured')
 def request(path,body):
  req=urllib.request.Request(base+path,method='POST',headers={'api-key':key,'content-type':'application/json'},data=json.dumps(body).encode())
  with urllib.request.urlopen(req,timeout=10) as r:return json.load(r)['result']
 filt={'must':[{'key':'space','match':{'any':spaces}}]}
 result=request('scroll',{'filter':filt,'limit':limit,'with_payload':True,'with_vector':True,**({'offset':offset} if offset is not None else {})})
 count=request('count',{'filter':filt,'exact':True})['count'] if offset is None else None
 return result['points'],count,result.get('next_page_offset')

def validate_points(points,canonical,spaces):
 valid=[]
 for point in points:
  payload=point.get('payload',{});doc=canonical.get(payload.get('doc_id'))
  if not doc or doc['space'] not in spaces or payload.get('space')!=doc['space'] or payload.get('version')!=doc['version']:continue
  vector=point.get('vector')
  if not isinstance(vector,list) or len(vector)!=384 or not all(isinstance(x,(float,int)) and math.isfinite(x) for x in vector):continue
  offset=payload.get('offset',0)
  if not isinstance(offset,int) or not 0<=offset<=len(doc['text']):continue
  valid.append(({'id':str(point['id']),'docId':doc['doc_id'],'title':doc['title'],'space':doc['space'],'source':doc['source'],'excerpt':doc['text'][offset:offset+480],'topic':doc.get('topic','Souvenirs')},vector))
 return valid

def memory_map(data):
 space=data.get('space','member1')
 if space not in SPACES:raise ValueError('Espace inconnu.')
 offset=data.get('offset')
 if offset is not None:
  if isinstance(offset,str) and offset.isdigit():offset=int(offset)
  elif isinstance(offset,str):
   import uuid
   offset=str(uuid.UUID(offset))
  elif not isinstance(offset,int) or isinstance(offset,bool) or offset<0:raise ValueError('Curseur invalide.')
 spaces=sorted({space,'shared'});points,total,next_offset=fetch_sample(spaces,750,offset)
 canonical={d['doc_id']:d for d in documents() if d['space'] in spaces}
 db=sqlite3.connect('file:'+str(ROOT/'data/brain.sqlite')+'?mode=ro',uri=True)
 for doc_id,topic in db.execute('SELECT id,topic FROM docs WHERE space IN ('+','.join('?' for _ in spaces)+')',spaces):
  if 'brain:'+doc_id in canonical:canonical['brain:'+doc_id]['topic']=topic
 db.close()
 valid=validate_points(points,canonical,spaces)
 # A deterministic orthogonal projection keeps pages in the same coordinate system.
 # No truncated sample and no quadratic PCA over all embeddings in the request.
 axes=[]
 for k in range(3):
  axis=[math.sin((j+1)*(k+1)*1.61803398875) for j in range(384)]
  for previous in axes:
   dot=sum(a*b for a,b in zip(axis,previous));axis=[a-dot*b for a,b in zip(axis,previous)]
  norm=math.sqrt(sum(a*a for a in axis));axes.append([a/norm for a in axis])
 coords=[[round(sum(x*a for x,a in zip(v,axis)),7) for axis in axes] for _,v in valid]
 return {'points':[{**p,'position':xyz} for (p,_),xyz in zip(valid,coords)],'sampled':len(valid),'scanned':len(points),'nextOffset':next_offset,'indexedPoints':total,'documents':len({p['docId'] for p,_ in valid}),'spaces':spaces,'projection':'Projection orthogonale 3D stable','checkedAt':time.time(),'note':'Tous les extraits courants sont parcourus par pages. Projection 3D approximative : la proximité visuelle ne conserve pas toutes les distances sémantiques.'}
if __name__=='__main__':
 try:print(json.dumps({'ok':True,'data':memory_map(json.load(sys.stdin))}))
 except Exception:print(json.dumps({'ok':False,'error':'La carte Qdrant est indisponible. Réessaie dans un instant.'}))
