import unittest,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));import run_study as rs
class T(unittest.TestCase):
 def test_prior(self): self.assertEqual(rs.PRIOR,.125)
 def test_zero_contrast(self):
  cs=np.zeros((3,24));*_,ag,ac,ad,tg,th,w,t=rs.shrinkers(cs)
  self.assertEqual(ag,0);self.assertEqual(ac,0);self.assertEqual(ad,0);self.assertEqual(w,0);self.assertTrue(np.all(t==0))
 def test_saturating_sum(self):
  for ag,ac,expected in [(0,0,0),(.2,0,.2),(0,.4,.4),(.2,.4,.6),(.7,.6,1.)]:
   self.assertAlmostEqual(min(1.,ag+ac),expected)
if __name__=="__main__":unittest.main()
