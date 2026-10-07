import unittest
import numpy as np
from model import patient_weights,smooth_templates,fit_population,condition,predict

class ShapeMixtureTests(unittest.TestCase):
    def population(self):
        rng=np.random.default_rng(771);m=rng.normal(size=(7,10));a=rng.normal(size=(10,10))
        cov=a@a.T/10+.1*np.eye(10);w=np.arange(1,8,dtype=float);w/=w.sum()
        return {'means':m,'covariance':cov,'weights':w}
    def curves(self):
        rng=np.random.default_rng(551);t=np.linspace(0.,1.,8)
        y=np.array([.8-.7/(1+np.exp(-8*(t-c))) for c in np.linspace(0,1,12)])
        x=y[:,:,None]+rng.normal(scale=.04,size=(12,8,2));p=np.array([f'p{i}' for i in range(12)])
        return x,t,p
    def test_single_component_equivalence(self):
        pop=self.population();pop['means']=pop['means'][:1];pop['weights']=np.ones(1)
        q=np.arange(1,11)/55.;ix=[0,2,6];x=np.ones((5,3))
        np.testing.assert_allclose(predict(condition(pop,ix,q,'mixture'),x),predict(condition(pop,ix,q,'gaussian_control'),x),atol=1e-12)
    def test_all_observed_endpoint_is_exact(self):
        pop=self.population();q=np.ones(10)/10;x=np.random.default_rng(11).normal(size=(8,10))
        for mode in ('mixture','gaussian_control'):
            np.testing.assert_allclose(predict(condition(pop,np.arange(10),q,mode),x),x@q,atol=1e-11,rtol=0)
    def test_independent_gaussian_formula(self):
        pop=self.population();q=np.arange(1,11)/55.;ix=np.array([1,3,4]);x=np.ones((4,3))
        mu=pop['weights']@pop['means'];diff=pop['means']-mu
        cov=pop['covariance']+diff.T@(pop['weights'][:,None]*diff)
        expected=mu@q+(x-mu[ix])@np.linalg.solve(cov[np.ix_(ix,ix)],cov[ix]@q)
        np.testing.assert_allclose(predict(condition(pop,ix,q,'gaussian_control'),x),expected,atol=1e-12)
    def test_independent_component_posterior_formula(self):
        pop=self.population();q=np.ones(10)/10;ix=np.array([0,4,6]);x=np.array([[.1,.2,.3]])
        c=pop['covariance'][np.ix_(ix,ix)];slope=np.linalg.solve(c,pop['covariance'][ix]@q)
        weighted=[];means=[]
        for mu,w in zip(pop['means'],pop['weights']):
            residual=x[0]-mu[ix];weighted.append(w*np.exp(-.5*residual@np.linalg.solve(c,residual)))
            means.append(mu@q+residual@slope)
        expected=np.dot(weighted,means)/np.sum(weighted)
        self.assertAlmostEqual(float(predict(condition(pop,ix,q),x)[0]),float(expected),places=12)
    def test_component_order_invariance(self):
        pop=self.population();other={k:v.copy() for k,v in pop.items()};other['means']=other['means'][::-1];other['weights']=other['weights'][::-1]
        q=np.ones(10)/10;x=np.ones((4,3))
        np.testing.assert_allclose(predict(condition(pop,[0,2,3],q),x),predict(condition(other,[0,2,3],q),x),atol=1e-12)
    def test_zero_endpoint_returns_zero(self):
        pop=self.population();s=condition(pop,[0,1],np.zeros(10))
        np.testing.assert_allclose(predict(s,np.ones((3,2))),0.,atol=1e-15)
    def test_constant_curve_uses_constant(self):
        x=np.full((4,8,2),.73);templates,param=smooth_templates(x,np.linspace(0.,1.,8))
        np.testing.assert_allclose(templates,.73,atol=1e-14);np.testing.assert_array_equal(param[:,1],0.)
    def test_covariance_positive_and_templates_finite(self):
        x,t,p=self.curves();pop=fit_population(x,t,p)
        self.assertGreaterEqual(np.linalg.eigvalsh(pop['covariance']).min(),.0001-1e-12)
        self.assertTrue(np.isfinite(pop['means']).all())
    def test_duplicate_single_patient_row_invariance(self):
        x,t,p=self.curves();a=fit_population(x,t,p);b=fit_population(np.concatenate([x,x[:1]]),t,np.concatenate([p,p[:1]]))
        q=np.ones(16)/16;query=np.ones((4,3))
        for mode in ('mixture','gaussian_control'):
            np.testing.assert_allclose(predict(condition(a,[1,4,8],q,mode),query),predict(condition(b,[1,4,8],q,mode),query),atol=1e-11,rtol=0)
    def test_weights_equal_patient_total(self):
        p=np.array(['a','a','b']);w=patient_weights(p);self.assertAlmostEqual(float(w[:2].sum()),float(w[2]))
    def test_missing_query_rejected(self):
        s=condition(self.population(),[0,2],np.ones(10)/10)
        with self.assertRaises(ValueError):predict(s,np.array([[np.nan,1.]]))
    def test_missing_training_rejected(self):
        x,t,p=self.curves();x[0,0,0]=np.nan
        with self.assertRaises(ValueError):fit_population(x,t,p)
    def test_duplicate_observation_rejected(self):
        with self.assertRaises(ValueError):condition(self.population(),[0,0],np.ones(10)/10)
    def test_wrong_query_width_rejected(self):
        s=condition(self.population(),[0,2],np.ones(10)/10)
        with self.assertRaises(ValueError):predict(s,np.ones((2,3)))

if __name__=='__main__':unittest.main(verbosity=2)
