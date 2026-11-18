import hashlib,json,os,socket,sqlite3,struct,subprocess,tempfile,threading,unittest
from pathlib import Path
from .broker.store import Jobs
from .broker.service import Broker
from .broker.transport import Server
from .broker.isolation import plan,check_uid
from .legacy_repository import LegacyRepository

class FinalTests(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory(prefix='jarvis-6d-final-');self.root=Path(self.tmp.name)
 def tearDown(self):self.tmp.cleanup()
 def test_broker_permissions_idempotence_restart_no_remote_budget(self):
    path=self.root/'jobs.sqlite';jobs=Jobs(path);called=[]
    broker=Broker(jobs,{'alice':{'read':['dose'],'write':['dose']},'bob':{'read':[],'write':[]}},launch=lambda row:called.append(row),authorize=lambda row:True)
    args={'subject':'alice','project':'dose','key':'one','payload':{'question':'synthetic','context':{'space':'user'}}}
    one=broker.call('gateway-human','submit',args);self.assertEqual(one,broker.call('gateway-human','submit',args))
    for service,subject in [('hermes','alice'),('gateway-human','bob')]:
        with self.assertRaises(PermissionError):broker.call(service,'submit',{**args,'subject':subject})
    with self.assertRaises(PermissionError):broker.work(one['id'],approved=True,remote_budget_micros=0)
    self.assertFalse(called)
    with self.assertRaises(PermissionError):jobs.get('bob',one['id'])
    with jobs.db:jobs.db.execute("UPDATE jobs SET state='running' WHERE id=?",(one['id'],))
    jobs.close();jobs=Jobs(path);self.assertEqual(jobs.get('alice',one['id'])['state'],'uncertain');jobs.close()
 def test_cancel_race_claim_does_not_execute(self):
    jobs=Jobs(self.root/'race.sqlite');called=[];broker=Broker(jobs,{'alice':{'read':['dose'],'write':['dose']}},launch=lambda row:called.append(row))
    job=broker.call('gateway-human','submit',{'subject':'alice','project':'dose','key':'race','payload':{'question':'synthetic','context':{}}})['id']
    broker.authorize=lambda row:(jobs.cancel('alice',job),True)[1]
    with self.assertRaises(PermissionError):broker.work(job,approved=True,remote_budget_micros=1)
    self.assertFalse(called);self.assertEqual(jobs.get('alice',job)['state'],'cancelled');jobs.close()
 def test_executor_control_file_cannot_self_authorize(self):
    from .broker.execute import control_file
    control=self.root/'control.json';control.write_text('{"approved":true}');control.chmod(0o600)
    self.assertTrue(control_file(control,{os.getuid()})['approved'])
    with self.assertRaises(PermissionError):control_file(control,{os.getuid()+10000})
    control.chmod(0o666)
    with self.assertRaises(PermissionError):control_file(control,{os.getuid()})
    linked=self.root/'linked.json';linked.symlink_to(control)
    with self.assertRaises(OSError):control_file(linked,{os.getuid()})
 def test_inventory_is_read_only_content_free_and_twenty_total(self):
    from scripts.phase6d_owner_inventory import collect
    first=self.root/'metadata.sqlite';second=self.root/'facts.sqlite'
    with sqlite3.connect(first) as db:
        db.execute('CREATE TABLE docs(id TEXT,space TEXT,updated REAL,kind TEXT,body TEXT,title TEXT)')
        db.executemany('INSERT INTO docs VALUES(?,?,?,?,?,?)',[(str(i),'user',i,'Codex','PRIVATE_CONTENT_SENTINEL','PRIVATE_TITLE_SENTINEL') for i in range(23)])
    with sqlite3.connect(second) as db:db.execute('CREATE TABLE facts(key TEXT,space TEXT,updated REAL,fact TEXT)')
    before=hashlib.sha256(first.read_bytes()).hexdigest();r=collect([(first,'docs','id','kind'),(second,'facts','key',None)])
    self.assertEqual(r['sample_count'],20);self.assertNotIn('PRIVATE_',json.dumps(r));self.assertFalse(r['owners_assigned']);self.assertEqual(hashlib.sha256(first.read_bytes()).hexdigest(),before)
 def test_unix_rpc_real_service_without_model(self):
    jobs=Jobs(self.root/'rpc.sqlite');broker=Broker(jobs,{'alice':{'read':['dose'],'write':['dose']}})
    # SQLite connection belongs to the serving thread in real deployment. In this
    # deterministic test handle one request in the creating thread.
    token='synthetic-'+('x'*40);sock=self.root/'broker.sock';server=Server(sock,broker,{hashlib.sha256(token.encode()).hexdigest():{'service':'gateway-human','subjects':['alice']}})
    result=[]
    def client():
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as s:
            s.connect(str(sock));body=json.dumps({'credential':token,'method':'submit','args':{'subject':'alice','project':'dose','key':'rpc','payload':{'question':'fake','context':{}}}}).encode();s.sendall(struct.pack('!I',len(body))+body)
            data=s.recv(65540);result.append(json.loads(data[4:]))
    thread=threading.Thread(target=client);thread.start();server.handle_request();thread.join();server.server_close();self.assertTrue(result[0]['ok']);jobs.close()
 def test_actual_namespace_blocks_host_files_environment_and_network(self):
    workspace=self.root/'workspace';runtime=self.root/'runtime';workspace.mkdir();runtime.mkdir();outside=self.root/'synthetic-secret';outside.write_text('SYNTHETIC_ONLY');(workspace/'leak').symlink_to(outside)
    command=plan(workspace,runtime,gateway_uid=os.getuid(),executor_uid=os.getuid()+10000)
    prefix=command[:command.index('--')]
    script="""import os,socket,json
assert 'GATEWAY_SENTINEL' not in os.environ
for p in ['/home/user/gateway/.env','/workspace/leak']:
 try:open(p).read();raise AssertionError('host path visible')
 except FileNotFoundError:pass
s=socket.socket();s.settimeout(.2)
try:s.connect(('127.0.0.1',PORT));raise AssertionError('host network reachable')
except OSError:pass
open('/workspace/result.txt','w').write('synthetic')
print(json.dumps({'filesystem_isolated':True,'network_isolated':True,'environment_filtered':True}))
"""
    with socket.socket() as listener:
        listener.bind(('127.0.0.1',0));listener.listen();script=script.replace('PORT',str(listener.getsockname()[1]))
        result=subprocess.run(prefix+['--','/usr/bin/python3','-I','-c',script],env={'PATH':'/usr/bin','GATEWAY_SENTINEL':'FAKE_ONLY'},capture_output=True,text=True,timeout=10)
    self.assertEqual(result.returncode,0,result.stderr);self.assertTrue(json.loads(result.stdout)['filesystem_isolated']);self.assertEqual((workspace/'result.txt').read_text(),'synthetic')
    with self.assertRaises(PermissionError):check_uid(os.getuid(),os.getuid())
 def test_actual_installed_cli_help_inside_namespace_no_inference(self):
    runtime=Path('/home/user/.local/lib/node_modules/@openai/codex/node_modules/@openai/codex-linux-x64/vendor/x86_64-unknown-linux-musl')
    workspace=self.root/'cli';workspace.mkdir()
    command=plan(workspace,runtime,gateway_uid=os.getuid(),executor_uid=os.getuid()+10000);prefix=command[:command.index('--')]
    result=subprocess.run(prefix+['--','/runtime/bin/codex','exec','--help'],env={'PATH':'/usr/bin'},capture_output=True,text=True,timeout=10)
    self.assertEqual(result.returncode,0,result.stderr);self.assertIn('--ignore-user-config',result.stdout)
 def test_provider_policy_zero_budget_and_shared_ceiling(self):
    from .broker.provider import Provider
    calls=[];models={'approved-model':{'output_limit':2048,'input_micros_per_token':1,'output_micros_per_token':1}}
    path=self.root/'cost.sqlite';p=Provider(path,'job-a',models,forward=lambda *a:calls.append(a),authorized=lambda j:True)
    with self.assertRaises(PermissionError):p.request('POST','/v1/responses',{'model':'approved-model'})
    self.assertFalse(calls);p.close()
    p=Provider(path,'job-a',models,budget_micros=10000,forward=lambda *a:{'status':200,'body':'synthetic'},authorized=lambda j:True)
    self.assertEqual(p.request('POST','/v1/responses',{'model':'approved-model'})['status'],200)
    with self.assertRaises(PermissionError):p.request('POST','/v1/responses',{'model':'approved-model','tools':[{'type':'web_search'}]})
    p.close();p=Provider(path,'job-b',models,budget_micros=10000,forward=lambda *a:{},authorized=lambda j:True)
    with self.assertRaises(PermissionError):p.request('POST','/v1/responses',{'model':'approved-model'})
    p.close()
 def test_real_http_unix_relay_with_fake_provider(self):
    from .broker.provider_socket import Server as ProviderServer
    from .broker.relay import server as relay_server,profile
    import urllib.request
    class FakeProvider:
        def request(self,method,path,body):
            if method!='POST' or path!='/v1/responses':raise PermissionError()
            return {'status':200,'type':'text/event-stream','body':'data: synthetic\n\n'}
    sock=self.root/'provider.sock';provider=ProviderServer(sock,FakeProvider());relay=relay_server(str(sock))
    t=threading.Thread(target=provider.handle_request);t.start();rt=threading.Thread(target=relay.serve_forever);rt.start()
    try:
        req=urllib.request.Request('http://127.0.0.1:'+str(relay.server_port)+'/v1/responses',data=b'{"model":"fake"}',headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(req,timeout=2) as response:self.assertEqual(response.read(),b'data: synthetic\n\n')
        self.assertIn('model_provider="jarvis_private"',profile(relay.server_port))
    finally:relay.shutdown();relay.server_close();provider.server_close();t.join();rt.join()
 def test_executor_output_and_time_limits(self):
    from .broker.executor import bounded
    with self.assertRaises(ValueError):bounded(['/usr/bin/python3','-I','-c',"print('x'*100000)"],b'',limit=1000)
    with self.assertRaises(TimeoutError):bounded(['/usr/bin/python3','-I','-c','import time;time.sleep(5)'],b'',seconds=.1)
 def test_existing_document_schema_acl_join_and_atomic_move(self):
    path=self.root/'brain.sqlite'
    with sqlite3.connect(path) as db:
        db.executescript('CREATE TABLE docs(id TEXT PRIMARY KEY,title TEXT,body TEXT,kind TEXT,topic TEXT,status TEXT,source TEXT,updated REAL,fingerprint TEXT,space TEXT);CREATE VIRTUAL TABLE search USING fts5(id UNINDEXED,title,body);')
        db.execute("INSERT INTO docs VALUES('old','Synthétique','fake','Codex','Technique','Source','synthetic://original',1,NULL,'user')")
        db.execute("INSERT INTO search VALUES('old','Synthétique','fake')")
    repo=LegacyRepository(path);migration=repo.migrate();self.assertEqual(migration['backup']['integrity'],'ok');self.assertFalse(repo.migrate()['changed']);self.assertIsNone(repo.metadata('document','old'))
    with self.assertRaises(PermissionError):repo.claim('document','old','alice','user')
    repo.claim('document','old','alice','user',approved=True)
    self.assertEqual(repo.list('document',{'owner':'bob','spaces':['user'],'projects':[]}),[])
    self.assertEqual(repo.get('document','old')['source'],'synthetic://original')
    found=repo.list('document',{'owner':'alice','spaces':['user'],'projects':[],'q':'fake absent'})
    self.assertEqual(found[0]['id'],'old');self.assertEqual(found[0]['preview'],'fake');self.assertNotIn('body',found[0])
    with self.assertRaises(PermissionError):repo.mutate('document','old',{'target':'commun'},{'expectedOwner':'bob','expectedVersion':1})
    repo.mutate('document','old',{'target':'commun'},{'expectedOwner':'alice','expectedVersion':1});self.assertEqual(repo.get('document','old')['space'],'commun')
    created=repo.create('document',{'owner':'alice','space':'user','title':'note','body':'synthétique'});self.assertEqual(repo.get('document',created['id'])['owner'],'alice');repo.close()
if __name__=='__main__':unittest.main()
