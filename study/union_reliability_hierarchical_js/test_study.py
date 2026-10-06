import unittest,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));import run_study as rs
class T(unittest.TestCase):
 def test_prior(self): self.assertEqual(rs.PRIOR,.125)
 def test_zero_contrast(self):
  cs=np.zeros((3,24));*_,ag,ac,ad,tg,th,wu,t=rs.shrinkers(cs)
  self.assertEqual(ag,0);self.assertEqual(ac,0);self.assertEqual(ad,0);self.assertEqual(wu,0);self.assertTrue(np.all(t==0))
 def test_union_identity(self):
  for ag,ac in [(0,0),(.2,0),(0,.4),(.2,.4),(1,.7)]:
   wu=1-(1-ag)*(1-ac)
   self.assertGreaterEqual(wu,max(ag,ac)-1e-15);self.assertLessEqual(wu,1)
 def test_union_reduces_to_global_without_common(self):
  ag=.3;ac=0.;self.assertAlmostEqual(1-(1-ag)*(1-ac),ag)
if __name__=="__main__":unittest.main()
