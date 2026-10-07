"""Runner orchestration checks on invented arrays and a synthetic test double.
These do not run or reproduce the original DosePilot biological engine.
"""
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
import run_trial as rt


def fake_plan():
    native=[]; owner=[]; plates=[]; doses=[]
    for t in range(24):
        k=2 if t<8 else 3
        start=0 if k==2 else (t-8)%2
        for j in range(k):
            native.append(3*t+j);owner.append(t);plates.append((start+j)%2);doses.append(str(10**j))
    return {'selected_native_indices':native,'selected_native_ids':[f'n{i}' for i in native],
       'coordinate_target_indices':owner,'selected_concentrations_nM':doses,
       'orientation_A_plate_indices':plates,'orientation_B_plate_indices':[1-v for v in plates]}


def fake_acquire(x,plan,o):
    p=x[:,np.array(plan['selected_native_indices']),np.array(plan[f'orientation_{o}_plate_indices'])]
    if p.shape!=(len(x),64) or not np.isfinite(p).all():raise ValueError('invalid paid values')
    return p.copy()


def fake_context(a,b,y,patients,plan,target_ids):
    x=np.r_[a,b];yy=np.r_[y,y];pp=np.concatenate((patients,patients))
    ids,inv,count=np.unique(pp,return_inverse=True,return_counts=True);w=1./(len(ids)*count[inv])
    mx=w@x;my=w@yy;s=np.maximum(np.sqrt(w@((x-mx)**2)),.05);z=(x-mx)/s
    return SimpleNamespace(mean_x=mx,scale_x=s,mean_y=my,gram=z.T@(w[:,None]*z),cross=z.T@(w[:,None]*(yy-my)))


class FakeBase:
    def __init__(self,ctx,plan,alpha):
        self.mean_x=ctx.mean_x;self.scale_x=ctx.scale_x;self.mean_y=ctx.mean_y
        self.beta=np.zeros((64,24));owner=np.asarray(plan['coordinate_target_indices'])
        for j in range(24):
            cols=np.flatnonzero(owner==j)
            self.beta[cols,j]=np.linalg.solve(ctx.gram[np.ix_(cols,cols)]+alpha*np.eye(len(cols)),ctx.cross[cols,j])
    def predict(self,x):return self.mean_y+((x-self.mean_x)/self.scale_x)@self.beta


class FakeKernel:
    def __init__(self,z,residual,w,owner,bw):
        self.z=z.copy();self.residual=residual;self.w=w;self.owner=owner
        raw=self.raw_cross(z);self.train_mean=w@raw;self.grand=float(self.train_mean@w)
        centered=self.centered_cross(z);sw=np.sqrt(w)
        self.e,self.u=np.linalg.eigh(sw[:,None]*centered*sw[None,:]);self.e=np.maximum(self.e,0);self.sw=sw
    def raw_cross(self,q):
        raw=q@self.z.T
        for t in range(24):
            cols=np.flatnonzero(self.owner==t);d=np.sum((q[:,None,cols]-self.z[None,:,cols])**2,axis=2)
            raw+=len(cols)*np.exp(-d/(2*len(cols)*.49))
        return raw
    def centered_cross(self,q):
        raw=self.raw_cross(q)
        return raw-(raw@self.w)[:,None]-self.train_mean[None,:]+self.grand
    def coefficients(self,alpha,fraction):
        proj=self.u.T@(self.sw[:,None]*self.residual)
        coef=self.sw[:,None]*(self.u@(proj/(self.e+alpha)[:,None]))*(1-fraction)
        return coef,None,None


def fake_folds(p,n,salt):
    ids=np.unique(p);lookup={g:i%n for i,g in enumerate(ids)}
    return np.array([lookup[g] for g in p]),lookup


def fake_engine():
    return {'coverage_methods':SimpleNamespace(acquire=fake_acquire,fit_prediction_context=fake_context,CoveragePredictor=FakeBase),
            'fast_coverage':SimpleNamespace(plan_panel_fast=lambda x,y,p,c:fake_plan()),
            'methods':SimpleNamespace(patient_folds=fake_folds),
            'bandwidth_additive':SimpleNamespace(BandwidthAdditive=FakeKernel)}


