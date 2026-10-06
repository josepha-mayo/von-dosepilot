import unittest,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));import run_study as rs
class T(unittest.TestCase):
 def test_zero_signal(self):
  pred=np.zeros((2,6,2));y=np.zeros((6,2));p=np.array(["a","a","b","b","c","c"]);inner=np.array([0,0,1,1,2,2])
  c,bar,v,t,a=rs.calibrator(pred,y,p,inner);self.assertEqual(t,0.0);self.assertTrue(np.all(a==0))
 def test_reliability_bounds(self):
  pred=np.zeros((2,6,2));y=np.array([[1,0],[1,0],[2,0],[2,0],[3,0],[3,0]],float);p=np.array(["a","a","b","b","c","c"]);inner=np.array([0,0,1,1,2,2])
  c,bar,v,t,a=rs.calibrator(pred,y,p,inner);self.assertTrue(np.all((a>=0)&(a<=1)))
if __name__=="__main__":unittest.main()
