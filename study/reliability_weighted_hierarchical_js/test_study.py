import unittest,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));import run_study as rs
class T(unittest.TestCase):
 def test_prior(self):self.assertEqual(rs.PRIOR,.125)
 def test_zero_contrast(self):
  cs=np.zeros((3,24));*_,ag,ac,ad,tg,th,t=rs.shrinkers(cs);self.assertEqual(ag,0);self.assertEqual(ac,0);self.assertEqual(ad,0);self.assertTrue(np.all(t==0))
 def test_reliability_weight_identity(self):
  tg=np.arange(24.,dtype=float);th=tg+2;ag=.3;t=(1-ag)*tg+ag*th;self.assertTrue(np.allclose(t,tg+.6))
if __name__=="__main__":unittest.main()
