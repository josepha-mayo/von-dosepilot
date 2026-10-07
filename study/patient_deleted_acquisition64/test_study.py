import sys,unittest
from pathlib import Path
from types import SimpleNamespace
import numpy as np
HERE=Path(__file__).resolve().parent;sys.path[:0]=[str(HERE),str(HERE.parents[1]/'study/engine')]
from planner import patient_moments,deleted_risk,plan_patient_deleted
from coverage_methods import validate_plan

class DeletedPlannerTests(unittest.TestCase):
    def fixture(self):
        rng=np.random.default_rng(931);x=rng.normal(size=(19,6));y=rng.normal(size=19)
        p=np.array([f'p{i//3}' for i in range(19)])
        return x,y,p
    def brute(self,x,y,p,cols):
        losses=[];betas=[];intercepts=[]
        for patient in np.unique(p):
            tr=p!=patient;te=~tr;xt=x[tr][:,cols];yt=y[tr];pt=p[tr]
            ids,inv,count=np.unique(pt,return_inverse=True,return_counts=True);w=1/(len(ids)*count[inv])
            mx=w@xt;my=float(w@yt);scale=np.maximum(np.sqrt(w@((xt-mx)**2)),.05)
            z=(xt-mx)/scale;beta=np.linalg.solve(z.T@(w[:,None]*z)+.01*np.eye(len(cols)),z.T@(w*(yt-my)))/scale
            intercept=my-mx@beta;pred=intercept+x[te][:,cols]@beta
            losses.append(float(np.mean((pred-y[te])**2)));betas.append(beta);intercepts.append(intercept)
        return np.array(losses),np.array(betas),np.array(intercepts)
    def test_exact_deletion_matches_brute_refits(self):
        x,y,p=self.fixture();mom=patient_moments(x,y,p)
        for cols in ([0,3],[0,3,4]):
            a=deleted_risk(mom,cols);b=self.brute(x,y,p,cols)
            for v,w in zip(a,b):np.testing.assert_allclose(v,w,atol=1e-11,rtol=0)
    def test_recomputed_scale_floor(self):
        x,y,p=self.fixture();x[:,0]*=.0001
        a=deleted_risk(patient_moments(x,y,p),[0,3]);b=self.brute(x,y,p,[0,3])
        for v,w in zip(a,b):np.testing.assert_allclose(v,w,atol=1e-10,rtol=0)
    def test_deleted_fit_does_not_use_deleted_labels(self):
        x,y,p=self.fixture();a=deleted_risk(patient_moments(x,y,p),[0,3]);changed=y.copy();changed[p==np.unique(p)[0]]+=101
        b=deleted_risk(patient_moments(x,changed,p),[0,3])
        np.testing.assert_allclose(a[1][0],b[1][0],atol=1e-11,rtol=0);self.assertAlmostEqual(a[2][0],b[2][0])
    def test_constant_data_is_finite(self):
        x=np.ones((9,4));y=np.ones(9);p=np.array([f'p{i//3}' for i in range(9)])
        loss,beta,intercept=deleted_risk(patient_moments(x,y,p),[0,1])
        np.testing.assert_allclose(loss,0,atol=1e-12);np.testing.assert_allclose(beta,0,atol=1e-12)
    def test_group_moments_weight_samples_equally_within_patient(self):
        x,y,p=self.fixture();mx,xx,my,xy,yy=patient_moments(x,y,p)
        np.testing.assert_allclose(mx[0],x[:3].mean(0));self.assertAlmostEqual(my[0],y[:3].mean())
    def test_nonfinite_rejected(self):
        x,y,p=self.fixture();x[0,0]=np.nan
        with self.assertRaises(ValueError):patient_moments(x,y,p)
    def test_too_few_patients_rejected(self):
        with self.assertRaises(ValueError):patient_moments(np.ones((2,3)),np.ones(2),['a','b'])
    def test_exact_budget_and_complementary_plates(self):
        rng=np.random.default_rng(73);x=rng.normal(size=(12,72,2));y=rng.normal(size=(12,24));p=np.array([f'p{i//2}' for i in range(12)])
        cat=SimpleNamespace(library_id='lib1',native_ids=np.array([f'n{i}' for i in range(72)]),target_ids=np.array([f't{i}' for i in range(24)]),native_target_indices=np.repeat(np.arange(24),3),concentrations=tuple(['1','10','100']*24))
        plan=plan_patient_deleted(x,y,p,cat);validate_plan(plan,cat)
        self.assertEqual(len(plan['selected_native_indices']),64);self.assertEqual(len(plan['upgraded_target_ids']),16)
        self.assertEqual(plan['orientation_A_plate_indices'].count(0),32)

if __name__=='__main__':unittest.main(verbosity=2)
