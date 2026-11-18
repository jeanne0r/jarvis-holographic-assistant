import ast,base64,hashlib,io,json,pathlib,sqlite3,tempfile,unittest,uuid,zipfile
from .persistence import Persistence,ROOT
from .storage_service import Storage

def fixture(brain,voice):
 # DDL comes from the actual legacy source, never from a live database.
 for target,source in [(brain,'store.py'),(voice,'voice-memory.py')]:
  with sqlite3.connect(target) as db:
   for n in ast.walk(ast.parse((ROOT/source).read_text())):
    if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr in ('execute','executescript') and n.args and isinstance(n.args[0],ast.Constant) and isinstance(n.args[0].value,str):
     sql=n.args[0].value
     if sql.startswith('CREATE TABLE IF NOT EXISTS') or sql.startswith('''CREATE TABLE IF NOT EXISTS docs'''):db.executescript(sql)
   if source=='store.py':db.execute("ALTER TABLE docs ADD COLUMN space TEXT NOT NULL DEFAULT 'user'")

class PersistentTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=pathlib.Path(self.tmp.name);self.brain=self.root/'brain.sqlite';self.voice=self.root/'voice.sqlite';fixture(self.brain,self.voice)
  self.repo=Persistence(self.brain,self.voice);self.addCleanup(self.repo.close);self.repo.migrate()
  self.policy={u:{'permissions':['storage.read','storage.write'],'spaces':['user','commun'],'write_spaces':['user'],'project_read':['dose'],'project_write':['dose'],'common_read':['commun']} for u in ['alice','bob']}
  self.storage=Storage(self.repo,self.policy,staging=self.root,json_files={})
 def call(self,method,**args):return self.storage.call('gateway-storage',method,{'subject':'alice','space':'user',**args})
 def test_actual_schema_documents_archive_revisions_owner_restart(self):
  sid=str(uuid.uuid4());d={'id':sid,'channel':'written','turn':0,'revision':1,'user':'Cellules identiques : 1 kg','assistant':'','status':'partial'}
  self.call('conversation.record',data=d)
  self.call('conversation.record',data={**d,'revision':2,'assistant':'Confirmé comme déclaration','status':'complete'})
  self.assertTrue(self.call('conversation.record',data=d)['duplicate'])
  with self.assertRaises(PermissionError):self.storage.call('gateway-storage','conversation.record',{'subject':'bob','space':'user','data':{**d,'revision':3}})
  self.assertEqual(self.repo.db.execute('SELECT count(*) FROM g_conversation_revisions').fetchone()[0],1)
  row=self.call('get',kind='document',id='jarvis:'+sid+':0');self.assertIn('1 kg',row['body']);self.assertEqual(row['owner'],'alice')
  db=sqlite3.connect(self.brain);self.assertEqual(db.execute('SELECT revision FROM conversation_turns').fetchone()[0],2);db.close()
  reopened=Persistence(self.brain,self.voice)
  try:self.assertEqual(reopened.get('document',row['id'])['source'],row['source'])
  finally:reopened.close()
 def test_facts_unclaimed_denied_history_and_logical_forget(self):
  with self.repo.voice:self.repo.voice.execute('INSERT INTO facts VALUES(?,?,?,?,?,?,?)',('user','ancien','Ancien','Privé',None,None,1))
  self.assertEqual(self.call('facts'),[])
  with self.assertRaises(PermissionError):self.call('fact.save',data={'key':'ancien','fact':'Écrasement'})
  self.call('fact.save',data={'key':'cellule de pesée','fact':'1 kg'})
  self.call('fact.save',data={'key':'cellule de pesée','fact':'Correction : 2 kg'})
  rows=self.call('facts');self.assertEqual(rows[0]['status'],'inferred')
  self.call('fact.forget',data={'key':'cellule de pesée'});self.assertEqual(self.call('facts'),[])
  self.assertEqual(self.repo.voice.execute('SELECT count(*) FROM g_fact_revisions').fetchone()[0],3)
  self.assertEqual(self.repo.voice.execute('SELECT count(*) FROM facts').fetchone()[0],2)
 def test_native_chatgpt_json_and_zip_import_idempotent_sources_dates(self):
  c={'id':'synthetic','title':'Étalonnage','update_time':1234567890,'mapping':{'one':{'parent':None,'message':{'author':{'role':'user'},'content':{'parts':['Quatre cellules de 1 kg.']}}}},'current_node':'one'}
  p=self.root/'fixture.upload';p.write_text(json.dumps([c]));self.repo.ingest('alice','user',p)
  self.assertEqual(self.repo.ingest('alice','user',p)['imported'],0)
  row=self.repo.get('document','chatgpt:synthetic');self.assertEqual(row['updated'],1234567890);self.assertIn('synthetic',row['source'])
  with zipfile.ZipFile(p,'w') as z:z.writestr('conversations.json',json.dumps([c]))
  self.assertEqual(self.repo.ingest('alice','user',p)['imported'],0)
  with self.assertRaises(PermissionError):self.repo.ingest('bob','user',p)
  self.assertEqual(self.repo.get('document','chatgpt:synthetic')['owner'],'alice')
 def test_stream_upload_wrong_owner_offset_and_transaction_rollback(self):
  raw=json.dumps([{'id':'x','mapping':{},'current_node':None}]).encode();u=self.call('upload.begin',size=len(raw))['upload']
  with self.assertRaises(PermissionError):self.storage.call('gateway-storage','upload.abort',{'subject':'bob','space':'user','upload':u})
  with self.assertRaises(ValueError):self.call('upload.chunk',upload=u,offset=1,chunk=base64.b64encode(raw).decode())
  self.call('upload.chunk',upload=u,offset=0,chunk=base64.b64encode(raw).decode());self.assertEqual(self.call('upload.finish',upload=u)['imported'],0)
  self.assertFalse((self.root/(u+'.upload')).exists())
 def test_sync_configured_only_and_existing_unknown_never_adopted(self):
  p=self.root/'note.md';p.write_text('# Configuration\n'+'Mesure synthétique vérifiée. '*4)
  self.storage.sync_sources={'alice':{'user':[str(p)]}}
  self.assertEqual(self.call('sync')['changed'],1);self.assertEqual(self.call('sync')['changed'],0)
  p.unlink();p.symlink_to(self.brain)
  with self.assertRaises(PermissionError):self.call('sync')
 def test_json_chat_format_backups_filter_accounts_and_reopen(self):
  p=self.root/'dose.json';p.write_text('[{"id":"m","role":"user","text":"Bonjour"}]')
  self.storage.json_files={'chat:dose':str(p)}
  self.repo.claim('service-account','chat:dose','alice','user','dose',approved=True)
  self.assertEqual(self.call('chat.read',project='dose')[0]['text'],'Bonjour')
  with self.assertRaises(PermissionError):self.storage.call('gateway-storage','chat.clear',{'subject':'bob','space':'user','project':'dose'})
  self.call('chat.clear',project='dose');self.assertEqual(json.loads(p.read_text()),[])
  backups=list(self.root.glob('dose.json.before-*'));self.assertEqual(len(backups),1);self.assertIn('Bonjour',backups[0].read_text())
 def test_auxiliary_tasks_and_fridge_use_actual_json_shapes(self):
  tasks=self.root/'mirror-tasks.json';tasks.write_text('[]');fridge=self.root/'fridge-stock.json';fridge.write_text(json.dumps({'items':[{'id':'mine','barcode':'123','status':'in_fridge'},{'id':'other','barcode':'999','status':'in_fridge'}],'products':{'123':{'name':'Synthétique'},'999':{'name':'Non autorisé'}},'events':[{'itemId':'mine'},{'itemId':'other'}]}))
  self.storage.json_files={'tasks':str(tasks),'fridge':str(fridge)}
  for id in ['tasks','fridge']:self.repo.claim('service-account',id,'alice','user',approved=True)
  self.repo.claim('fridge-item','mine','alice','user',approved=True);self.repo.claim('fridge-item','other','bob','user',approved=True)
  created=self.call('tasks.change',id='tasks',action='POST',data={'title':'Vérifier','person':'amelie'})['task']
  self.assertEqual(self.repo.metadata('task',created['id'])['owner'],'alice')
  self.assertEqual(self.call('tasks.list',id='tasks')['tasks'][0]['id'],created['id'])
  self.call('tasks.change',id='tasks',action='PATCH',data={'id':created['id'],'done':True})
  self.assertTrue(json.loads(tasks.read_text())[0]['done'])
  result=self.call('fridge.list',id='fridge');self.assertEqual([r['id'] for r in result['items']],['mine']);self.assertEqual(set(result['products']),{'123'});self.assertEqual(len(result['events']),1)
 def test_semantic_map_revalidates_acl_versions_and_legacy_shape(self):
  from .projection import qdrant_reader
  mine=self.call('create',kind='document',data={'space':'user','title':'Actuel','body':'Quatre cellules identiques.'})
  other=self.storage.call('gateway-storage','create',{'subject':'bob','space':'user','kind':'document','data':{'space':'user','title':'Privé','body':'Autre projet.'}})
  def point(row,version=None):return {'id':row['id'],'payload':{'doc_id':'brain:'+row['id'],'space':'user','version':version or hashlib.sha256((row['title']+'\n'+row['body']).encode()).hexdigest()},'vector':[0.1]*384}
  calls=[]
  def index(url,body):calls.append((url,body));return {'points':[point(mine),point(other),point(mine,'stale')],'next_page_offset':None}
  self.storage.index_reader=qdrant_reader('http://127.0.0.1:6333','synthetic','jarvis_knowledge_experimental_v1',transport=index)
  result=self.call('map');self.assertEqual(len(result['points']),1);self.assertEqual(result['points'][0]['docId'],'brain:'+mine['id']);self.assertEqual(len(result['points'][0]['position']),3)
  self.assertTrue(calls[0][0].endswith('/points/scroll'))
 def test_prepared_migration_cli_fixture_idempotent_and_no_source_rewrite(self):
  import os,subprocess
  with self.repo.db:self.repo.db.execute('INSERT INTO docs VALUES(?,?,?,?,?,?,?,?,?,?)',('unclaimed','Historique','Texte synthétique','Codex','Projet','Source','test-source',123,None,'user'))
  before=dict(self.repo.db.execute('SELECT * FROM docs WHERE id=?',('unclaimed',)).fetchone())
  backup=self.root/'approved-backups';backup.mkdir(mode=0o700)
  manifest=self.root/'approval.json';manifest.write_text(json.dumps({'approved':True,'writers_stopped':True,'brain':str(self.brain),'voice':str(self.voice),'backup_directory':str(backup),'approved_subjects':['alice'],'approved_spaces':['user'],'mapping':[{'kind':'document','id':'unclaimed','owner':'alice','space':'user'}]}));manifest.chmod(0o600)
  command=['python3',str(ROOT/'ops/production-storage-migrate.py'),'--execute-approved','--approval-file',str(manifest)]
  for _ in range(2):
   run=subprocess.run(command,capture_output=True,text=True,timeout=15);self.assertEqual(run.returncode,0,run.stderr)
  self.assertEqual(self.repo.metadata('document','unclaimed')['owner'],'alice');self.assertEqual(dict(self.repo.db.execute('SELECT * FROM docs WHERE id=?',('unclaimed',)).fetchone()),before)
 def test_common_access_requires_explicit_grant(self):
  self.policy['alice']['write_spaces'].append('commun')
  self.storage.call('gateway-storage','fact.save',{'subject':'alice','space':'commun','data':{'key':'Maison','fact':'Synthétique'}})
  self.policy['bob']['common_read']=[]
  self.assertEqual(self.storage.call('gateway-storage','facts',{'subject':'bob','space':'commun'}),[])
  with self.assertRaises(PermissionError):self.storage.call('gateway-storage','fact.save',{'subject':'bob','space':'commun','data':{'key':'Autre','fact':'Test'}})
 def test_additive_backup_integrity_restored_fixture_only(self):
  for source in [self.brain,self.voice]:
   backups=list(self.root.glob(source.name+'.before-*'));self.assertTrue(backups)
   for path in backups:
    with sqlite3.connect(path) as db:self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
if __name__=='__main__':unittest.main()
