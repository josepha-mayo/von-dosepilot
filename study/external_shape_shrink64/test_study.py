import unittest
import numpy as np
from model import patient_weights,external_covariance,relative_correlation,fit_target,condition,predict

class TransferTests(unittest.TestCase):
    def fixture(self):
        rng=np.random.default_rng(81);curves=rng.normal(size=(17,7,2));p=np.array([f'p{i//2}' for i in range(17)])
        external=rng.normal(size=(31,5));weights=np.arange(1,32,dtype=float);weights/=weights.sum()
        cov=external_covariance(external,weights);t=np.linspace(0,1,7);corr=relative_correlation(cov,t)
        q=np.repeat(np.array([.05,.1,.2,.3,.2,.1,.05])/2,2)
        return curves,p,cov,corr,q
    def test_external_covariance_weighted_definition(self):
        rng=np.random.default_rng(5);x=rng.normal(size=(11,5));w=np.arange(1,12,dtype=float);w/=w.sum();mean=sum(w[i]*x[i] for i in range(11))
        expected=sum(w[i]*np.outer(x[i]-mean,x[i]-mean) for i in range(11))
        np.testing.assert_allclose(external_covariance(x,w),expected,atol=1e-13)
    def test_relative_grid_interpolation(self):
        x,p,cov,corr,q=self.fixture();s=relative_correlation(cov,np.linspace(0,1,5));sd=np.sqrt(np.diag(cov))
        np.testing.assert_allclose(s,cov/(sd[:,None]*sd[None,:]),atol=1e-13)
    def test_source_unit_scaling_invariance(self):
        x,p,cov,corr,q=self.fixture();np.testing.assert_allclose(corr,relative_correlation(10000*cov,np.linspace(0,1,7)),atol=1e-13)
    def test_invalid_grid_rejected(self):
        with self.assertRaises(ValueError):relative_correlation(np.eye(5),np.array([0,.5,.4,1]))
    def test_invalid_source_weights_rejected(self):
        with self.assertRaises(ValueError):external_covariance(np.ones((4,5)),np.ones(4))
    def test_missing_source_response_rejected(self):
        x=np.ones((4,5));x[0,0]=np.nan
        with self.assertRaises(ValueError):external_covariance(x,np.full(4,.25))
    def test_all_local_control_source_invariance(self):
        x,p,cov,corr,q=self.fixture();a=fit_target(x,p,corr,0.);b=fit_target(x,p,np.eye(7),0.)
        np.testing.assert_array_equal(a['mean'],b['mean']);np.testing.assert_array_equal(a['covariance'],b['covariance'])
    def test_external_strength_changes_mean_covariance_only(self):
        x,p,cov,corr,q=self.fixture();a=fit_target(x,p,corr,0.);b=fit_target(x,p,corr,.5)
        np.testing.assert_array_equal(a['mean'],b['mean']);np.testing.assert_array_equal(a['contrast_covariance'],b['contrast_covariance'])
        self.assertGreater(float(np.max(abs(a['mean_covariance']-b['mean_covariance']))),1e-5)
    def test_positive_definite_paired_covariances(self):
        x,p,cov,corr,q=self.fixture()
        for strength in (0.,.5):self.assertGreater(np.linalg.eigvalsh(fit_target(x,p,corr,strength)['covariance']).min(),0.)
    def test_independent_gaussian_conditional_formula(self):
        x,p,cov,corr,q=self.fixture();target=fit_target(x,p,corr,.5);ix=np.array([0,5,10]);s=condition(target,ix,q);v=x.reshape(len(x),-1)[:3,ix]
        expected=target['mean']@q+(v-target['mean'][ix])@np.linalg.inv(target['covariance'][np.ix_(ix,ix)])@target['covariance'][ix]@q
        np.testing.assert_allclose(predict(s,v),expected,atol=1e-12,rtol=0)
    def test_all_observed_endpoint_exact(self):
        x,p,cov,corr,q=self.fixture();s=condition(fit_target(x,p,corr,.5),np.arange(14),q);v=x.reshape(len(x),-1)
        np.testing.assert_allclose(predict(s,v),v@q,atol=1e-11,rtol=0)
    def test_duplicate_patient_row_invariant(self):
        x,p,cov,corr,q=self.fixture();a=fit_target(x,p,corr,.5)
        # Duplicate all rows of one patient, preserving that patient's empirical distribution.
        mask=p==p[0];xx=np.concatenate((x,x[mask]));pp=np.concatenate((p,p[mask]));b=fit_target(xx,pp,corr,.5)
        np.testing.assert_allclose(a['mean'],b['mean'],atol=1e-13);np.testing.assert_allclose(a['covariance'],b['covariance'],atol=1e-13)
    def test_missing_query_rejected(self):
        x,p,cov,corr,q=self.fixture();s=condition(fit_target(x,p,corr,.5),np.array([0,5,10]),q)
        with self.assertRaises(ValueError):predict(s,np.full((2,3),np.nan))
    def test_duplicate_physical_index_rejected(self):
        x,p,cov,corr,q=self.fixture()
        with self.assertRaises(ValueError):condition(fit_target(x,p,corr,.5),np.array([0,0,5]),q)
    def test_training_nan_rejected(self):
        x,p,cov,corr,q=self.fixture();x[0,0,0]=np.nan
        with self.assertRaises(ValueError):fit_target(x,p,corr,.5)
    def test_source_zero_variance_fallback(self):
        np.testing.assert_array_equal(relative_correlation(np.zeros((5,5)),np.linspace(0,1,7)),np.eye(7))

if __name__=='__main__':unittest.main(verbosity=2)
