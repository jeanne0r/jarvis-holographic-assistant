import json,os,pathlib,subprocess,tempfile,unittest
SCRIPT=str(pathlib.Path(__file__).with_name('voice-memory.py'))
class MemoryTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.env={**os.environ,'JARVIS_VOICE_MEMORY_DB':self.temp.name+'/memory.sqlite'}
 def tearDown(self):self.temp.cleanup()
 def call(self,action,**data):
  return json.loads(subprocess.check_output(['python3',SCRIPT,action],input=json.dumps(data).encode(),env=self.env))
 def test_persists_across_processes_and_isolates_spaces(self):
  self.assertTrue(self.call('save',space='user',key='Éclairage salon',fact='Désigne la lampe.',entity_id='light.salon')['data']['saved'])
  self.assertEqual(self.call('list',space='user')['data'][0]['entity_id'],'light.salon')
  self.assertEqual(self.call('list',space='amelie')['data'],[])
  self.call('save',space='commun',key='Lampe commune',fact='Au salon.')
  self.assertEqual(len(self.call('list',space='amelie')['data']),1)
  self.assertEqual(self.call('list',space='amelie',include_common=False)['data'],[])
 def test_correct_and_forget(self):
  for fact in ['Avant','Après']:self.call('save',key='Préférence',fact=fact)
  rows=self.call('list')['data'];self.assertEqual(len(rows),1);self.assertEqual(rows[0]['fact'],'Après')
  self.assertTrue(self.call('forget',key='La préférence')['data']['forgotten'])
  self.assertEqual(self.call('list')['data'],[])
 def test_rejects_secrets_invalid_space_and_fields(self):
  for data in [dict(key='secret',fact='mot de passe: secret'),dict(key='a',fact='b',space='invalid'),dict(key='a',fact='x'*801),dict(key='a',fact='b',entity_id='../bad')]:self.assertFalse(self.call('save',**data)['ok'])
  self.assertEqual(self.call('list')['data'],[])
if __name__=='__main__':unittest.main()
