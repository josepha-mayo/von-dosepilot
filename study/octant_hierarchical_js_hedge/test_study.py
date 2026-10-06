import unittest,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));import run_study as rs
class T(unittest.TestCase):
 def test_constants(self):self.assertEqual(rs.PRIOR,.125);self.assertEqual(rs.HEDGE,.125)
 def test_zero_contrast(self):
  cs=np.zeros((3,24));*_,ag,ac,ad,tg,th,t=rs.shrinkers(cs);self.assertEqual(ag,0);self.assertEqual(ac,0);self.assertEqual(ad,0);self.assertTrue(np.all(t==0))
 def test_hedge_identity(self):
  a=np.arange(24.);b=np.arange(24.)+1;c=(1-rs.HEDGE)*a+rs.HEDGE*b;self.assertTrue(np.allclose(c,a+rs.HEDGE))
if __name__=="__main__":unittest.main()
