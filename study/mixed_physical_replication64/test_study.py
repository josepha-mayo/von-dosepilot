import sys,unittest
from itertools import combinations
from types import SimpleNamespace
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE),str(HERE.parents[1]/'study/engine')]
from planner import target_moments,enumerate_physical,batched_proxy,plan_pair,validate_physical,acquire_physical,weights
from coverage_methods import validate_plan as validate_original

class PhysicalPlannerTests(unittest.TestCase):
    def fixture(self):
        rng=np.random.default_rng(839);n=18;x=rng.normal(size=(n,72,2));y=rng.normal(size=(n,24));p=np.array([f'p{i//2}' for i in range(n)])
        cat=SimpleNamespace(library_id='lib1',native_ids=np.array([f'n{i}' for i in range(72)]),target_ids=np.array([f't{i:02}' for i in range(24)]),native_target_indices=np.repeat(np.arange(24),3),concentrations=tuple(['1','10','100']*24))
        return x,y,p,cat
    def test_enumeration_matches_exhaustive_physical_sets(self):
        for n in (3,4):
            for size in (2,3):
                for allow in (False,True):
                    expected={c for c in combinations(range(2*n),size) if sum(v%2==0 for v in c)==size-1 and (allow or len({v//2 for v in c})==size)}
                    actual={tuple(c) for c in enumerate_physical(n,size,allow)}
                    self.assertEqual(expected,actual)
    def test_batched_proxy_matches_independent_penalized_fit(self):
        x,y,p,_=self.fixture();v=x[:,:4];target=y[:,0];moment=target_moments(v,target,p)
        for size in (2,3):
            subsets=enumerate_physical(4,size,True);actual=batched_proxy(moment,subsets)
            for subset,score in zip(subsets,actual):
                train=np.r_[v.reshape(len(v),-1)[:,subset],v[:,:,::-1].reshape(len(v),-1)[:,subset]];truth=np.r_[target,target]
                w=np.tile(weights(p),2)/2;mx=w@train;my=w@truth;sx=np.maximum(np.sqrt(w@((train-mx)**2)),.05)
                z=(train-mx)/sx;beta=np.linalg.solve(z.T@(w[:,None]*z)+.1*np.eye(size),z.T@(w*(truth-my)))
                independent=float(w@((truth-my-z@beta)**2)+.1*np.sum(beta**2))
                self.assertAlmostEqual(float(score),independent,places=12)
    def test_budgets_and_target_counts(self):
        x,y,p,cat=self.fixture();plans=plan_pair(x,y,p,cat)
        for plan in plans.values():
            validate_physical(plan,cat);self.assertEqual(plan['orientation_A_plate_indices'].count(0),32)
            self.assertEqual(sum(np.bincount(plan['coordinate_target_indices'])==3),16)
        self.assertEqual(plans['distinct_physical']['distinct_native_doses'],64)
    def test_replicate_can_be_selected_and_original_guard_not_bypassed(self):
        x,y,p,cat=self.fixture();rng=np.random.default_rng(922)
        for j in range(24):
            base=y[:,j];noise=rng.normal(scale=3,size=len(p));x[:,3*j,0]=base+noise;x[:,3*j,1]=base-noise
            x[:,3*j+1:3*j+3,:]=rng.normal(scale=10,size=(len(p),2,2))
        plan=plan_pair(x,y,p,cat)['mixed_replication'];self.assertGreater(plan['replicated_native_doses'],0)
        self.assertFalse(plan['original_64_distinct_native_contract_satisfied'])
        with self.assertRaises(ValueError):validate_original(plan,cat)
    def test_acquisition_uses_only_paid_cells(self):
        x,y,p,cat=self.fixture();plan=plan_pair(x,y,p,cat)['mixed_replication'];idx=np.asarray(plan['selected_native_indices'])
        for o in ('A','B'):
            plate=np.asarray(plan[f'orientation_{o}_plate_indices']);masked=np.full_like(x,np.nan);masked[:,idx,plate]=x[:,idx,plate]
            np.testing.assert_array_equal(acquire_physical(x,plan,o),acquire_physical(masked,plan,o))
    def test_duplicate_same_physical_cell_rejected(self):
        x,y,p,cat=self.fixture();plan=plan_pair(x,y,p,cat)['mixed_replication']
        plan['selected_native_indices'][1]=plan['selected_native_indices'][0]
        plan['orientation_A_plate_indices'][1]=plan['orientation_A_plate_indices'][0]
        plan['orientation_B_plate_indices'][1]=plan['orientation_B_plate_indices'][0]
        with self.assertRaises(ValueError):validate_physical(plan)
    def test_missing_paid_input_rejected(self):
        x,y,p,cat=self.fixture();plan=plan_pair(x,y,p,cat)['mixed_replication'];n=plan['selected_native_indices'][0];pl=plan['orientation_A_plate_indices'][0];x[0,n,pl]=np.nan
        with self.assertRaises(ValueError):acquire_physical(x,plan,'A')
    def test_group_duplicates_preserve_moments(self):
        x,y,p,_=self.fixture();idx=np.flatnonzero(p==p[0]);a=target_moments(x[:,:4],y[:,0],p)
        b=target_moments(np.r_[x[:,:4],x[idx,:4]],np.r_[y[:,0],y[idx,0]],np.r_[p,p[idx]])
        for key in a:np.testing.assert_allclose(a[key],b[key],atol=1e-12,rtol=0)
    def test_nonfinite_fit_rejected(self):
        x,y,p,_=self.fixture();x[0,0,0]=np.nan
        with self.assertRaises(ValueError):target_moments(x[:,:4],y[:,0],p)

if __name__=='__main__':unittest.main(verbosity=2)
