import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np

HERE=Path(__file__).resolve().parent
STUDY=HERE.parent
import sys
sys.path[:0]=[str(HERE),str(STUDY/'hybrid_residual'),str(STUDY/'spectral_residual')]

from test_inference import fixture
from bandwidth_additive import BandwidthAdditive
from bandwidth_inference import BandwidthAdditiveModel
import bandwidth_lifecycle
import lifecycle as old_lifecycle

class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.d=Path(self.tmp.name)
        self.modeldir=self.d/'model';self.modeldir.mkdir()
        self.ledger=self.d/'ledger';self.ledger.mkdir()
        arrays,plan,request,values=fixture();arrays.pop('correction')
        rng=np.random.default_rng(70317)
        z=rng.normal(size=(20,64));res=rng.normal(scale=.02,size=(20,24))
        owner=np.asarray(plan['coordinate_target_indices'])
        kernel=BandwidthAdditive(z,res,np.ones(20)/20,owner,.7)
        arrays.update(kernel.arrays(kernel.coefficients(1.,.1)[0]))
        self.model=BandwidthAdditiveModel(arrays,plan)
        self.request=request;self.values=values
        np.savez_compressed(self.modeldir/'model_private.npz',**arrays)
        (self.modeldir/'plan.json').write_text(json.dumps(plan))
        receipt={'model_kind':BandwidthAdditiveModel.MODEL_KIND,'bandwidth_multiplier':.7,
                 'selected':[.1,1.],
                 'plan_sha256':hashlib.sha256((self.modeldir/'plan.json').read_bytes()).hexdigest(),
                 'model_sha256':hashlib.sha256((self.modeldir/'model_private.npz').read_bytes()).hexdigest()}
        (self.modeldir/'CONSTRUCTION.json').write_text(json.dumps(receipt))
        self.anchor=hashlib.sha256((self.modeldir/'CONSTRUCTION.json').read_bytes()).hexdigest()
        self.commitment=self.d/'commitment.json';self.template=self.d/'template.json'
        inv={'schema':'dosepilot.spectral_inventory.v1',
             'sample_id':request['sample_id'],'run_id':request['run_id'],'orientation':'A',
             'plate_instances':{'p1':'fictional-p1','p2':'fictional-p2'},
             'treatment_wells':[{k:row[k] for k in ['native_id','drug_id','dose_nM','plate','well_id']}
                                for row in request['measurements']],
             'controls':[{'control_type':'vehicle','plate':'p1','well_id':'ctrl-v'},
                         {'control_type':'viability','plate':'p2','well_id':'ctrl-live'}]}
        self.inventory=self.d/'inventory.json';self.inventory.write_text(json.dumps(inv))
        self.kw=dict(model_dir=self.modeldir,construction_sha256=self.anchor,
                     ledger_dir=self.ledger,commitment=self.commitment)
    def tearDown(self):self.tmp.cleanup()
    def commit(self):
        return bandwidth_lifecycle.execute('commit',**self.kw,inventory=self.inventory,template=self.template)
    def complete_file(self,name='complete.json'):
        if not self.template.exists():self.commit()
        m=json.loads(self.template.read_text())
        for row,value in zip(m['measurements'],self.values):row['value']=float(value)
        p=self.d/name;p.write_text(json.dumps(m));return p,m
    def missing_file(self,index=0,name='missing.json'):
        p,m=self.complete_file(name);m['measurements'][index]['value']=None;p.write_text(json.dumps(m));return p,m
    def test_commit_receipt_binds_bandwidth_lifecycle(self):
        c=self.commit();r=c['model_receipt']
        self.assertEqual(r['lifecycle_policy'],bandwidth_lifecycle.POLICY)
        self.assertEqual(r['runtime_implementation'],'dosepilot.bandwidth_durable.v1')
        self.assertEqual(c['plate_counts'],{'p1':32,'p2':32})
    def test_complete_prediction_matches_bandwidth_backend(self):
        p,_=self.complete_file();out=self.d/'primary.json'
        got=bandwidth_lifecycle.execute('predict',**self.kw,measurements=p,output=out)
        direct=self.model.predict(self.request)
        self.assertEqual(got['model_kind'],BandwidthAdditiveModel.MODEL_KIND)
        np.testing.assert_allclose([got['predictions'][t] for t in self.model.targets],
                                   [direct['predictions'][t] for t in self.model.targets],atol=1e-13,rtol=0)
    def test_one_missing_is_baseline_only(self):
        p,_=self.missing_file();out=self.d/'baseline.json'
        r=bandwidth_lifecycle.execute('recover',**self.kw,measurements=p,output=out,
                                      acknowledge_baseline_only=True)
        self.assertEqual(r['source_model_kind'],BandwidthAdditiveModel.MODEL_KIND)
        self.assertEqual(r['primary_predictions'],{})
        self.assertEqual(len(r['baseline_predictions']),23)
        self.assertFalse(r['missing_values_imputed'])
    def test_recovery_requires_explicit_ack(self):
        p,_=self.missing_file();out=self.d/'baseline.json'
        with self.assertRaisesRegex(ValueError,'ACKNOWLEDGEMENT'):
            bandwidth_lifecycle.execute('recover',**self.kw,measurements=p,output=out)
    def test_completion_checks_recovery_history(self):
        missing,_=self.missing_file();bandwidth_lifecycle.execute(
            'recover',**self.kw,measurements=missing,output=self.d/'baseline.json',
            acknowledge_baseline_only=True)
        complete,m=self.complete_file('full.json')
        m['measurements'][1]['value']+=.01;complete.write_text(json.dumps(m))
        with self.assertRaisesRegex(ValueError,'OBSERVATION_CHANGED'):
            bandwidth_lifecycle.execute('predict',**self.kw,measurements=complete,output=self.d/'primary.json')
        self.assertFalse(list(self.ledger.glob('*.prediction.json')))
    def test_recovered_frame_completes_to_bandwidth_primary(self):
        missing,_=self.missing_file();bandwidth_lifecycle.execute(
            'recover',**self.kw,measurements=missing,output=self.d/'baseline.json',
            acknowledge_baseline_only=True)
        complete,_=self.complete_file('full.json');out=self.d/'primary.json'
        r=bandwidth_lifecycle.execute('predict',**self.kw,measurements=complete,output=out)
        self.assertEqual(r['model_kind'],BandwidthAdditiveModel.MODEL_KIND)
        self.assertEqual(len(r['predictions']),24)
        self.assertEqual(len(list(self.ledger.glob('*.recovery_completion.json'))),1)
    def test_old_additive_lifecycle_cannot_open_bandwidth_model(self):
        p,_=self.complete_file();out=self.d/'old.json'
        with self.assertRaises(ValueError):
            old_lifecycle.execute('predict',**self.kw,measurements=p,output=out)
        self.assertFalse(out.exists())
    def test_wrong_model_family_rejected(self):
        receipt=json.loads((self.modeldir/'CONSTRUCTION.json').read_text())
        receipt['model_kind']='dosepilot.additive_kernel.v1'
        (self.modeldir/'CONSTRUCTION.json').write_text(json.dumps(receipt))
        self.kw['construction_sha256']=hashlib.sha256((self.modeldir/'CONSTRUCTION.json').read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError,'Wrong model family'):
            self.commit()

if __name__=='__main__':unittest.main(verbosity=2)
