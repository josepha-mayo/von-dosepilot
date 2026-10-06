import unittest,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));import run_study as rs
class T(unittest.TestCase):
 def test_prior(self): self.assertEqual(rs.PRIOR,.125)
 def test_zero_contrast(self):
  cs=np.zeros((3,24));*_,ag,ac,ad,tg,th,w,t=rs.shrinkers(cs)
  self.assertEqual(ag,0);self.assertEqual(ac,0);self.assertEqual(ad,0);self.assertTrue(np.all(w==0));self.assertTrue(np.all(t==0))
 def test_amplitude_reliability(self):
  r=np.array([0.,.25,1.]);a=np.sqrt(r)
  self.assertTrue(np.allclose(a,[0.,.5,1.]))
 def test_saturating_additive_weight(self):
  r=np.array([0.,.25,1.]);ac=.2;ag=.1
  w=np.minimum(1.,np.sqrt(r)+ac+ag)
  self.assertTrue(np.allclose(w,[.3,.8,1.]))
  self.assertTrue(np.all((w>=0)&(w<=1)))
if __name__=="__main__":unittest.main()
