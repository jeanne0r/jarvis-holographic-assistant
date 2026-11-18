import copy,unittest
from .turn_plan import plan

class Turns(unittest.TestCase):
    def setUp(self):
        self.source={'document_id':'synthetic','space':'user','format':'chatgpt-active-branch-metadata-v1','fingerprint':'fixture-revision','updated_at':1700000000}
        self.messages=[{'id':f'{r}{n}','role':r,'revision':'1','observed_at':None if r=='assistant' else 1600000000+n} for n in range(21) for r in ('user','assistant')]
    def test_twenty_references_deterministic_no_date_invention(self):
        ids=[f'user{n}' for n in range(20)]
        a=plan(self.source,self.messages,ids);self.assertEqual(a,plan(self.source,self.messages,ids))
        self.assertEqual(len(a['turns']),20);self.assertFalse(a['import_authorized'])
        self.assertIsNone(a['turns'][0]['turn_reference']['assistant_messages'][0]['observed_at'])
        changed={**self.source,'fingerprint':'next'}
        self.assertNotEqual(a['approval_fingerprint'],plan(changed,self.messages,ids)['approval_fingerprint'])
    def test_rejects_content_flattening_bounds_and_ambiguity(self):
        with self.assertRaises(ValueError):plan(self.source,self.messages,[f'user{n}' for n in range(21)])
        with self.assertRaises(ValueError):plan({**self.source,'format':'flattened-docs'},self.messages,['user0'])
        bad=copy.deepcopy(self.messages);bad[0]['content']='Toi: an embedded quotation'
        with self.assertRaises(ValueError):plan(self.source,bad,['user0'])
        with self.assertRaises(ValueError):plan(self.source,self.messages,['user0','user0'])
        with self.assertRaises(ValueError):plan(self.source,self.messages[:-1],['user20'])
        with self.assertRaises(ValueError):plan(self.source,self.messages[1:],['user1'])
        with self.assertRaises(ValueError):plan({**self.source,'updated_at':'private text'},self.messages,['user0'])

if __name__=='__main__':unittest.main()
