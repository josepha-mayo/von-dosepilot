import unittest
import numpy as np
from calibrated_control import fit, weights, group_target_risks, select_from_folds, OPTIONS

class Tests(unittest.TestCase):
    def setUp(self):
        self.rng=np.random.default_rng(20260930)
        self.x=self.rng.normal(size=(20,4))
        self.y=self.x*np.array([.3,1.1,-.7,2.])+np.array([.2,.1,.4,-.3])
        self.p=np.array([f'p{i//2}' for i in range(20)])
    def test_affine_recovery(self):
        np.testing.assert_allclose(fit(self.x,self.y,self.p,0.).predict(self.x),self.y,atol=2e-14)
    def test_identity_exact(self):
        np.testing.assert_array_equal(fit(self.x,self.y,self.p,'identity').predict(self.x),self.x)
    def test_direct_augmented_least_squares(self):
        q=weights(self.p)
        for lam in (0.,.01,.1,1.,10.):
            m=fit(self.x,self.y,self.p,lam)
            for j in range(4):
                z=(self.x[:,j]-m.mean_x[j])/m.scale_x[j]
                a=np.c_[np.ones(len(z)),z]
                aug=np.vstack([a*np.sqrt(q)[:,None], [0.,np.sqrt(lam)]])
                target=np.r_[self.y[:,j]*np.sqrt(q),0.]
                coef=np.linalg.lstsq(aug,target,rcond=None)[0]
                np.testing.assert_allclose([m.mean_y[j],m.beta[j]],coef,atol=2e-14)
    def test_constant_input(self):
        x=np.ones_like(self.x)
        m=fit(x,self.y,self.p,0.)
        np.testing.assert_allclose(m.predict(x),np.tile(weights(self.p)@self.y,(20,1)))
    def test_raw_patient_mass(self):
        q=weights(['a','a','b'])
        np.testing.assert_allclose(q,[.25,.25,.5])
    def test_duplicate_patient_invariance(self):
        a=fit(self.x,self.y,self.p,.1)
        b=fit(np.repeat(self.x,2,0),np.repeat(self.y,2,0),np.repeat(self.p,2),.1)
        np.testing.assert_allclose(a.predict(self.x),b.predict(self.x),atol=1e-14)
    def test_no_cross_target_dependence(self):
        m=fit(self.x,self.y,self.p,.1);x=self.x.copy();x[:,1]+=10
        np.testing.assert_array_equal(m.predict(x)[:,[0,2,3]],m.predict(self.x)[:,[0,2,3]])
    def test_no_input_mutation(self):
        x,y=self.x.copy(),self.y.copy();fit(x,y,self.p,.1)
        np.testing.assert_array_equal(x,self.x);np.testing.assert_array_equal(y,self.y)
    def test_invalid_input(self):
        for x in [np.full((3,4),np.nan),np.zeros(4),np.zeros((0,4))]:
            with self.subTest(shape=x.shape),self.assertRaises(ValueError):fit(x,x,['x']*len(x),.1)
        with self.assertRaises(ValueError):fit(self.x,self.y,self.p,.2)
    def test_balanced_metric(self):
        y=np.zeros((3,2));pred=np.array([[1,1],[1,1],[3,3]])
        self.assertAlmostEqual(group_target_risks(y,pred,['a','a','b']).mean(),5.)
    def blocks(self):
        result=[]
        for f in range(5):
            test=np.arange(20)//4==f;tr=np.flatnonzero(~test);va=np.flatnonzero(test)
            result.append({'train':tr,'validation':va,'fit_interpolation':self.x[tr],
                'validation_interpolation':self.x[va]})
        return result
    def test_selection_train_only(self):
        option,scores,preds=select_from_folds(self.blocks(),self.y,self.p)
        self.assertEqual(option,0.);self.assertEqual(preds.shape,(6,20,4))
        self.assertLess(scores[1],1e-27)
    def test_fold_patient_leakage_rejected(self):
        blocks=self.blocks();p=self.p.copy();p[4]=p[0]
        with self.assertRaises(ValueError):select_from_folds(blocks,self.y,p)
    def test_incomplete_folds_rejected(self):
        with self.assertRaises(ValueError):select_from_folds(self.blocks()[:-1],self.y,self.p)
    def test_array_roundtrip(self):
        m=fit(self.x,self.y,self.p,.1);a=m.arrays()
        self.assertEqual(str(a['option']),str(.1));self.assertEqual(a['beta'].shape,(4,))

if __name__=='__main__':unittest.main(verbosity=2)
