import unittest,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));import run_study as rs
class T(unittest.TestCase):
 def test_prior(self): self.assertEqual(rs.PRIOR,.125)
 def test_zero_contrast(self):
  cs=np.zeros((3,24));*_,ag,ac,ad,tg,th,w,conf,amp,t=rs.shrinkers(cs)
  self.assertEqual(ag,0);self.assertEqual(ac,0);self.assertEqual(ad,0);self.assertEqual(conf,0);self.assertEqual(amp,1);self.assertTrue(np.all(w==0));self.assertTrue(np.all(t==0))
 def test_confidence_amplification(self):
  for ag,ac in [(0,0),(.2,0),(0,.4),(.2,.4),(1,.7)]:
   c=max(ag,ac);self.assertAlmostEqual(1+c,1+max(ag,ac));self.assertGreaterEqual(1+c,1);self.assertLessEqual(1+c,2)
 def test_amplitude_reliability(self):
  r=np.array([0.,.25,1.]);self.assertTrue(np.allclose(np.sqrt(r),[0,.5,1]))
if __name__=="__main__":unittest.main()
