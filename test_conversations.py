import json,os,pathlib,sqlite3,subprocess,tempfile,unittest,uuid
SCRIPT=str(pathlib.Path(__file__).with_name('store.py'))
class ConversationTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.path=self.temp.name+'/brain.sqlite';self.env={**os.environ,'JARVIS_DB':self.path};self.sid=str(uuid.uuid4())
 def tearDown(self):self.temp.cleanup()
 def call(self,action,**data):return json.loads(subprocess.run(['python3',SCRIPT,'conversation_'+action],input=json.dumps(data).encode(),env=self.env,stdout=subprocess.PIPE,check=False).stdout)
 def record(self,**changes):return self.call('record',**({'id':self.sid,'channel':'written','space':'member1','turn':0,'revision':1,'user':'Bonjour','assistant':'','status':'partial'}|changes))
 def doc(self):
  db=sqlite3.connect(self.path);db.row_factory=sqlite3.Row
  return dict(db.execute('SELECT * FROM docs').fetchone())
 def test_written_persistence_and_idempotency(self):
  self.assertTrue(self.record()['ok']);self.assertTrue(self.record(revision=2,assistant='Salut',status='complete')['ok'])
  self.record();self.record(revision=2,assistant='Salut',status='complete')
  d=self.doc();self.assertEqual(d['space'],'member1');self.assertIn('Jarvis : Salut',d['body'])
  db=sqlite3.connect(self.path);self.assertEqual(db.execute('SELECT count(*) FROM docs').fetchone()[0],1);self.assertEqual(db.execute('SELECT count(*) FROM conversation_turns').fetchone()[0],1)
  self.assertFalse(self.record(space='member2',revision=3)['ok'])
 def test_voice_session_space_is_server_bound_and_survives_restart(self):
  self.assertFalse(self.record(channel='voice')['ok'])
  self.assertTrue(self.call('session',id=self.sid,space='member2',channel='voice')['ok'])
  self.assertTrue(self.record(channel='voice',space='member1',assistant='Réponse partielle',status='interrupted')['ok'])
  d=self.doc();self.assertEqual(d['space'],'member2');self.assertIn('interrompue',d['body'])
 def test_no_secrets_in_event_or_projection(self):
  self.record(user='Ma clé API: AIza'+'x'*35,assistant='sk-'+'a'*28)
  db=sqlite3.connect(self.path)
  for row in db.execute('SELECT user,assistant FROM conversation_turns'):
   self.assertNotIn('AIza',str(row));self.assertNotIn('sk-',str(row))
  self.assertNotIn('AIza',self.doc()['body'])
 def test_invalid_payload_rejected(self):
  for changes in [{'id':'bad'},{'turn':-1},{'revision':False},{'user':'x'*40001},{'channel':'audio'}]:self.assertFalse(self.record(**changes)['ok'])
if __name__=='__main__':unittest.main()
