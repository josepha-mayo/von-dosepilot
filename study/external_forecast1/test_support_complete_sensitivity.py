import unittest
import numpy as np
import support_complete_sensitivity as e

class Tests(unittest.TestCase):
    def setUp(self):
        rng=np.random.default_rng(44)
        self.doses=np.tile(np.logspace(-3,2,9),(6,1))
        self.x=rng.uniform(-0.1,1.2,(30,6,9))
        self.p=np.array(["P%02d"%(i//2) for i in range(30)])
        self.y=e.auc_targets(self.x,self.doses)

    def test_patient_mass_equal(self):
        w=e.patient_weights(self.p)
        for pid in np.unique(self.p):
            self.assertAlmostEqual(w[self.p==pid].sum(),1/15)
        self.assertAlmostEqual(w.sum(),1)
    def test_auc_constant(self):
        x=np.ones((3,6,9))*0.37
        np.testing.assert_allclose(e.auc_targets(x,self.doses),0.37,atol=1e-15)

    def test_auc_log_linear(self):
        x=np.stack([2+3*np.log(self.doses)]*4)
        target=e.auc_targets(x,self.doses)
        expected=(x[:,:,0]+x[:,:,-1])/2
        np.testing.assert_allclose(target,expected,atol=1e-13)

    def test_interpolation_weights(self):
        for subset in ([0,8],[1,4,7],[0,4,8]):
            w=e.interp_weights(self.doses[0],subset)
            self.assertAlmostEqual(w.sum(),1)
            self.assertTrue((w>=0).all())

    def test_candidate_budget(self):
        p=e.candidate_plan(self.x,self.y,self.p)
        self.assertEqual(sum(map(len,p["subsets"])),16)
        self.assertEqual(sum(len(s)==3 for s in p["subsets"]),4)
    def test_interpolation_budget(self):
        p=e.interp_plan(self.x,self.y,self.p,self.doses)
        self.assertEqual(sum(map(len,p["subsets"])),16)
        self.assertEqual(sum(len(s)==3 for s in p["subsets"]),4)

    def test_candidate_model_shape(self):
        plan=e.candidate_plan(self.x,self.y,self.p)
        model=e.fit_model(self.x,self.y,self.p,plan,0.1)
        pred=e.predict(self.x,model)
        self.assertEqual(pred.shape,(30,6))
        self.assertTrue(np.isfinite(pred).all())

    def test_interpolation_shape(self):
        plan=e.interp_plan(self.x,self.y,self.p,self.doses)
        pred=e.interp_predict(self.x,plan,self.doses)
        self.assertEqual(pred.shape,(30,6))
        self.assertTrue(np.isfinite(pred).all())

    def test_plan_unique_within_drug(self):
        for plan in (e.candidate_plan(self.x,self.y,self.p),
                     e.interp_plan(self.x,self.y,self.p,self.doses)):
            for subset in plan["subsets"]:
                self.assertEqual(len(subset),len(set(subset)))
    def test_cv_patient_separation(self):
        lam,scores,folds=e.cv_select_lambda(self.x,self.y,self.p)
        self.assertIn(lam,e.LAMBDAS)
        self.assertEqual(len(scores),4)
        self.assertEqual(len(folds),5)
        self.assertEqual(sum(f["valid_patients"] for f in folds),15)

    def test_weighted_mse_zero(self):
        self.assertEqual(e.weighted_mse(self.y,self.y,self.p),0)

    def test_compatible_dose_rounding(self):
        a=np.array([[1e-5,4e-5,1.6e-4]])
        b=a*np.array([[1.0005,0.9996,1.0002]])
        self.assertTrue(e.compatible_dose_grids(a,b))
        self.assertFalse(e.compatible_dose_grids(a,a*1.01))

    def test_patient_parser(self):
        self.assertEqual(e.patient_id("WCB123LM"),"WCB123")
        with self.assertRaises(ValueError):
            e.patient_id("bad")

    def test_nonfinite_context_propagates_to_prediction_guard(self):
        plan=e.candidate_plan(self.x,self.y,self.p)
        model=e.fit_model(self.x,self.y,self.p,plan,0.1)
        bad=self.x.copy(); selected=plan["subsets"][0][0]; bad[0,0,selected]=np.nan
        with self.assertRaises(ValueError):
            e.predict(bad,model)

if __name__=="__main__":
    unittest.main(verbosity=2)