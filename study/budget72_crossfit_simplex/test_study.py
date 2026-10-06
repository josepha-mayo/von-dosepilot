import sys,unittest
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import run_study as r

class SimplexTests(unittest.TestCase):
    def test_selects_perfect_bandwidth(self):
        y=np.zeros((4,1))
        p0=np.ones((2,4,1))
        p1=np.zeros((2,4,1))
        p2=np.full((2,4,1),2.0)
        patients=np.array(["a","b","c","d"])
        w,best,_=r.simplex_weights(y,p0,p1,p2,patients)
        np.testing.assert_allclose(w,[0,1,0],atol=1e-12)
        self.assertLess(best["weighted_sse"],1e-20)

    def test_convex_edge_solution(self):
        y=np.zeros((2,1))
        p0=np.ones((2,2,1))
        p1=-np.ones((2,2,1))
        p2=np.full((2,2,1),3.0)
        patients=np.array(["a","b"])
        w,_,_=r.simplex_weights(y,p0,p1,p2,patients)
        np.testing.assert_allclose(w,[0.5,0.5,0],atol=1e-12)
        self.assertAlmostEqual(float(w.sum()),1.0)

    def test_patient_weights_equal_total(self):
        p=np.array(["a","a","b"])
        w=r.patient_weights(p)
        self.assertAlmostEqual(float(w[p=="a"].sum()),0.5)
        self.assertAlmostEqual(float(w[p=="b"].sum()),0.5)

if __name__=="__main__":
    unittest.main(verbosity=2)
