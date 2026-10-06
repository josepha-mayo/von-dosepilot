import unittest,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));import run_study as rs
class T(unittest.TestCase):
    def test_patient_weights(self):
        p=np.array(["a","a","b"]);w=rs.patient_weights(p)
        self.assertAlmostEqual(float(w[:2].sum()),.5);self.assertAlmostEqual(float(w[2]),.5)
    def test_affine_exact(self):
        x=np.array([1.,2.,3.,4.]);p=np.array(["a","b","c","d"]);r=2.+3.*(x-2.5)
        m=rs.fit_affine_paid_max(x,r,p)
        self.assertAlmostEqual(m["intercept"],2.);self.assertAlmostEqual(m["slope"],3.)
        self.assertTrue(np.allclose(rs.predict_affine_paid_max(x,m),r))
    def test_affine_zero_denominator(self):
        x=np.ones(3);p=np.array(["a","b","c"]);r=np.array([1.,2.,3.]);m=rs.fit_affine_paid_max(x,r,p)
        self.assertEqual(m["slope"],0.);self.assertAlmostEqual(m["intercept"],2.)
    def test_max_summary(self):
        X=np.array([[1.,3.,2.],[4.,0.,2.]])
        self.assertTrue(np.array_equal(X.max(1),np.array([3.,4.])))
    def test_constants(self):
        self.assertEqual(rs.TARGETS,24);self.assertEqual(rs.EXPECTED_BEST,0.0010545312547735701)
if __name__=="__main__":unittest.main()
