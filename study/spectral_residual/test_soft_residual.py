import unittest
import numpy as np
from residual_rank import reduced_ridge
from soft_residual import soft_reduced_ridge
class Tests(unittest.TestCase):
    def setUp(self):
        r=np.random.default_rng(20011925);x=r.normal(size=(90,12));y=r.normal(size=(90,5))
        self.g=x.T@x/90;self.c=x.T@y/90
    def test_zero_fraction_full_ridge(self):
        a,_,_=soft_reduced_ridge(self.g,self.c,.1,0.)
        b,_=reduced_ridge(self.g,self.c,.1,5)
        np.testing.assert_allclose(a,b,atol=1e-14,rtol=0)
    def test_fraction_one_is_zero(self):
        b,_,_=soft_reduced_ridge(self.g,self.c,.1,1.)
        np.testing.assert_array_equal(b,np.zeros_like(b))
    def test_shrunk_values(self):
        b,s,sv=soft_reduced_ridge(self.g,self.c,1.,.3)
        lo=np.linalg.cholesky(self.g+np.eye(12))
        np.testing.assert_allclose(np.linalg.svd(lo.T@b,compute_uv=False),sv,atol=1e-14)
        np.testing.assert_allclose(sv,np.maximum(s-.3*s[0],0))
    def test_stationary_subgradient(self):
        b,s,sv=soft_reduced_ridge(self.g,self.c,.1,.1)
        lo=np.linalg.cholesky(self.g+.1*np.eye(12));t=lo.T@b;g=np.linalg.solve(lo,self.c)
        u,s_t,v=np.linalg.svd(t,full_matrices=False)
        self.assertTrue((s_t>1e-12).all())
        np.testing.assert_allclose(g-t,.1*s[0]*(u@v),atol=1e-14)
    def test_invalid_fraction(self):
        with self.assertRaises(ValueError):soft_reduced_ridge(self.g,self.c,.1,.2)
if __name__=='__main__':unittest.main(verbosity=2)
