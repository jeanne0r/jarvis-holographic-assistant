import json,tempfile,unittest,sqlite3
from pathlib import Path
from ..store import Memory,Principal
from ..phase2.database import migrate as old_migrate
from ..phase2.bridge import Bridge
from ..phase3 import lab
from . import evidence,heartbeat,database

class SecurityTests(unittest.TestCase):
 def setUp(self):
    self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'lab.sqlite';self.m=Memory(self.path,create=True);old_migrate(self.m);self.migration=database.migrate(self.m);self.ids=lab.seed(self.m)
    self.host=Principal(lab.OWNER,frozenset({'private'}),lab.HOST.roles|{'reader','mission_worker','mission_writer','evidence_writer','worker_supervisor'},'controller')
    self.caller=Principal(lab.OWNER,frozenset({'private'}),frozenset({'reader','mission_worker'}),'model-tools')
    self.reporter=Principal(lab.OWNER,frozenset({'private'}),frozenset({'reader','worker_reporter'}),'monitor')
    self.definition={'objective':'Synthetic security','trigger':'offline','priority':1,'memory_context':[],'plan':['read'],'allowed_tools':['memory.search','report'],'budget':{'tokens':0,'cost_micros':0,'seconds':30,'attempts':1}}
    self.mid=Bridge(self.m,self.host).submit('one',self.definition)
 def tearDown(self):self.m.close();self.tmp.cleanup()
 def test_authenticated_http_evidence_and_heartbeat(self):
    import hashlib,threading,urllib.request,urllib.error
    from ..api import server
    from .api import extension
    clients={}
    def client(token,p):clients[hashlib.sha256(token.encode()).hexdigest()]={'name':p.name,'scopes':list(p.scopes),'roles':list(p.roles),'actor_id':p.actor}
    client('synthetic-model',self.caller);client('synthetic-host',self.host);client('synthetic-monitor',self.reporter)
    epoch=heartbeat.register(self.m,self.host,'windows','monitor')
    srv=server(self.path,clients,extension=extension({self.caller.actor:self.host}));thread=threading.Thread(target=srv.serve_forever,daemon=True);thread.start()
    def call(path,token=None,body=None):
        headers={'Content-Type':'application/json'}
        if token:headers['Authorization']='Bearer '+token
        req=urllib.request.Request('http://127.0.0.1:'+str(srv.server_port)+path,headers=headers,data=json.dumps(body).encode() if body is not None else None)
        try:
            with urllib.request.urlopen(req,timeout=2) as r:return r.status,json.loads(r.read())
        except urllib.error.HTTPError as e:return e.code,json.loads(e.read())
    try:
        path='/v1/missions/'+self.mid
        self.assertEqual(call(path+'/canonical')[0],401)
        code,data=call(path+'/tools/read','synthetic-model',{'name':'memory.history','arguments':{'memory_id':self.ids['configuration_memory_id']}});self.assertEqual(code,200);self.assertTrue(data['receipt_id'])
        code,data=call(path+'/canonical','synthetic-model');self.assertEqual(code,200);self.assertEqual(data['projection']['selection_origin'],'authenticated_host_tool_receipts')
        self.assertEqual(call(path+'/tools/read','synthetic-model',{'name':'skill.publish','arguments':{}})[0],403)
        self.assertEqual(call('/v1/workers/windows/heartbeat','synthetic-model',{'epoch':epoch,'sequence':1,'state':'ready'})[0],403)
        self.assertEqual(call('/v1/workers/windows/heartbeat','synthetic-monitor',{'epoch':epoch,'sequence':1,'state':'gpu_busy'})[0],200)
        code,data=call('/v1/workers/windows/status','synthetic-host');self.assertEqual(code,200);self.assertFalse(data['dispatch_allowed'])
    finally:srv.shutdown();srv.server_close();thread.join()
 def test_worker_stale_busy_and_unknown_never_dispatch(self):
    from .worker import tick
    from unittest.mock import Mock
    heartbeat.register(self.m,self.host,'windows','monitor');client=Mock();telemetry=Mock()
    info=tick(self.m,self.host,self.mid,'windows',client,telemetry,approved=True)
    self.assertEqual(info['state'],'queued');self.assertFalse(info['worker_availability']['fresh']);self.assertFalse(client.mock_calls);self.assertFalse(telemetry.mock_calls)
    self.m.db.execute("UPDATE p2_outbox SET state='unknown' WHERE mission_id=?",(self.mid,));self.m.db.commit()
    self.m.close();self.m=Memory(self.path)
    info=tick(self.m,self.host,self.mid,'windows',client,telemetry,approved=True)
    self.assertEqual(info['dispatch_state'],'unknown');self.assertFalse(client.mock_calls)
    with self.assertRaises(PermissionError):tick(self.m,self.host,self.mid,'windows',client,telemetry)
 def test_verified_backup_restore_and_idempotence(self):
    self.assertFalse(database.migrate(self.m)['changed'])
    backup=Path(self.migration['backup']['path'])
    restored=self.path.parent/'restore.sqlite'
    import shutil
    shutil.copyfile(backup,restored)
    with sqlite3.connect(restored) as db:
        self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
        self.assertFalse(db.execute("SELECT 1 FROM sqlite_master WHERE name='p6d_receipts'").fetchone())
 def test_real_authorized_history_receipt_and_restart(self):
    result,rid=evidence.ObservedTools(self.m,self.host,self.caller,self.mid).call('memory.history',{'memory_id':self.ids['configuration_memory_id']})
    self.assertEqual(len(result),2)
    self.m.close();self.m=Memory(self.path)
    p=evidence.metadata(self.m,self.host,self.mid,[rid]);self.assertEqual(p['selection_origin'],'authenticated_host_tool_receipts')
    self.assertEqual([r['observed_utc'] for r in p['items']],['2023-11-14T22:13:20Z','2023-11-14T22:15:00Z']);self.assertFalse(p['promotion_performed'])
    with self.assertRaises(sqlite3.IntegrityError):self.m.db.execute('DELETE FROM p6d_receipts WHERE id=?',(rid,))
 def test_forged_receipt_wrong_mission_and_model_authority_denied(self):
    with self.assertRaises(PermissionError):evidence.ObservedTools(self.m,self.caller,self.caller,self.mid)
    with self.assertRaises(PermissionError):evidence.metadata(self.m,self.host,self.mid,['forged'])
    _,rid=evidence.ObservedTools(self.m,self.host,self.caller,self.mid).call('memory.history',{'memory_id':self.ids['configuration_memory_id']})
    second=Bridge(self.m,self.host).submit('two',self.definition)
    with self.assertRaises(PermissionError):evidence.metadata(self.m,self.host,second,[rid])
    other=Principal('other',frozenset({'private'}),self.host.roles,'other')
    with self.assertRaises(PermissionError):evidence.metadata(self.m,other,self.mid,[rid])
 def test_search_receipt_revision_binding(self):
    rows,rid=evidence.ObservedTools(self.m,self.host,self.caller,self.mid).call('memory.knowledge',{'q':'DoseLab'})
    self.assertTrue(rows)
    projection=evidence.metadata(self.m,self.host,self.mid,[rid]);self.assertTrue(projection['items'])
    self.assertEqual({r['revision_id'] for r in projection['items']},{r.get('revision_id',r.get('id')) for r in rows})
 def test_heartbeat_expiry_replay_busy_and_restart(self):
    epoch=heartbeat.register(self.m,self.host,'windows','monitor')
    heartbeat.observe(self.m,self.reporter,'windows',epoch,1,'ready',now=100)
    self.assertTrue(heartbeat.status(self.m,self.host,'windows',now=101)['dispatch_allowed'])
    self.assertFalse(heartbeat.status(self.m,self.host,'windows',now=131)['dispatch_allowed'])
    with self.assertRaises(ValueError):heartbeat.observe(self.m,self.reporter,'windows',epoch,1,'ready',now=102)
    heartbeat.observe(self.m,self.reporter,'windows',epoch,2,'gpu_busy',now=102)
    self.m.close();self.m=Memory(self.path)
    self.assertFalse(heartbeat.status(self.m,self.host,'windows',now=103)['dispatch_allowed'])
    new=heartbeat.register(self.m,self.host,'windows','monitor');self.assertNotEqual(new,epoch)
    with self.assertRaises(PermissionError):heartbeat.observe(self.m,self.reporter,'windows',epoch,3,'ready',now=104)
    with self.assertRaises(PermissionError):heartbeat.observe(self.m,self.caller,'windows',new,1,'ready',now=104)
    self.assertFalse(heartbeat.status(self.m,self.host,'windows',now=105)['automatic_replay'])
if __name__=='__main__':unittest.main()
