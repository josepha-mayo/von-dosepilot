import unittest,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));import run_study as rs
class T(unittest.TestCase):
 def test_prior(self):self.assertEqual(rs.PRIOR,0.125)
 def test_zero_signal_recovers_prior(self):
  pred=np.zeros((2,6,2));y=np.zeros((6,2));p=np.array(["a","a","b","b","c","c"]);inner=np.array([0,0,1,1,2,2])
  *_,alpha,scale=rs.calibrator(pred,y,p,inner);self.assertTrue(np.all(alpha==0));self.assertTrue(np.allclose(scale,rs.PRIOR))
 def test_scale_bounds(self):
  a=np.linspace(0,1,9);s=rs.PRIOR+(1-rs.PRIOR)*a;self.assertTrue(np.all((s>=rs.PRIOR)&(s<=1)))
if __name__=="__main__":unittest.main()
