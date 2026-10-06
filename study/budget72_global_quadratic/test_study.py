import sys,unittest
from pathlib import Path
import numpy as np

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import run_study as r
from global_quadratic72 import GlobalQuadratic72

class GlobalQuadraticTests(unittest.TestCase):
    def fixture(self):
        rng=np.random.default_rng(0)
        z=rng.normal(size=(24,72))
        residual=rng.normal(size=(24,24))
        w=np.full(24,1/24)
        owner=np.repeat(np.arange(24),3)
        return z,residual,w,owner

    def test_zero_strength_exact_incumbent_parity(self):
        z,residual,w,owner=self.fixture()
        base=r.parent.BandwidthAdditive72(z,residual,w,owner,0.7)
        cand=GlobalQuadratic72(z,residual,w,owner,0.0,0.7)
        np.testing.assert_allclose(cand.raw_cross(z),base.raw_cross(z),atol=0,rtol=0)
        np.testing.assert_allclose(
            cand.coefficients(1.0,0.3)[0],
            base.coefficients(1.0,0.3)[0],
            atol=1e-12,rtol=0)

    def test_positive_quadratic_is_finite_psd(self):
        z,residual,w,owner=self.fixture()
        cand=GlobalQuadratic72(z,residual,w,owner,0.25,0.7)
        k=cand.raw_cross(z)
        self.assertTrue(np.isfinite(k).all())
        eig=np.linalg.eigvalsh((k+k.T)/2)
        self.assertGreater(eig.min(),-1e-9)
        self.assertTrue(np.isfinite(cand.coefficients(1.0,0.3)[0]).all())

    def test_frozen_grid_contains_incumbent(self):
        self.assertEqual(r.STRENGTHS,(0.0,0.0625,0.125,0.25,0.5,1.0))
        self.assertEqual(len(r.OPTIONS),10)
        self.assertEqual(len(r.STRENGTHS)*len(r.OPTIONS),60)

if __name__=="__main__":
    unittest.main(verbosity=2)
