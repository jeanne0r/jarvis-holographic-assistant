"""Legacy 384-D map contract, with owner/space/version checks before text access."""
import hashlib,math,time,uuid

def memory_map(storage,subject,space,offset,reader):
 if reader is None:raise RuntimeError('Projection service not configured')
 if offset is not None:
  if isinstance(offset,str) and offset.isdigit():offset=int(offset)
  elif isinstance(offset,str):offset=str(uuid.UUID(offset))
  elif type(offset)!=int or offset<0:raise ValueError('Map cursor')
 grant=storage.grant(subject,'storage.read',space);spaces=sorted({space}|({'commun'} if 'commun' in grant.get('common_read',[]) else set()))
 page=reader(spaces,750,offset);points=page['points'];valid=[]
 if not isinstance(points,list) or len(points)>750:raise ValueError('Map bound')
 axes=[]
 for k in range(3):
  axis=[math.sin((j+1)*(k+1)*1.61803398875) for j in range(384)]
  for previous in axes:
   dot=sum(a*b for a,b in zip(axis,previous));axis=[a-dot*b for a,b in zip(axis,previous)]
  norm=math.sqrt(sum(a*a for a in axis));axes.append([a/norm for a in axis])
 for point in points:
  p=point.get('payload',{});id=p.get('doc_id','');vector=point.get('vector');doc=None
  if not isinstance(vector,list) or len(vector)!=384 or any(type(x) not in (float,int) or not math.isfinite(x) for x in vector):continue
  try:
   if id.startswith('brain:'):
    key=id[6:];meta=storage.owned(subject,'document',key)
    if meta['space'] not in spaces:continue
    row=storage.repo.get('document',key)
    if not row or row['space']!=meta['space']:continue
    doc={'docId':id,'title':row['title'][:200],'text':row['body'],'source':row['source'][:300],'space':row['space'],'topic':row['topic']}
   elif id.startswith('voice:'):
    _,target,key=id.split(':',2)
    import json
    meta=storage.owned(subject,'memory',json.dumps([target,key],ensure_ascii=False))
    if target not in spaces:continue
    row=storage.repo.voice.execute('SELECT * FROM facts WHERE space=? AND key=?',(target,key)).fetchone()
    text=row['fact']+(' Entité : '+row['entity_id'] if row['entity_id'] else '')+(' Pièce : '+row['area'] if row['area'] else '')
    doc={'docId':id,'title':row['label'],'text':text,'source':'Souvenir vocal explicite','space':target,'topic':'Souvenirs'}
  except (PermissionError,TypeError,ValueError):continue
  if not doc or p.get('space')!=doc['space'] or p.get('version')!=hashlib.sha256((doc['title']+'\n'+doc['text']).encode()).hexdigest():continue
  start=p.get('offset',0)
  if type(start)!=int or not 0<=start<=len(doc['text']):continue
  text=doc.pop('text');valid.append({'id':str(point['id']),**doc,'excerpt':text[start:start+480],'position':[round(sum(x*a for x,a in zip(vector,axis)),7) for axis in axes]})
 return {'points':valid,'sampled':len(valid),'scanned':len(points),'nextOffset':page.get('next_offset'),'indexedPoints':None,'documents':len({p['docId'] for p in valid}),'spaces':spaces,'projection':'Projection orthogonale 3D stable','checkedAt':time.time(),'note':'Références, propriétaires, espaces et versions revérifiés dans SQLite.'}

def qdrant_reader(base,key,collection,*,transport=None):
 """Read-only scroll endpoint. No create/delete/prune/index operations exist here."""
 import ipaddress,json,urllib.parse,urllib.request
 url=urllib.parse.urlsplit(base)
 if url.scheme not in ('http','https') or url.path not in ('','/') or url.query or url.fragment or url.username or url.password or not ipaddress.ip_address(url.hostname).is_private:raise ValueError('Pinned private literal Qdrant origin')
 if collection not in ('jarvis_memory_v1','jarvis_knowledge_experimental_v1') or not isinstance(key,str) or not key:raise ValueError('Reviewed Qdrant collection/credential')
 endpoint=base.rstrip('/')+'/collections/'+collection+'/points/scroll'
 def reader(spaces,limit,offset):
  if limit!=750:raise ValueError('Bounded legacy page')
  body={'filter':{'must':[{'key':'space','match':{'any':spaces}}]},'limit':limit,'with_payload':True,'with_vector':True,**({'offset':offset} if offset is not None else {})}
  if transport is not None:result=transport(endpoint,body)
  else:
   # Ignore ambient proxy settings; redirects cannot change the credential target.
   class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args):return None
   opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
   req=urllib.request.Request(endpoint,method='POST',headers={'api-key':key,'content-type':'application/json'},data=json.dumps(body).encode())
   with opener.open(req,timeout=10) as r:
    raw=r.read(16*1024**2+1)
    if len(raw)>16*1024**2:raise ValueError('Index response bound')
    result=json.loads(raw)['result']
  return {'points':result['points'],'next_offset':result.get('next_page_offset')}
 return reader
