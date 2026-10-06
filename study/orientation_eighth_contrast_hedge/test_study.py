import unittest,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));import run_study as rs
class T(unittest.TestCase):
 def test_scale(self):self.assertEqual(rs.T,0.125)
 def test_rule(self):
  loo=np.zeros((2,2,1));ij=np.ones_like(loo);j=np.zeros_like(loo);oc=np.ones_like(loo)*2
  q=np.empty_like(loo);q[0]=loo[0];q[1]=ij[1]+rs.T*(oc[1]-j[1])
  self.assertTrue(np.allclose(q[0],0));self.assertTrue(np.allclose(q[1],1.25))
if __name__=="__main__":unittest.main()
