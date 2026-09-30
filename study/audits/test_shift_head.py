import unittest
import numpy as np
from coverage_methods import CoveragePredictor, fit_prediction_context
from sparse_methods import LAMBDAS
from shift_head import ShiftConstrainedPredictor


def fixture():
    rng=np.random.default_rng(2042)
    counts=[3]*16+[2]*8
    owner=np.repeat(np.arange(24), counts)
    plates=[]
    for j,k in enumerate(counts):
        plates.extend((j%2+np.arange(k))%2 if k==3 else np.arange(k)%2)
    plan={'selected_native_indices':list(range(64)), 'selected_native_ids':[f'q{i}' for i in range(64)],
          'coordinate_target_indices':owner.tolist(), 'orientation_A_plate_indices':list(map(int,plates)),
          'orientation_B_plate_indices':list(map(int,1-np.array(plates)))}
    x=rng.normal(size=(60,64)); b=x+rng.normal(scale=.12,size=x.shape)
    y=np.stack([x[:,owner==j].mean(1)+rng.normal(scale=.07,size=60) for j in range(24)],axis=1)
    patients=np.array([f'P{i//2}' for i in range(60)])
    ctx=fit_prediction_context(x,b,y,patients,plan,[f'd{j}' for j in range(24)])
    return x,b,y,patients,plan,ctx

class Tests(unittest.TestCase):
    def setUp(self):
        self.x,self.b,self.y,self.p,self.plan,self.c=fixture()
    def test_zero_is_exact_baseline(self):
        for lam in LAMBDAS:
            a=CoveragePredictor(self.c,self.plan,lam)
            b=ShiftConstrainedPredictor(self.c,self.plan,lam,0.)
            np.testing.assert_array_equal(a.beta,b.beta)
            np.testing.assert_array_equal(a.predict(self.x),b.predict(self.x))
    def test_hard_raw_slope_sum_one(self):
        for lam in LAMBDAS:
            m=ShiftConstrainedPredictor(self.c,self.plan,lam,1.)
            np.testing.assert_allclose((m.beta/m.scale_x[:,None]).sum(0),1,atol=2e-14)
    def test_direct_kkt_solution(self):
        lam=.1;m=ShiftConstrainedPredictor(self.c,self.plan,lam,1.)
        for j in range(24):
            cols=np.flatnonzero(m.feature_mask[j]);a=1/m.scale_x[cols]
            h=self.c.cxx[np.ix_(cols,cols)]+lam*np.eye(len(cols))
            kkt=np.block([[h,a[:,None]],[a[None,:],np.zeros((1,1))]])
            rhs=np.r_[self.c.cxy[cols,j],1.]
            np.testing.assert_allclose(m.beta[cols,j],np.linalg.solve(kkt,rhs)[:-1],atol=1e-13)
    def test_half_is_exact_convex_coefficient_path(self):
        a=ShiftConstrainedPredictor(self.c,self.plan,.1,0.)
        b=ShiftConstrainedPredictor(self.c,self.plan,.1,1.)
        h=ShiftConstrainedPredictor(self.c,self.plan,.1,.5)
        np.testing.assert_allclose(h.beta,(a.beta+b.beta)/2,atol=1e-15)
    def test_own_head_shift_equivariance(self):
        m=ShiftConstrainedPredictor(self.c,self.plan,.1,1.)
        shifted=self.x.copy();shifted[:,m.feature_mask[5]]+=.17
        d=m.predict(shifted)-m.predict(self.x)
        expected=np.zeros_like(d);expected[:,5]=.17
        np.testing.assert_allclose(d,expected,atol=1e-14)
    def test_all_head_different_shifts(self):
        m=ShiftConstrainedPredictor(self.c,self.plan,.1,1.)
        delta=np.linspace(-.2,.2,24)
        shifted=self.x+delta[np.array(self.plan['coordinate_target_indices'])]
        np.testing.assert_allclose(m.predict(shifted)-m.predict(self.x),np.tile(delta,(60,1)),atol=1e-14)
    def test_training_orientation_exchange(self):
        c=fit_prediction_context(self.b,self.x,self.y,self.p,self.plan,[f'd{j}' for j in range(24)])
        a=ShiftConstrainedPredictor(self.c,self.plan,.1,1.)
        b=ShiftConstrainedPredictor(c,self.plan,.1,1.)
        np.testing.assert_allclose(a.predict(self.x),b.predict(self.x),atol=1e-14)
    def test_weight_mass(self):
        for p in np.unique(self.p):
            expanded=np.r_[self.p,self.p]
            self.assertAlmostEqual(self.c.weights[expanded==p].sum(),1.)
            self.assertAlmostEqual((self.c.weights/self.c.weights.sum())[expanded==p].sum(),1/30)
    def test_context_unchanged(self):
        before={n:getattr(self.c,n).copy() for n in ('mean_x','scale_x','mean_y','cxx','cxy')}
        ShiftConstrainedPredictor(self.c,self.plan,.1,1.)
        for n,a in before.items():np.testing.assert_array_equal(a,getattr(self.c,n))
    def test_bad_strength_rejected(self):
        with self.assertRaises(ValueError):ShiftConstrainedPredictor(self.c,self.plan,.1,.25)
    def test_nonfinite_paid_rejected(self):
        m=ShiftConstrainedPredictor(self.c,self.plan,.1,1.);bad=self.x.copy();bad[0,0]=np.nan
        with self.assertRaises(ValueError):m.predict(bad)
    def test_wrong_paid_width_rejected(self):
        m=ShiftConstrainedPredictor(self.c,self.plan,.1,1.)
        with self.assertRaises(ValueError):m.predict(self.x[:,:63])
    def test_own_drug_coefficients_only(self):
        m=ShiftConstrainedPredictor(self.c,self.plan,.1,1.)
        self.assertTrue((m.beta[~m.feature_mask.T]==0).all())

if __name__=='__main__':unittest.main()
