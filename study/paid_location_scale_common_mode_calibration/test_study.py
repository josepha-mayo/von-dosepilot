import unittest,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));import run_study as rs
class T(unittest.TestCase):
    def test_patient_weights(self):
        p=np.array(["a","a","b"]);w=rs.patient_weights(p)
        self.assertAlmostEqual(float(w[:2].sum()),.5);self.assertAlmostEqual(float(w[2]),.5)
    def test_paid_features(self):
        P=np.array([[1.,2.,3.],[2.,2.,2.]])
        P=np.pad(P,((0,0),(0,61)),constant_values=2.)
        F=rs.paid_features(P)
        self.assertEqual(F.shape,(2,3));self.assertTrue(np.allclose(F[:,2],[3.,2.]))
    def test_common_calibration_exact(self):
        F=np.array([[0.,0.,0.],[1.,0.,0.],[0.,1.,0.],[0.,0.,1.],[1.,1.,1.]])
        p=np.array(["a","b","c","d","e"]);r=2.+F@np.array([1.5,-2.,.5])
        m=rs.fit_common_calibration(F,r,p)
        self.assertAlmostEqual(m["intercept"],float(np.mean(r)))
        self.assertTrue(np.allclose(rs.predict_common_calibration(F,m),r))
    def test_constant_features(self):
        F=np.ones((4,3));p=np.array(["a","b","c","d"]);r=np.array([1.,2.,3.,4.])
        m=rs.fit_common_calibration(F,r,p);self.assertTrue(np.allclose(m["beta"],0.));self.assertAlmostEqual(m["intercept"],2.5)
    def test_constants(self):
        self.assertEqual(rs.EXPECTED_BASE,0.0010545312547735701);self.assertEqual(rs.EXPECTED_BEST,0.00104997801532859)
if __name__=="__main__":unittest.main()
