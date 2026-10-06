import unittest,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import run_study as rs

class T(unittest.TestCase):
 def test_constants(self):
  self.assertEqual(rs.PRIOR,.125); self.assertEqual(rs.LOCAL_STRENGTH,.25); self.assertEqual(rs.TARGETS,24)
 def test_control_basis(self):
  F=np.array([[2.,4.],[3.,3.]])
  got=rs.control_basis(F)
  self.assertTrue(np.allclose(got,np.array([[3.,-1.,9.],[3.,0.,9.]])))
 def test_control_ridge_lambda(self):
  raw=np.array([[0.,0.],[1.,0.],[0.,1.],[1.,1.]])
  F=rs.control_basis(raw);r=np.array([0.,1.,1.,2.]);pp=np.array(["a","b","c","d"])
  m=rs.fit_control_ridge(F,r,pp)
  self.assertAlmostEqual(float(m["ridge_lambda"]),rs.PRIOR*float(m["feature_energy_scale"]))
  self.assertEqual(len(m["beta"]),3)
 def test_plate_imbalance(self):
  owner=[];plates=[]
  for j in range(8):
   owner += [j,j]; plates += [0,1]
  for j in range(8,24):
   owner += [j,j,j]; plates += [0,1,0]
  plan={"coordinate_target_indices":owner,"orientation_B_plate_indices":plates}
  q=rs.target_plate_imbalance(plan)
  self.assertTrue(np.allclose(q[:8],0.0));self.assertTrue(np.allclose(q[8:],1/3))
 def test_plate_interaction_fit(self):
  X=np.ones((4,24));R=np.full((4,24),2.0);pp=np.array(["a","b","c","d"])
  m=rs.fit_plate_interaction(X,R,pp)
  self.assertAlmostEqual(float(m["ridge_factor"]),1+rs.PRIOR)
  self.assertAlmostEqual(float(m["beta"]),2/(1+rs.PRIOR))
 def test_pooling(self):
  sep=np.array([3.,6.]);common=np.array([0.,3.]);got=(2/3)*sep+(1/3)*common
  self.assertTrue(np.allclose(got,[2.,5.]))
 def test_patient_weights(self):
  w=rs.patient_weights(np.array(["a","a","b"]));self.assertAlmostEqual(float(w.sum()),1.0)

if __name__=="__main__":unittest.main()
