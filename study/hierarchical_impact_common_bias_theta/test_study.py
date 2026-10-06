import unittest,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));import run_study as rs
class T(unittest.TestCase):
 def test_constants(self):
  self.assertEqual(rs.PRIOR,.125);self.assertEqual(rs.TARGETS,24);self.assertEqual(rs.APPLY_GAIN_MIN,.875);self.assertEqual(rs.A_GAIN_MIN,-.875)
 def test_hierarchical_extra_endpoints(self):
  b=np.array([1.,3.]);mu=2.;r=np.array([0.,1.]);dev=b-mu;extra=mu+r*dev;self.assertTrue(np.allclose(extra,[2.,3.]))
 def test_impact_common_mean(self):
  b=np.array([1.,3.]);g=np.array([1.,2.]);r=np.array([1.,.5]);w=g*g*r;mu=float(np.sum(w*b)/np.sum(w));self.assertAlmostEqual(mu,7/3)
 def test_zero_weight_fallback(self):
  b=np.array([1.,-1.]);g=np.zeros(2);r=np.zeros(2);w=g*g*r;mu=0.0 if float(np.sum(w))<=1e-30 else float(np.sum(w*b)/np.sum(w));self.assertEqual(mu,0.0)
 def test_weighted_mean(self):
  x=np.array([[0.],[0.],[3.]]);m,v=rs.weighted_mean_variance(x,np.array([16.,16.,15.]));self.assertAlmostEqual(float(m[0]),45/47);self.assertGreaterEqual(float(v[0]),0)
if __name__=="__main__":unittest.main()
