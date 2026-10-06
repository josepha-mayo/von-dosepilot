import unittest,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));import run_study as rs
class T(unittest.TestCase):
 def test_constants(self):
  self.assertEqual(rs.PRIOR,.125);self.assertEqual(rs.A_GAIN_MIN,-.9375);self.assertEqual(rs.A_GAIN_MAX,.5)
 def test_half_prior_extension(self):
  self.assertAlmostEqual(rs.A_GAIN_MIN,-(1-rs.PRIOR/2))
 def test_threefold_strength(self):
  self.assertAlmostEqual(1/3,0.3333333333333333)
 def test_weighted_median(self):
  x=np.array([0.,10.,20.]);w=np.array([1.,8.,1.]);self.assertEqual(rs.weighted_median(x,w),10.)
 def test_weighted_mean(self):
  x=np.array([[0.],[0.],[3.]]);m,v=rs.weighted_mean_variance(x,np.array([16.,16.,15.]));self.assertAlmostEqual(float(m[0]),45/47);self.assertGreaterEqual(float(v[0]),0)
if __name__=="__main__":unittest.main()
