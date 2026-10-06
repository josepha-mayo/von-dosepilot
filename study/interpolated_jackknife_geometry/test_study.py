import unittest,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;STUDY=HERE.parent
sys.path[:0]=[str(HERE),str(STUDY/"hybrid_residual"),str(STUDY/"cross_patient_bandwidth"),str(STUDY/"interpolated_median_geometry")]
import interpolated_jackknife as ij
class T(unittest.TestCase):
 def test_jackknife_identity(self):
  theta=np.array([1.,2.]);loo=np.tile(theta,(5,1));bc=5*theta-4*loo.mean(0);self.assertTrue(np.allclose(bc,theta))
 def test_bias_direction(self):
  theta=np.array([1.]);loo=np.array([[.9],[.9],[.9],[.9]]);bc=4*theta-3*loo.mean(0);self.assertGreater(float(bc[0]),1.)
if __name__=="__main__":unittest.main()
