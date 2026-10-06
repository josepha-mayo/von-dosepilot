import sys,unittest
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import run_study as r
from pair_augmented72 import PairAugmented72

class PairTests(unittest.TestCase):
    def fixture(self):
        rng=np.random.default_rng(0)
        z=rng.normal(size=(24,72))
        residual=rng.normal(size=(24,24))
        w=np.full(24,1/24)
        owner=np.repeat(np.arange(24),3)
        return z,residual,w,owner

    def test_strength_zero_exact_incumbent_parity(self):
        z,residual,w,owner=self.fixture()
        base=r.parent.BandwidthAdditive72(z,residual,w,owner,0.7)
        pair=PairAugmented72(z,residual,w,owner,0.0,0.7)
        np.testing.assert_allclose(pair.raw_cross(z),base.raw_cross(z),atol=0,rtol=0)
        c0=base.coefficients(1.0,0.3)[0]
        c1=pair.coefficients(1.0,0.3)[0]
        np.testing.assert_allclose(c1,c0,atol=1e-12,rtol=0)

    def test_positive_pair_kernel_is_finite(self):
        z,residual,w,owner=self.fixture()
        pair=PairAugmented72(z,residual,w,owner,0.25,0.7)
        self.assertTrue(np.isfinite(pair.raw_cross(z[:3])).all())
        self.assertGreaterEqual(pair.pair_scale,0.0)
        c=pair.coefficients(1.0,0.3)[0]
        self.assertTrue(np.isfinite(c).all())

    def test_frozen_grid_contains_incumbent(self):
        self.assertEqual(r.STRENGTHS,(0.0,0.1,0.25,0.5))
        self.assertEqual(len(r.OPTIONS),10)
        self.assertEqual(len(r.STRENGTHS)*len(r.OPTIONS),40)

if __name__=="__main__":
    unittest.main(verbosity=2)
