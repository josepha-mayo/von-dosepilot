import unittest
import numpy as np
from bandwidth_additive import BandwidthAdditive
from mahalanobis_additive import MahalanobisAdditive

class Tests(unittest.TestCase):
    def setUp(self):
        r=np.random.default_rng(20261004)
        self.z=r.normal(size=(36,64))
        self.res=r.normal(scale=.1,size=(36,24))
        w=np.arange(1,37,dtype=float);self.w=w/w.sum()
        self.owner=np.repeat(np.arange(24),[3]*16+[2]*8)

    def test_rho_zero_matches_bandwidth07_geometry(self):
        old=BandwidthAdditive(self.z,self.res,self.w,self.owner,.7)
        new=MahalanobisAdditive(self.z,self.res,self.w,self.owner,0.,.7)
        q=np.random.default_rng(7).normal(size=(5,64))
        np.testing.assert_allclose(new.raw_cross(q),old.raw_cross(q),atol=2e-13,rtol=0)
        np.testing.assert_allclose(new.centered_cross(q),old.centered_cross(q),atol=2e-13,rtol=0)
        for f,l in ((.1,.1),(.3,1.),(.6,10.)):
            np.testing.assert_allclose(new.coefficients(l,f)[0],old.coefficients(l,f)[0],atol=3e-13,rtol=0)

    def test_precision_is_positive_and_trace_normalized(self):
        m=MahalanobisAdditive(self.z,self.res,self.w,self.owner,.5,.7)
        for group,p in zip(m.groups,m.precisions):
            np.testing.assert_allclose(p,p.T,atol=1e-14,rtol=0)
            self.assertGreater(np.linalg.eigvalsh(p).min(),0)
            self.assertAlmostEqual(np.trace(p),len(group),places=13)

    def test_row_permutation_prediction_invariance(self):
        q=np.random.default_rng(8).normal(size=(4,64))
        order=np.random.default_rng(9).permutation(len(self.z))
        a=MahalanobisAdditive(self.z,self.res,self.w,self.owner,.5,.7)
        b=MahalanobisAdditive(self.z[order],self.res[order],self.w[order],self.owner,.5,.7)
        ca=a.coefficients(1.,.1)[0];cb=b.coefficients(1.,.1)[0]
        np.testing.assert_allclose(a.centered_cross(q)@ca,b.centered_cross(q)@cb,atol=3e-12,rtol=0)

    def test_query_batching(self):
        q=np.random.default_rng(10).normal(size=(5,64))
        m=MahalanobisAdditive(self.z,self.res,self.w,self.owner,.5,.7)
        c=m.coefficients(1.,.1)[0]
        batch=m.centered_cross(q)@c
        singles=np.vstack([m.centered_cross(row[None,:])@c for row in q])
        np.testing.assert_allclose(batch,singles,atol=2e-13,rtol=0)

    def test_constant_group_is_finite(self):
        z=self.z.copy();z[:,:3]=4.
        m=MahalanobisAdditive(z,self.res,self.w,self.owner,.5,.7)
        self.assertTrue(np.isfinite(m.raw_cross(z[:2])).all())
        np.testing.assert_allclose(m.precisions[0],np.eye(3),atol=1e-14,rtol=0)

    def test_metadata_shapes(self):
        m=MahalanobisAdditive(self.z,self.res,self.w,self.owner,.5,.7)
        a=m.arrays(m.coefficients(1.,.1)[0])
        self.assertEqual(a['mahalanobis_precision_padded'].shape,(24,3,3))
        self.assertEqual(a['mahalanobis_group_dims'].shape,(24,))
        self.assertAlmostEqual(float(a['mahalanobis_rho']),.5)
        self.assertAlmostEqual(float(a['kernel_bandwidth_multiplier']),.7)

    def test_invalid_geometry_parameters(self):
        for rho in (-.1,1.1,float('nan')):
            with self.assertRaises(ValueError):
                MahalanobisAdditive(self.z,self.res,self.w,self.owner,rho,.7)
        for bw in (0,-1,float('nan')):
            with self.assertRaises(ValueError):
                MahalanobisAdditive(self.z,self.res,self.w,self.owner,.5,bw)

if __name__=='__main__':
    unittest.main(verbosity=2)
