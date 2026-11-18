"""Resumable experimental index, read-only fallback and canonical ACL validation."""
import hashlib
import math
import uuid
from ..store import encode, digest
from ..consolidate import plan_index
from ..phase2.vector import COLLECTION, MODEL, Qdrant as BaseQdrant
from ..phase2.local_model import Unavailable
from .database import require, hidden_ids


def validate_vector(vector):
    if (not isinstance(vector,list) or len(vector)!=384 or any(type(v) not in (int,float) or not math.isfinite(v) for v in vector)
            or not 0 < sum(v*v for v in vector) < float('inf')): raise ValueError('Finite nonzero 384D vector required')
    return vector


class Embeddings:
    def __init__(self, transport, artifact_sha256):
        if len(artifact_sha256)!=64 or any(c not in '0123456789abcdef' for c in artifact_sha256): raise ValueError('Pinned pipeline manifest required')
        self.http,self.artifact=transport,artifact_sha256

    def __call__(self,text,*,kind='document',timeout=15):
        if kind not in {'query','document'} or not isinstance(text,str) or not 0<len(text.encode())<=8000: raise ValueError('Embedding input')
        r=self.http('POST','/v1/embeddings',{'model':MODEL,'input':text,'kind':kind},timeout=min(15,timeout))
        if (r.get('model')!=MODEL or r.get('artifact_sha256')!=self.artifact or r.get('dimensions')!=384
                or r.get('kind')!=kind or type(r.get('input_tokens')) is not int or not 0<r['input_tokens']<=128):
            raise ValueError('Embedding model, artifact, preprocessing or context mismatch')
        if len(r.get('data',[]))!=1: raise ValueError('One embedding expected')
        return validate_vector(r['data'][0]['embedding'])


class Qdrant(BaseQdrant):
    def upsert(self,collection,point,*,timeout=15):
        validate_vector(point['vector'])
        r=self.http('PUT',self.path(collection)+'/points?wait=true',{'points':[point]},timeout=min(15,timeout))
        if r.get('status')!='ok' or r.get('result',{}).get('status')!='completed': raise Unavailable('Durable Qdrant acknowledgement required')

    def hits(self,vector,principal,artifact):
        validate_vector(vector)
        if not principal.scopes:return []
        r=self.http('POST',self.path(COLLECTION)+'/points/query',{'query':vector,'limit':100,'with_payload':True,'with_vector':False,
            'filter':{'must':[{'key':'scope','match':{'any':sorted(principal.scopes)}},
                {'key':'embedding_model','match':{'value':MODEL}}, {'key':'embedding_artifact_sha256','match':{'value':artifact}},
                {'key':'payload_schema','match':{'value':1}}],
                'should':[{'key':'owner','match':{'value':principal.name}}, {'key':'scope','match':{'except':['private']}}]}},timeout=10)
        return [x.get('payload',{}) for x in r['result']['points'][:100]]


def chunks(text,maximum=96):
    """UTF-8 byte bound leaves headroom under 128 WordPiece tokens, checked again by endpoint."""
    part=''
    for char in text:
        if len((part+char).encode())>maximum:
            yield part;part=''
        part+=char
    if part:yield part


def index(memory,principal,driver,embeddings,*,rebuild=False,max_points=100,seconds=10,interrupt=None):
    principal.require('indexer');require(memory)
    if not 1<=max_points<=1000 or not 0<seconds<=30:raise ValueError('Index bounds')
    import time
    deadline=time.monotonic()+seconds
    if driver.dimensions(COLLECTION)!=384:raise ValueError('Collection mismatch')
    hidden=hidden_ids(memory);written=skipped=0
    for row in sorted(plan_index(memory,principal),key=lambda r:(r['memory_id'],r['revision'])):
        if row['memory_id'] in hidden:continue
        for i,text in enumerate(chunks(row['text'])):
            pid=str(uuid.uuid5(uuid.NAMESPACE_URL,':'.join([COLLECTION,embeddings.artifact,row['memory_id'],row['revision'],str(i)])))
            payload={k:row[k] for k in ('memory_id','revision','owner','scope')}
            payload.update(payload_schema=1,chunk=i,content_sha256=hashlib.sha256(row['text'].encode()).hexdigest(),
                embedding_model=MODEL,embedding_artifact_sha256=embeddings.artifact)
            ack=memory.db.execute('SELECT payload_hash FROM p5_index_ack WHERE collection=? AND artifact=? AND point_id=?',(COLLECTION,embeddings.artifact,pid)).fetchone()
            if ack and ack[0]==digest(payload) and not rebuild:skipped+=1;continue
            if written>=max_points or time.monotonic()>=deadline:return {'upserted':written,'skipped':skipped,'complete':False,'deleted':0}
            # Recheck canonical revision/visibility just before a remote write. A correction
            # racing after this check is still rejected during retrieval.
            current={x['memory_id']:x for x in memory.current(principal)}
            if (row['memory_id'] not in current or current[row['memory_id']]['id']!=row['revision']
                    or current[row['memory_id']]['effective_status'] not in {'verified','user_confirmed'} or row['memory_id'] in hidden_ids(memory)):continue
            remaining=deadline-time.monotonic()
            if remaining<=0:return {'upserted':written,'skipped':skipped,'complete':False,'deleted':0}
            v=embeddings(text,kind='document',timeout=remaining)
            remaining=deadline-time.monotonic()
            if remaining<=0:return {'upserted':written,'skipped':skipped,'complete':False,'deleted':0}
            driver.upsert(COLLECTION,{'id':pid,'vector':v,'payload':payload},timeout=remaining)
            if interrupt:interrupt(pid)  # Crash after remote acknowledgement, before checkpoint.
            with memory.db:
                memory.db.execute('INSERT INTO p5_index_ack VALUES(?,?,?,?) ON CONFLICT(collection,artifact,point_id) DO UPDATE SET payload_hash=excluded.payload_hash',
                    (COLLECTION,embeddings.artifact,pid,digest(payload)))
            written+=1
    return {'upserted':written,'skipped':skipped,'complete':True,'deleted':0}


def search(memory,principal,query,driver,embeddings,**filters):
    require(memory);principal.require('reader')
    hits=[];state='semantic_and_fts'
    try:
        raw=driver.hits(embeddings(query,kind='query'),principal,embeddings.artifact) if query else []
        # One rank contribution per canonical revision, regardless of chunk count.
        # Qdrant already orders chunks by score; keep the best one only.
        seen=set()
        for p in raw:
            if p.get('embedding_model')!=MODEL or p.get('embedding_artifact_sha256')!=embeddings.artifact or p.get('payload_schema')!=1:continue
            ref=(p.get('memory_id'),p.get('revision'))
            if ref in seen:continue
            seen.add(ref);hits.append(p)
    except (Unavailable,ValueError,KeyError,TimeoutError,OSError):state='fts_only_degraded'
    # Text/content/owner claimed by Qdrant are never returned. Memory.search rereads
    # current revision, ACL, validity and contradiction status for every candidate.
    rows=memory.search(principal,query,vector_hits=hits,exclude_ids=hidden_ids(memory),**filters)
    for row in rows:
        row['retrieval_mode']=state
        row['evidence_kind']='independent_evidence' if row['effective_status']=='verified' else 'user_statement' if row['effective_status']=='user_confirmed' else 'unverified_or_disputed'
    return rows
