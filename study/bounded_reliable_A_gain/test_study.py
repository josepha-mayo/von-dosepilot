import unittest,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));import run_study as rs
class T(unittest.TestCase):
 def test_bounds(self):self.assertEqual((rs.A_GAIN_MIN,rs.A_GAIN_MAX),(-.5,.5));self.assertEqual((rs.GAIN_MIN,rs.GAIN_MAX),(1.,3.))
 def test_A_gain_formula(self):
  T=np.ones((3,24));ra=np.full((3,24),.1);n=np.ones(3);g,raw=rs.fit_bounded_A_gain(T,ra,n)
  self.assertTrue(np.allclose(raw,.2));self.assertTrue(np.allclose(g,.2))
 def test_A_gain_clipping(self):
  T=np.ones((3,24));n=np.ones(3);g,_=rs.fit_bounded_A_gain(T,np.full((3,24),10.),n);self.assertTrue(np.all(g==.5))
  g,_=rs.fit_bounded_A_gain(T,np.full((3,24),-10.),n);self.assertTrue(np.all(g==-.5))
 def test_reliability(self):
  g=np.array([0.,1.,2.]);v=np.array([1.,1.,0.]);r=np.divide(g*g,g*g+v,out=np.zeros_like(g),where=(g*g+v)>0);self.assertTrue(np.allclose(r,[0,.5,1]))
 def test_zero_global_signal(self):
  g=np.zeros(24);v=np.ones(24);norm=float(np.sum(g*g));R=0 if norm<=1e-30 else max(0,1-22*float(np.mean(v))/norm);self.assertEqual(R,0)
if __name__=="__main__":unittest.main()
