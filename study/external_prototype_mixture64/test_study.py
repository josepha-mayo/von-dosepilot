import unittest
import numpy as np
from scipy.special import logsumexp
from model import (compress_external,external_covariance,relative_correlation,fit_target,
                   mixture_population,condition_mixture,predict_mixture,original)

class MixtureTests(unittest.TestCase):
    def fixture(self):
        rng=np.random.default_rng(163)
        centres=rng.normal(size=(19,5));weights=np.arange(1,20,dtype=float);weights/=weights.sum()
        mean=weights@centres;cov=external_covariance(centres,weights)+.2*np.eye(5)
        bank={'centres5':centres,'weights':weights,'mean5':mean,'covariance5':cov}
        curves=rng.normal(size=(17,7,2));patients=np.array([f'p{i//2}' for i in range(17)])
        positions=np.linspace(0,1,7);corr=relative_correlation(cov,positions)
        target=fit_target(curves,patients,corr,.5)
        q=np.repeat(np.array([.05,.1,.2,.3,.2,.1,.05])/2,2)
        return curves,patients,positions,bank,target,q
    def test_compression_preserves_weighted_mean_and_covariance_decomposition(self):
        rng=np.random.default_rng(72);v=rng.normal(size=(80,5));w=np.arange(1,81,dtype=float);w/=w.sum()
        bank=compress_external(v,w,n_clusters=8)
        np.testing.assert_allclose(bank['weights']@bank['centres5'],w@v,atol=1e-12,rtol=0)
        d=bank['centres5']-bank['mean5'];between=d.T@(bank['weights'][:,None]*d)
        np.testing.assert_allclose(between+bank['quantization_covariance5'],external_covariance(v,w),atol=1e-12,rtol=0)
        self.assertGreaterEqual(np.linalg.eigvalsh(bank['quantization_covariance5']).min(),-1e-10)
    def test_compression_invalid_mass_rejected(self):
        with self.assertRaises(ValueError):compress_external(np.ones((8,5)),np.ones(8),n_clusters=4)
    def test_mixture_matches_first_two_moments(self):
        x,p,t,b,target,q=self.fixture();m=mixture_population(target,x,p,t,b)
        mean=m['weights']@m['means'];d=m['means']-mean
        covariance=m['common_covariance']+d.T@(m['weights'][:,None]*d)
        np.testing.assert_allclose(mean,target['mean'],atol=1e-12,rtol=0)
        np.testing.assert_allclose(covariance,target['covariance'],atol=1e-12,rtol=0)
    def test_common_covariance_is_positive_definite(self):
        x,p,t,b,target,q=self.fixture();m=mixture_population(target,x,p,t,b)
        self.assertGreater(np.linalg.eigvalsh(m['common_covariance']).min(),0.)
    def test_local_duplicate_patient_distribution_invariant(self):
        x,p,t,b,target,q=self.fixture();m=mixture_population(target,x,p,t,b);mask=p==p[0]
        xx=np.concatenate((x,x[mask]));pp=np.concatenate((p,p[mask]))
        tt=fit_target(xx,pp,relative_correlation(b['covariance5'],t),.5)
        mm=mixture_population(tt,xx,pp,t,b);ix=np.array([0,5,10]);query=x[:4].reshape(4,-1)[:,ix]
        np.testing.assert_allclose(predict_mixture(condition_mixture(m,ix,q),query),
          predict_mixture(condition_mixture(mm,ix,q),query),atol=1e-11,rtol=0)
    def test_independent_cholesky_logsumexp_posterior(self):
        x,p,t,b,target,q=self.fixture();m=mixture_population(target,x,p,t,b);ix=np.array([0,5,10])
        query=x[:4].reshape(4,-1)[:,ix];s=condition_mixture(m,ix,q)
        chol=np.linalg.cholesky(m['common_covariance'][np.ix_(ix,ix)])
        delta=query[:,None,:]-m['means'][None,:,ix]
        solved=np.linalg.solve(chol,delta.reshape(-1,len(ix)).T).T.reshape(delta.shape)
        logw=np.log(m['weights'])[None,:]-.5*np.sum(solved*solved,axis=2)
        posterior=np.exp(logw-logsumexp(logw,axis=1,keepdims=True))
        slope=np.linalg.solve(m['common_covariance'][np.ix_(ix,ix)],m['common_covariance'][ix]@q)
        conditional=m['means'][None,:,:]@q+np.einsum('bni,i->bn',delta,slope)
        expected=np.sum(posterior*conditional,axis=1)
        np.testing.assert_allclose(predict_mixture(s,query),expected,atol=1e-12,rtol=0)
    def test_single_component_equals_gaussian(self):
        x,p,t,b,target,q=self.fixture();ix=np.array([0,5,10])
        m={'means':target['mean'][None,:],'common_covariance':target['covariance'],'weights':np.ones(1)}
        query=x[:4].reshape(4,-1)[:,ix]
        np.testing.assert_allclose(predict_mixture(condition_mixture(m,ix,q),query),
          original.predict(original.condition(target,ix,q),query),atol=1e-12,rtol=0)
    def test_all_observed_exact_endpoint(self):
        x,p,t,b,target,q=self.fixture();m=mixture_population(target,x,p,t,b);v=x.reshape(len(x),-1)
        np.testing.assert_allclose(predict_mixture(condition_mixture(m,np.arange(14),q),v),v@q,atol=1e-11,rtol=0)
    def test_extreme_finite_query_stable(self):
        x,p,t,b,target,q=self.fixture();m=mixture_population(target,x,p,t,b)
        self.assertTrue(np.isfinite(predict_mixture(condition_mixture(m,np.array([0,5,10]),q),np.full((2,3),1000.))).all())
    def test_query_nan_rejected(self):
        x,p,t,b,target,q=self.fixture();m=mixture_population(target,x,p,t,b)
        with self.assertRaises(ValueError):predict_mixture(condition_mixture(m,np.array([0,5,10]),q),np.full((2,3),np.nan))
    def test_duplicate_physical_coordinate_rejected(self):
        x,p,t,b,target,q=self.fixture();m=mixture_population(target,x,p,t,b)
        with self.assertRaises(ValueError):condition_mixture(m,np.array([0,0,5]),q)
    def test_invalid_mixture_mass_rejected(self):
        x,p,t,b,target,q=self.fixture();m=mixture_population(target,x,p,t,b);m['weights']*=2
        with self.assertRaises(ValueError):condition_mixture(m,np.array([0,5,10]),q)

if __name__=='__main__':unittest.main(verbosity=2)
