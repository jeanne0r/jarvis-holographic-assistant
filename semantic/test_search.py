import importlib,json,os,pathlib,sqlite3,tempfile,unittest
from unittest.mock import patch
class SearchTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.temp.name);(self.root/'data').mkdir()
  os.environ['JARVIS_SEMANTIC_ROOT']=str(self.root)
  import documents,search
  self.docs=importlib.reload(documents);self.search=importlib.reload(search)
  d=sqlite3.connect(self.root/'data/brain.sqlite')
  d.executescript("CREATE TABLE docs(id TEXT,space TEXT,title TEXT,body TEXT,source TEXT,status TEXT DEFAULT 'Source',updated REAL DEFAULT 0);CREATE VIRTUAL TABLE search USING fts5(id UNINDEXED,title,body);")
  for row in [('r','user','Bateau','Le voilier familial porte le nom Calypso.','test'),('a','amelie','Privé','Note privée sans lien.','test'),('c','commun','Maison','Note commune.','test')]:
   d.execute('INSERT INTO docs(id,space,title,body,source) VALUES(?,?,?,?,?)',row);d.execute('INSERT INTO search VALUES(?,?,?)',(row[0],row[2],row[3]))
  d.commit();d.close()
 def tearDown(self):self.temp.cleanup();os.environ.pop('JARVIS_SEMANTIC_ROOT',None)
 def hit(self,doc_id,space,title,text,**extra):
  return {'doc_id':'brain:'+doc_id,'space':space,'version':self.docs.version(title,text),'text':text,'score':.8,**extra}
 def test_semantic_finds_synonym_and_ignores_other_spaces(self):
  hits=[self.hit('a','amelie','Privé','Note privée sans lien.'),self.hit('r','user','Bateau','Le voilier familial porte le nom Calypso.')]
  with patch.object(self.search,'call',return_value={'hits':hits}):r=self.search.search({'query':'Comment s’appelle notre embarcation ?','space':'user'})
  self.assertTrue(r['semantic']);self.assertEqual([s['id'] for s in r['sources']],['r'])
 def test_stale_vectors_are_rejected(self):
  hit=self.hit('r','user','Bateau','Ancien nom.')
  with patch.object(self.search,'call',return_value={'hits':[hit]}):r=self.search.search({'query':'embarcation','space':'user'})
  self.assertEqual(r['sources'],[])
 def test_keyword_fallback_if_qdrant_offline(self):
  with patch.object(self.search,'call',side_effect=OSError()):r=self.search.search({'query':'Calypso','space':'user'})
  self.assertFalse(r['semantic']);self.assertEqual(r['sources'][0]['id'],'r')
 def test_common_requires_explicit_scope(self):
  hit=self.hit('c','commun','Maison','Note commune.')
  with patch.object(self.search,'call',return_value={'hits':[hit]}):
   self.assertEqual(self.search.search({'query':'foyer','space':'user'})['sources'],[])
   self.assertEqual(self.search.search({'query':'foyer','space':'user','include_common':True})['sources'][0]['id'],'c')
 def test_structured_memory_remains_searchable_when_qdrant_is_offline(self):
  db=sqlite3.connect(self.root/'data/voice-memory.sqlite')
  db.execute('CREATE TABLE facts(space TEXT,key TEXT,label TEXT,fact TEXT,entity_id TEXT,area TEXT,updated REAL)')
  db.execute('INSERT INTO facts VALUES(?,?,?,?,?,?,?)',('commun','eclairage salon','Éclairage du salon','Désigne le dimmer Zigbee.','light.salon','Salon',1));db.commit();db.close()
  with patch.object(self.search,'call',side_effect=OSError()):
   r=self.search.search({'query':'éclairage salon','space':'user','include_common':True})
   self.assertEqual(r['sources'][0]['id'],'voice:commun:eclairage salon')
   self.assertEqual(self.search.search({'query':'éclairage salon','space':'amelie'})['sources'],[])
 def test_deleted_voice_fact_cannot_be_returned_by_stale_vector(self):
  db=sqlite3.connect(self.root/'data/voice-memory.sqlite');db.execute('CREATE TABLE facts(space TEXT,key TEXT,label TEXT,fact TEXT,entity_id TEXT,area TEXT,updated REAL)');db.close()
  hit={'doc_id':'voice:user:obsolete','space':'user','version':'stale','text':'Fait oublié','score':.9}
  with patch.object(self.search,'call',return_value={'hits':[hit]}):self.assertEqual(self.search.search({'query':'obsolete','space':'user'})['sources'],[])
if __name__=='__main__':unittest.main()
