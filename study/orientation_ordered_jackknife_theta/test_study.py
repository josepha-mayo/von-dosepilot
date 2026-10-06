import unittest,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));import run_study as rs
class T(unittest.TestCase):
 def test_confidence_order(self):
  r=np.array([0.,.0625,.25,1.]);a=r;b=np.sqrt(np.sqrt(r))
  self.assertTrue(np.all((a>=0)&(a<=1)));self.assertTrue(np.all((b>=0)&(b<=1)));self.assertTrue(np.all(b>=a))
 def test_endpoints(self):
  r=np.array([0.,1.]);self.assertTrue(np.allclose(1+r,[1,2]));self.assertTrue(np.allclose(1+np.sqrt(np.sqrt(r)),[1,2]))
 def test_bounds_between_half_and_full(self):
  full=np.array([1.,2.]);loo=np.array([.8,2.2]);bias=full-loo;r=np.array([.25,.25]);ta=full+(1+r)*bias;tb=full+(1+np.sqrt(np.sqrt(r)))*bias;bc=full+2*bias
  self.assertTrue(np.all(np.abs(ta-full)<=np.abs(bc-full)+1e-15));self.assertTrue(np.all(np.abs(tb-full)<=np.abs(bc-full)+1e-15))
 def test_constants(self):self.assertEqual(rs.PRIOR,.125);self.assertEqual(rs.APPLY_GAIN_MIN,.875);self.assertEqual(rs.A_GAIN_MIN,-.875)
if __name__=="__main__":unittest.main()
