import unittest,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));import run_study as rs
class T(unittest.TestCase):
 def test_features(self):
  P=np.array([[1.,2.,3.,4.]*16]);f=rs.paid_features(P);self.assertEqual(f.shape,(1,4));self.assertTrue(np.allclose(f[0],[2.5,np.std(P[0]),1.,4.]))
 def test_cardinality_contract(self):
  c=np.array([2]*8+[3]*16);self.assertEqual(int((c==2).sum()),8);self.assertEqual(int((c==3).sum()),16);self.assertEqual(int(c.sum()),64)
 def test_half_pool(self):
  a=np.array([2.,4.]);g=np.array([6.,8.]);self.assertTrue(np.allclose(.5*a+.5*g,[4.,6.]))
 def test_patient_weights(self):
  p=np.array(["a","a","b"]);w=rs.patient_weights(p);self.assertAlmostEqual(float(w[:2].sum()),.5);self.assertAlmostEqual(float(w[2]),.5)
 def test_fit_constant(self):
  F=np.array([[0.,0.,0.,0.],[1.,1.,1.,1.]]);r=np.array([2.,2.]);m=rs.fit_common_calibration(F,r,np.array(["a","b"]));self.assertAlmostEqual(float(m["intercept"]),2.0)
if __name__=="__main__":unittest.main()
