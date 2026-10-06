import unittest,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));import run_study as rs
class T(unittest.TestCase):
 def test_constants(self):
  self.assertEqual(rs.PRIOR,.125);self.assertEqual(rs.A_GAIN_MIN,-.9375);self.assertEqual(rs.APPLY_GAIN_MIN,.875)
 def test_strength_bounds(self):
  for r in [0.,.25,.5,.75,1.]:
   s=1/(2+r);self.assertGreaterEqual(s,1/3);self.assertLessEqual(s,.5)
 def test_strength_decreases_with_reliability(self):
  self.assertGreater(1/2,1/3);self.assertGreater(1/(2+.2),1/(2+.8))
 def test_mean_reliability(self):
  r=np.array([0.,.5,1.]);self.assertAlmostEqual(float(r.mean()),.5);self.assertAlmostEqual(1/(2+r.mean()),.4)
 def test_weighted_median(self):
  self.assertEqual(rs.weighted_median(np.array([0.,1.,10.]),np.array([1.,8.,1.])),1.0)
if __name__=="__main__":unittest.main()
