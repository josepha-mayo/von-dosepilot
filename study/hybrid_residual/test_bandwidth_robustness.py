import unittest
import numpy as np
from simulate_bandwidth_robustness import model_predict,metrics

class RobustnessTests(unittest.TestCase):
    def fixture(self):
        r=np.random.default_rng(703);n=12;t=15
        owner=np.repeat(np.arange(24),[3]*16+[2]*8)
        model={'mean_x':np.zeros(64),'scale_x':np.ones(64),'mean_y':np.zeros(24),
          'beta':np.zeros((64,24)),'z_training':r.normal(size=(t,64)),
          'kernel_owner':owner,'kernel_bandwidth_multiplier':np.asarray(.7),
          'weights':np.ones(t)/t,'dual_coefficients':np.zeros((t,24))}
        train=model['z_training'];raw=train@train.T
        for j in range(24):
            g=np.flatnonzero(owner==j);a=train[:,g]
            dist=np.maximum((a*a).sum(1)[:,None]+(a*a).sum(1)[None,:]-2*a@a.T,0.)
            raw+=len(g)*np.exp(-dist/(2*len(g)*.7*.7))
        model['train_kernel_mean']=model['weights']@raw
        model['kernel_grand']=np.asarray(float(model['train_kernel_mean']@model['weights']))
        return r,model,n
    def test_zero_dual_is_exact_base(self):
        r,m,n=self.fixture();x=r.normal(size=(n,64))
        np.testing.assert_array_equal(model_predict(m,x),np.zeros((n,24)))
    def test_wrong_bandwidth_rejected(self):
        r,m,n=self.fixture();m['kernel_bandwidth_multiplier']=np.asarray(.8)
        with self.assertRaises(ValueError):model_predict(m,r.normal(size=(n,64)))
    def test_patient_balanced_metric_shape(self):
        r,m,n=self.fixture();pred=np.zeros((2,n,24));y=r.normal(size=(n,24))
        p=np.array([f'p{i//2}' for i in range(n)])
        got=metrics(pred,y,p)
        self.assertGreaterEqual(got['mse'],0);self.assertEqual(got['target_mse'].shape,(24,))
        self.assertGreaterEqual(got['p90_rmse'],0)

if __name__=='__main__':unittest.main(verbosity=2)
