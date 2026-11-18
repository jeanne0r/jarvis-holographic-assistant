"""Synthetic integration. SQLite/HTTP are real; vectors, GPU and Hermes are fakes."""
import hashlib
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
import urllib.request
import urllib.error
from memory_manager.store import Memory, Principal, digest
from memory_manager.phase2 import database as p2, skill_registry
from memory_manager.phase2.memory_tools import MemoryTools
from memory_manager.phase2.local_model import Unavailable
from memory_manager.phase2.test_integration import WORKER, HUMAN, OTHER
from memory_manager.phase2.bridge import Bridge
from memory_manager.api import server
from memory_manager.phase5 import database, vector, skills, import_plan
from memory_manager.phase5.api import extension
from memory_manager.phase5.embedding_endpoint import Provider, attach

ART='a'*64
SPEC={'name':'doselab_freshness','version':1,'description':'Synthetic flow/freshness review',
      'allowed_tools':['memory.search','report'],'checks':['flow','freshness']}


class FakeEmbeddings:
    """Deliberately constant vectors: proves plumbing, never semantic quality."""
    def __init__(self):self.calls=[]
    def __call__(self,method,path,body=None,**kwargs):
        self.calls.append((method,path,body))
        return {'model':vector.MODEL,'artifact_sha256':ART,'dimensions':384,'kind':body['kind'],
                'input_tokens':len(body['input'].encode())+2,'data':[{'embedding':[1.0]+[0.0]*383}]}


class FakeQdrant:
    def __init__(self):self.points={};self.calls=[];self.status='completed';self.offline=False
    def __call__(self,method,path,body=None,**kwargs):
        self.calls.append((method,path,body))
        assert path.startswith('/collections/'+vector.COLLECTION)
        if self.offline:raise Unavailable('fake outage')
        if method=='GET':return {'result':{'config':{'params':{'vectors':{'distance':'Cosine','size':384}}}}}
        if method=='PUT':
            assert path.endswith('wait=true')
            for point in body['points']:self.points[point['id']]=point
            return {'status':'ok','result':{'status':self.status}}
        return {'result':{'points':[{'payload':p['payload']} for p in self.points.values()]}}


