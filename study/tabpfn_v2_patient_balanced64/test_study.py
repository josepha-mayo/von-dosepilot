"""Synthetic contract tests. No biological input or pretrained checkpoint is read."""
import sys,types,unittest
from unittest.mock import patch
import numpy as np
from core import balanced_contexts,feature_order,from_paid,predict_target

class ContractTests(unittest.TestCase):
    def fixture(self):
        p=np.array(['a','a','b','c','c','d']);s=np.array([f's{i}' for i in range(6)])
        return p,s,np.array([0,1,2,3,4])
    def owner(self):return np.r_[np.repeat(np.arange(16),3),np.repeat(np.arange(16,24),2)]
    def test_balanced_once_per_patient(self):
        p,s,tr=self.fixture()
        for c in balanced_contexts(p,s,tr):self.assertEqual(sorted(p[c].tolist()),['a','b','c'])
    def test_contexts_deterministic_under_row_order(self):
        p,s,tr=self.fixture();a=balanced_contexts(p,s,tr);b=balanced_contexts(p,s,tr[::-1])
        for x,y in zip(a,b):np.testing.assert_array_equal(x,y)
    def test_distinct_contexts_use_distinct_available_samples(self):
        p,s,tr=self.fixture();a,b=balanced_contexts(p,s,tr)
        self.assertNotEqual(a[0],b[0]);self.assertNotEqual(a[2],b[2]);self.assertEqual(a[1],b[1])
    def test_duplicate_train_index_rejected(self):
        p,s,_=self.fixture()
        with self.assertRaises(ValueError):balanced_contexts(p,s,[0,0,2])
    def test_duplicate_sample_identity_rejected(self):
        p,s,tr=self.fixture();s[1]=s[0]
        with self.assertRaises(ValueError):balanced_contexts(p,s,tr)
    def test_feature_order_permutation_and_own_first(self):
        o=self.owner()
        for t in range(24):
            q=feature_order(o,t);self.assertEqual(sorted(q.tolist()),list(range(64)))
            np.testing.assert_array_equal(o[q[:sum(o==t)]],t)
    def test_nonfinite_paid_rejected(self):
        x=np.zeros((3,64));x[0,0]=np.nan
        with self.assertRaises(ValueError):from_paid(x,'A',np.arange(64))
    def test_partial_paid_rejected(self):
        with self.assertRaises(ValueError):from_paid(np.ones((3,63)),'A',np.arange(64))
    def test_orientation_metadata_not_prediction_averaging(self):
        a=from_paid(np.ones((2,64)),'A',np.arange(64));b=from_paid(np.ones((2,64)),'B',np.arange(64))
        np.testing.assert_array_equal(a[:,:64],b[:,:64]);self.assertTrue(np.all(a[:,-1]==0));self.assertTrue(np.all(b[:,-1]==1))
    def stub(self):
        class Reg:
            @staticmethod
            def create_default_for_version(*a,**kw):return Reg()
            def fit(self,x,y):self.mean=float(np.mean(y));return self
            def predict(self,x):return self.mean+x[:,0]*.01
        module=types.ModuleType('tabpfn');module.TabPFNRegressor=Reg
        constants=types.ModuleType('tabpfn.constants');constants.ModelVersion=types.SimpleNamespace(V2='v2')
        return {'tabpfn':module,'tabpfn.constants':constants}
    def test_whole_patient_overlap_rejected(self):
        p,s,tr=self.fixture();y=np.zeros((6,24));a=np.ones((6,64))
        with patch.dict(sys.modules,self.stub()),self.assertRaises(ValueError):
            predict_target(a,a,y,p,s,tr,[1],self.owner(),0,0,'unused')
    def test_context_escaping_training_rejected(self):
        p,s,tr=self.fixture();y=np.zeros((6,24));a=np.ones((6,64))
        with patch.dict(sys.modules,self.stub()),self.assertRaises(ValueError):
            predict_target(a,a,y,p,s,tr,[5],self.owner(),0,0,'unused',contexts=[np.array([5])])
    def test_hidden_labels_invariant_and_output_shapes(self):
        p,s,tr=self.fixture();rng=np.random.default_rng(21);y=rng.normal(size=(6,24));a=rng.normal(size=(6,64));b=rng.normal(size=(6,64))
        with patch.dict(sys.modules,self.stub()):
            first,members,_=predict_target(a,b,y,p,s,tr,[5],self.owner(),0,0,'unused')
            changed=y.copy();changed[5]=999
            second,_,_=predict_target(a,b,changed,p,s,tr,[5],self.owner(),0,0,'unused')
        np.testing.assert_array_equal(first,second);self.assertEqual(first.shape,(2,1));self.assertEqual(members.shape,(2,2,1))

if __name__=='__main__':unittest.main(verbosity=2)
