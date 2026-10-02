import copy,hashlib,json,tempfile,unittest
from pathlib import Path
import numpy as np
from hybrid_inference import HybridModel
from kernel_spectral import KernelSpectral
from test_inference import fixture

class Tests(unittest.TestCase):
    def setUp(self):
        self.a,self.plan,self.request,self.values=fixture();self.a.pop('correction')
        rng=np.random.default_rng(202610021114);z=rng.normal(size=(18,64));r=rng.normal(size=(18,24))*.02;w=np.ones(18)/18
        self.kernel=KernelSpectral(z,r,w,True);self.coef=self.kernel.coefficients(1.,.1)[0]
        self.a.update(self.kernel.arrays(self.coef));self.model=HybridModel(self.a,self.plan)
    def test_numerical_output(self):
        z=(self.values-self.a['mean_x'])/self.a['scale_x'];direct=self.a['mean_y']+z@self.a['beta']+self.kernel.predict(z[None,:],self.coef)[0]
        got=self.model.predict(self.request)
        np.testing.assert_allclose(np.array(list(got['predictions'].values())),direct,atol=1e-14)
    def test_all64_missing_positions(self):
        for i in range(64):
            r=copy.deepcopy(self.request);r['measurements'][i]['value']=None
            with self.subTest(i=i),self.assertRaises(ValueError):self.model.predict(r)
    def test_order_invariance(self):
        r=copy.deepcopy(self.request);r['measurements'].reverse();self.assertEqual(self.model.predict(r),self.model.predict(self.request))
    def test_wrong_record_identities(self):
        for k,v in [('dose_nM','999'),('plate','p2'),('native_id','bad'),('run_id','bad'),('drug_id','bad'),('sample_id','bad')]:
            r=copy.deepcopy(self.request);r['measurements'][0][k]=v
            with self.subTest(k=k),self.assertRaises(ValueError):self.model.predict(r)
    def test_nonfinite_and_boolean(self):
        for v in [np.nan,np.inf,True]:
            r=copy.deepcopy(self.request);r['measurements'][0]['value']=v
            with self.subTest(v=v),self.assertRaises(ValueError):self.model.predict(r)
    def test_incompatible_kernel_parameters(self):
        for k,v in [('z_training',np.zeros((1,63))),('weights',np.zeros(18)),('dual_coefficients',np.zeros((18,23))),('kernel_grand',np.array([1.])),('train_kernel_mean',np.zeros(18))]:
            a=copy.deepcopy(self.a);a[k]=v
            with self.subTest(k=k),self.assertRaises(ValueError):HybridModel(a,self.plan)
    def test_extra_linear_correction_forbidden(self):
        a=copy.deepcopy(self.a);a['correction']=np.zeros((64,24))
        with self.assertRaises(ValueError):HybridModel(a,self.plan)
    def test_family_and_hash_binding(self):
        with tempfile.TemporaryDirectory() as td:
            d=Path(td);np.savez_compressed(d/'model_private.npz',**self.a);(d/'plan.json').write_text(json.dumps(self.plan))
            rec={'selected':[.1,1.],'model_kind':'dosepilot.hybrid_kernel.v1','plan_sha256':hashlib.sha256((d/'plan.json').read_bytes()).hexdigest(),'model_sha256':hashlib.sha256((d/'model_private.npz').read_bytes()).hexdigest()}
            (d/'CONSTRUCTION.json').write_text(json.dumps(rec));self.assertEqual(HybridModel.load(d).predict(self.request),self.model.predict(self.request))
            from inference import SpectralModel
            with self.assertRaises(ValueError):SpectralModel.load(d)
            rec['model_kind']='spectral';(d/'CONSTRUCTION.json').write_text(json.dumps(rec))
            with self.assertRaises(ValueError):HybridModel.load(d)
    def test_template_is_not_data(self):
        r=copy.deepcopy(self.request);r['measurements']=[]
        with self.assertRaises(ValueError):self.model.predict(r)
    def test_zero_coefficients_equal_original(self):
        a=copy.deepcopy(self.a);a['dual_coefficients'][:]=0;m=HybridModel(a,self.plan);got=np.array(list(m.predict(self.request)['predictions'].values()))
        np.testing.assert_allclose(got,self.a['mean_y']+(self.values-self.a['mean_x'])@self.a['beta'],atol=1e-14)

if __name__=='__main__':unittest.main(verbosity=2)
