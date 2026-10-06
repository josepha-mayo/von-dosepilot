import unittest,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));import run_study as rs
class T(unittest.TestCase):
 def test_reliability_bounds(self):
  b=np.array([0.,1.,2.]);v=np.array([0.,1.,4.]);r=np.divide(b*b,b*b+v,out=np.zeros_like(b),where=(b*b+v)>0)
  self.assertTrue(np.all((r>=0)&(r<=1)));self.assertTrue(np.allclose(r,[0,.5,.5]))
 def test_multiplier_endpoints(self):
  r=np.array([0.,1.]);m=1+np.sqrt(r);self.assertTrue(np.allclose(m,[1.,2.]))
 def test_half_recovery_zero_reliability(self):
  full=np.array([1.,2.]);loo=np.array([.8,2.2]);bias=full-loo;m=np.ones(2);deploy=full+m*bias
  bc=3*full-2*loo;half=.5*(full+bc);self.assertTrue(np.allclose(deploy,half))
 def test_full_recovery_unit_reliability(self):
  full=np.array([1.,2.]);loo=np.array([.8,2.2]);bias=full-loo;m=np.full(2,2.);deploy=full+m*bias;bc=3*full-2*loo;self.assertTrue(np.allclose(deploy,bc))
 def test_constants(self): self.assertEqual(rs.PRIOR,.125);self.assertEqual(rs.APPLY_GAIN_MIN,.875);self.assertEqual(rs.A_GAIN_MIN,-.875)
if __name__=="__main__":unittest.main()
