"""Private local semantic index. SQLite remains the canonical source."""
import hashlib,hmac,json,os,threading,uuid,urllib.request,urllib.error
from contextlib import asynccontextmanager
from fastapi import FastAPI,HTTPException,Request,Depends
from fastembed import TextEmbedding
from pydantic import BaseModel,Field
MODEL='sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
COLLECTION='jarvis_memory_v1'
KEY=os.environ['QDRANT__SERVICE__API_KEY']
lock=threading.Lock();model=None

def qdrant(path,method='GET',body=None):
 req=urllib.request.Request(os.environ.get('QDRANT_URL','http://127.0.0.1:6333')+path,method=method,headers={'api-key':KEY,'content-type':'application/json'},data=json.dumps(body).encode() if body is not None else None)
 with urllib.request.urlopen(req,timeout=90) as r:return json.load(r).get('result')

@asynccontextmanager
async def lifespan(app):
 global model
 model=TextEmbedding(MODEL,cache_dir=os.environ.get('JARVIS_MODEL_CACHE','./data/models'),threads=2)
 list(model.embed(['Mémoire locale Jarvis.']))
 try:qdrant('/collections/'+COLLECTION)
 except urllib.error.HTTPError as e:
  if e.code!=404:raise
  qdrant('/collections/'+COLLECTION,'PUT',{'vectors':{'size':384,'distance':'Cosine','on_disk':True},'on_disk_payload':True,'optimizers_config':{'default_segment_number':2},'hnsw_config':{'on_disk':True,'m':16,'ef_construct':100}})
 for field in ['space','doc_id','version']:
  qdrant('/collections/'+COLLECTION+'/index?wait=true','PUT',{'field_name':field,'field_schema':'keyword'})
 yield
app=FastAPI(lifespan=lifespan,docs_url=None,redoc_url=None,openapi_url=None)

def authorize(req:Request):
 if not hmac.compare_digest(req.headers.get('x-jarvis-key',''),KEY):raise HTTPException(403,'Accès refusé.')
class Document(BaseModel):
 doc_id:str=Field(max_length=200)
 space:str=Field(pattern='^(member1|member2|member3|member4|shared)$')
 version:str=Field(max_length=64)
 title:str=Field(max_length=200)
 text:str=Field(max_length=250000)
 source:str=Field(max_length=300)
class Query(BaseModel):
 query:str=Field(min_length=1,max_length=2000)
 space:str=Field(pattern='^(member1|member2|member3|member4|shared)$')
 include_common:bool=False
 limit:int=Field(default=12,ge=1,le=30)
class Keep(BaseModel):
 ids:list[str]=Field(max_length=20000)

def chunks(text):
 start=0
 while start<len(text):
  end=min(start+400,len(text))
  if end<len(text):
   split=max(text.rfind('\n',start+230,end),text.rfind(' ',start+230,end))
   if split>start:end=split
  part=text[start:end].strip()
  if part:yield start,part
  if end==len(text):break
  start=max(start+1,end-60)

@app.get('/health',dependencies=[Depends(authorize)])
def health():
 info=qdrant('/collections/'+COLLECTION)
 return {'ready':True,'model':MODEL,'collection':COLLECTION,'points':info.get('points_count',0)}

@app.post('/index',dependencies=[Depends(authorize)])
def index(doc:Document):
 if hashlib.sha256((doc.title+'\n'+doc.text).encode()).hexdigest()!=doc.version:raise HTTPException(400,'Empreinte invalide.')
 parts=list(chunks(doc.text))
 for start in range(0,len(parts),64):
  batch=parts[start:start+64]
  with lock:vectors=list(model.embed([doc.title+'\n'+text for _,text in batch],batch_size=32))
  points=[{'id':str(uuid.uuid5(uuid.NAMESPACE_URL,doc.doc_id+':'+doc.version+':'+str(offset))),'vector':v.tolist(),'payload':{'doc_id':doc.doc_id,'space':doc.space,'version':doc.version,'title':doc.title,'text':text,'offset':offset,'source':doc.source}} for (offset,text),v in zip(batch,vectors)]
  qdrant('/collections/'+COLLECTION+'/points?wait=true','PUT',{'points':points})
 qdrant('/collections/'+COLLECTION+'/points/delete?wait=true','POST',{'filter':{'must':[{'key':'doc_id','match':{'value':doc.doc_id}}],'must_not':[{'key':'version','match':{'value':doc.version}}]}})
 return {'indexed':len(parts),'doc_id':doc.doc_id,'version':doc.version}

@app.post('/search',dependencies=[Depends(authorize)])
def search(query:Query):
 with lock:vector=list(model.query_embed([query.query]))[0].tolist()
 spaces=list(set([query.space]+(['shared'] if query.include_common else [])))
 result=qdrant('/collections/'+COLLECTION+'/points/query','POST',{'query':vector,'filter':{'must':[{'key':'space','match':{'any':spaces}}]},'limit':query.limit,'with_payload':True,'with_vector':False})
 return {'hits':[{'score':p['score'],**p['payload']} for p in result['points']]}

@app.post('/prune',dependencies=[Depends(authorize)])
def prune(keep:Keep):
 if not keep.ids:raise HTTPException(400,'Liste vide refusée.')
 qdrant('/collections/'+COLLECTION+'/points/delete?wait=true','POST',{'filter':{'must_not':[{'key':'doc_id','match':{'any':keep.ids}}]}})
 return {'ok':True}
