import unittest,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
STUDY=HERE.parent
sys.path[:0]=[str(HERE),str(STUDY/"hybrid_residual"),str(STUDY/"cross_patient_bandwidth")]
import bagged_geometry as bg
class T(unittest.TestCase):
 def test_zero_distance(self):
  self.assertTrue(np.allclose(bg.empirical_rbf_bag(np.zeros((2,2)),3,np.array([.5,.7,.9])),1))
 def test_exact_average(self):
  d=np.array([1.,2.]);b=np.array([.5,.8]);x=bg.empirical_rbf_bag(d,2,b)
  y=sum(np.exp(-d/(2*2*v*v)) for v in b)/2
  self.assertTrue(np.allclose(x,y))
 def test_psd_small(self):
  x=np.linspace(-1,1,6)[:,None];dist=(x-x.T)**2;k=bg.empirical_rbf_bag(dist,1,np.array([.4,.7,1.1]))
  self.assertGreaterEqual(float(np.linalg.eigvalsh((k+k.T)/2).min()),-1e-10)
if __name__=="__main__":unittest.main()
