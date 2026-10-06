import unittest,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));import run_study as rs
class T(unittest.TestCase):
 def test_constants(self):
  self.assertEqual(rs.PRIOR,.125);self.assertEqual(rs.GAIN_MIN,1);self.assertEqual(rs.GAIN_MAX,3);self.assertEqual(rs.HEDGE,.5)
 def test_weighted_mean(self):
  x=np.array([[0.],[0.],[3.]]);m,v=rs.weighted_mean_variance(x,np.array([16.,16.,15.]));self.assertAlmostEqual(float(m[0]),45/47);self.assertGreaterEqual(float(v[0]),0)
 def test_gain_formula_identity(self):
  cs=np.ones((3,24));rb=np.full((3,24),-.5);n=np.array([10.,10.,10.])
  # monkeypatch theta_amp to avoid relying on nonzero contrast shape details
  old=rs.theta_amp
  try:
   rs.theta_amp=lambda c,counts:(np.ones(24),{})
   g,raw,T=rs.crossfit_gain(cs,rb,n)
   self.assertTrue(np.allclose(raw,1));self.assertTrue(np.allclose(g,1));self.assertEqual(T.shape,(3,24))
  finally:rs.theta_amp=old
 def test_gain_clipping(self):
  old=rs.theta_amp
  try:
   rs.theta_amp=lambda c,counts:(np.ones(24),{})
   cs=np.ones((3,24));n=np.ones(3)
   g,raw,_=rs.crossfit_gain(cs,np.full((3,24),-10.),n);self.assertTrue(np.all(g==3))
   g,raw,_=rs.crossfit_gain(cs,np.full((3,24),10.),n);self.assertTrue(np.all(g==1))
  finally:rs.theta_amp=old
 def test_half_hedge(self):
  a=np.zeros((2,3,24));b=np.ones_like(a);q=rs.HEDGE*a+(1-rs.HEDGE)*b;self.assertTrue(np.allclose(q,.5))
if __name__=="__main__":unittest.main()
