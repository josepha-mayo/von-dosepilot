import unittest,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));import run_study as rs
class T(unittest.TestCase):
 def test_constants(self):
  self.assertEqual(rs.PRIOR,.125);self.assertEqual(rs.LOCAL_STRENGTH,.25);self.assertEqual(rs.K,3)
 def test_rank1(self):
  F=np.array([[0.,0.,0.],[1.,0.,0.],[0.,1.,0.],[0.,0.,1.]])
  R=np.outer(np.arange(4.),np.arange(1,25.));m=rs.fit_rank1_control(F,R,np.array(["a","b","c","d"]))
  self.assertLessEqual(np.linalg.matrix_rank(np.asarray(m["beta"]),tol=1e-10),1)
 def test_nested_strength(self):self.assertAlmostEqual((1/rs.K)*(1/rs.K),1/9)
 def test_basis(self):self.assertTrue(np.allclose(rs.up.control_basis(np.array([[2.,4.]])),[[3.,-1.,9.]]))
if __name__=="__main__":unittest.main()
