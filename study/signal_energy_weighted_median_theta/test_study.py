import unittest,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));import run_study as rs
class T(unittest.TestCase):
 def test_constants(self):
  self.assertEqual(rs.PRIOR,.125);self.assertEqual(rs.A_GAIN_MIN,-.9375);self.assertEqual(rs.A_GAIN_MAX,.5)
 def test_signal_energy_weight(self):
  g=np.array([2.,3.]);t=np.array([.5,2.]);r=np.array([.25,.5]);w=g*g*t*t*r
  self.assertTrue(np.allclose(w,[.25,18.]))
 def test_zero_theta_zero_weight(self):
  g=np.array([2.]);t=np.array([0.]);r=np.array([1.]);self.assertEqual(float((g*g*t*t*r)[0]),0.0)
 def test_weighted_median(self):
  self.assertEqual(rs.weighted_median(np.array([0.,1.,10.]),np.array([1.,8.,1.])),1.0)
 def test_weighted_mean(self):
  x=np.array([[0.],[0.],[3.]]);m,v=rs.weighted_mean_variance(x,np.array([16.,16.,15.]));self.assertAlmostEqual(float(m[0]),45/47);self.assertGreaterEqual(float(v[0]),0)
if __name__=="__main__":unittest.main()
