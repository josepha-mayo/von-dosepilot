import unittest
import numpy as np
import run_study as r

class SweepTests(unittest.TestCase):
    def test_grid_is_frozen(self):
        self.assertEqual(r.BANDWIDTHS,(0.4,0.55,0.7,0.9,1.2))
        self.assertEqual(len(r.OPTIONS),46)
        self.assertEqual(r.OPTIONS[0],("identity",0.0,0.0))
    def test_each_bandwidth_has_nine_options(self):
        for bw in r.BANDWIDTHS:
            self.assertEqual(sum(1 for x in r.OPTIONS[1:] if x[0]==bw),9)
    def test_parent_kernel_accepts_all_bandwidths(self):
        rng=np.random.default_rng(0)
        z=rng.normal(size=(20,72));res=rng.normal(size=(20,24))
        w=np.full(20,1/20);owner=np.repeat(np.arange(24),3)
        for bw in r.BANDWIDTHS:
            m=r.parent.BandwidthAdditive72(z,res,w,owner,bw)
            self.assertEqual(m.multiplier,bw)
if __name__=="__main__":
    unittest.main(verbosity=2)