class Phase5(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'memory.sqlite'
        self.m=Memory(self.path,create=True);p2.migrate(self.m);self.backup=database.migrate(self.m)
        self.eq=FakeEmbeddings();self.q=FakeQdrant();self.e=vector.Embeddings(self.eq,ART);self.d=vector.Qdrant(self.q)
    def tearDown(self):self.m.close();self.tmp.cleanup()
    def put(self,content=None,principal=WORKER,**extra):
        return self.m.ingest(principal,'event-'+str(time.time_ns()),{'kind':'user','ref':'synthetic://phase5','observed_at':time.time()},
            [{'type':'knowledge','subject':'DoseLab','predicate':'cells','content':content or {'kg':[1,1,1,1]},'status':'user_confirmed',**extra}])[0]
    def current(self,mid):return next(r for r in self.m.current(WORKER) if r['memory_id']==mid)
    def index(self,**kw):return vector.index(self.m,WORKER,self.d,self.e,**kw)
    def search(self,q='aucunmot',p=WORKER):return vector.search(self.m,p,q,self.d,self.e)
    def test_backup_additive_idempotent(self):
        self.assertTrue(self.backup['changed']);self.assertFalse(database.migrate(self.m)['changed'])
        self.assertTrue(list(self.path.parent.glob('*.before-phase5-*')))
    def test_index_idempotent_and_stable_rebuild(self):
        self.put();self.assertGreater(self.index()['upserted'],0);ids=set(self.q.points)
        self.assertEqual(self.index()['upserted'],0);self.assertGreater(self.index(rebuild=True)['upserted'],0)
        self.assertEqual(ids,set(self.q.points));self.assertEqual(self.search()[0]['content'],{'kg':[1,1,1,1]})
    def test_crash_ack_reopen_no_duplicate(self):
        self.put()
        def crash(_):raise RuntimeError('simulated kill after acknowledgement')
        with self.assertRaises(RuntimeError):self.index(interrupt=crash)
        ids=set(self.q.points);self.m.close();self.m=Memory(self.path);self.index()
        self.assertEqual(ids,set(self.q.points));self.assertEqual(self.index()['upserted'],0)
    def test_noncompleted_ack_has_no_checkpoint(self):
        self.put();self.q.status='acknowledged'
        with self.assertRaises(Unavailable):self.index()
        self.assertEqual(self.m.db.execute('SELECT count(*) FROM p5_index_ack').fetchone()[0],0)
    def test_correction_rejects_stale_remote_revision(self):
        mid=self.put({'kg':[1,2,5,10]});self.index();old=self.current(mid)['id']
        self.put({'kg':[1,1,1,1]},correction_of=mid,expected_revision=old)
        self.assertEqual(self.search(),[]);self.index()
        self.assertEqual(self.search()[0]['content']['kg'],[1,1,1,1]);self.assertEqual(len(self.m.history(WORKER,mid)),2)
    def test_remote_payload_cannot_forge_acl_or_content(self):
        self.put(principal=OTHER);vector.index(self.m,OTHER,self.d,self.e)
        for p in self.q.points.values():p['payload'].update(owner='alice',content={'invented':True})
        self.assertEqual(self.search(),[])
    def test_disputed_and_expired_not_independent_evidence(self):
        self.put({'kg':[1]});self.put({'kg':[2]});self.index()
        self.assertEqual(self.q.points,{}) # contradictory accepted candidates not indexed
        rows=self.search('DoseLab');self.assertTrue(all(r['effective_status']=='disputed' for r in rows))
        self.assertTrue(all(r['evidence_kind']=='unverified_or_disputed' for r in rows))
        self.put({'old':True},predicate='expired',valid_from=1,valid_to=2);self.index()
        self.assertFalse(any(r['content'].get('old') for r in self.search('DoseLab')))
    def test_logical_hide_restore_and_acl(self):
        mid=self.put();self.index()
        with self.assertRaises(PermissionError):database.visibility(self.m,WORKER.__class__(WORKER.name,WORKER.scopes,{'reader'}),mid,hidden=True,reason='test',key='x')
        database.visibility(self.m,HUMAN,mid,hidden=True,reason='review',key='hide')
        database.visibility(self.m,HUMAN,mid,hidden=True,reason='review',key='hide')
        self.assertEqual(self.search(),[]);self.assertEqual(self.index()['upserted'],0)
        database.visibility(self.m,HUMAN,mid,hidden=False,reason='restore',key='restore')
        self.assertEqual(len(self.search()),1);self.assertGreater(len(self.q.points),0)
    def test_many_chunks_do_not_inflate_document_rank(self):
        best=self.put({'result':'best semantic match'})
        other=self.put({'result':'secondary'},predicate='secondary')
        for i,mid in enumerate([best]+[other]*8):
            self.q.points[str(i)]={'payload':{'memory_id':mid,'revision':self.current(mid)['id'],
                'embedding_model':vector.MODEL,'embedding_artifact_sha256':ART,'payload_schema':1}}
        self.assertEqual(self.search()[0]['memory_id'],best)

    def test_fts_fallback_and_wrong_pipeline(self):
        self.put();self.q.offline=True;rows=self.search('DoseLab')
        self.assertEqual(rows[0]['retrieval_mode'],'fts_only_degraded')
        self.q.offline=False
        bad=vector.Embeddings(lambda *a,**k:{'model':'wrong'},ART)
        self.assertEqual(vector.search(self.m,WORKER,'DoseLab',self.d,bad)[0]['retrieval_mode'],'fts_only_degraded')
    def test_collection_vector_and_bounds(self):
        with self.assertRaises(PermissionError):self.d.path('jarvis_memory_v1')
        for v in ([0.0]*384,[True]*384,[float('inf')]*384,[1]*383):
            with self.assertRaises(ValueError):vector.validate_vector(v)
        with self.assertRaises(ValueError):self.index(max_points=1001)
        self.put({'text':'é'*500});self.assertFalse(self.index(max_points=1)['complete']);self.index()
        self.assertTrue(all(len(c[2]['input'].encode())<=96 for c in self.eq.calls))
        self.assertTrue(all('text' not in p['payload'] for p in self.q.points.values()))
    def test_injection_security_regressions(self):
        untrusted=Principal('alice',WORKER.scopes,{'reader','proposer'},'hermes-alice')
        tools=MemoryTools(self.m,untrusted)
        for name in ('shell','execute_physical','memory.validate','skill.publish','home_assistant.call','budget.change'):
            with self.assertRaises(PermissionError):tools.call(name,{'shell_authorized':True,'execute_physical':True})
        for privilege in ({'execute_physical':True},{'shell_authorized':True}):
            with self.assertRaises((PermissionError,ValueError)):
                tools.call('memory.propose',{'key':'evil','reference':'synthetic://external','candidate':{'type':'knowledge','subject':'DoseLab','predicate':'injection','content':privilege,'status':'verified'}})
        with self.assertRaises(PermissionError):skill_registry.publish(self.m,untrusted,'doselab_freshness',1)
        with self.assertRaises(PermissionError):skill_registry.propose(self.m,untrusted,{**SPEC,'allowed_tools':['shell']},['fake'])
    def test_extended_skills_and_release_remains_candidate(self):
        mid=self.put();skill_registry.propose(self.m,WORKER,SPEC,[mid]);self.assertTrue(skills.evaluate(SPEC)['passed'])
        prepared=skills.prepare_release(self.m,HUMAN,SPEC['name'],1)
        self.assertFalse(prepared['publication_authorized']);self.assertFalse(prepared['execution_authorized'])
        self.assertEqual(skill_registry.get(self.m,WORKER,SPEC['name'],1)['state'],'candidate')
        self.assertFalse(skills.evaluate({**SPEC,'checks':['flow']})['passed'])
        with self.assertRaises(PermissionError):skills.prepare_release(self.m,WORKER,SPEC['name'],1)
        self.put({'kg':[2,2,2,2]},correction_of=mid,expected_revision=self.current(mid)['id'])
        with self.assertRaises(ValueError):skills.prepare_release(self.m,HUMAN,SPEC['name'],1)
    def test_dry_run_import_provenance_dedup_contradiction(self):
        base={'source_db':'synthetic','table':'facts','id':'1','space':'legacy','observed_at':1000,'type':'knowledge','subject':'DoseLab','predicate':'cells','content':{'kg':1},'speaker':'user','replaces':None}
        rows=[base,{**base,'id':'2'},{**base,'id':'3','content':{'kg':2},'speaker':'assistant','replaces':'1'}]
        result=import_plan.plan(rows,{'legacy':('alice','private')})
        self.assertEqual(result['writes'],0);self.assertEqual(result['counts']['duplicate'],1)
        self.assertEqual(result['contradiction_candidates'],3)
        self.assertTrue(all(i['proposed_status']=='inferred' and not i['automatic_supersession'] for i in result['items']))
        with self.assertRaises(PermissionError):import_plan.plan(rows,{})
    def test_provider_pin_and_context_no_model_load(self):
        p=Path(self.tmp.name)/'fake.onnx';p.write_bytes(b'synthetic weights');files={str(p):hashlib.sha256(p.read_bytes()).hexdigest()};runtime={'fastembed':'fake'}
        artifact=digest({'model':vector.MODEL,'files':files,'runtime':runtime,'preprocessing':'fastembed-document/query-v1;max128;no-truncation'})
        class Model:
            def embed(self,values):return [[1]+[0]*383]
            query_embed=embed
        provider=Provider(model=Model(),lock=threading.Lock(),token_count=lambda text,kind:len(text)+2,
            files=files,runtime=runtime,loaded_onnx=p,expected_manifest=artifact)
        self.assertEqual(provider.embed({'model':vector.MODEL,'input':'test','kind':'query'})['input_tokens'],6)
        with self.assertRaises(ValueError):provider.embed({'model':vector.MODEL,'input':'x'*200,'kind':'query'})
        self.assertFalse(attach(None,None))
        p.write_bytes(b'changed')
        with self.assertRaises(ValueError):Provider(model=Model(),lock=threading.Lock(),token_count=lambda *_:1,files=files,runtime=runtime,loaded_onnx=p,expected_manifest=artifact)
    def test_historical_startup_readonly_guard(self):
        import ast
        import contextlib
        from unittest.mock import patch
        source=(Path(__file__).resolve().parents[2]/'semantic'/'service.py').read_text()
        node=next(n for n in ast.parse(source).body if isinstance(n,ast.AsyncFunctionDef) and n.name=='lifespan')
        class Model:
            def embed(self,_):return [1]
        calls=[]
        namespace={'asynccontextmanager':contextlib.asynccontextmanager,'TextEmbedding':lambda *a,**k:Model(),
                   'MODEL':vector.MODEL,'COLLECTION':'jarvis_memory_v1','os':__import__('os'),
                   'qdrant':lambda *a:calls.append(a),'urllib':__import__('urllib')}
        exec(compile(ast.Module(body=[node],type_ignores=[]),'<synthetic-startup>','exec'),namespace)
        import asyncio
        async def run():
            async with namespace['lifespan'](None):pass
        with patch.dict('os.environ',{'JARVIS_EMBEDDINGS_READONLY_STARTUP':'1','JARVIS_EXPERIMENTAL_EMBEDDINGS':'0'}):asyncio.run(run())
        self.assertEqual(calls,[('/collections/jarvis_memory_v1',)])
        calls.clear()
        with patch.dict('os.environ',{'JARVIS_EMBEDDINGS_READONLY_STARTUP':'0','JARVIS_EXPERIMENTAL_EMBEDDINGS':'1'}):
            with self.assertRaises(RuntimeError):asyncio.run(run())
        self.assertEqual(calls,[])

    def test_frozen_qwen_unsafe_claims_cannot_grant_capabilities(self):
        evidence=json.loads((Path(__file__).resolve().parents[2]/'docs'/'JARVIS_2_PHASE3_QWEN4B_REAL.json').read_text())
        failed=[case for case in evidence['cases'] if case['case'] in {'permissions','injection_tool_result'}]
        self.assertEqual(len(failed),2)
        tools=MemoryTools(self.m,Principal('alice',WORKER.scopes,{'reader','proposer'},'hermes-alice'))
        for case in failed:
            self.assertFalse(case['passed'])
            capability='execute_physical' if case['case']=='permissions' else 'shell_authorized'
            self.assertIs(case['actual'][capability],True)
            with self.assertRaises(PermissionError):tools.call('home_assistant.call' if capability=='execute_physical' else 'shell',case['actual'])

    def test_api_mcp_hybrid_e2e_synthetic_restart(self):
        mid=self.put();self.index()
        token='synthetic-token-not-a-secret';clients={hashlib.sha256(token.encode()).hexdigest():{'name':WORKER.name,'scopes':list(WORKER.scopes),'roles':list(WORKER.roles),'actor_id':WORKER.actor}}
        srv=server(self.path,clients,extension=extension(self.d,self.e));thread=threading.Thread(target=srv.serve_forever,daemon=True);thread.start()
        def post(path,body,key=None):
            headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'}
            if key:headers['Idempotency-Key']=key
            req=urllib.request.Request('http://127.0.0.1:'+str(srv.server_address[1])+path,data=json.dumps(body).encode(),headers=headers)
            with urllib.request.urlopen(req,timeout=3) as r:return r.status,json.load(r)
        try:
            definition={'objective':'Synthetic DoseLab learning','trigger':'test','priority':1,'memory_context':[],'plan':['read','report'],
              'allowed_tools':['memory.search','memory.propose','report'],'budget':{'tokens':0,'cost_micros':0,'seconds':120,'attempts':1}}
            status,admitted=post('/v1/missions',{'definition':definition},'e2e')
            self.assertEqual(status,202);mission=admitted['mission_id']
            from memory_manager import missions
            missions.transition(self.m,WORKER,mission,'queued','planning')
            missions.transition(self.m,WORKER,mission,'planning','running')
            result=post('/v1/tools/call',{'name':'memory.search','arguments':{'q':'aucunmot'}})[1]['result']
            self.assertEqual(result[0]['memory_id'],mid);self.assertEqual(result[0]['retrieval_mode'],'semantic_and_fts')
            post('/v1/tools/call',{'name':'skill.propose','arguments':{'spec':SPEC,'sources':[mid]}})
            self.assertTrue(skill_registry.assess(self.m,WORKER,SPEC['name'],1)['passed'])
            self.assertTrue(skills.prepare_release(self.m,HUMAN,SPEC['name'],1)['evaluation']['passed'])
            post('/v1/missions/'+mission+'/result',{'summary':'Synthetic emulator read current sources; candidate evaluated'})
            missions.transition(self.m,WORKER,mission,'running','testing')
            missions.transition(self.m,WORKER,mission,'testing','completed',{'synthetic_agent':True,'skill_state':'candidate'})
        finally:srv.shutdown();thread.join();srv.server_close()
        self.m.close();self.m=Memory(self.path)
        self.assertEqual(skill_registry.get(self.m,WORKER,SPEC['name'],1)['state'],'candidate')
        experiences=self.m.search(WORKER,'Synthetic',memory_type='episode')
        self.assertTrue(experiences);self.assertEqual(experiences[0]['usage'],'analogy_only')
        self.assertEqual(Bridge(self.m,WORKER).submit('e2e',definition),mission)
        self.assertEqual(Bridge(self.m,WORKER).get(mission)['state'],'completed')
        later=Bridge(self.m,WORKER).submit('e2e-later',{**definition,'objective':'Reuse a synthetic experience in a different mission'})
        self.assertNotEqual(later,mission)
        # New Python process, fresh Memory connection; no model or service launch.
        import subprocess,sys
        code="from memory_manager.store import Memory; from memory_manager.phase2.test_integration import WORKER; from memory_manager.phase2.skill_registry import get; import sys; m=Memory(sys.argv[1]); assert get(m,WORKER,'doselab_freshness',1)['state']=='candidate'; assert m.search(WORKER,'Synthetic',memory_type='episode');m.close()"
        subprocess.run([sys.executable,'-c',code,str(self.path)],check=True,timeout=5)


if __name__=='__main__':unittest.main()
