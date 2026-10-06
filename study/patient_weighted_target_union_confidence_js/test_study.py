import unittest,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));import run_study as rs
class T(unittest.TestCase):
 def test_prior(self): self.assertEqual(rs.PRIOR,.125)
 def test_weighted_mean(self):
  x=np.array([[0.],[0.],[3.]]);m,v=rs.weighted_mean_variance(x,np.array([16.,16.,15.]))
  self.assertAlmostEqual(float(m[0]),45/47);self.assertGreaterEqual(float(v[0]),0)
 def test_zero_contrast(self):
  cs=np.zeros((3,24));counts=np.array([16.,16.,15.]);*_,ag,ac,ad,tg,th,s,w,t=rs.shrinkers(cs,counts)
  self.assertEqual(ag,0);self.assertEqual(ac,0);self.assertTrue(np.all(s==0));self.assertTrue(np.all(t==0))
 def test_target_amplification_bounds(self):
  s=np.array([0.,.25,.5,1.]);cu=.4;a=1+cu*s
  self.assertTrue(np.allclose(a,[1.,1.1,1.2,1.4]));self.assertTrue(np.all((a>=1)&(a<=2)))
 def test_union_confidence(self):
  ag=.2;ac=.4;self.assertAlmostEqual(1-(1-ag)*(1-ac),.52)
if __name__=="__main__":unittest.main()
