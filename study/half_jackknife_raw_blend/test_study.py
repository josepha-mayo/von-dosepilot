import unittest,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));import run_study as rs
class T(unittest.TestCase):
 def test_weight(self):self.assertEqual(rs.W,0.5)
 def test_symmetric_average(self):
  a=np.zeros((2,3,1));b=np.ones_like(a);q=rs.W*a+(1-rs.W)*b;self.assertTrue(np.allclose(q,.5))
if __name__=="__main__":unittest.main()
