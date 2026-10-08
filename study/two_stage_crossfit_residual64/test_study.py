import unittest
import numpy as np
from kernel import encode,Kernel,predict_saved,DIMENSION

class EncoderTests(unittest.TestCase):
    def fixture(self):
        rng=np.random.default_rng(321);bank={}
        for j in range(24):
            bank[f't{j}_initial_native']=np.array([3*j,3*j+1])
            bank[f't{j}_s0_option_native']=np.array([-1,3*j+2]);bank[f't{j}_s0_option_plate']=np.array([-1,j%2])
        first=rng.normal(size=(7,24,2));actions=np.zeros((7,24),int);actions[:,:16]=1
        later=rng.normal(size=(7,24));later[actions==0]=np.nan;base=rng.normal(size=(7,24));pos=np.tile([0.,.5,1.],24)
        return bank,first,actions,later,base,pos
    def test_explicit_values_metadata_and_mask(self):
        bank,x,a,z,b,t=self.fixture();f=encode(bank,x,a,z,0,b,t).reshape(7,24,11)
        np.testing.assert_array_equal(f[:,:,0],x[:,:,0]);np.testing.assert_array_equal(f[:,:,3],x[:,:,1]);np.testing.assert_array_equal(f[:,:,10],b)
        np.testing.assert_array_equal(f[:,:,9],a>0);np.testing.assert_array_equal(f[:,16:,6:10],0)
    def test_unbought_placeholder_not_an_input(self):
        bank,x,a,z,b,t=self.fixture();first=encode(bank,x,a,z,0,b,t);z[a==0]=1e6
        np.testing.assert_array_equal(first,encode(bank,x,a,z,0,b,t))
    def test_bought_nan_rejected(self):
        bank,x,a,z,b,t=self.fixture();z[0,0]=np.nan
        with self.assertRaises(ValueError):encode(bank,x,a,z,0,b,t)
    def test_known_dose_metadata_affects_encoding(self):
        bank,x,a,z,b,t=self.fixture();f=encode(bank,x,a,z,0,b,t);changed=t.copy();changed[2]=.9
        self.assertFalse(np.array_equal(f,encode(bank,x,a,z,0,b,changed)))
    def test_feature_dimension_not_measurement_count(self):
        bank,x,a,z,b,t=self.fixture();f=encode(bank,x,a,z,0,b,t)
        self.assertEqual(f.shape,(7,264));self.assertTrue(np.all(48+(a>0).sum(1)==64))

class KernelTests(unittest.TestCase):
    def fixture(self):
        rng=np.random.default_rng(838);x=rng.normal(size=(28,DIMENSION));r=rng.normal(size=(28,24));w=np.arange(1,29,dtype=float);w/=w.sum()
        return x,r,w
    def test_psd_raw_kernel(self):
        x,r,w=self.fixture();model=Kernel(x,r,w);k=model.raw_cross(model.z)
        self.assertGreaterEqual(np.linalg.eigvalsh((k+k.T)/2).min(),-1e-9)
    def test_identity_is_exact_without_bias_correction(self):
        x,r,w=self.fixture();model=Kernel(x,r+19,w);base=np.zeros((6,24));pred=model.predict_all(x[:6],base)
        np.testing.assert_array_equal(pred[0],base)
    def test_zero_residual_returns_base(self):
        x,r,w=self.fixture();model=Kernel(x,np.zeros_like(r),w);base=r[:6]
        for pred in model.predict_all(x[:6],base):np.testing.assert_array_equal(pred,base)
    def test_constant_residual_mean_is_added_only_to_corrections(self):
        x,r,w=self.fixture();model=Kernel(x,np.full_like(r,2),w);base=np.zeros((6,24));p=model.predict_all(x[:6],base)
        np.testing.assert_array_equal(p[0],0);np.testing.assert_allclose(p[1:],2,atol=1e-12,rtol=0)
    def test_numeric_state_matches_every_option(self):
        x,r,w=self.fixture();model=Kernel(x,r,w);base=r[:6];allpred=model.predict_all(x[:6],base)
        for i in range(10):np.testing.assert_allclose(predict_saved(model.arrays(i),x[:6],base),allpred[i],atol=1e-12,rtol=0)
    def test_malformed_weight_sum_rejected(self):
        x,r,w=self.fixture()
        with self.assertRaises(ValueError):Kernel(x,r,w*2)
    def test_nonfinite_features_rejected(self):
        x,r,w=self.fixture();x[0,0]=np.nan
        with self.assertRaises(ValueError):Kernel(x,r,w)

if __name__=='__main__':unittest.main(verbosity=2)
