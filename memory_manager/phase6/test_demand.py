"""On-demand queue + existing controller/lifecycle protocols, all synthetic."""
import copy,hashlib,json,sqlite3,tempfile,time,unittest
from pathlib import Path
from contextlib import closing
from unittest.mock import Mock
from memory_manager.store import Memory,Principal
from memory_manager.phase3.lab import OWNER,HOST,seed
from memory_manager.phase2 import database
from memory_manager.phase2.bridge import Bridge
from memory_manager.phase6.operational import definition,TEXT_PREFIX
from memory_manager.phase6.demand_queue import Queue,migrate
from memory_manager.phase6.memory_audit import audit
from scripts.demand_supervisor import Supervisor

class DemandTests(unittest.TestCase):
 def setUp(self):
    self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'test.sqlite';self.m=Memory(self.path,create=True);database.migrate(self.m);self.ids=seed(self.m);migrate(self.m)
    self.clock=[time.time()];roles=frozenset({'reader','mission_writer','mission_worker'})
    self.host=Principal(OWNER,frozenset({'private'}),roles,'host')
    self.panel=Principal(OWNER,frozenset({'private'}),frozenset({'reader','mission_writer'}),'interactive-panel')
    self.supervisor=Principal(OWNER,frozenset({'private'}),frozenset({'queue_supervisor'}),'on-demand-supervisor')
    self.q=Queue(self.m,self.host,accepting=True,execution=True,clock=lambda:self.clock[0])
 def tearDown(self):self.m.close();self.tmp.cleanup()
 def admit(self,key='x'):
    return self.q.admit(self.panel,key,{'scope':'private','definition':definition(TEXT_PREFIX+'Analyse fictive DoseLab Ω '+key)})['mission_id']
 def test_queue_idempotence_capacity_expiry_and_restart(self):
    mid=self.admit();self.assertEqual(mid,self.admit())
    for i in range(9):self.admit(str(i))
    with self.assertRaises(ValueError):self.admit('too-many')
    self.assertEqual(self.q.peek(self.supervisor)['mission_id'],mid)
    self.m.close();self.m=Memory(self.path);self.q=Queue(self.m,self.host,accepting=True,execution=True,clock=lambda:self.clock[0]);self.q.recover()
    self.assertEqual(self.q.peek(self.supervisor)['mission_id'],mid)
    self.clock[0]+=86401;self.q.expire();self.assertIsNone(self.q.peek(self.supervisor));self.assertEqual(Bridge(self.m,self.host).get(mid)['state'],'cancelled')
 def test_single_execution_and_uncertain_restart_never_replayed(self):
    a=self.admit('a');b=self.admit('b');lease=self.q.reserve(self.supervisor,a)
    with self.assertRaises(PermissionError):self.q.reserve(self.supervisor,b)
    self.q.recover();self.assertEqual(Bridge(self.m,self.host).get(a)['state'],'paused')
    with self.assertRaises(PermissionError):self.q.reserve(self.supervisor,b)
    self.assertTrue(self.q.finish(self.supervisor,lease['lease'],False)['quarantined'])
 def test_completed_result_preserved_and_cleanup_required(self):
    a=self.admit();lease=self.q.reserve(self.supervisor,a)
    with self.m.db:
     self.m.db.execute("UPDATE mm_missions SET state='completed' WHERE id=?",(a,));self.m.db.execute("UPDATE p2_outbox SET state='completed' WHERE mission_id=?",(a,))
    self.q.recover();self.assertEqual(Bridge(self.m,self.host).get(a)['state'],'completed')
    self.assertTrue(self.q.finish(self.supervisor,lease['lease'],True)['released']);self.assertEqual(Bridge(self.m,self.host).get(a)['state'],'completed')
    b=self.admit('b');self.assertEqual(self.q.reserve(self.supervisor,b)['mission_id'],b)
 def test_authority_tool_injection_and_maintenance(self):
    bad=Principal('other',frozenset({'private'}),self.panel.roles,'interactive-panel')
    for p in [bad,self.supervisor]:
     with self.assertRaises(PermissionError):self.q.admit(p,'bad',{'scope':'private','definition':definition(TEXT_PREFIX+'test')})
    with self.assertRaises(PermissionError):self.q.reserve(self.panel,self.admit())
    d=definition(TEXT_PREFIX+'test');d['allowed_tools'].append('shell')
    with self.assertRaises(PermissionError):self.q.admit(self.panel,'bad',{'scope':'private','definition':d})
    self.q.accepting=False
    with self.assertRaises(PermissionError):self.admit('maintenance')
    self.q.accepting=True;mid=self.admit('offline');self.q.execution=False
    with self.assertRaises(PermissionError):self.q.reserve(self.supervisor,mid)
 def test_supervisor_defers_without_leasing_or_model_and_no_retry_uncertain(self):
    mid=self.admit();calls=[]
    def http(method,path,data=None):
     calls.append(path)
     if path.endswith('next'):return {'job':self.q.peek(self.supervisor)}
     if path.endswith('defer'):self.q.defer(self.supervisor,data['mission_id'],data['reason']);return {}
     if path.endswith('reserve'):return self.q.reserve(self.supervisor,data['mission_id'])
     return self.q.finish(self.supervisor,data['lease'],data['cleanup_ok'])
    run=Mock(return_value={'cleanup_verified':False})
    for reason in ['windows_offline','gpu_busy','miner_active','insufficient_vram']:
     s=Supervisor(http,lambda:reason,run,clock=lambda:self.clock[0]);self.assertEqual(s.tick()['state'],'waiting');self.clock[0]+=31
    run.assert_not_called();self.assertNotIn('/v1/queue/reserve',calls)
    s=Supervisor(http,lambda:None,run,clock=lambda:self.clock[0]);self.assertEqual(s.tick()['state'],'uncertain');run.assert_called_once()
    self.clock[0]+=31;s.tick();run.assert_called_once();self.assertEqual(Bridge(self.m,self.host).get(mid)['state'],'paused')
 def test_memory_audit_is_read_only_sources_and_not_topic_deduplication(self):
    before=list(self.m.db.iterdump());r=audit(self.m,self.host,'DoseLab')
    self.assertEqual(before,list(self.m.db.iterdump()));self.assertEqual(r['mutations_performed'],0)
    self.assertEqual(set(r['source_refs']),{'synthetic://doselab/old','synthetic://doselab/correction','synthetic://doselab/experience'})
    self.assertEqual(len(r['duplicate_candidates']),0);self.assertEqual(r['contradictions'][0]['kind'],'replaced_history_not_unresolved_conflict')
    self.assertTrue(all(p['source_refs'] for p in r['proposals']))
 def test_similar_reports_not_identical_and_vector_revalidation_acl(self):
    for i in range(2):self.m.ingest(HOST,'extra-'+str(i),{'kind':'external','ref':'mission://synthetic-'+str(i),'observed_at':time.time()-100+i},[{'type':'episode','subject':'DoseLab X4','predicate':'report','content':{'summary':'Quatre cellules ; conclusion identique'},'status':'inferred'}])
    r=audit(self.m,self.host,'DoseLab');self.assertEqual(r['duplicate_candidates'][0]['kind'],'similarity_candidate');self.assertFalse(r['duplicate_candidates'][0]['provenance_equal'])
    other=Principal('other',frozenset({'private'}),frozenset({'reader'}),'other')
    with self.assertRaises(PermissionError):audit(self.m,other,'DoseLab',searcher=lambda q:[{'memory_id':self.ids['configuration_memory_id'],'source':{'ref':'forged'}}])

 def test_daily_quota_and_atomic_idempotent_admission(self):
    for i in range(12):
     mid=self.admit('quota-'+str(i));lease=self.q.reserve(self.supervisor,mid)
     Bridge(self.m,self.host).cancel(mid);self.q.finish(self.supervisor,lease['lease'],True)
    with self.assertRaises(PermissionError):self.q.reserve(self.supervisor,self.admit('over-quota'))
    import concurrent.futures
    def submit(_):
     with closing(Memory(self.path)) as memory:
      return Queue(memory,self.host,accepting=True).admit(self.panel,'parallel',{'scope':'private','definition':definition(TEXT_PREFIX+'Fictif concurrent')})['mission_id']
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:ids=list(pool.map(submit,range(2)))
    self.assertEqual(ids[0],ids[1])
 def test_unresolved_contradictions_expired_and_unverified_sources(self):
    for i in range(2):self.m.ingest(HOST,'conflict-'+str(i),{'kind':'user','ref':'synthetic://doselab/conflict-'+str(i),'observed_at':time.time()-10},[{'type':'knowledge','subject':'DoseLab X4','predicate':'voltage','content':{'volts':12+i},'status':'user_confirmed'}])
    self.m.ingest(HOST,'expired',{'kind':'external','ref':'synthetic://doselab/expired','observed_at':10},[{'type':'knowledge','subject':'DoseLab X4','predicate':'expired','content':{'example':True},'status':'inferred','valid_from':10,'valid_to':20}])
    before=list(self.m.db.iterdump());r=audit(self.m,self.host,'DoseLab')
    self.assertTrue(any(x['kind']=='unresolved' for x in r['contradictions']))
    self.assertTrue(any('outside_validity_period' in x['reasons'] for x in r['proposals']))
    self.assertTrue(any('not_independently_verified' in x['reasons'] for x in r['proposals']))
    self.assertEqual(before,list(self.m.db.iterdump()))
 def test_existing_hybrid_vector_driver_is_read_only_and_canonical(self):
    from memory_manager.phase5 import database as p5,vector
    from memory_manager.phase5.test_memory import FakeQdrant,FakeEmbeddings,ART
    from memory_manager.phase6.memory_audit import hybrid_searcher
    p5.migrate(self.m)
    p=Principal(OWNER,frozenset({'private'}),HOST.roles|{'indexer'},'synthetic-index-fixture')
    transport=FakeQdrant();driver=vector.Qdrant(transport);embeddings=vector.Embeddings(FakeEmbeddings(),ART)
    vector.index(self.m,p,driver,embeddings);transport.calls.clear()
    retrieve=hybrid_searcher(driver,embeddings);before=list(self.m.db.iterdump())
    result=audit(self.m,self.host,'aucunmot',searcher=lambda q:retrieve(self.m,self.host,q))
    self.assertIn('synthetic://doselab/correction',result['source_refs'])
    self.assertEqual(before,list(self.m.db.iterdump()));self.assertTrue(transport.calls)
    self.assertTrue(all(method!='PUT' for method,_,_ in transport.calls))

 def test_reconnect_changed_key_same_exact_intent_and_no_key_reuse(self):
    data={'scope':'private','definition':definition(TEXT_PREFIX+'Même demande synthétique')}
    first=self.q.admit(self.panel,'before-loss',data)['mission_id']
    self.assertEqual(first,self.q.admit(self.panel,'after-reconnect',data)['mission_id'])
    self.assertEqual(self.m.db.execute('SELECT count(*) FROM mm_missions').fetchone()[0],1)
    with self.assertRaises(ValueError):self.q.admit(self.panel,'after-reconnect',{'scope':'private','definition':definition(TEXT_PREFIX+'Autre intention')})
    with self.m.db:
     self.m.db.execute("UPDATE mm_missions SET state='completed' WHERE id=?",(first,))
     self.m.db.execute("UPDATE p2_outbox SET state='completed' WHERE mission_id=?",(first,))
    self.assertEqual(first,self.q.admit(self.panel,'new-device-key',data)['mission_id'])
