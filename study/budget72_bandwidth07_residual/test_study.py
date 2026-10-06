import sys,unittest
from pathlib import Path
import numpy as np

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from bandwidth_additive72 import BandwidthAdditive72
import run_study as r

class Bandwidth72Tests(unittest.TestCase):
    def fixture(self):
        rng=np.random.default_rng(0)
        z=rng.normal(size=(30,72))
        residual=rng.normal(size=(30,24))
        w=np.full(30,1/30)
        owner=np.repeat(np.arange(24),3)
        return z,residual,w,owner

    def test_kernel_and_coefficients(self):
        z,residual,w,owner=self.fixture()
        m=BandwidthAdditive72(z,residual,w,owner,0.7)
        self.assertEqual(m.centered_cross(z[:4]).shape,(4,30))
        c,s,p=m.coefficients(0.1,0.3)
        self.assertEqual(c.shape,(30,24))
        self.assertEqual(p.shape,(24,24))
        self.assertTrue(np.isfinite(c).all())

    def test_owner_contract_rejects_wrong_group_size(self):
        z,residual,w,owner=self.fixture()
        owner=owner.copy();owner[-1]=0
        with self.assertRaises(ValueError):
            BandwidthAdditive72(z,residual,w,owner,0.7)

    def test_frozen_option_grid(self):
        self.assertEqual(len(r.OPTIONS),10)
        self.assertEqual(r.OPTIONS[0],("identity",0.0))
        self.assertEqual(r.OPTIONS[1:],[(f,l) for f in (0.1,0.3,0.6) for l in (0.1,1.0,10.0)])

if __name__=="__main__":
    unittest.main(verbosity=2)
