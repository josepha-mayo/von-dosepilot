import unittest
import numpy as np
from additive_kernel import AdditiveKernel
class Tests(unittest.TestCase):
    def setUp(self):
        rng=np.random.default_rng(202610021123);self.z=rng.normal(size=(32,64));self.r=rng.normal(size=(32,24));self.w=np.ones(32)/32;self.owner=np.repeat(np.arange(24),[3]*16+[2]*8);self.m=AdditiveKernel(self.z,self.r,self.w,self.owner)
    def test_diagonal_budget(self):np.testing.assert_allclose(np.diag(self.m.raw_cross(self.z)),np.sum(self.z*self.z,axis=1)+64,atol=1e-12)
    def test_psd(self):self.assertGreaterEqual(np.linalg.eigvalsh(self.m.raw_cross(self.z)).min(),-1e-10)
    def test_centered(self):np.testing.assert_allclose(self.w@self.m.centered_cross(self.z),0,atol=1e-13)
    def test_explicit_formula(self):
        query=self.z[:3]+.13;k=query@self.z.T
        for g in self.m.groups:k+=len(g)*np.exp(-np.sum((query[:,None,g]-self.z[None,:,g])**2,axis=-1)/(2*len(g)))
        np.testing.assert_allclose(k,self.m.raw_cross(query),atol=1e-12)
    def test_query_batch(self):
        c=self.m.coefficients(1.,.1)[0];q=self.z[:4]+.03
        np.testing.assert_allclose(self.m.predict(q,c),np.concatenate([self.m.predict(v[None,:],c) for v in q]),atol=1e-13)
    def test_owner_relabel_invariant(self):
        m=AdditiveKernel(self.z,self.r,self.w,23-self.owner)
        np.testing.assert_allclose(m.raw_cross(self.z),self.m.raw_cross(self.z),atol=1e-12)
    def test_wrong_allocation(self):
        bad=self.owner.copy();bad[0]=1
        with self.assertRaises(ValueError):AdditiveKernel(self.z,self.r,self.w,bad)
    def test_fraction_one(self):np.testing.assert_array_equal(self.m.coefficients(1.,1.)[0],np.zeros((32,24)))
if __name__=='__main__':unittest.main(verbosity=2)