class TrialGuards(unittest.TestCase):
    def test_exact_menu_and_half_error_target(self):
        self.assertEqual(len(rt.MENU),13)
        self.assertEqual([v['ridge'] for v in rt.MENU[10:]],[.001,.01,.1])
        self.assertEqual(rt.TARGET,.000521372861048106)
    def test_nonwindows_biological_execution_refused(self):
        with patch.object(rt.os,'name','posix'):
            with self.assertRaisesRegex(RuntimeError,'Windows D:'):rt.check_paths(SimpleNamespace())
    def test_losses_average_not_free_ensemble(self):
        y=np.zeros((5,24));pred=np.stack((np.ones_like(y),-np.ones_like(y)));p=np.array(list('abcde'))
        np.testing.assert_array_equal(rt.risks(pred,y,p),1.)
        self.assertEqual(float(np.mean((pred.mean(0)-y)**2)),0.)
    def test_patients_equal_weight_not_organoids(self):
        y=np.zeros((3,24));a=np.stack((np.ones(24),np.full(24,3),np.full(24,2)));pred=np.stack((a,a));p=np.array(['a','a','b'])
        self.assertAlmostEqual(float(rt.risks(pred,y,p).mean()),4.5)
    def test_original_catalog_hash_pinned(self):
        self.assertEqual(rt.INPUT_HASHES['catalog'],'84eae3976307448ac696852d39d1b2376cce479d8af5e386ce04097020deff5e')
        self.assertEqual(len(rt.DEPENDENCIES),9)
    def test_saved_pooled_model_matches_direct_predictions(self):
        rng=np.random.default_rng(441);p=np.array([f'p{i}' for i in range(9)])
        x=rng.normal(size=(9,72,2));y=rng.normal(size=(9,24));bounds=np.tile([1.,100.],(24,1))
        cat=SimpleNamespace(target_ids=np.array([f't{i}' for i in range(24)]))
        bundle=rt.build(fake_engine(),x,y,p,cat,bounds,np.arange(9))
        for selected in (0,3,10,11,12):
            state=rt.export_selected(bundle,selected)
            for o in ('A','B'):
                paid=fake_acquire(x,bundle['plan'],o)
                expected=rt.predict_paid_options(bundle,paid,o)[selected]
                np.testing.assert_allclose(rt.predict_exported(state,paid,o),expected,atol=1e-12,rtol=0)
    def test_saved_predictor_rejects_missing_paid_value(self):
        with self.assertRaises(ValueError):rt.predict_exported({},np.full((1,64),np.nan),'A')
    def test_invented_nested_runner_and_heldout_isolation(self):
        rng=np.random.default_rng(430)
        p=np.array([f'p{i:02d}' for i in range(15)])
        x=rng.normal(size=(15,72,2));y=.6+.1*np.mean(x.reshape(15,24,3,2),axis=(2,3))
        y+=rng.normal(0,.02,size=y.shape);folds=np.arange(15)%5
        bounds=np.tile([1.,100.],(24,1));cat=SimpleNamespace(target_ids=np.array([f't{i}' for i in range(24)]))
        e=fake_engine();c,b,record,_=rt.outer(e,x,y,p,cat,bounds,folds,0,x)
        changed_x=x.copy();changed_y=y.copy();changed_x[folds==0]+=100;changed_y[folds==0]-=70
        c2,b2,record2,_=rt.outer(e,changed_x,changed_y,p,cat,bounds,folds,0,x)
        self.assertEqual(c.shape,(2,3,24));self.assertEqual(len(record['inner_mse']),13)
        self.assertEqual(record['selected_index'],record2['selected_index'])
        np.testing.assert_allclose(c,c2,atol=1e-12,rtol=0)
        np.testing.assert_allclose(b,b2,atol=1e-12,rtol=0)
        self.assertEqual(record['unpaid_poison_maxdiff'],0.)
        self.assertLess(record['saved_model_replay_maxdiff'],1e-12)

if __name__=='__main__':unittest.main(verbosity=2)
