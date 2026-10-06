import unittest,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));import run_study as rs
class T(unittest.TestCase):
 def test_prior(self): self.assertEqual(rs.PRIOR,.125)
 def test_weighted_mean_equal_counts(self):
  x=np.array([[1.,2.],[3.,4.],[5.,6.]]);m,v=rs.weighted_mean_variance(x,np.array([2.,2.,2.]))
  self.assertTrue(np.allclose(m,x.mean(0)));self.assertTrue(np.all(v>=0))
 def test_patient_count_weight(self):
  x=np.array([[0.],[0.],[3.]]);m,v=rs.weighted_mean_variance(x,np.array([16.,16.,15.]))
  self.assertAlmostEqual(float(m[0]),45/47);self.assertGreaterEqual(float(v[0]),0)
 def test_zero_contrast(self):
  cs=np.zeros((3,24));counts=np.array([16.,16.,15.]);*_,ag,ac,ad,tg,th,w,t=rs.shrinkers(cs,counts)
  conf=1-(1-ag)*(1-ac);self.assertEqual(conf,0);self.assertTrue(np.all(t==0))
 def test_union_confidence_bounds(self):
  for ag,ac in [(0,0),(.2,0),(0,.4),(.2,.4),(1,.7)]:
   c=1-(1-ag)*(1-ac);self.assertGreaterEqual(c,max(ag,ac)-1e-15);self.assertLessEqual(c,1);self.assertGreaterEqual(1+c,1);self.assertLessEqual(1+c,2)
if __name__=="__main__":unittest.main()
