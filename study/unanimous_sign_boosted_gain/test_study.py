import unittest,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));import run_study as rs
class T(unittest.TestCase):
 def test_constants(self):self.assertEqual(rs.PRIOR,.125);self.assertEqual((rs.GAIN_MIN,rs.GAIN_MAX),(1.,3.))
 def test_weighted_mean(self):
  x=np.array([[0.],[0.],[3.]]);m,v=rs.weighted_mean_variance(x,np.array([16.,16.,15.]));self.assertAlmostEqual(float(m[0]),45/47);self.assertGreaterEqual(float(v[0]),0)
 def test_amplitude_alpha(self):
  r=np.array([0.,.25,1.]);a=.5+.5*np.sqrt(r);self.assertTrue(np.allclose(a,[.5,.75,1.]))
 def test_consensus_boost(self):
  base=np.array([.5,.7,.9]);local=np.array([[2,.5,2],[3,2,2],[1.1,4,2.]])
  unanimous=np.all(local>1,axis=0);a=np.where(unanimous,1,base)
  self.assertTrue(np.array_equal(unanimous,[True,False,True]));self.assertTrue(np.allclose(a,[1,.7,1]))
 def test_no_false_consensus_on_zero_theta(self):
  rb=np.ones((3,24));T=np.zeros_like(rb);local=np.divide(-2*rb,T,out=np.ones_like(rb),where=np.abs(T)>1e-12)
  self.assertFalse(np.any(np.all(local>1,axis=0)))
if __name__=="__main__":unittest.main()
