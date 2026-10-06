import unittest,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));import run_study as rs
class T(unittest.TestCase):
 def test_constants(self):
  self.assertEqual(rs.PRIOR,.125);self.assertEqual(2*rs.PRIOR,.25);self.assertEqual(rs.APPLY_GAIN_MIN,.875)
 def test_weighted_median(self):
  x=np.array([0.,10.,20.]);w=np.array([1.,8.,1.]);self.assertEqual(rs.weighted_median(x,w),10.)
 def test_weighted_median_zero_weight(self):
  self.assertEqual(rs.weighted_median(np.array([1.,2.]),np.array([0.,0.])),0.)
 def test_two_prior_shrink(self):
  raw=np.array([1.,3.]);common=np.array([2.,2.]);s=2*rs.PRIOR;g=(1-s)*raw+s*common;self.assertTrue(np.allclose(g,[1.25,2.75]))
 def test_weighted_mean(self):
  x=np.array([[0.],[0.],[3.]]);m,v=rs.weighted_mean_variance(x,np.array([16.,16.,15.]));self.assertAlmostEqual(float(m[0]),45/47);self.assertGreaterEqual(float(v[0]),0)
if __name__=="__main__":unittest.main()
