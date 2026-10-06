import unittest,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));import run_study as rs
class T(unittest.TestCase):
 def test_zero_signal_prior(self):
  pred=np.zeros((2,6,24));y=np.zeros((6,24));p=np.array(["a","a","b","b","c","c"]);inner=np.array([0,0,1,1,2,2])
  *_,alpha,scale=rs.james_stein_calibrator(pred,y,p,inner);self.assertEqual(alpha,0.0);self.assertEqual(scale,rs.PRIOR)
 def test_scale_bounds(self):
  self.assertGreaterEqual(rs.PRIOR,0);self.assertLessEqual(rs.PRIOR,1)
 def test_option_index(self):self.assertEqual(rs.option_index([0.3,1.0]),5)
if __name__=="__main__":unittest.main()
