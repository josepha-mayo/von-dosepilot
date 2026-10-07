import unittest,sys,json,io
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pooled_curve64 import *

class PooledTests(unittest.TestCase):
    def fixture(self):
        rng=np.random.default_rng(91);x=rng.normal(size=(30,15));r=rng.normal(size=30);t=np.tile(np.arange(3),10);p=np.repeat([f'p{i}' for i in range(10)],3)
        return x,r,t,p
    def physical_fixture(self):
        owner=[];dose=[];plate=[]
        for t in range(24):
            ds=[1,10,100] if t<16 else [10,100];start=t%2 if t<16 else 0
            owner.extend([t]*len(ds));dose.extend(ds);plate.extend([(start+i)%2 for i in range(len(ds))])
        plan={'coordinate_target_indices':owner,'selected_native_indices':list(range(64)),
              'selected_concentrations_nM':dose,'orientation_A_plate_indices':plate,'orientation_B_plate_indices':[1-x for x in plate]}
        return plan,np.tile([1.,100.],(24,1))
    def test_schur_equals_independent_dense_ridge(self):
        rng=np.random.default_rng(13);phi=rng.normal(size=(30,5));r=rng.normal(size=30);t=np.tile(np.arange(3),10);w=np.arange(1,31,dtype=float);w/=w.sum();alpha=.03
        s=solve_shared_private(phi,r,t,w,alpha,3)
        design=np.zeros((len(phi),20));design[:,:5]=phi
        for j in range(3):design[t==j,(j+1)*5:(j+2)*5]=phi[t==j]
        b=np.linalg.solve(design.T@(w[:,None]*design)+alpha*np.eye(20),design.T@(w*r))
        actual=np.r_[s['shared'],s['private'].reshape(-1)]
        np.testing.assert_allclose(actual,b,atol=1e-11,rtol=0)
    def test_normal_equations(self):
        x,r,t,p=self.fixture();m=PooledCurveResidual(.01,3).fit(x,r,t,p)
        self.assertLess(m.state['max_normal_equation_error'],1e-11)
    def test_state_round_trip(self):
        x,r,t,p=self.fixture();m=PooledCurveResidual(.01,3).fit(x,r,t,p)
        data=io.BytesIO();np.savez_compressed(data,**m.state);data.seek(0)
        with np.load(data,allow_pickle=False) as z:s={k:z[k] for k in z.files}
        np.testing.assert_allclose(m.predict(x,t),m.predict_state(s,x,t),rtol=0,atol=1e-12)
    def test_repeated_fit_deterministic(self):
        x,r,t,p=self.fixture();a=PooledCurveResidual(.01,3).fit(x,r,t,p);b=PooledCurveResidual(.01,3).fit(x,r,t,p)
        np.testing.assert_array_equal(a.predict(x,t),b.predict(x,t))
    def test_row_order_invariance(self):
        x,r,t,p=self.fixture();order=np.random.default_rng(7).permutation(len(x))
        a=PooledCurveResidual(.01,3).fit(x,r,t,p);b=PooledCurveResidual(.01,3).fit(x[order],r[order],t[order],p[order])
        np.testing.assert_allclose(a.predict(x,t),b.predict(x,t),atol=1e-10,rtol=0)
    def test_duplicate_all_rows_of_one_patient_invariant(self):
        x,r,t,p=self.fixture();mask=p==p[0]
        a=PooledCurveResidual(.01,3).fit(x,r,t,p);b=PooledCurveResidual(.01,3).fit(np.r_[x,x[mask]],np.r_[r,r[mask]],np.r_[t,t[mask]],np.concatenate((p,p[mask])))
        np.testing.assert_allclose(a.predict(x,t),b.predict(x,t),atol=1e-10,rtol=0)
    def test_fit_invalid_nan(self):
        x,r,t,p=self.fixture();x[0,0]=np.nan
        with self.assertRaises(ValueError):PooledCurveResidual(.01,3).fit(x,r,t,p)
    def test_missing_task_rejected(self):
        x,r,t,p=self.fixture()
        with self.assertRaises(ValueError):PooledCurveResidual(.01,4).fit(x,r,t,p)
    def test_predict_invalid_task(self):
        x,r,t,p=self.fixture();m=PooledCurveResidual(.01,3).fit(x,r,t,p)
        with self.assertRaises(ValueError):m.predict(x,np.full(len(x),3))
    def test_predict_before_fit(self):
        with self.assertRaises(ValueError):PooledCurveResidual(.01,3).predict(np.zeros((1,15)),np.array([0]))
    def test_patient_overlap_guard(self):
        with self.assertRaises(ValueError):assert_disjoint(['a','b'],['b','c'])
        assert_disjoint(['a'],['b'])
    def test_heldout_labels_cannot_enter_core_fit(self):
        x,r,t,p=self.fixture();tr=p!='p9';te=~tr;assert_disjoint(p[tr],p[te]);changed=r.copy();changed[te]+=999
        a=PooledCurveResidual(.01,3).fit(x[tr],r[tr],t[tr],p[tr]);b=PooledCurveResidual(.01,3).fit(x[tr],changed[tr],t[tr],p[tr])
        np.testing.assert_array_equal(a.predict(x[te],t[te]),b.predict(x[te],t[te]))
    def test_paid_encoding_shape_masks(self):
        plan,bounds=self.physical_fixture();x=np.ones((2,64));bp=np.full((2,24),.7);feat,t=encode_paid(x,bp,plan,bounds,'A')
        self.assertEqual(feat.shape,(48,15));self.assertEqual(int(np.sum(feat[:,6:9])),128)
        self.assertEqual(feat.reshape(2,24,15)[0,16,8],0)
    def test_layout_flip_updates_only_plate_features(self):
        plan,bounds=self.physical_fixture();x=np.ones((2,64));bp=np.full((2,24),.7)
        a,_=encode_paid(x,bp,plan,bounds,'A');b,_=encode_paid(x,bp,plan,bounds,'B')
        np.testing.assert_array_equal(a[:,:9],b[:,:9]);np.testing.assert_array_equal(a[:,9:12],-b[:,9:12]);np.testing.assert_array_equal(a[:,12:],b[:,12:])
    def test_missing_purchased_reading_fails_not_imputed(self):
        plan,bounds=self.physical_fixture();x=np.ones((2,64));x[0,0]=np.nan
        with self.assertRaises(ValueError):encode_paid(x,np.zeros((2,24)),plan,bounds,'A')
    def test_wrong_well_budget_fails(self):
        plan,bounds=self.physical_fixture()
        with self.assertRaises(ValueError):encode_paid(np.ones((2,72)),np.zeros((2,24)),plan,bounds,'A')
    def test_duplicate_dose_fails(self):
        plan,bounds=self.physical_fixture();plan['selected_concentrations_nM'][1]=plan['selected_concentrations_nM'][0]
        with self.assertRaises(ValueError):encode_paid(np.ones((2,64)),np.zeros((2,24)),plan,bounds,'A')
    def test_same_dose_unit_change_invariance(self):
        plan,bounds=self.physical_fixture();x=np.ones((2,64));bp=np.zeros((2,24));a,_=encode_paid(x,bp,plan,bounds,'A')
        plan2=dict(plan,selected_concentrations_nM=(np.array(plan['selected_concentrations_nM'])*1000).tolist())
        b,_=encode_paid(x,bp,plan2,bounds*1000,'A');np.testing.assert_allclose(a,b,atol=1e-12,rtol=0)

if __name__=='__main__':unittest.main(verbosity=2)
