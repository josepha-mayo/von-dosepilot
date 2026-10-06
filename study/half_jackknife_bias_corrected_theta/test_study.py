import unittest,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));import run_study as rs
class T(unittest.TestCase):
 def test_half_jackknife_identity(self):
  full=np.array([1.,2.,3.]);loo=np.array([.8,2.2,2.5]);bc=3*full-2*loo;deploy=.5*full+.5*bc
  self.assertTrue(np.allclose(deploy,2*full-loo))
 def test_no_bias_when_loo_equals_full(self):
  full=np.arange(24.,dtype=float);loo=full.copy();bc=3*full-2*loo;deploy=.5*(full+bc);self.assertTrue(np.array_equal(deploy,full))
 def test_constants(self):
  self.assertEqual(rs.PRIOR,.125);self.assertEqual(rs.APPLY_GAIN_MIN,.875);self.assertEqual(rs.A_GAIN_MIN,-.875)
 def test_weighted_mean(self):
  x=np.array([[0.],[0.],[3.]]);m,v=rs.weighted_mean_variance(x,np.array([16.,16.,15.]));self.assertAlmostEqual(float(m[0]),45/47);self.assertGreaterEqual(float(v[0]),0)
if __name__=="__main__":unittest.main()
