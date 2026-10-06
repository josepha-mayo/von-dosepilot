import unittest,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));import run_study as rs
class T(unittest.TestCase):
 def test_prior(self): self.assertEqual(rs.PRIOR,.125)
 def test_zero_contrast(self):
  cs=np.zeros((3,24));*_,ag,ac,ad,tg,th,w,t=rs.shrinkers(cs)
  self.assertEqual(ag,0);self.assertEqual(ac,0);self.assertEqual(ad,0);self.assertTrue(np.all(w==0));self.assertTrue(np.all(t==0))
 def test_union_bounds(self):
  r=np.array([0.,.2,.8,1.]);ac=.4;w=1-(1-r)*(1-ac)
  self.assertTrue(np.all((w>=0)&(w<=1)));self.assertTrue(np.all(w>=r));self.assertTrue(np.all(w>=ac))
 def test_target_reliability_formula(self):
  d=np.array([0.,1.,2.]);v=np.array([1.,.5,1.]);r=np.maximum(0,1-v/(d*d+1e-30))
  self.assertEqual(r[0],0);self.assertAlmostEqual(r[1],.5);self.assertAlmostEqual(r[2],.75)
if __name__=="__main__":unittest.main()
