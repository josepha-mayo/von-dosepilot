import unittest,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));import run_study as rs
class T(unittest.TestCase):
 def test_constants(self):
  self.assertEqual(rs.PRIOR,.125);self.assertEqual(rs.LOCAL_STRENGTH,.25);self.assertEqual(rs.TARGETS,24)
 def test_control_ridge_lambda(self):
  F=np.array([[0.,0.],[1.,0.],[0.,1.],[1.,1.]])
  r=np.array([0.,1.,1.,2.]);pp=np.array(["a","b","c","d"])
  m=rs.fit_control_ridge(F,r,pp)
  self.assertAlmostEqual(float(m["ridge_lambda"]),rs.PRIOR*float(m["feature_energy_scale"]))
  self.assertGreater(float(m["ridge_lambda"]),0.0)
 def test_control_prediction_shape(self):
  F=np.array([[0.,0.],[1.,1.]]);r=np.array([0.,1.]);pp=np.array(["a","b"])
  m=rs.fit_control_ridge(F,r,pp);q=rs.predict_control(F,m);self.assertEqual(q.shape,(2,))
 def test_pooling(self):
  sep=np.array([3.,6.]);common=np.array([0.,3.]);got=(2/3)*sep+(1/3)*common;self.assertTrue(np.allclose(got,[2.,5.]))
 def test_cardinality_contract(self):
  owner=np.array(list(range(8))*2 + list(range(8,24))*3);c=np.bincount(owner,minlength=24)
  self.assertEqual(len(owner),64);self.assertEqual(int((c==2).sum()),8);self.assertEqual(int((c==3).sum()),16)
 def test_patient_weights(self):
  w=rs.patient_weights(np.array(["a","a","b"]));self.assertAlmostEqual(float(w.sum()),1.0)
if __name__=="__main__":unittest.main()
