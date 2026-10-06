import unittest,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));import run_study as rs
class T(unittest.TestCase):
 def test_constants(self):
  self.assertEqual(rs.PRIOR,.125);self.assertEqual(rs.LOCAL_STRENGTH,.25);self.assertEqual(rs.TARGETS,24)
 def test_pooling(self):
  sep=np.array([3.,6.]);common=np.array([0.,3.]);got=(2/3)*sep+(1/3)*common;self.assertTrue(np.allclose(got,[2.,5.]))
 def test_masked_local_normalizes(self):
  X=np.zeros((2,2,1));R=np.array([[1.,2.],[3.,4.]]);pp=np.array(["a","b"]);mask=np.array([[True,False],[True,False]])
  m=rs.fit_local_mask(X,R,pp,mask);self.assertAlmostEqual(float(m["intercept"]),2.0)
 def test_cardinality_contract(self):
  owner=np.array(list(range(8))*2 + list(range(8,24))*3)
  self.assertEqual(len(owner),64);c=np.bincount(owner,minlength=24);self.assertEqual(int((c==2).sum()),8);self.assertEqual(int((c==3).sum()),16)
 def test_pooled_correction_equal_target(self):
  card=np.array([2]*8+[3]*16);C=rs.pooled_correction(np.array([1.]),np.array([3.]),card);self.assertAlmostEqual(float(C.mean()),1.0)
 def test_patient_weights(self):
  w=rs.patient_weights(np.array(["a","a","b"]));self.assertAlmostEqual(float(w.sum()),1.0)
if __name__=="__main__":unittest.main()
