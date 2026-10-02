import copy,hashlib,importlib.util,json,tempfile,unittest
from pathlib import Path
import numpy as np
from additive_kernel import AdditiveKernel
from additive_inference import AdditiveModel
from hybrid_inference import HybridModel,SpectralModel
from test_inference import fixture

class Tests(unittest.TestCase):
    def setUp(self):
        self.a,self.plan,self.request,self.values=fixture();self.a.pop('correction')
        rng=np.random.default_rng(202610021139);z=rng.normal(size=(18,64));r=rng.normal(size=(18,24))*.02
        self.kernel=AdditiveKernel(z,r,np.ones(18)/18,np.asarray(self.plan['coordinate_target_indices']));self.coef=self.kernel.coefficients(1.,.1)[0];self.a.update(self.kernel.arrays(self.coef));self.m=AdditiveModel(self.a,self.plan)
    def store(self,d):
        np.savez_compressed(d/'model_private.npz',**self.a);(d/'plan.json').write_text(json.dumps(self.plan))
        rec={'model_kind':'dosepilot.additive_kernel.v1','selected':[.1,1.],'plan_sha256':hashlib.sha256((d/'plan.json').read_bytes()).hexdigest(),'model_sha256':hashlib.sha256((d/'model_private.npz').read_bytes()).hexdigest()}
        (d/'CONSTRUCTION.json').write_text(json.dumps(rec));return hashlib.sha256((d/'CONSTRUCTION.json').read_bytes()).hexdigest()
    def test_direct_kernel(self):
        z=(self.values-self.a['mean_x'])/self.a['scale_x'];expected=self.a['mean_y']+z@self.a['beta']+self.kernel.predict(z[None,:],self.coef)[0]
        got=self.m.predict(self.request);np.testing.assert_allclose(np.array(list(got['predictions'].values())),expected,atol=1e-14);self.assertEqual(got['model_kind'],'dosepilot.additive_kernel.v1')
    def test_missing_every_coordinate(self):
        for i in range(64):
            r=copy.deepcopy(self.request);r['measurements'][i]['value']=None
            with self.subTest(i=i),self.assertRaises(ValueError):self.m.predict(r)
    def test_reordered_records(self):
        r=copy.deepcopy(self.request);r['measurements'].reverse();self.assertEqual(self.m.predict(r),self.m.predict(self.request))
    def test_group_identity_checked(self):
        a=copy.deepcopy(self.a);a['kernel_owner']=a['kernel_owner'][::-1]
        with self.assertRaises(ValueError):AdditiveModel(a,self.plan)
    def test_wrong_backend_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            d=Path(td);self.store(d)
            self.assertEqual(AdditiveModel.load(d).predict(self.request),self.m.predict(self.request))
            for cls in [HybridModel,SpectralModel]:
                with self.subTest(cls=cls),self.assertRaises(ValueError):cls.load(d)
    def test_tampered_model(self):
        with tempfile.TemporaryDirectory() as td:
            d=Path(td);self.store(d);(d/'model_private.npz').write_bytes(b'bad')
            with self.assertRaises(ValueError):AdditiveModel.load(d)
    def test_bad_dose_identity(self):
        r=copy.deepcopy(self.request);r['measurements'][0]['dose_nM']='999'
        with self.assertRaises(ValueError):self.m.predict(r)
    def test_committed_inventory_path(self):
        spec=importlib.util.spec_from_file_location('_additive_adapter_fixture',Path(__file__).with_name('additive_workflow.py'));adapter=importlib.util.module_from_spec(spec);spec.loader.exec_module(adapter);w=adapter.load_backend()
        with tempfile.TemporaryDirectory() as td:
            d=Path(td);model=d/'model';model.mkdir();anchor=self.store(model);ledger=d/'ledger';ledger.mkdir()
            inv={'schema':'dosepilot.spectral_inventory.v1','sample_id':self.request['sample_id'],'run_id':self.request['run_id'],'orientation':'A','plate_instances':{'p1':'p1instance','p2':'p2instance'},'treatment_wells':[{k:r[k] for k in ['native_id','drug_id','dose_nM','plate','well_id']} for r in self.request['measurements']],'controls':[{'control_type':'vehicle','plate':'p1','well_id':'c1'},{'control_type':'viability','plate':'p2','well_id':'c2'}]}
            (d/'inventory.json').write_text(json.dumps(inv));w.commit(model,anchor,d/'inventory.json',d/'commitment.json',d/'template.json',ledger)
            measure=json.loads((d/'template.json').read_text());values={r['native_id']:r['value'] for r in self.request['measurements']}
            for row in measure['measurements']:row['value']=values[row['native_id']]
            (d/'measurements.json').write_text(json.dumps(measure));result=w.predict(model,anchor,d/'commitment.json',d/'measurements.json',d/'output.json',ledger)
            self.assertEqual(result['predictions'],self.m.predict(self.request)['predictions']);self.assertEqual(result['model_kind'],'dosepilot.additive_kernel.v1')

if __name__=='__main__':unittest.main(verbosity=2)
