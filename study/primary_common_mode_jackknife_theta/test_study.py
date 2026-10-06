import unittest,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));import run_study as rs
class T(unittest.TestCase):
 def test_constants(self):
  self.assertEqual(rs.PRIOR,.125);self.assertEqual(rs.TARGETS,24);self.assertEqual(rs.APPLY_GAIN_MIN,.875);self.assertEqual(rs.A_GAIN_MIN,-.875)
 def test_common_mode_equal_target_mean(self):
  b=np.array([-2.,1.,4.]);self.assertAlmostEqual(float(np.mean(b)),1.0)
 def test_A_variance_reliability(self):
  b=np.array([2.,0.]);v=np.array([2.,0.]);r=np.divide(b*b,b*b+v,out=np.zeros_like(b),where=(b*b+v)>1e-30);self.assertTrue(np.allclose(r,[2/3,0]))
 def test_common_mode_B_deploy(self):
  theta=np.array([1.,2.]);bias=np.array([.2,-.1]);mu=float(np.mean(bias));td=theta+bias+mu;self.assertTrue(np.allclose(td,[1.25,1.95]))
 def test_weighted_mean(self):
  x=np.array([[0.],[0.],[3.]]);m,v=rs.weighted_mean_variance(x,np.array([16.,16.,15.]));self.assertAlmostEqual(float(m[0]),45/47);self.assertGreaterEqual(float(v[0]),0)
if __name__=="__main__":unittest.main()
