import unittest,itertools
from types import SimpleNamespace
import numpy as np
import run_study as run
import methods_flexible as m
from bandwidth_additive import BandwidthAdditive

class FlexibleTests(unittest.TestCase):
    def catalog(self):
        n=24*8
        return SimpleNamespace(library_id='lib1',native_ids=np.array([f'q{i:03d}' for i in range(n)]),
             target_ids=np.array([f't{i:02d}' for i in range(24)]),native_target_indices=np.repeat(np.arange(24),8),
             concentrations=tuple(str(2.**j) for _ in range(24) for j in range(8)))
    def tables(self):
        c=self.catalog()
        return [{k:{'risk':float((j+1)/(k+.5)),'subset':list(range(j*8,j*8+k)),
              'native_ids':list(map(str,c.native_ids[j*8:j*8+k]))} for k in range(1,7)} for j in range(24)]
    def test_dp_matches_brute_force(self):
        tables=[{1:7.,2:3.,3:1.},{1:8.,2:2.,3:1.7},{1:2.,2:1.,3:.5}]
        sizes,risk=m.choose_sizes(tables,6)
        expected=min((sum(tables[j][k] for j,k in enumerate(v)),v) for v in itertools.product((1,2,3),repeat=3) if sum(v)==6)
        self.assertEqual((risk,sizes),expected)
    def test_dp_infeasible_rejected(self):
        with self.assertRaises(ValueError):m.choose_sizes([{2:1.},{2:2.}],3)
    def test_dp_deterministic_tie(self):
        sizes,risk=m.choose_sizes([{1:0.,2:0.},{1:0.,2:0.}],3)
        self.assertEqual(sizes,(1,2))
    def test_dp_nonfinite_rejected(self):
        with self.assertRaises(ValueError):m.choose_sizes([{1:float('nan')}],1)
    def test_plans_have_exact_budget_and_all_targets(self):
        c=self.catalog()
        for minimum in (1,2):
            p=m.make_plan(self.tables(),c,minimum);m.validate_plan(p,c)
            self.assertEqual(sum(p['cardinalities']),64)
            self.assertEqual(p['orientation_A_plate_indices'].count(0),32)
            self.assertGreaterEqual(min(p['cardinalities']),minimum)
    def test_unpurchased_values_not_read(self):
        c=self.catalog();p=m.make_plan(self.tables(),c,1)
        x=np.full((3,len(c.native_ids),2),np.nan)
        x[:,p['selected_native_indices'],p['orientation_A_plate_indices']]=.5
        self.assertEqual(m.acquire(x,p,'A').shape,(3,64))
        with self.assertRaises(ValueError):m.acquire(x,p,'B')
    def test_duplicate_native_rejected(self):
        p=m.make_plan(self.tables(),self.catalog(),1);p['selected_native_indices'][1]=p['selected_native_indices'][0]
        with self.assertRaises(ValueError):m.validate_plan(p)
    def test_generic_kernel_matches_incumbent(self):
        rng=np.random.default_rng(78);z=rng.normal(size=(24,64));res=rng.normal(size=(24,24));w=np.full(24,1/24)
        owner=np.concatenate([np.full(2 if j<8 else 3,j) for j in range(24)])
        old=BandwidthAdditive(z,res,w,owner,.7);new=m.FlexibleKernel(z,res,w,owner,.7)
        np.testing.assert_allclose(new.raw_cross(z),old.raw_cross(z),atol=1e-12,rtol=0)
        np.testing.assert_allclose(new.coefficients(1.,.3)[0],old.coefficients(1.,.3)[0],atol=1e-11,rtol=0)
    def test_kernel_variable_groups_psd(self):
        rng=np.random.default_rng(9);p=m.make_plan(self.tables(),self.catalog(),1)
        z=rng.normal(size=(25,64));res=rng.normal(size=(25,24));w=np.full(25,1/25)
        k=m.FlexibleKernel(z,res,w,p['coordinate_target_indices'])
        a=k.raw_cross(z);self.assertGreater(np.linalg.eigvalsh((a+a.T)/2).min(),-1e-9)
    def test_cached_subsets_match_reference_two_three(self):
        rng=np.random.default_rng(123);c=self.catalog();x=rng.normal(size=(15,len(c.native_ids),2));y=rng.normal(size=(15,24));p=np.array([f'p{i//2}' for i in range(15)])
        old=run.plan_panel_fast(x,y,p,c);tables=m.fitting_subset_table(x,y,p,c)
        for j in range(24):
            for size in (2,3):
                self.assertEqual(tables[j][size]['subset'],old['choices'][j][f'best{size}'])
                self.assertAlmostEqual(tables[j][size]['risk'],old['choices'][j][f'proxy{size}'],places=12)
    def test_menu_frozen(self):
        self.assertEqual(len(run.MENU),30);self.assertEqual(run.POLICIES[0],'incumbent')

if __name__=='__main__':unittest.main(verbosity=2)
