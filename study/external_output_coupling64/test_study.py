import unittest
import numpy as np
from model import coefficients
from source import weighted_auc,output_prior

class OutputTests(unittest.TestCase):
    def fixture(self):
        rng=np.random.default_rng(326);x=rng.normal(size=(13,7));k=x@x.T;y=rng.normal(size=(13,3))
        w=np.arange(1,14,dtype=float);w/=w.sum();sw=np.sqrt(w);e,u=np.linalg.eigh(sw[:,None]*k*sw[None,:])
        c=np.array([[1,.4,-.1],[.4,1,.2],[-.1,.2,1]])
        return k,y,w,e,u,c
    def test_independent_full_kronecker_system(self):
        k,y,w,e,u,c=self.fixture();lam=.3;sw=np.sqrt(w);a=sw[:,None]*k*sw[None,:]
        rhs=(sw[:,None]*y).reshape(-1,order='F')
        full=np.linalg.solve(np.kron(c,a)+lam*np.eye(y.size),rhs).reshape(y.shape,order='F')
        expected=k@(sw[:,None]*full)@c
        actual=k@coefficients(e,u,w,y,c,lam)
        np.testing.assert_allclose(actual,expected,atol=2e-11,rtol=0)
    def test_identity_matches_independent_ridge(self):
        k,y,w,e,u,c=self.fixture();lam=1.;sw=np.sqrt(w)
        expected=sw[:,None]*np.linalg.solve(sw[:,None]*k*sw[None,:]+lam*np.eye(len(w)),sw[:,None]*y)
        np.testing.assert_allclose(coefficients(e,u,w,y,np.eye(3),lam),expected,atol=2e-12,rtol=0)
    def test_output_permutation_equivariant(self):
        k,y,w,e,u,c=self.fixture();permutation=[2,0,1]
        a=coefficients(e,u,w,y,c,.1);b=coefficients(e,u,w,y[:,permutation],c[np.ix_(permutation,permutation)],.1)
        np.testing.assert_allclose(a[:,permutation],b,atol=2e-12,rtol=0)
    def test_zero_residual_zero_prediction(self):
        k,y,w,e,u,c=self.fixture();np.testing.assert_array_equal(coefficients(e,u,w,np.zeros_like(y),c,1.),0)
    def test_nonpositive_prior_rejected(self):
        k,y,w,e,u,c=self.fixture();c[0,0]=-1
        with self.assertRaises(ValueError):coefficients(e,u,w,y,c,1.)
    def test_nan_residual_rejected(self):
        k,y,w,e,u,c=self.fixture();y[0,0]=np.nan
        with self.assertRaises(ValueError):coefficients(e,u,w,y,c,1.)
    def test_auc_constant_and_linear(self):
        x=np.array([-8.,-7.,-6.]);self.assertAlmostEqual(weighted_auc(x,np.ones(3)),1.)
        self.assertAlmostEqual(weighted_auc(x,x),-7.)
    def test_common_source_cell_covariance(self):
        rng=np.random.default_rng(22);cells=np.array([f'c{i}' for i in range(5)]*3);nsc=np.repeat(['a','b','c'],5)
        values=rng.normal(size=(15,5));high=np.full(15,-4.)
        records=[{'status':'PARTIAL_CHEMICAL_DOSE_TRANSFER','covered_log_molar_range':[-8,-6],'candidates':[name],'drug':name} for name in ('a','b','c')]
        fit=output_prior(values,nsc,cells,high,records,minimum=4)
        self.assertEqual(fit['source_summary_matrix'].shape,(5,3));self.assertEqual(fit['prior'].shape,(3,3))
        self.assertGreaterEqual(fit['min_eigenvalue'],.5-1e-12)
        corr=np.corrcoef(fit['source_summary_matrix'],rowvar=False)
        np.testing.assert_allclose(fit['prior'],.5*corr+.5*np.eye(3),atol=1e-12,rtol=0)
    def test_missing_source_cells_are_not_imputed(self):
        rng=np.random.default_rng(22);cells=np.array(['c0','c1','c2','c3','c4']*2);nsc=np.repeat(['a','b'],5)
        cells[-1]='different';values=rng.normal(size=(10,5));high=np.full(10,-4.)
        records=[{'status':'PARTIAL_CHEMICAL_DOSE_TRANSFER','covered_log_molar_range':[-8,-6],'candidates':[name],'drug':name} for name in ('a','b')]
        with self.assertRaises(ValueError):output_prior(values,nsc,cells,high,records,minimum=5)

if __name__=='__main__':unittest.main(verbosity=2)
