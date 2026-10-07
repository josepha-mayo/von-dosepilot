import sys,types,unittest
from unittest.mock import patch
import numpy as np
from anchor import observed_weights,known_contribution,predict_target

class AnchorTests(unittest.TestCase):
    def fixture(self):
        q=np.zeros((144,24));owner=np.repeat(np.arange(24),3)
        for t in range(24):q[6*t:6*t+6,t]=1/6
        native=np.r_[np.arange(48),np.array([3*t+j for t in range(16,24) for j in (0,2)])]
        plan={'selected_native_indices':native,'orientation_A_plate_indices':np.tile([0,1],32),'orientation_B_plate_indices':np.tile([1,0],32)}
        return q,plan,owner[native]
    def test_exact_sum_decomposition(self):
        q,plan,_=self.fixture();rng=np.random.default_rng(77);full=rng.normal(size=(9,72,2))
        for o in ('A','B'):
            w=observed_weights(plan,q,np.arange(72),o);n=plan['selected_native_indices'];p=plan[f'orientation_{o}_plate_indices']
            paid=full[:,n,p];remaining=full.copy();remaining[:,n,p]=0
            np.testing.assert_allclose(known_contribution(paid,w)+remaining.reshape(9,-1)@q,full.reshape(9,-1)@q,atol=1e-15,rtol=0)
    def test_known_term_only_depends_on_paid_input(self):
        q,plan,_=self.fixture();w=observed_weights(plan,q,np.arange(72),'A')
        paid=np.arange(64,dtype=float)[None,:];a=known_contribution(paid,w);changed=paid.copy();changed[0,3]+=10
        np.testing.assert_allclose(known_contribution(changed,w)-a,10*w[[3]],atol=1e-13)
    def test_bad_budget_rejected(self):
        q,plan,_=self.fixture();plan['orientation_A_plate_indices']=np.zeros(64,int)
        with self.assertRaises(ValueError):observed_weights(plan,q,np.arange(72),'A')
    def test_duplicate_paid_dose_rejected(self):
        q,plan,_=self.fixture();plan['selected_native_indices'][1]=plan['selected_native_indices'][0]
        with self.assertRaises(ValueError):observed_weights(plan,q,np.arange(72),'A')
    def test_missing_paid_value_rejected(self):
        q,plan,_=self.fixture();w=observed_weights(plan,q,np.arange(72),'A');paid=np.ones((2,64));paid[0,0]=np.nan
        with self.assertRaises(ValueError):known_contribution(paid,w)
    def stub(self):
        class R:
            @staticmethod
            def create_default_for_version(*a,**kw):return R()
            def fit(self,x,y):self.labels=y.copy();return self
            def predict(self,x):return np.zeros(len(x))
        m=types.ModuleType('tabpfn');m.TabPFNRegressor=R;c=types.ModuleType('tabpfn.constants');c.ModelVersion=types.SimpleNamespace(V2='v2')
        return {'tabpfn':m,'tabpfn.constants':c}
    def test_zero_missing_prediction_returns_exact_paid_contribution(self):
        q,plan,owner=self.fixture();rng=np.random.default_rng(71);a=rng.normal(size=(8,64));b=rng.normal(size=(8,64));y=rng.normal(size=(8,24));p=np.array([f'p{i}' for i in range(8)])
        ka=known_contribution(a,observed_weights(plan,q,np.arange(72),'A'));kb=known_contribution(b,observed_weights(plan,q,np.arange(72),'B'))
        with patch.dict(sys.modules,self.stub()):pr,missing=predict_target(a,b,ka,kb,y,p,np.arange(6),np.arange(6,8),owner,0,0,'unused')
        np.testing.assert_array_equal(pr,np.stack([ka[6:,0],kb[6:,0]]));np.testing.assert_array_equal(missing,0.)
    def test_heldout_labels_do_not_enter_fitting(self):
        q,plan,owner=self.fixture();a=np.ones((8,64));ka=known_contribution(a,observed_weights(plan,q,np.arange(72),'A'));y=np.zeros((8,24));p=np.array([f'p{i}' for i in range(8)])
        with patch.dict(sys.modules,self.stub()):
            first,_=predict_target(a,a,ka,ka,y,p,np.arange(6),np.arange(6,8),owner,0,0,'unused')
            y[6:]=999;second,_=predict_target(a,a,ka,ka,y,p,np.arange(6),np.arange(6,8),owner,0,0,'unused')
        np.testing.assert_array_equal(first,second)
    def test_patient_overlap_rejected(self):
        q,plan,owner=self.fixture();a=np.ones((8,64));ka=np.zeros((8,24));y=ka.copy();p=np.array([f'p{i//2}' for i in range(8)])
        with patch.dict(sys.modules,self.stub()),self.assertRaises(ValueError):predict_target(a,a,ka,ka,y,p,np.arange(5),np.arange(5,8),owner,0,0,'unused')

if __name__=='__main__':unittest.main(verbosity=2)
