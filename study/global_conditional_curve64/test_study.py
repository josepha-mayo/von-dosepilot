import unittest
import numpy as np
from conditional import patient_weights,quadrature_weights,fit_population,condition,predict

class ConditionalTests(unittest.TestCase):
    def fixture(self):
        rng=np.random.default_rng(732)
        x=rng.normal(size=(25,12,2));p=np.array([f'p{i}' for i in range(len(x))])
        owner=np.repeat(np.arange(4),3)
        q=np.zeros((24,4))
        for j in range(4):q[6*j:6*j+6,j]=1/6
        native=np.array([0,2,3,5,6,8,9,11]);plates=np.tile([0,1],4)
        plan={'selected_native_indices':native,'orientation_A_plate_indices':plates,'orientation_B_plate_indices':1-plates}
        return x,p,owner,q,plan
    def test_quadrature_constant(self):
        q=quadrature_weights([1,3,10,100],[2,50])
        self.assertAlmostEqual(q.sum(),1)
        self.assertGreaterEqual(q.min(),0)
    def test_quadrature_log_linear_exact(self):
        d=np.array([1,3,10,100]);bounds=[2,50]
        q=quadrature_weights(d,bounds)
        self.assertAlmostEqual(float(q@np.log(d)),float(np.mean(np.log(bounds))))
    def test_outside_bounds_rejected(self):
        with self.assertRaises(ValueError):quadrature_weights([1,10],[.1,5])
    def test_unsorted_doses_rejected(self):
        with self.assertRaises(ValueError):quadrature_weights([1,10,5],[1,5])
    def test_covariance_positive_definite(self):
        x,p,owner,q,plan=self.fixture()
        for rank in (0,4,12):
            pop=fit_population(x,p,owner,rank)
            self.assertGreater(np.linalg.eigvalsh(pop['covariance']).min(),0)
    def test_rank_zero_has_no_cross_drug_covariance(self):
        x,p,owner,q,plan=self.fixture();pop=fit_population(x,p,owner,0)
        np.testing.assert_array_equal(pop['covariance'][:6,6:],0.)
    def test_direct_gaussian_conditional_equivalence(self):
        x,p,owner,q,plan=self.fixture();pop=fit_population(x,p,owner,4);s=condition(pop,plan,q)
        v=x[0].ravel();idx=s['orientations']['A']['indices'];rawcov=pop['scale'][:,None]*pop['covariance']*pop['scale'][None,:]
        expected=pop['mean']@q+(v[idx]-pop['mean'][idx])@np.linalg.solve(rawcov[np.ix_(idx,idx)],rawcov[idx]@q)
        np.testing.assert_allclose(predict(s,v[idx][None,:],'A')[0],expected,atol=1e-11,rtol=0)
    def test_all_observed_reconstructs_exact_auc(self):
        x,p,owner,q,plan=self.fixture();pop=fit_population(x,p,owner,12)
        plan={'selected_native_indices':np.repeat(np.arange(12),2),'orientation_A_plate_indices':np.tile([0,1],12),'orientation_B_plate_indices':np.tile([1,0],12)}
        s=condition(pop,plan,q);v=x.reshape(len(x),-1)
        np.testing.assert_allclose(predict(s,v,'A'),v@q,atol=2e-11,rtol=0)
    def test_duplicate_patient_row_invariant(self):
        x,p,owner,q,plan=self.fixture();a=fit_population(x,p,owner,4)
        b=fit_population(np.concatenate((x,x[:1])),np.concatenate((p,p[:1])),owner,4)
        np.testing.assert_allclose(a['covariance'],b['covariance'],atol=1e-11,rtol=0)
    def test_nonfinite_training_rejected(self):
        x,p,owner,q,plan=self.fixture();x[0,0,0]=np.nan
        with self.assertRaises(ValueError):fit_population(x,p,owner,4)
    def test_nonfinite_query_rejected(self):
        x,p,owner,q,plan=self.fixture();s=condition(fit_population(x,p,owner,4),plan,q)
        with self.assertRaises(ValueError):predict(s,np.full((2,8),np.nan),'A')
    def test_duplicate_physical_input_rejected(self):
        x,p,owner,q,plan=self.fixture();plan['selected_native_indices'][1]=0;plan['orientation_A_plate_indices'][1]=0
        with self.assertRaises(ValueError):condition(fit_population(x,p,owner,4),plan,q)
    def test_patient_weights_equal_total(self):
        p=np.array(['a','a','b']);w=patient_weights(p)
        self.assertAlmostEqual(w[:2].sum(),w[2])

if __name__=='__main__':unittest.main(verbosity=2)
