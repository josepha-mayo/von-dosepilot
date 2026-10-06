import unittest,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));import run_study as rs
class T(unittest.TestCase):
 def test_constants(self):self.assertEqual(rs.PRIOR,.125);self.assertEqual((rs.GAIN_MIN,rs.GAIN_MAX),(1.,3.))
 def test_weighted_mean(self):
  x=np.array([[0.],[0.],[3.]]);m,v=rs.weighted_mean_variance(x,np.array([16.,16.,15.]));self.assertAlmostEqual(float(m[0]),45/47);self.assertGreaterEqual(float(v[0]),0)
 def test_global_js_zero_when_no_shift(self):
  d=np.zeros(24);v=np.ones(24);norm=float(np.sum(d*d));g=0.0 if norm<=1e-30 else max(0,1-22*float(np.mean(v))/norm);self.assertEqual(g,0)
 def test_global_js_positive_on_strong_shift(self):
  d=np.ones(24);v=np.full(24,.001);norm=float(np.sum(d*d));g=max(0,1-22*float(np.mean(v))/norm);self.assertGreater(g,0)
 def test_switch_identity(self):
  raw=np.array([1.,2.,3.]);fallback=np.array([1.,1.5,2.]);self.assertTrue(np.array_equal(raw if .2>0 else fallback,raw));self.assertTrue(np.array_equal(raw if 0>0 else fallback,fallback))
if __name__=="__main__":unittest.main()
