import tempfile,unittest
from pathlib import Path
from ..store import Memory,Principal
from ..phase2.database import migrate
from ..phase2.bridge import Bridge
from ..phase3 import lab
from .canonical_metadata import project,utc

class ProjectionTests(unittest.TestCase):
 def setUp(self):
    self.tmp=tempfile.TemporaryDirectory();self.m=Memory(Path(self.tmp.name)/'synthetic.sqlite',create=True);migrate(self.m)
    self.ids=lab.seed(self.m)
    self.p=Principal(lab.OWNER,frozenset({'private'}),lab.HOST.roles|{'mission_worker','mission_writer'},'controller')
    self.mid=Bridge(self.m,self.p).submit('metadata-only',{'objective':'Synthetic metadata test','trigger':'offline','priority':1,'memory_context':[],'plan':['report'],'allowed_tools':['memory.search','report'],'budget':{'tokens':0,'cost_micros':0,'seconds':30,'attempts':1}})
 def tearDown(self):self.m.close();self.tmp.cleanup()
 def test_dates_history_and_no_writes(self):
    before=self.m.db.total_changes
    data=project(self.m,self.p,self.mid,[self.ids['configuration_memory_id']])
    self.assertEqual(before,self.m.db.total_changes)
    self.assertEqual([r['observed_utc'] for r in data['items']],['2023-11-14T22:13:20Z','2023-11-14T22:15:00Z'])
    self.assertEqual([r['revision_status'] for r in data['items']],['superseded','user_confirmed'])
    self.assertEqual([r['is_current_revision'] for r in data['items']],[False,True]);self.assertFalse(data['promotion_performed'])
 def test_no_source_uri_or_revision_substitution(self):
    revision=self.m.history(self.p,self.ids['configuration_memory_id'])[-1]['id']
    with self.assertRaises(KeyError):project(self.m,self.p,self.mid,[revision])
    with self.assertRaises(ValueError):project(self.m,self.p,self.mid,['synthetic://doselab/correction'])
 def test_acl_and_model_permissions(self):
    other=Principal('other',frozenset({'private'}),self.p.roles,'other')
    with self.assertRaises(PermissionError):project(self.m,other,self.mid,[self.ids['configuration_memory_id']])
    model=Principal(lab.OWNER,frozenset({'private'}),frozenset({'reader'}),'model')
    with self.assertRaises(PermissionError):project(self.m,model,self.mid,[self.ids['configuration_memory_id']])
 def test_bounds_and_invalid_dates(self):
    with self.assertRaises(ValueError):project(self.m,self.p,self.mid,[self.ids['configuration_memory_id']]*21)
    for value in [True,float('nan'),float('inf'),1e50,'2023-11-15']:
        with self.assertRaises(ValueError):utc(value)
    self.assertIsNone(utc(None))
if __name__=='__main__':unittest.main()
