import unittest
import numpy as np
from additive_kernel import AdditiveKernel
from bandwidth_additive import BandwidthAdditive
from bandwidth_inference import BandwidthAdditiveModel

class Tests(unittest.TestCase):
    def setUp(self):
        r=np.random.default_rng(703)
        self.z=r.normal(size=(28,64));self.res=r.normal(scale=.1,size=(28,24))
        self.w=np.arange(1,29,dtype=float);self.w/=self.w.sum()
        self.owner=np.repeat(np.arange(24),[3]*16+[2]*8)
    def test_multiplier_one_matches_historical_kernel(self):
        a=AdditiveKernel(self.z,self.res,self.w,self.owner)
        b=BandwidthAdditive(self.z,self.res,self.w,self.owner,1.)
        q=np.random.default_rng(2).normal(size=(6,64))
        np.testing.assert_array_equal(a.raw_cross(q),b.raw_cross(q))
        for f,l in ((.1,.1),(.3,1.),(.6,10.)):
            np.testing.assert_allclose(a.coefficients(l,f)[0],b.coefficients(l,f)[0],atol=1e-14,rtol=0)
    def test_metadata_roundtrip(self):
        m=BandwidthAdditive(self.z,self.res,self.w,self.owner,.7)
        arrays=m.arrays(m.coefficients(1.,.1)[0])
        self.assertEqual(arrays['kernel_bandwidth_multiplier'].shape,())
        self.assertAlmostEqual(float(arrays['kernel_bandwidth_multiplier']),.7,places=15)
    def test_inference_kernel_matches_training_kernel(self):
        m=BandwidthAdditive(self.z,self.res,self.w,self.owner,.7)
        fake=BandwidthAdditiveModel.__new__(BandwidthAdditiveModel)
        fake.owner=self.owner.copy();fake.bandwidth=.7
        q=np.random.default_rng(5).normal(size=(4,64))
        np.testing.assert_allclose(fake._kernel(q,self.z),m.raw_cross(q),atol=1e-14,rtol=0)
    def test_invalid_multiplier(self):
        for x in (0,-1,float('nan')):
            with self.assertRaises(ValueError):BandwidthAdditive(self.z,self.res,self.w,self.owner,x)
    def test_inference_rejects_wrong_declared_multiplier(self):
        fake=BandwidthAdditiveModel.__new__(BandwidthAdditiveModel)
        fake.a={'kernel_owner':self.owner.copy(),'kernel_bandwidth_multiplier':np.asarray(.9)}
        fake.owner=self.owner.copy()
        with self.assertRaises(ValueError):fake._check_kernel_metadata()

if __name__=='__main__':unittest.main(verbosity=2)