import sys,unittest
from pathlib import Path
from types import SimpleNamespace
import numpy as np
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import run_study as r

class LowRidgeTests(unittest.TestCase):
    def test_frozen_grids(self):
        self.assertEqual(r.LAMBDAS,(0.0001,0.0003,0.001,0.003,0.01))
        self.assertEqual(len(r.OPTIONS),10)
        self.assertEqual(r.OPTIONS[-1],(0.6,10.0))
        self.assertEqual(len(r.LAMBDAS)*len(r.OPTIONS),50)

    def test_incumbent_base_lambda_is_included(self):
        self.assertIn(0.01,r.LAMBDAS)
        self.assertEqual(r.LAMBDAS[-1],0.01)

    def test_lower_lambda_changes_ridge_strength(self):
        ctx=SimpleNamespace(
          mean_x=np.zeros(72),scale_x=np.ones(72),mean_y=np.zeros(24),
          cxx=np.eye(72),cxy=np.ones((72,24)))
        plan={"coordinate_target_indices":np.repeat(np.arange(24),3)}
        low=r.parent.bc.Predictor(ctx,plan,0.0001)
        old=r.parent.bc.Predictor(ctx,plan,0.01)
        self.assertGreater(float(np.abs(low.beta).sum()),float(np.abs(old.beta).sum()))

    def test_inner_oof_assignment_axes(self):
        oof=np.full((5,10,2,7,24),np.nan)
        pred=np.arange(10*2*3*24,dtype=float).reshape(10,2,3,24)
        mask=np.array([True,False,True,False,False,True,False])
        li=2
        for oi in range(len(r.OPTIONS)):
            for orient in range(2):
                oof[li,oi,orient,mask,:]=pred[oi,orient]
        for oi in range(len(r.OPTIONS)):
            for orient in range(2):
                np.testing.assert_array_equal(oof[li,oi,orient,mask,:],pred[oi,orient])

if __name__=="__main__":
    unittest.main(verbosity=2)
