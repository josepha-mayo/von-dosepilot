import unittest
import numpy as np
from additive_kernel import AdditiveKernel
from local_bandwidth_additive import (
    GLOBAL_BANDWIDTH, LocalBandwidthAdditive, local_multipliers, weighted_median,
)
from local_bandwidth_inference import LocalBandwidthAdditiveModel

class Tests(unittest.TestCase):
    def setUp(self):
        rng=np.random.default_rng(20261004)
        self.z=rng.normal(size=(30,64));self.res=rng.normal(scale=.1,size=(30,24))
        self.w=np.arange(1,31,dtype=float);self.w/=self.w.sum()
        self.owner=np.repeat(np.arange(24),[3]*16+[2]*8)

    def test_weighted_median(self):
        self.assertEqual(weighted_median([1,2,9],[1,8,1]),2.)

    def test_geometric_mean_is_point_seven(self):
        ell=local_multipliers(self.z,self.w,self.owner)
        self.assertAlmostEqual(float(np.exp(np.mean(np.log(ell)))),GLOBAL_BANDWIDTH,places=13)
        self.assertTrue((ell>0).all())

    def test_constant_geometry_returns_global_bandwidth(self):
        ell=local_multipliers(np.zeros_like(self.z),self.w,self.owner)
        np.testing.assert_allclose(ell,GLOBAL_BANDWIDTH,atol=1e-14,rtol=0)

    def test_row_permutation_invariance(self):
        order=np.random.default_rng(4).permutation(len(self.z))
        a=local_multipliers(self.z,self.w,self.owner)
        b=local_multipliers(self.z[order],self.w[order],self.owner)
        np.testing.assert_allclose(a,b,atol=1e-14,rtol=0)

    def test_kernel_psd(self):
        m=LocalBandwidthAdditive(self.z,self.res,self.w,self.owner)
        raw=m.raw_cross(self.z);mean=self.w@raw;grand=float(mean@self.w)
        centered=raw-(raw@self.w)[:,None]-mean[None,:]+grand
        sw=np.sqrt(self.w);eig=np.linalg.eigvalsh(sw[:,None]*centered*sw[None,:])
        self.assertGreater(eig.min(),-1e-10)

    def test_inference_kernel_matches_training_kernel(self):
        m=LocalBandwidthAdditive(self.z,self.res,self.w,self.owner)
        fake=LocalBandwidthAdditiveModel.__new__(LocalBandwidthAdditiveModel)
        fake.owner=self.owner.copy();fake.local_bandwidths=m.local_multipliers.copy()
        q=np.random.default_rng(5).normal(size=(4,64))
        np.testing.assert_allclose(fake._kernel(q,self.z),m.raw_cross(q),atol=1e-14,rtol=0)

    def test_query_batching(self):
        m=LocalBandwidthAdditive(self.z,self.res,self.w,self.owner)
        coef=m.coefficients(1.,.1)[0];q=np.random.default_rng(6).normal(size=(4,64))
        batch=m.centered_cross(q)@coef
        single=np.vstack([m.centered_cross(row[None,:])@coef for row in q])
        np.testing.assert_allclose(batch,single,atol=1e-13,rtol=0)

    def test_metadata_rejects_wrong_geomean(self):
        fake=LocalBandwidthAdditiveModel.__new__(LocalBandwidthAdditiveModel)
        fake.a={"kernel_owner":self.owner.copy(),
                "kernel_bandwidth_multiplier":np.asarray(.7),
                "local_bandwidth_multipliers":np.full(24,.9)}
        fake.owner=self.owner.copy()
        with self.assertRaises(ValueError):fake._check_kernel_metadata()

    def test_local_rule_does_not_receive_responses(self):
        # Signature intentionally contains only input geometry, weights and ownership.
        import inspect
        self.assertEqual(list(inspect.signature(local_multipliers).parameters),
                         ["z","weights","owner"])

if __name__=="__main__":unittest.main(verbosity=2)
