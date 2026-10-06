import unittest,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));import run_study as rs
class T(unittest.TestCase):
 def test_bases(self):
  Q=np.array([[2.,4.,10.,12.,6.,8.,.1,.3,.2,.4]])
  self.assertEqual(rs.meanquad_basis(Q).shape,(1,3));self.assertEqual(rs.A_level_basis(Q).shape,(1,7));self.assertEqual(rs.B_full_quality_basis(Q).shape,(1,11))
  self.assertTrue(np.allclose(rs.meanquad_basis(Q),[[3.,-1.,9.]]))
 def test_rank1(self):
  F=np.arange(44,dtype=float).reshape(4,11);R=np.outer(np.arange(4.),np.arange(1,25.));m=rs.fit_rank1(F,R,np.array(["a","b","c","d"]))
  self.assertEqual(m["rank"],1);self.assertEqual(m["feature_count"],11);self.assertLessEqual(np.linalg.matrix_rank(np.asarray(m["beta"]),tol=1e-10),1)
 def test_strengths(self):self.assertAlmostEqual(1/rs.K,1/3);self.assertAlmostEqual(1/(rs.K*rs.K),1/9)
 def test_constants(self):self.assertEqual(rs.PRIOR,.125);self.assertEqual(rs.LOCAL_STRENGTH,.25);self.assertEqual(rs.TARGETS,24)
if __name__=="__main__":unittest.main()
