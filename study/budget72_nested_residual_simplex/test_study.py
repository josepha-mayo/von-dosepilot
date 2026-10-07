import unittest
import numpy as np
import run_study as r

class NestedSimplexTests(unittest.TestCase):
    def test_perfect_expert(self):
        p=np.stack([np.ones((2,4,1)),np.zeros((2,4,1)),np.full((2,4,1),2.)])
        w,_=r.solve_simplex(np.zeros((4,1)),p,np.array(['a','b','c','d']))
        np.testing.assert_allclose(w,[0,1,0],atol=1e-12)
    def test_convex_cancellation(self):
        p=np.stack([np.ones((2,4,1)),-np.ones((2,4,1)),np.full((2,4,1),3.)])
        w,_=r.solve_simplex(np.zeros((4,1)),p,np.array(['a','b','c','d']))
        np.testing.assert_allclose(np.einsum('k,konq->onq',w,p),0,atol=1e-12)
    def test_solver_beats_random_feasible_weights(self):
        rng=np.random.default_rng(18);y=rng.normal(size=(9,3));p=rng.normal(size=(3,2,9,3));ids=np.array(['a']*5+['b','c','d','e'])
        w,d=r.solve_simplex(y,p,ids);G=np.array(d['gram'])
        grid=rng.dirichlet(np.ones(3),size=2000)
        self.assertLessEqual(float(w@G@w),float(np.min(np.einsum('nk,kl,nl->n',grid,G,grid)))+1e-12)
        self.assertGreaterEqual(float(w.min()),0)
        self.assertAlmostEqual(float(w.sum()),1)
    def test_duplicate_experts_are_safe(self):
        y=np.zeros((4,1));p=np.ones((3,2,4,1))
        w,d=r.solve_simplex(y,p,np.array(['a','b','c','d']))
        self.assertAlmostEqual(float(w.sum()),1);self.assertAlmostEqual(d['inner_mse'],1)
    def test_oof_assignment_preserves_axes(self):
        oof=np.full((10,2,7,24),np.nan);mask=np.array([True,False,False,True,False,True,False]);pp=np.arange(10*2*3*24).reshape(10,2,3,24)
        for oi in range(10):
            for orient in range(2): oof[oi,orient,mask,:]=pp[oi,orient]
        for oi in range(10):
            for orient in range(2): np.testing.assert_array_equal(oof[oi,orient,mask,:],pp[oi,orient])
    def test_nan_inputs_rejected(self):
        with self.assertRaises(ValueError): r.solve_simplex(np.zeros((4,1)),np.full((3,2,4,1),np.nan),np.array(['a','b','c','d']))

if __name__=='__main__': unittest.main(verbosity=2)
