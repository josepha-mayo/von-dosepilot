import sys,unittest
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import run_study as r
from shape_bandwidth72 import ShapeBandwidth72

class ShapeTests(unittest.TestCase):
    def fixture(self):
        rng=np.random.default_rng(0)
        z=rng.normal(size=(24,72)); residual=rng.normal(size=(24,24))
        w=np.full(24,1/24); owner=np.repeat(np.arange(24),3)
        conc=np.tile(np.array([1.0,3.0,10.0]),24)
        return z,residual,w,owner,conc

    def test_identity_shape_matches_incumbent(self):
        z,residual,w,owner,conc=self.fixture()
        base=r.parent.BandwidthAdditive72(z,residual,w,owner,0.7)
        cand=ShapeBandwidth72(z,residual,w,owner,conc,(1,1,1),0.7)
        np.testing.assert_allclose(cand.raw_cross(z),base.raw_cross(z),atol=2e-12,rtol=0)
        np.testing.assert_allclose(cand.coefficients(1.0,0.3)[0],
                                   base.coefficients(1.0,0.3)[0],atol=2e-11,rtol=0)

    def test_shape_geometry_is_finite_psd(self):
        z,residual,w,owner,conc=self.fixture()
        cand=ShapeBandwidth72(z,residual,w,owner,conc,(1,1,.25),0.7)
        k=cand.raw_cross(z)
        self.assertTrue(np.isfinite(k).all())
        self.assertGreater(np.linalg.eigvalsh((k+k.T)/2).min(),-1e-9)

    def test_frozen_grid(self):
        self.assertEqual(len(r.SHAPES),6)
        self.assertEqual(r.SHAPES[0],(1.0,1.0,1.0))
        self.assertEqual(len(r.SHAPES)*len(r.OPTIONS),60)

if __name__=="__main__":
    unittest.main(verbosity=2)
