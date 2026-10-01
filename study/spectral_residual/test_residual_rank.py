import unittest
import numpy as np
from residual_rank import reduced_ridge

class Tests(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(10011925)
        self.x = rng.normal(size=(70, 12)); self.y = rng.normal(size=(70, 5))
        w = rng.uniform(.1, 1, 70); self.w = w/w.sum()
        self.g = self.x.T @ (self.w[:, None]*self.x)
        self.c = self.x.T @ (self.w[:, None]*self.y)
    def test_full_rank_matches_ridge(self):
        b,_=reduced_ridge(self.g,self.c,.1,5)
        np.testing.assert_allclose(b,np.linalg.solve(self.g+.1*np.eye(12),self.c),atol=1e-14)
    def test_rank_cap(self):
        b,_=reduced_ridge(self.g,self.c,.1,2)
        self.assertLessEqual(np.linalg.matrix_rank(b),2)
    def test_augmentation_reference(self):
        # Independent SVD of fitted augmented outputs, not the Cholesky formula.
        lam=.3;rank=3
        a=np.vstack([self.x*np.sqrt(self.w[:,None]),np.sqrt(lam)*np.eye(12)])
        y=np.vstack([self.y*np.sqrt(self.w[:,None]),np.zeros((12,5))])
        full=np.linalg.lstsq(a,y,rcond=None)[0]
        _,_,v=np.linalg.svd(a@full,full_matrices=False)
        direct=full@v[:rank].T@v[:rank]
        actual,_=reduced_ridge(self.g,self.c,lam,rank)
        np.testing.assert_allclose(actual,direct,atol=2e-14,rtol=0)
    def test_monotone_objective_with_rank(self):
        obj=[]
        for rank in range(1,6):
            b,_=reduced_ridge(self.g,self.c,.2,rank)
            obj.append(float(np.sum(self.w[:,None]*(self.y-self.x@b)**2)+.2*np.sum(b*b)))
        self.assertTrue(np.all(np.diff(obj)<=1e-13))
    def test_zero_residual_no_change(self):
        b,_=reduced_ridge(self.g,np.zeros_like(self.c),.1,2)
        np.testing.assert_array_equal(b,np.zeros_like(b))
    def test_target_rotation_equivariance(self):
        q,_=np.linalg.qr(np.random.default_rng(45).normal(size=(5,5)))
        b,_=reduced_ridge(self.g,self.c,.1,3)
        rotated,_=reduced_ridge(self.g,self.c@q,.1,3)
        np.testing.assert_allclose(rotated,b@q,atol=1e-14)
    def test_bad_penalty(self):
        for lam in [0,-1,float('nan')]:
            with self.assertRaises(ValueError):reduced_ridge(self.g,self.c,lam,2)
    def test_bad_rank(self):
        for r in [0,6,1.5]:
            with self.assertRaises(ValueError):reduced_ridge(self.g,self.c,.1,r)
    def test_nonfinite(self):
        c=self.c.copy();c[0,0]=np.nan
        with self.assertRaises(ValueError):reduced_ridge(self.g,c,.1,2)
    def test_asymmetric(self):
        g=self.g.copy();g[0,1]+=.1
        with self.assertRaises(ValueError):reduced_ridge(g,self.c,.1,2)
if __name__=='__main__':unittest.main(verbosity=2)
