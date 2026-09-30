import unittest
import numpy as np
from coverage_methods import CoverageCatalog, acquire, subset_orientations
from interpolation_policy import integration_weights, patient_weights, plan_panel, predict_paid

class InterpolationTests(unittest.TestCase):
    def setUp(self):
        self.cat = CoverageCatalog(np.array([f'd{j:02}_{k}' for j in range(24) for k in range(4)]),
                np.array([f'd{j:02}' for j in range(24)]), np.repeat(np.arange(24), 4),
                tuple(['1', '10', '100', '1000'] * 24))
        self.bounds = np.tile([1., 1000.], (24, 1))
        rng = np.random.default_rng(27)
        self.x = rng.uniform(0, 1, (6, 96, 2))
        self.y = rng.uniform(0, 1, (6, 24))
        self.patients = ['a', 'a', 'b', 'c', 'd', 'e']
    def test_constant(self):
        self.assertAlmostEqual(integration_weights([1, 10, 100], [2, 200]).sum(), 1)
    def test_linear(self):
        x = np.array([1., 3., 20., 100.])
        self.assertAlmostEqual(integration_weights(x, [2, 50]) @ (2 + 3*np.log(x)), 2+3*np.log(100)/2)
    def test_outside(self):
        np.testing.assert_allclose(integration_weights([10, 100], [1, 1000]), [.5, .5])
    def test_invalid(self):
        for d,b in [([0,1],[1,2]),([1,1],[1,2]),([2,1],[1,2]),([1,np.inf],[1,2]),([1,2],[2,1])]:
            with self.subTest(d=d,b=b), self.assertRaises(ValueError): integration_weights(d,b)
    def test_patient_balance(self):
        np.testing.assert_allclose(patient_weights(['a','a','b']), [.25,.25,.5])
    def test_plan_and_identity(self):
        plan=plan_panel(self.x,self.y,self.patients,self.cat,self.bounds)
        self.assertEqual(len(set(plan['selected_native_ids'])),64)
        self.assertEqual(plan['orientation_A_plate_indices'].count(0),32)
        self.assertEqual(plan['orientation_B_plate_indices'].count(0),32)
        self.assertEqual(len(plan['upgraded_target_ids']),16)
        for o in ('A','B'):
            paid=acquire(self.x,plan,o)
            pred=predict_paid(paid,plan)
            self.assertEqual(pred.shape,(6,24))
            self.assertTrue(np.all((pred>=0)&(pred<=1)))
    def test_flip_symmetry(self):
        a,b=subset_orientations(self.x,[0,1,2]); w=integration_weights([1,10,100],[1,1000])
        np.testing.assert_allclose(((a@w-self.y[:,0])**2+(b@w-self.y[:,0])**2)/2,
            ((b@w-self.y[:,0])**2+(a@w-self.y[:,0])**2)/2)
    def test_fit_risk_matches_paid(self):
        plan=plan_panel(self.x,self.y,self.patients,self.cat,self.bounds)
        errors=[(predict_paid(acquire(self.x,plan,o),plan)-self.y)**2 for o in ('A','B')]
        observed=patient_weights(self.patients) @ ((errors[0]+errors[1])/2).mean(axis=1)
        chosen=sum(c['risk3' if c['target_id'] in plan['upgraded_target_ids'] else 'risk2'] for c in plan['choices'])/24
        self.assertAlmostEqual(observed,chosen,places=14)
    def test_own_drug_only(self):
        plan=plan_panel(self.x,self.y,self.patients,self.cat,self.bounds)
        values=np.zeros((1,64)); pred0=predict_paid(values,plan)
        values[0,0]=1; pred1=predict_paid(values,plan)
        self.assertEqual(np.count_nonzero(pred1-pred0),1)
    def test_nonfinite(self):
        plan=plan_panel(self.x,self.y,self.patients,self.cat,self.bounds)
        with self.assertRaises(ValueError):predict_paid(np.full((1,64),np.nan),plan)
    def test_no_unpaid_values(self):
        plan=plan_panel(self.x,self.y,self.patients,self.cat,self.bounds)
        with self.assertRaises(ValueError):predict_paid(np.zeros((1,128)),plan)
if __name__=='__main__':unittest.main(verbosity=2)
