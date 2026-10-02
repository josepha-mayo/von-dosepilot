import copy
import unittest
import numpy as np
from global_acquisition import moments, direct_proxy, block_scores, optimize
from coverage_methods import CoverageCatalog, acquire, fit_prediction_context
from fast_coverage import plan_panel_fast

class Tests(unittest.TestCase):
    def setUp(self):
        r=np.random.default_rng(10021625)
        self.x=r.normal(size=(20,120,2));self.y=r.normal(size=(20,24))
        self.p=np.array([f'p{i//2}' for i in range(20)])
        self.c=CoverageCatalog(np.array([f'q{i:03}' for i in range(120)]),
            np.array([f'd{i:02}' for i in range(24)]), np.repeat(np.arange(24),5),
            tuple(['1','3','10','30','100']*24))
        self.plan=plan_panel_fast(self.x,self.y,self.p,self.c)
    def test_cached_selected_moments_match_reference(self):
        g,b,v=moments(self.x,self.y,self.p)
        cols=2*np.array(self.plan['selected_native_indices'])+self.plan['orientation_A_plate_indices']
        a,bb=[acquire(self.x,self.plan,o) for o in ('A','B')]
        ctx=fit_prediction_context(a,bb,self.y,self.p,self.plan,self.c.target_ids)
        np.testing.assert_allclose(g[np.ix_(cols,cols)],ctx.cxx,atol=2e-14,rtol=0)
        np.testing.assert_allclose(b[cols],ctx.cxy,atol=2e-14,rtol=0)
        self.assertAlmostEqual(v,np.trace(ctx.cyy),places=13)
    def test_schur_matches_full_solve(self):
        g,b,v=moments(self.x,self.y,self.p)
        keep=np.arange(5,65);candidates=[np.array([0,1,2]),np.array([0,2,3]),np.array([1,3,4])]
        fast=block_scores(g,b,v,keep,candidates)
        slow=[direct_proxy(g,b,v,np.r_[keep,c]) for c in candidates]
        np.testing.assert_allclose(fast,slow,atol=1e-13,rtol=0)
    def test_one_sweep_budget_and_monotone(self):
        p=optimize(self.x,self.y,self.p,self.c,self.plan)
        self.assertEqual(len(p['search_records']),24)
        self.assertEqual(len(set(p['selected_native_indices'])),64)
        self.assertEqual(p['orientation_A_plate_indices'],self.plan['orientation_A_plate_indices'])
        self.assertLessEqual(p['proxy_final'],p['proxy_initial']+1e-12)
    def test_permutation_invariance(self):
        a=optimize(self.x,self.y,self.p,self.c,self.plan)
        ix=np.random.default_rng(5).permutation(20)
        b=optimize(self.x[ix],self.y[ix],self.p[ix],self.c,self.plan)
        self.assertEqual(a['selected_native_indices'],b['selected_native_indices'])
    def test_no_mutation(self):
        plan=copy.deepcopy(self.plan);x=self.x.copy()
        optimize(self.x,self.y,self.p,self.c,self.plan)
        self.assertEqual(plan,self.plan);np.testing.assert_array_equal(x,self.x)
    def test_patient_replication_invariance(self):
        a=optimize(self.x,self.y,self.p,self.c,self.plan)
        ix=np.r_[np.arange(20),0,1]
        b=optimize(self.x[ix],self.y[ix],self.p[ix],self.c,self.plan)
        self.assertEqual(a['selected_native_indices'],b['selected_native_indices'])
    def test_zero_target_signal_preserves_start(self):
        p=optimize(self.x,np.ones_like(self.y),self.p,self.c,self.plan)
        self.assertEqual(p['selected_native_indices'],self.plan['selected_native_indices'])
        self.assertEqual(p['changed_targets'],0)
    def test_unpaid_values_irrelevant(self):
        plan=optimize(self.x,self.y,self.p,self.c,self.plan)
        for o in ('A','B'):
            paid=acquire(self.x,plan,o);masked=np.full_like(self.x,np.nan)
            masked[:,plan['selected_native_indices'],plan[f'orientation_{o}_plate_indices']]=paid
            np.testing.assert_array_equal(acquire(masked,plan,o),paid)
    def test_nonfinite_rejected(self):
        x=self.x.copy();x[0,0,0]=np.nan
        with self.assertRaises(ValueError):optimize(x,self.y,self.p,self.c,self.plan)
if __name__=='__main__':unittest.main(verbosity=2)
