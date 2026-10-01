import unittest
import numpy as np
from coverage_methods import plan_panel,CoverageCatalog,acquire,fit_prediction_context,CoveragePredictor
from fast_coverage import plan_panel_fast
KEYS=['selected_native_indices','selected_native_ids','coordinate_target_indices','selected_concentrations_nM','orientation_A_plate_indices','orientation_B_plate_indices','upgraded_target_ids','choices']
class Tests(unittest.TestCase):
 def fixture(self,seed=1,constant=False):
  rng=np.random.default_rng(seed);x=rng.normal(size=(20,120,2));y=rng.normal(size=(20,24));p=np.array([f'p{i//2}' for i in range(20)])
  c=CoverageCatalog(np.array([f'q{i:03}' for i in range(120)]),np.array([f'd{i:02}' for i in range(24)]),np.repeat(np.arange(24),5),tuple(['1','3','10','30','100']*24))
  if constant:x[:]=1;y[:]=.5
  return x,y,p,c
 def test_four_random_fixtures(self):
  for seed in range(4):
   with self.subTest(seed=seed):
    x,y,p,c=self.fixture(seed);a=plan_panel(x,y,p,c);b=plan_panel_fast(x,y,p,c)
    for k in KEYS:self.assertEqual(a[k],b[k],k)
 def test_exact_ties(self):
  x,y,p,c=self.fixture(constant=True);a=plan_panel(x,y,p,c);b=plan_panel_fast(x,y,p,c)
  self.assertGreater(b['near_tie_reference_rechecks'],0)
  for k in KEYS:self.assertEqual(a[k],b[k],k)
 def test_duplicate_patient_balance(self):
  x,y,p,c=self.fixture();a=plan_panel(x,y,p,c);b=plan_panel_fast(np.repeat(x,2,0),np.repeat(y,2,0),np.repeat(p,2),c)
  for k in KEYS[:-1]:self.assertEqual(a[k],b[k],k)
 def test_predictor_equivalence(self):
  x,y,p,c=self.fixture();a=plan_panel(x,y,p,c);b=plan_panel_fast(x,y,p,c)
  for lam in (.01,.1,1.,10.):
   pred=[]
   for plan in [a,b]:
    pa,pb=[acquire(x,plan,o) for o in ['A','B']];ctx=fit_prediction_context(pa,pb,y,p,plan,c.target_ids);m=CoveragePredictor(ctx,plan,lam);pred.append(m.predict(pa))
   np.testing.assert_array_equal(*pred)
 def test_nonfinite_rejected(self):
  x,y,p,c=self.fixture();x[0,0,0]=np.nan
  with self.assertRaises(ValueError):plan_panel_fast(x,y,p,c)
 def test_unpaid_mask(self):
  x,y,p,c=self.fixture();b=plan_panel_fast(x,y,p,c);v=acquire(x,b,'A');masked=np.full_like(x,np.nan);masked[:,b['selected_native_indices'],b['orientation_A_plate_indices']]=v
  np.testing.assert_array_equal(v,acquire(masked,b,'A'))
if __name__=='__main__':unittest.main(verbosity=2)
