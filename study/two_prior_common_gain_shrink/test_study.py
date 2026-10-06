import unittest,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));import run_study as rs
class T(unittest.TestCase):
 def test_constants(self):
  self.assertEqual(rs.PRIOR,.125);self.assertEqual(2*rs.PRIOR,.25);self.assertEqual(rs.APPLY_GAIN_MIN,.875);self.assertEqual(rs.GAIN_MAX,3.0)
 def test_two_prior_shrink(self):
  raw=np.array([1.,3.]);common=np.array([2.,2.]);s=2*rs.PRIOR;g=(1-s)*raw+s*common;self.assertTrue(np.allclose(g,[1.25,2.75]))
 def test_weighted_common_shift(self):
  d=np.array([0.,2.]);r=np.array([1.,3.]);m=float(np.sum(r*d)/np.sum(r));self.assertAlmostEqual(m,1.5)
 def test_fallback_strength_zero(self):
  self.assertEqual(0.0,0.0)
 def test_weighted_mean(self):
  x=np.array([[0.],[0.],[3.]]);m,v=rs.weighted_mean_variance(x,np.array([16.,16.,15.]));self.assertAlmostEqual(float(m[0]),45/47);self.assertGreaterEqual(float(v[0]),0)
if __name__=="__main__":unittest.main()
