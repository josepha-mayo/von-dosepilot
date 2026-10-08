import unittest
from types import SimpleNamespace
import numpy as np
import run_study as r

class CrossfitWiringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rng=np.random.default_rng(852);x=rng.normal(size=(30,72,2));owner=np.repeat(np.arange(24),3);q=np.zeros((144,24))
        for j in range(24):q[6*j:6*j+6,j]=np.repeat([.25,.5,.25],2)/2
        y=x.reshape(30,-1)@q;p=np.array([f'p{i//2:02d}' for i in range(30)])
        cat=SimpleNamespace(library_id='lib1',native_ids=np.array([f'n{i}' for i in range(72)]),target_ids=np.array([f't{i}' for i in range(24)]),
          native_target_indices=owner,concentrations=tuple(['1','10','100']*24))
        cls.data={'x':x,'y':y,'p':p,'catalog':cat,'full':{'values':x.copy(),'owner':owner,'query_to_full':np.arange(72),'q':q},
          'positions':[np.array([0.,.5,1.]) for _ in range(24)],'query_positions':np.tile([0.,.5,1.],24)}
        cls.tr=np.arange(24);cls.model=r.fit_model(cls.data,cls.tr,'synthetic')
    def test_meta_rows_have_grouped_out_of_sample_provenance(self):
        p=self.data['p'];seen=[]
        for rec in self.model['partitions']:
            fit=np.array(rec['fitting_indices']);held=np.array(rec['held_indices'])
            self.assertFalse(set(p[fit])&set(p[held]));self.assertTrue(set(fit).issubset(set(self.tr)));seen.extend(held.tolist())
        self.assertEqual(sorted(seen),self.tr.tolist())
    def test_all_options_and_physical_queries(self):
        pred,base,features,trace=r.predict_all(self.model,self.data['x'][24:])
        for name in r.POLICIES:
            self.assertEqual(pred[name].shape,(10,2,6,24));self.assertTrue(np.isfinite(pred[name]).all())
            np.testing.assert_array_equal(pred[name][0],base[name])
            for seed in (0,1):self.assertEqual(trace[f'{name}_s{seed}_cells'].shape,(6,64,2))
    def test_held_query_labels_and_full_curves_do_not_change_fit(self):
        changed=dict(self.data);changed['x']=self.data['x'].copy();changed['y']=self.data['y'].copy();changed['full']=dict(self.data['full']);changed['full']['values']=self.data['full']['values'].copy()
        changed['x'][24:]+=19;changed['y'][24:]-=111;changed['full']['values'][24:]+=71
        second=r.fit_model(changed,self.tr,'synthetic')
        for key in self.model['bank']:np.testing.assert_array_equal(self.model['bank'][key],second['bank'][key])
        a,_,_,_=r.predict_all(self.model,self.data['x'][24:]);b,_,_,_=r.predict_all(second,self.data['x'][24:])
        for name in r.POLICIES:np.testing.assert_array_equal(a[name],b[name])

if __name__=='__main__':unittest.main(verbosity=2)
