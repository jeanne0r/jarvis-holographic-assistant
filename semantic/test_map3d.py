import unittest,math
from map3d import project,validate_points
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
  doc={'doc_id':'brain:x','title':'Test','text':'Source fiable','version':'current','space':'member1','source':'Test'}
  def point(**changes):
   p={'doc_id':'brain:x','version':'current','space':'member1','offset':0};p.update(changes);return {'id':'x','vector':[.1]*384,'payload':p}
  self.assertEqual(len(validate_points([point()],{'brain:x':doc},['member1','shared'])),1)
  for p in [point(version='obsolete'),point(space='member2'),point(doc_id='brain:deleted')]:self.assertEqual(validate_points([p],{'brain:x':doc},['member1','shared']),[])
  self.assertEqual(validate_points([point()],{'brain:x':doc},['member2','shared']),[])
if __name__=='__main__':unittest.main()
