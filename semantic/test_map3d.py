import unittest,math
from map3d import project,validate_points,memory_map,fetch_sample
from unittest.mock import patch,MagicMock
import json
class ProjectionTests(unittest.TestCase):
 def test_three_dimensions_preserve_pair_distances_up_to_scale(self):
  rows=[[float(x),float(y),float(z)]+[0.]*381 for x,y,z in [(0,0,0),(2,0,0),(0,4,0),(0,0,8),(3,5,9),(-2,4,-3)]]
  coords=project(rows);ratios=[]
  for i in range(len(rows)):
   for j in range(i):
    a=sum((x-y)**2 for x,y in zip(rows[i],rows[j]));b=sum((x-y)**2 for x,y in zip(coords[i],coords[j]));ratios.append(b/a)
  self.assertLess(max(ratios)-min(ratios),1e-5)
 def test_degenerate_and_empty(self):
  self.assertEqual(project([]),[]);self.assertEqual(project([[1.]*384]*3),[[0.,0.,0.]]*3)
 def test_current_sources_only_and_no_other_person(self):
  doc={'doc_id':'brain:x','title':'Test','text':'Source fiable','version':'current','space':'user','source':'Test'}
  def point(**changes):
   p={'doc_id':'brain:x','version':'current','space':'user','offset':0};p.update(changes);return {'id':'x','vector':[.1]*384,'payload':p}
  self.assertEqual(len(validate_points([point()],{'brain:x':doc},['user','commun'])),1)
  for p in [point(version='obsolete'),point(space='amelie'),point(doc_id='brain:deleted')]:self.assertEqual(validate_points([p],{'brain:x':doc},['user','commun']),[])
  self.assertEqual(validate_points([point()],{'brain:x':doc},['amelie','commun']),[])
class PaginationTests(unittest.TestCase):
 def test_invalid_owner_or_cursor_before_any_network_access(self):
  for data in [{'space':'stranger'},{'space':'user','offset':'not-a-qdrant-id'},{'space':'user','offset':-1},{'space':'user','offset':True}]:
   with self.assertRaises(ValueError):memory_map(data)
 def test_scroll_keeps_owner_filter_vectors_and_offset(self):
  cursor='11111111-1111-4111-8111-111111111111';payloads=[]
  def open_request(req,timeout):
   payloads.append(json.loads(req.data));response=MagicMock();response.__enter__.return_value.read.return_value=json.dumps({'result':{'points':[],'next_page_offset':None}}).encode();return response
  with patch('map3d.SECRET') as secret,patch('map3d.socket.gethostbyname',return_value='127.0.0.1'),patch('map3d.urllib.request.urlopen',side_effect=open_request):
   secret.read_text.return_value='JARVIS_SEMANTIC_URL=http://semantic.local:8000\nQDRANT__SERVICE__API_KEY=fixture-only'
   points,count,next_offset=fetch_sample(['user','commun'],750,cursor)
  self.assertEqual(points,[]);self.assertIsNone(count);self.assertIsNone(next_offset);self.assertEqual(len(payloads),1)
  self.assertEqual(payloads[0]['offset'],cursor);self.assertTrue(payloads[0]['with_vector']);self.assertEqual(payloads[0]['filter']['must'][0]['match']['any'],['user','commun'])
if __name__=='__main__':unittest.main()
