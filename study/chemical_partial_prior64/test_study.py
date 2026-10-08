import unittest
import numpy as np
from source import complete_correlation,partial_bank,strict

class PartialTests(unittest.TestCase):
    def correlation(self,n):
        x=np.arange(n);return np.exp(-np.abs(x[:,None]-x[None,:])/.8)
    def test_nanomolar_to_logmolar(self):
        np.testing.assert_allclose(strict.log_molar([1,10,1000]),[-9,-8,-6],atol=1e-14,rtol=0)
    def test_invalid_dose_rejected(self):
        with self.assertRaises(ValueError):strict.log_molar([0,1])
    def test_completion_identity(self):
        r=self.correlation(7);ix=np.array([2,3,4]);out=complete_correlation(r,ix,r[np.ix_(ix,ix)])
        np.testing.assert_allclose(out,.9*r+.1*np.eye(7),atol=1e-12,rtol=0)
    def test_all_coordinates_matched(self):
        p=self.correlation(4);s=.4*np.ones((4,4))+.6*np.eye(4)
        np.testing.assert_allclose(complete_correlation(p,np.arange(4),s),.9*s+.1*np.eye(4),atol=1e-12,rtol=0)
    def test_completed_matrix_positive_definite(self):
        p=self.correlation(8);s=.99*np.ones((3,3))+.01*np.eye(3);ix=np.array([3,4,5])
        q=complete_correlation(p,ix,s);self.assertGreater(np.linalg.eigvalsh(q).min(),0)
        np.testing.assert_allclose(np.diag(q),1,atol=1e-12);np.testing.assert_allclose(q[np.ix_(ix,ix)],.9*s+.1*np.eye(3),atol=1e-12)
    def test_nan_correlation_rejected(self):
        p=self.correlation(4);p[0,0]=np.nan
        with self.assertRaises(ValueError):complete_correlation(p,np.arange(2),np.eye(2))
    def fixture(self):
        rng=np.random.default_rng(63);v=rng.normal(size=(12,5));nsc=np.array(['100']*8+['200']*4)
        cells=np.array([f'c{i%4}' for i in range(12)]);high=np.full(12,-4.)
        return v,nsc,cells,high
    def test_partial_range_does_not_extrapolate(self):
        v,n,c,h=self.fixture();doses=[.1,1,10,100,1000];r=self.correlation(5)
        q,record=partial_bank(v,n,c,h,['100'],doses,r,min_cells=3)
        self.assertEqual(record['covered_indices'],[2,3,4]);self.assertFalse(record['source_response_extrapolation'])
        self.assertGreater(np.linalg.eigvalsh(q).min(),0)
    def test_unsupported_compound_preserves_control(self):
        v,n,c,h=self.fixture();r=self.correlation(5)
        q,record=partial_bank(v,n,c,h,['999'],[.1,1,10,100,1000],r,min_cells=3)
        np.testing.assert_array_equal(q,.9*r+.1*np.eye(5));self.assertEqual(record['status'],'POOLED_FALLBACK')
    def test_unmatched_external_values_do_not_affect_prior(self):
        v,n,c,h=self.fixture();r=self.correlation(5);doses=[.1,1,10,100,1000]
        a,_=partial_bank(v,n,c,h,['100'],doses,r,min_cells=3);v[n=='200']+=999
        b,_=partial_bank(v,n,c,h,['100'],doses,r,min_cells=3);np.testing.assert_array_equal(a,b)
    def test_equal_total_cell_weight(self):
        w=strict.equal_cell_compound_weights(['a','a','a','b'],['10','10','20','10'])
        self.assertAlmostEqual(w[:3].sum(),.5);self.assertAlmostEqual(w[-1],.5)
        self.assertAlmostEqual(w[:2].sum(),w[2])

if __name__=='__main__':unittest.main(verbosity=2)
