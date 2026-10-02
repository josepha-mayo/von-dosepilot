import copy,hashlib,json,tempfile,unittest
from pathlib import Path
import numpy as np
from hybrid_inference import HybridModel,SpectralModel
import importlib.util
spec=importlib.util.spec_from_file_location('_hybrid_adapter_test',Path(__file__).with_name('operating_workflow.py'))
adapter=importlib.util.module_from_spec(spec);spec.loader.exec_module(adapter)
load_backend=adapter.load_backend
from kernel_spectral import KernelSpectral
from test_inference import fixture

class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.modeldir=self.root/'model';self.modeldir.mkdir();self.ledger=self.root/'ledger';self.ledger.mkdir()
        arrays,plan,request,values=fixture();arrays.pop('correction')
        rng=np.random.default_rng(202610021145);z=rng.normal(size=(18,64));r=rng.normal(size=(18,24))*.02;model=KernelSpectral(z,r,np.ones(18)/18,True);arrays.update(model.arrays(model.coefficients(1.,.1)[0]))
        np.savez_compressed(self.modeldir/'model_private.npz',**arrays);(self.modeldir/'plan.json').write_text(json.dumps(plan))
        rec={'model_kind':'dosepilot.hybrid_kernel.v1','selected':[.1,1.],'plan_sha256':hashlib.sha256((self.modeldir/'plan.json').read_bytes()).hexdigest(),'model_sha256':hashlib.sha256((self.modeldir/'model_private.npz').read_bytes()).hexdigest()}
        (self.modeldir/'CONSTRUCTION.json').write_text(json.dumps(rec));self.anchor=hashlib.sha256((self.modeldir/'CONSTRUCTION.json').read_bytes()).hexdigest()
        self.request=request;self.values=values;self.w=load_backend();self.inventory=self.root/'inventory.json';self.commitment=self.root/'commitment.json';self.template=self.root/'template.json';self.measurements=self.root/'measurements.json';self.output=self.root/'output.json'
        inv={'schema':'dosepilot.spectral_inventory.v1','sample_id':request['sample_id'],'run_id':request['run_id'],'orientation':'A','plate_instances':{'p1':'physical1','p2':'physical2'},'treatment_wells':[{k:r[k] for k in ['native_id','drug_id','dose_nM','plate','well_id']} for r in request['measurements']],'controls':[{'control_type':'vehicle','plate':'p1','well_id':'control1'},{'control_type':'viability','plate':'p2','well_id':'control2'}]}
        self.inventory.write_text(json.dumps(inv))
    def tearDown(self):self.tmp.cleanup()
    def commit(self):return self.w.commit(self.modeldir,self.anchor,self.inventory,self.commitment,self.template,self.ledger)
    def complete(self):
        self.commit();m=json.loads(self.template.read_text());values={r['native_id']:r['value'] for r in self.request['measurements']}
        for r in m['measurements']:r['value']=values[r['native_id']]
        self.measurements.write_text(json.dumps(m));return m
    def test_valid_end_to_end(self):
        self.complete();got=self.w.predict(self.modeldir,self.anchor,self.commitment,self.measurements,self.output,self.ledger)
        want=HybridModel.load(self.modeldir).predict(self.request)
        self.assertEqual(got['predictions'],want['predictions']);self.assertEqual(got['model_kind'],'dosepilot.hybrid_kernel.v1');self.assertEqual(got['evidence']['treatment_wells'],64)
    def test_missing_stops_before_output(self):
        m=self.complete();m['measurements'][7]['value']=None;self.measurements.write_text(json.dumps(m))
        with self.assertRaises(ValueError):self.w.predict(self.modeldir,self.anchor,self.commitment,self.measurements,self.output,self.ledger)
        self.assertFalse(self.output.exists());self.assertFalse(list(self.ledger.glob('*.prediction.json')))
    def test_trust_anchor_required(self):
        with self.assertRaises(ValueError):self.w.commit(self.modeldir,'0'*64,self.inventory,self.commitment,self.template,self.ledger)
        self.assertFalse(self.commitment.exists())
    def test_original_class_not_modified(self):
        self.assertIs(self.w.SpectralModel,HybridModel);self.assertNotEqual(SpectralModel,HybridModel)
        import inference
        self.assertIs(inference.SpectralModel,SpectralModel)
    def test_recovery_no_reassignment(self):
        one=self.commit();self.template.unlink();two=self.commit();self.assertEqual(one,two)
    def test_measurement_replay_cannot_replace_result(self):
        m=self.complete();first=self.w.predict(self.modeldir,self.anchor,self.commitment,self.measurements,self.output,self.ledger)
        m['measurements'][0]['value']+=.01;self.measurements.write_text(json.dumps(m))
        with self.assertRaises(ValueError):self.w.predict(self.modeldir,self.anchor,self.commitment,self.measurements,self.output,self.ledger)
        self.assertEqual(json.loads(self.output.read_text()),first)
    def test_wrong_family_stops_commit(self):
        p=self.modeldir/'CONSTRUCTION.json';r=json.loads(p.read_text());r['model_kind']='linear';p.write_text(json.dumps(r));self.anchor=hashlib.sha256(p.read_bytes()).hexdigest()
        with self.assertRaises(ValueError):self.commit()
        self.assertFalse(self.commitment.exists())

if __name__=='__main__':unittest.main(verbosity=2)
