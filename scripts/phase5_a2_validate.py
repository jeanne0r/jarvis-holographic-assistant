"""Explicit A2 synthetic service validation. Does not start Hermes/Ollama or import personal data."""
import argparse
import json
import os
from pathlib import Path
import time
import uuid

from memory_manager.store import Memory,Principal
from memory_manager.phase2 import database as p2,skill_registry
from memory_manager.phase2.memory_tools import MemoryTools
from memory_manager.phase5 import database,vector
from memory_manager.phase5.ssh_transport import CT205

ROOT=Path(__file__).resolve().parents[1]
OWNER=Principal('phase5-a2-synthetic',frozenset({'private'}),frozenset({'reader','proposer','ingester','indexer','reviewer'}),'a2-test-host')
OTHER=Principal('phase5-a2-other',frozenset({'private'}),OWNER.roles,'a2-other')


def main():
    p=argparse.ArgumentParser();p.add_argument('--approved-a2',action='store_true');p.add_argument('--private-state',required=True);p.add_argument('--artifact',required=True)
    args=p.parse_args()
    if not args.approved_a2:raise PermissionError('A2 authorization required')
    os.umask(0o077)
    folder=ROOT/'data/phase5/a2'/('validation-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+'-'+uuid.uuid4().hex[:8]);folder.mkdir(mode=0o700)
    identity='/home/user/.ssh/proxmox_codex';known='/home/user/.ssh/known_hosts'
    q=vector.Qdrant(CT205('qdrant',args.private_state,identity=identity,known_hosts=known))
    e=vector.Embeddings(CT205('embedding',args.private_state,identity=identity,known_hosts=known),args.artifact)
    m=Memory(folder/'memory.sqlite',create=True);p2.migrate(m);database.migrate(m)
    report={'mode':'real embeddings and Qdrant; synthetic canonical data; no Hermes/generative-model/Windows calls','folder':str(folder),'checks':{},'events':[],'started_at':time.time()}
    def current(mid):return next(r for r in m.current(OWNER) if r['memory_id']==mid)
    def put(key,content,**kw):
        return m.ingest(OWNER,key,{'kind':'user','ref':'synthetic://a2/'+key,'observed_at':time.time()},[
            {'type':'knowledge','subject':'DoseLab X4','predicate':'load_cells','status':'user_confirmed','content':content,**kw}])[0]
    def finish_index(**kwargs):
        for _ in range(20):
            result=vector.index(m,OWNER,q,e,seconds=15,**kwargs);report['events'].append(result)
            if result['complete']:return result
        raise RuntimeError('Index resume bound')
    try:
        mid=put('old',{'description':'Les cellules du DoseLab ont des capacités différentes.','capacities_kg':[1,2,5,10]})
        first=vector.index(m,OWNER,q,e,max_points=1,seconds=15);report['events'].append(first)
        report['checks']['bounded_batch']=not first['complete']
        # Simulated interruption at the real remote-ack / local-checkpoint boundary.
        class Interruption(RuntimeError):pass
        def interrupt(_):raise Interruption('Synthetic interruption')
        try:vector.index(m,OWNER,q,e,seconds=15,interrupt=interrupt)
        except Interruption:pass
        before=q.http('GET',q.path(vector.COLLECTION),timeout=5)['result']['points_count']
        m.close();m=Memory(folder/'memory.sqlite');finish_index()
        count=q.http('GET',q.path(vector.COLLECTION),timeout=5)['result']['points_count']
        stable=finish_index();count2=q.http('GET',q.path(vector.COLLECTION),timeout=5)['result']['points_count']
        report['checks']['resume_idempotent']=stable['upserted']==0 and count==count2
        old_revision=current(mid)['id']
        put('correction',{'description':'Les quatre cellules de pesée sont identiques et supportent un kilogramme chacune.','capacities_kg':[1,1,1,1]},
            correction_of=mid,expected_revision=old_revision)
        report['checks']['history_preserved']=len(m.history(OWNER,mid))==2
        stale_hits=q.hits(e('masse nominale identique',kind='query'),OWNER,e.artifact)
        report['checks']['stale_vector_rejected']=not m.search(OWNER,'zzznomatch',vector_hits=stale_hits)
        # Unrelated accepted memories make this more than a one-document lookup.
        for key,subject,text in [('network','Réseau du laboratoire','Connexion réseau privée par tunnel chiffré.'),
                                 ('backup','Sauvegarde de laboratoire','Copie de fichiers avec vérification des empreintes.')]:
            m.ingest(OWNER,'distractor-'+key,{'kind':'user','ref':'synthetic://a2/'+key,'observed_at':time.time()},
                [{'type':'knowledge','subject':subject,'predicate':'description','content':{'texte':text},'status':'user_confirmed'}])
        finish_index()
        query='masse nominale identique'
        # This exact query has no FTS matches; the new result must come from vectors.
        lexical=m.search(OWNER,query)
        semantic=vector.search(m,OWNER,query,q,e)
        report['retrieval']={'query':query,'fts_count':len(lexical),'returned':[{'memory_id':r['memory_id'],'revision':r['id'],'content':r['content'],'source':r['source'],'effective_status':r['effective_status'],'retrieval_mode':r['retrieval_mode']} for r in semantic]}
        report['checks']['real_semantic_without_fts']=not lexical and bool(semantic) and semantic[0]['memory_id']==mid
        report['checks']['current_correction']=semantic[0]['content']['capacities_kg']==[1,1,1,1]
        report['checks']['cross_user_denied']=not vector.search(m,OTHER,query,q,e)
        searcher=lambda mm,pp,qq,**kw:vector.search(mm,pp,qq,q,e,**kw)
        report['checks']['controlled_tool_same_result']=MemoryTools(m,OWNER,searcher=searcher).call('memory.search',{'q':query})[0]['memory_id']==mid
        database.visibility(m,OWNER,mid,hidden=True,reason='synthetic logical deletion',key='hide')
        report['checks']['logical_delete']=all(r['memory_id']!=mid for r in vector.search(m,OWNER,query,q,e))
        database.visibility(m,OWNER,mid,hidden=False,reason='synthetic visibility restore',key='restore')
        report['checks']['logical_restore']=vector.search(m,OWNER,query,q,e)[0]['memory_id']==mid
        before_rebuild=q.http('GET',q.path(vector.COLLECTION),timeout=5)['result']['points_count']
        # Small synthetic fixture fits within one bounded explicit rebuild batch.
        rebuild=vector.index(m,OWNER,q,e,rebuild=True,seconds=30)
        after_rebuild=q.http('GET',q.path(vector.COLLECTION),timeout=5)['result']['points_count']
        report['checks']['rebuild_same_ids']=rebuild['complete'] and rebuild['upserted']>0 and before_rebuild==after_rebuild
        m.close();m=Memory(folder/'memory.sqlite')
        recovered=vector.search(m,OWNER,query,q,e)
        report['checks']['fresh_sqlite_connection']=recovered[0]['content']['capacities_kg']==[1,1,1,1]
        report['qdrant_points_final']=after_rebuild;report['old_point_count_after_interruption']=before
        report['passed']=all(report['checks'].values())
    except Exception as exc:
        report['passed']=False;report['error_class']=type(exc).__name__
    finally:
        m.close();report['finished_at']=time.time();(folder/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))


if __name__=='__main__':main()
