import copy,json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
import numpy as np
PARENT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(PARENT/'hybrid_residual'),str(PARENT/'spectral_residual')]
import test_recover_baseline as fixtures
from additive_inference import AdditiveModel
from compiled_inference import CompiledAdditiveModel
from durable_workflow import load_backend
from durable_json import write_new

class Tests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.Tests('test_record_order');self.f.setUp();self.d=self.f.d
        self.w=load_backend();self.ledger=self.d/'durable_ledger';self.ledger.mkdir()
        self.commitment=self.d/'durable_commitment.json';self.template=self.d/'durable_template.json'
        self.measure=self.d/'durable_measurements.json';self.output=self.d/'durable_prediction.json'
    def tearDown(self):self.f.tearDown()
    def commit(self):return self.w.commit(self.f.modeldir,self.f.anchor,self.d/'inventory.json',self.commitment,self.template,self.ledger)
    def prepare(self):
        c=self.commit();m=json.loads(self.template.read_text());values={r['native_id']:r['value'] for r in self.f.request['measurements']}
        for row in m['measurements']:row['value']=values[row['native_id']]
        self.measure.write_text(json.dumps(m));return c,m
    def predict(self):return self.w.predict(self.f.modeldir,self.f.anchor,self.commitment,self.measure,self.output,self.ledger)
    def test_complete_numerical_parity(self):
        self.prepare();got=self.predict();ref=self.f.model.predict(self.f.request)
        np.testing.assert_allclose(list(got['predictions'].values()),list(ref['predictions'].values()),atol=1e-12,rtol=0)
        self.assertEqual(got['implementation'],CompiledAdditiveModel.IMPLEMENTATION)
    def test_missing_all64_positions_rejected(self):
        model=CompiledAdditiveModel.load(self.f.modeldir)
        for i in range(64):
            req=copy.deepcopy(self.f.request);req['measurements'][i]['value']=None
            with self.subTest(i=i),self.assertRaises(ValueError):model.predict(req)
    def test_identity_check_matrix(self):
        model=CompiledAdditiveModel.load(self.f.modeldir)
        for key,val in [('sample_id','wrong'),('run_id','wrong'),('drug_id','wrong'),('dose_nM','999'),('plate','p9'),('well_id','')]:
            req=copy.deepcopy(self.f.request);req['measurements'][0][key]=val
            with self.subTest(key=key),self.assertRaises(ValueError):model.predict(req)
    def test_order_independence(self):
        model=CompiledAdditiveModel.load(self.f.modeldir);req=copy.deepcopy(self.f.request);req['measurements'].reverse()
        self.assertEqual(model.predict(req),model.predict(self.f.request))
    def test_runtime_identity_bound(self):
        c=self.commit();r=c['model_receipt']
        self.assertEqual(r['runtime_implementation'],CompiledAdditiveModel.IMPLEMENTATION)
        self.assertEqual(len(r['runtime_code_sha256']),9)
        self.assertEqual(r['evidence_writer'],'posix.fsync-exclusive-link.v1')
    def test_original_backend_unmodified(self):
        self.assertIs(self.f.w.SpectralModel,AdditiveModel)
        self.assertIs(self.w.SpectralModel,CompiledAdditiveModel)
    def test_old_commitment_not_silently_replayed(self):
        old=self.f.commitment_path.read_bytes()
        with self.assertRaises(ValueError):self.w.commit(self.f.modeldir,self.f.anchor,self.d/'inventory.json',self.d/'changed.json',self.d/'changed_template.json',self.f.ledger)
        self.assertEqual(self.f.commitment_path.read_bytes(),old)
    def test_prediction_export_recovery(self):
        self.prepare();first=self.predict();self.output.unlink();self.assertEqual(first,self.predict())
    def test_changed_measurement_no_overwrite(self):
        _,m=self.prepare();self.predict();old=self.output.read_bytes();m['measurements'][0]['value']+=.1;self.measure.write_text(json.dumps(m))
        with self.assertRaises(ValueError):self.predict()
        self.assertEqual(self.output.read_bytes(),old)
    def test_interrupted_commit_all_publication_sites(self):
        for call in range(3):
            for phase in ('first_chunk_written','published'):
                with self.subTest(call=call,phase=phase):
                    d=self.d/f'commit_case_{call}_{phase}';d.mkdir();ledger=d/'ledger';ledger.mkdir()
                    args=[str(self.f.modeldir),self.f.anchor,str(self.d/'inventory.json'),str(d/'commit.json'),str(d/'template.json'),str(ledger)]
                    self.child(d,{'action':'commit','args':args,'call_index':call,'phase':phase})
                    self.assert_valid_authoritative(d)
                    result=self.w.commit(*args)
                    self.assertEqual(json.loads((d/'commit.json').read_text()),result)
                    self.assertEqual(len(list(ledger.glob('*.commitment.json'))),1)
    def test_interrupted_prediction_all_publication_sites(self):
        for call in range(2):
            for phase in ('first_chunk_written','published'):
                with self.subTest(call=call,phase=phase):
                    d=self.d/f'predict_case_{call}_{phase}';d.mkdir();ledger=d/'ledger';ledger.mkdir()
                    c=self.w.commit(self.f.modeldir,self.f.anchor,self.d/'inventory.json',d/'commit.json',d/'template.json',ledger)
                    m=json.loads((d/'template.json').read_text());v={r['native_id']:r['value'] for r in self.f.request['measurements']}
                    for row in m['measurements']:row['value']=v[row['native_id']]
                    (d/'measure.json').write_text(json.dumps(m))
                    args=[str(self.f.modeldir),self.f.anchor,str(d/'commit.json'),str(d/'measure.json'),str(d/'pred.json'),str(ledger)]
                    self.child(d,{'action':'predict','args':args,'call_index':call,'phase':phase})
                    self.assert_valid_authoritative(d)
                    result=self.w.predict(*args)
                    self.assertEqual(json.loads((d/'pred.json').read_text()),result)
                    self.assertEqual(len(list(ledger.glob('*.prediction.json'))),1)
    def test_legacy_interrupted_dump_leaves_partial_final(self):
        d=self.d/'legacy';d.mkdir();path=d/'legacy_receipt.json'
        self.child(d,{'action':'legacy','path':str(path)})
        self.assertTrue(path.exists())
        with self.assertRaises(json.JSONDecodeError):json.loads(path.read_text())
    def child(self,d,config):
        path=d/'child_config.json';path.write_text(json.dumps(config))
        r=subprocess.run([sys.executable,str(Path(__file__).resolve()),'child',str(path)],capture_output=True,timeout=30)
        self.assertEqual(r.returncode,73,r.stderr.decode())
    def assert_valid_authoritative(self,d):
        for path in d.rglob('*.json'):
            if not path.name.startswith('.dosepilot-pending-'):json.loads(path.read_text())


def child(config):
    w=load_backend()
    if config['action']=='legacy':
        from additive_workflow import load_backend as old_backend
        old=old_backend();original_dump=json.dump
        class CrashWriter:
            def __init__(self,fp):self.fp=fp;self.count=0
            def write(self,value):
                out=self.fp.write(value);self.count+=len(value)
                if self.count>=4096:self.fp.flush();os._exit(73)
                return out
        def interrupted_dump(value,fp,**kwargs):return original_dump(value,CrashWriter(fp),**kwargs)
        old.json.dump=interrupted_dump
        old.write_new(config['path'],{'fictional_payload':['value'*100 for _ in range(100)]})
    else:
        counter=[-1]
        def intercepted(path,value):
            counter[0]+=1;index=counter[0]
            def hook(phase):
                if index==config['call_index'] and phase==config['phase']:os._exit(73)
            write_new(path,value,_checkpoint=hook)
        w.write_new=intercepted
        getattr(w,config['action'])(*config['args'])
    raise SystemExit('Fault injection did not fire')

if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='child':child(json.loads(Path(sys.argv[2]).read_text()))
    else:unittest.main(verbosity=2)
