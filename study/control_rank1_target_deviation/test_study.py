import unittest,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));import run_study as rs
class T(unittest.TestCase):
 def test_constants(self):
  self.assertEqual(rs.PRIOR,.125);self.assertEqual(rs.TARGETS,24);self.assertEqual(rs.LOCAL_STRENGTH,.25)
 def test_rank1(self):
  F=np.array([[0.,0.,0.],[1.,0.,0.],[0.,1.,0.],[0.,0.,1.]],float)
  R=np.outer(np.array([0.,1.,2.,3.]),np.arange(1,25,dtype=float))
  pp=np.array(["a","b","c","d"])
  m=rs.fit_rank1_control(F,R,pp);self.assertEqual(m["rank"],1);self.assertEqual(np.asarray(m["beta"]).shape,(3,24));self.assertLessEqual(np.linalg.matrix_rank(np.asarray(m["beta"]),tol=1e-10),1)
 def test_rank1_zero_mean_feature_prediction(self):
  F=np.array([[0.,0.,0.],[1.,0.,0.],[0.,1.,0.],[0.,0.,1.]],float);R=np.ones((4,24));pp=np.array(["a","b","c","d"]);m=rs.fit_rank1_control(F,R,pp)
  q=rs.predict_rank1_control(np.asarray(m["feature_mean"])[None,:],m);self.assertTrue(np.allclose(q,0))
 def test_one_over_K(self): self.assertAlmostEqual(1.0/3.0,0.3333333333333333)
 def test_control_basis(self):
  q=rs.control_basis(np.array([[2.,4.]]));self.assertTrue(np.allclose(q,[[3.,-1.,9.]]))
if __name__=="__main__":unittest.main()
