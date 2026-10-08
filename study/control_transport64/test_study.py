import unittest
import numpy as np
from core import control_plane,evaluate_plane,field,to_latent,fit_curve_head,predict_curve_head,patient_weights
from data import normalized_positions

class TransportTests(unittest.TestCase):
    def fixture(self):
        rng=np.random.default_rng(802);n=21
        own=np.r_[np.repeat(np.arange(16),3),np.repeat(np.arange(16,24),2)]
        full=np.repeat(np.arange(24),4)
        a=rng.normal(size=(n,64));b=rng.normal(size=(n,64));y=rng.normal(size=(n,96));p=np.array([f'p{i//2}' for i in range(n)])
        q=np.zeros((96,24))
        for j in range(24):q[full==j,j]=.25
        return a,b,y,p,own,full,q
    def test_affine_roundtrip(self):
        rng=np.random.default_rng(83);raw=rng.normal(size=(6,12));off=rng.normal(size=raw.shape);gain=rng.uniform(.25,4,size=raw.shape)
        np.testing.assert_allclose(off+gain*to_latent(raw,off,gain),raw,atol=1e-14,rtol=0)
    def test_identity_head_matches_direct_auc_ridge(self):
        a,b,y,p,own,full,q=self.fixture();state=fit_curve_head(a,b,y,p,own,full)
        actual=predict_curve_head(state,a,np.zeros_like(y),np.ones_like(y),q)
        xx=np.r_[a,b];target=np.r_[y@q,y@q];w=np.tile(patient_weights(p),2)/2
        mx=w@xx;my=w@target;scale=np.maximum(np.sqrt(w@((xx-mx)**2)),.05);z=(xx-mx)/scale
        expected=np.empty_like(actual)
        for j in range(24):
            c=np.flatnonzero(own==j);zz=z[:,c];beta=np.linalg.solve(zz.T@(w[:,None]*zz)+.01*np.eye(len(c)),zz.T@(w*(target[:,j]-my[j])))
            expected[:,j]=my[j]+((a[:,c]-mx[c])/scale[c])@beta
        np.testing.assert_allclose(actual,expected,atol=1e-12,rtol=0)
    def test_constant_geometry_zero_slope(self):
        pos=np.array([[0.,0.],[0.,.5],[0.,1.]]);signals=np.array([10.,11.,12.]);plane=control_plane(pos,signals,11.,10.,'spatial')
        self.assertEqual(plane['geometry_rank'],1);self.assertEqual(plane['slope'][0],0.)
    def test_flat_field_has_no_spatial_dependence(self):
        plane=control_plane(np.array([[0.,0.],[1.,1.]]),np.array([9.,12.]),10.,10.,'flat')
        val=evaluate_plane(plane,np.array([[0.,0.],[3.,5.]]));self.assertEqual(val[0],val[1])
    def test_identity_field_exact(self):
        pos=np.array([[-1.,-1.],[1.,1.]])
        off,gain,_=field(pos,[100.,120.],pos,[10.,12.],pos,'identity')
        np.testing.assert_array_equal(off,0.);np.testing.assert_array_equal(gain,1.)
    def test_invalid_dynamic_range_rejected(self):
        pos=np.array([[-1.,-1.],[1.,1.]])
        with self.assertRaises(ValueError):field(pos,[1.,1.],pos,[2.,2.],pos,'spatial')
    def test_nonfinite_controls_rejected(self):
        pos=np.array([[0.,0.],[1.,1.]])
        with self.assertRaises(ValueError):control_plane(pos,[np.nan,1.],1.,1.,'spatial')
    def test_missing_query_rejected(self):
        a,b,y,p,own,full,q=self.fixture();state=fit_curve_head(a,b,y,p,own,full);a[0,0]=np.nan
        with self.assertRaises(ValueError):predict_curve_head(state,a,np.zeros_like(y),np.ones_like(y),q)
    def test_patient_duplication_preserves_fit(self):
        a,b,y,p,own,full,q=self.fixture();s=fit_curve_head(a,b,y,p,own,full)
        ix=np.flatnonzero(p==p[0]);s2=fit_curve_head(np.r_[a,a[ix]],np.r_[b,b[ix]],np.r_[y,y[ix]],np.r_[p,p[ix]],own,full)
        for key in s:np.testing.assert_allclose(s[key],s2[key],atol=1e-12,rtol=0)
    def test_geometry_bounds_rejected(self):
        with self.assertRaises(ValueError):normalized_positions([[17,2]])
    def test_raw_endpoint_restoration(self):
        a,b,y,p,own,full,q=self.fixture();s=fit_curve_head(a,b,y,p,own,full)
        z=s['mean_curve']+((a-s['mean_x'])/s['scale_x'])@s['beta_curve']
        off=np.full_like(y,.2);gain=np.full_like(y,1.4)
        np.testing.assert_allclose(predict_curve_head(s,a,off,gain,q),(.2+1.4*z)@q,atol=1e-13,rtol=0)
    def test_fitting_outside_target_columns_zero(self):
        a,b,y,p,own,full,q=self.fixture();s=fit_curve_head(a,b,y,p,own,full)
        for j in range(24):np.testing.assert_array_equal(s['beta_curve'][np.ix_(own!=j,full==j)],0.)

if __name__=='__main__':unittest.main(verbosity=2)
