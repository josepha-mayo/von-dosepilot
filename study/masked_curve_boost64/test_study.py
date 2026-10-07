import unittest
from types import SimpleNamespace
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from core import weights,local_ridge,predict_ridge,context_stats,encode,build_rows,export_trees,predict_exported

class MaskTests(unittest.TestCase):
    def fixture(self):
        rng=np.random.default_rng(771);x=rng.normal(size=(18,96,2));y=rng.normal(size=(18,24));p=np.array([f'p{i//2}' for i in range(18)])
        native=[];owner=[];pa=[]
        for t in range(24):
            k=3 if t<16 else 2;native.extend(range(4*t,4*t+k));owner.extend([t]*k);start=t%2 if k==3 else 0;pa.extend([(start+j)%2 for j in range(k)])
        plan={'selected_native_indices':native,'coordinate_target_indices':owner,'orientation_A_plate_indices':pa,'orientation_B_plate_indices':[1-j for j in pa]}
        cat=SimpleNamespace(native_ids=np.array([f'n{i}' for i in range(96)]),native_target_indices=np.repeat(np.arange(24),4),target_ids=np.array([f't{i}' for i in range(24)]),concentrations=tuple(['1','3','10','30']*24))
        bounds={f't{i}':[1.,30.] for i in range(24)}
        return x,y,p,cat,bounds,plan
    def test_local_ridge_matches_independent_normal_equations(self):
        rng=np.random.default_rng(6);a=rng.normal(size=(17,3));b=rng.normal(size=(17,3));y=rng.normal(size=17);p=np.array([f'p{i//3}' for i in range(17)])
        s=local_ridge(a,b,y,p);x=np.r_[a,b];yy=np.tile(y,2);w=np.tile(weights(p),2)/2
        z=(x-s['mean'])/s['scale'];normal=z.T@np.diag(w)@z+.01*np.eye(3);rhs=z.T@np.diag(w)@(yy-s['mean_y'])
        np.testing.assert_allclose(s['beta'],np.linalg.solve(normal,rhs),atol=1e-12,rtol=0)
    def test_context_excludes_original_own_doses(self):
        x,y,p,cat,bounds,plan=self.fixture();native=np.asarray(plan['selected_native_indices']);owner=np.asarray(plan['coordinate_target_indices'])
        paid=x[:,native,np.asarray(plan['orientation_A_plate_indices'])];c=context_stats(paid,owner,0);paid[:,owner==0]+=100
        np.testing.assert_array_equal(c,context_stats(paid,owner,0))
    def test_row_and_weight_accounting(self):
        x,y,p,cat,bounds,plan=self.fixture()
        for augment in (False,True):
            xx,yy,w,states,inventory=build_rows(x,y,p,cat,bounds,plan,augment)
            expected=2*len(x)*sum(r['masks'] for r in inventory)
            self.assertEqual(xx.shape,(expected,46));self.assertEqual(len(yy),expected);self.assertEqual(len(states),24)
            self.assertAlmostEqual(float(w.sum()),2*len(x)*24)
            for t in range(24):self.assertAlmostEqual(float(w[xx[:,t]==1].sum()),2*len(x))
    def test_current_subset_is_preserved(self):
        x,y,p,cat,bounds,plan=self.fixture();a=build_rows(x,y,p,cat,bounds,plan,False);b=build_rows(x,y,p,cat,bounds,plan,True)
        for x,y in zip(a[3],b[3]):
            for name in x:np.testing.assert_allclose(x[name],y[name],atol=1e-12,rtol=0)
    def test_encoded_dimension_and_all_features_finite(self):
        v=np.array([[.9,.6],[1.,.2]])
        f=encode(v,[1,10],[0,1],[1,100],np.array([.7,.6]),np.ones((2,7)),0,'A')
        self.assertEqual(f.shape,(2,46));self.assertTrue(np.isfinite(f).all())
    def test_missing_paid_refused(self):
        with self.assertRaises(ValueError):context_stats(np.full((3,64),np.nan),np.repeat(np.arange(32),2),0)
    def test_tree_export_matches_library(self):
        rng=np.random.default_rng(33);x=rng.normal(size=(150,8));y=np.sin(x[:,0])+x[:,1]**2
        m=HistGradientBoostingRegressor(max_iter=15,max_leaf_nodes=5,min_samples_leaf=5,early_stopping=False,random_state=4).fit(x,y)
        queries=np.r_[x[:17],rng.normal(size=(17,8))];s=export_trees(m)
        np.testing.assert_allclose(predict_exported(s,queries),m.predict(queries),atol=1e-12,rtol=0)
    def test_weight_is_equal_per_patient(self):
        p=np.array(['a','a','a','b']);w=weights(p);self.assertAlmostEqual(w[:3].sum(),w[3])

if __name__=='__main__':unittest.main(verbosity=2)
