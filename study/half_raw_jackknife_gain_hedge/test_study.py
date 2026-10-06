import unittest,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));import run_study as rs
class T(unittest.TestCase):
 def test_constants(self):self.assertEqual(rs.PRIOR,.125);self.assertEqual(rs.HEDGE,.5);self.assertEqual((rs.GAIN_MIN,rs.GAIN_MAX),(1.,3.))
 def test_weighted_mean(self):
  x=np.array([[0.],[0.],[3.]]);m,v=rs.weighted_mean_variance(x,np.array([16.,16.,15.]));self.assertAlmostEqual(float(m[0]),45/47);self.assertGreaterEqual(float(v[0]),0)
 def test_gain_bounds(self):
  T=np.ones((3,24));n=np.ones(3)
  g,_=rs.fit_bounded_gain(T,np.full((3,24),-10.),n);self.assertTrue(np.all(g==3))
  g,_=rs.fit_bounded_gain(T,np.full((3,24),10.),n);self.assertTrue(np.all(g==1))
 def test_reliability(self):
  d=np.array([0.,1.,2.]);v=np.array([1.,1.,0.]);r=np.divide(d*d,d*d+v,out=np.zeros_like(d),where=(d*d+v)>0);self.assertTrue(np.allclose(r,[0,.5,1]))
 def test_half_gain_hedge(self):
  st=np.array([1.,2.,3.]);raw=np.array([3.,2.,1.]);g=rs.HEDGE*st+(1-rs.HEDGE)*raw;self.assertTrue(np.allclose(g,[2,2,2]))
if __name__=="__main__":unittest.main()
