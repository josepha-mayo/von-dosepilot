import copy
import json
import multiprocessing
import os
from pathlib import Path
import unittest
from unittest.mock import patch
import numpy as np
import lifecycle
import test_recover_baseline as fixtures
from durable_json import write_new


class Tests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.Tests('test_record_order');self.f.setUp()
        self.root=self.f.d/'lifecycle';self.root.mkdir();self.ledger=self.root/'ledger';self.ledger.mkdir()
        self.c=self.root/'commitment.json';self.template=self.root/'template.json'
        self.kw=dict(model_dir=self.f.modeldir,construction_sha256=self.f.anchor,
                     ledger_dir=self.ledger,commitment=self.c)
    def tearDown(self):self.f.tearDown()
    def commit(self):
        return lifecycle.execute('commit',**self.kw,inventory=self.f.d/'inventory.json',template=self.template)
    def measurements(self,missing=(),name='measurements.json'):
        if not self.c.exists():self.commit()
        m=json.loads(self.template.read_text())
        for row,value in zip(m['measurements'],self.f.values):row['value']=float(value)
        for i in missing:m['measurements'][i]['value']=None
        path=self.root/name;path.write_text(json.dumps(m));return path,m
    def recover(self,path,name='baseline.json',**kwargs):
        return lifecycle.execute('recover',**self.kw,measurements=path,output=self.root/name,
                                 acknowledge_baseline_only=True,**kwargs)
    def test_complete_path_matches_original(self):
        path,_=self.measurements()
        got=lifecycle.execute('predict',**self.kw,measurements=path,output=self.root/'primary.json')
        want=self.f.model.predict(self.f.request)
        np.testing.assert_allclose(list(got['predictions'].values()),list(want['predictions'].values()),atol=1e-13,rtol=0)
        self.assertEqual(got['evidence']['lifecycle_policy'],lifecycle.POLICY)
    def test_missing_primary_withheld(self):
        path,_=self.measurements((0,))
        with self.assertRaises(ValueError):lifecycle.execute('predict',**self.kw,measurements=path,output=self.root/'primary.json')
        self.assertFalse((self.root/'primary.json').exists())
    def test_recovery_requires_acknowledgement(self):
        path,_=self.measurements((0,))
        with self.assertRaisesRegex(ValueError,'ACKNOWLEDGEMENT'):
            lifecycle.execute('recover',**self.kw,measurements=path,output=self.root/'baseline.json')
    def test_explicit_recovery_retains_23_older_estimates(self):
        path,_=self.measurements((0,));r=self.recover(path)
        self.assertEqual(len(r['baseline_predictions']),23);self.assertEqual(r['primary_predictions'],{})
        self.assertFalse(r['kernel_prediction_called']);self.assertFalse(r['missing_values_imputed'])
    def test_predict_automatically_checks_recovery_history(self):
        path,_=self.measurements((0,));self.recover(path)
        complete,vals=self.measurements(name='complete.json');vals['measurements'][1]['value']+=.01;complete.write_text(json.dumps(vals))
        with self.assertRaisesRegex(ValueError,'OBSERVATION_CHANGED'):
            lifecycle.execute('predict',**self.kw,measurements=complete,output=self.root/'primary.json')
        self.assertFalse(list(self.ledger.glob('*.prediction.json')))
    def test_complete_missing_reading_preserves_primary(self):
        path,_=self.measurements((0,));self.recover(path)
        complete,_=self.measurements(name='complete.json')
        r=lifecycle.execute('predict',**self.kw,measurements=complete,output=self.root/'primary.json')
        again=lifecycle.execute('predict',**self.kw,measurements=complete,output=self.root/'primary.json')
        self.assertEqual(r,again);self.assertEqual(len(r['predictions']),24)
        self.assertEqual(len(list(self.ledger.glob('*.recovery_completion.json'))),1)
    def test_partial_publication_exposes_no_final_name(self):
        path,_=self.measurements((0,));backend=lifecycle.load_backend()
        def hook(stage):
            if stage=='first_chunk_written':raise OSError('injected interruption')
        backend.write_new=lambda p,v:write_new(p,v,_checkpoint=hook)
        with patch.object(lifecycle,'load_backend',return_value=backend),self.assertRaises(OSError):self.recover(path)
        self.assertFalse(list(self.ledger.glob('*.baseline_recovery.*.json')))
        self.assertEqual(len(self.recover(path)['baseline_predictions']),23)
    def test_after_publication_export_recovers_exactly(self):
        path,_=self.measurements((0,));backend=lifecycle.load_backend()
        def hook(stage):
            if stage=='published':raise OSError('injected interruption')
        backend.write_new=lambda p,v:write_new(p,v,_checkpoint=hook)
        with patch.object(lifecycle,'load_backend',return_value=backend),self.assertRaises(OSError):self.recover(path)
        self.assertEqual(len(list(self.ledger.glob('*.baseline_recovery.*.json'))),1)
        r=self.recover(path);self.assertEqual(r,self.recover(path))
    def test_old_commitment_not_silently_migrated(self):
        old=dict(self.kw,ledger_dir=self.f.ledger,commitment=self.f.commitment_path)
        self.f.measure_path.write_text(json.dumps(self.f.complete))
        with self.assertRaisesRegex(ValueError,'COMMITMENT_MISMATCH'):
            lifecycle.execute('predict',**old,measurements=self.f.measure_path,output=self.root/'old.json')
    def test_input_identity_change_during_lock_rejected(self):
        original=json.loads((self.f.d/'inventory.json').read_text())
        def changed():
            value=copy.deepcopy(original);value['run_id']='different';(self.f.d/'inventory.json').write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError,'IDENTITY_CHANGED'):
            lifecycle.execute('commit',**self.kw,inventory=self.f.d/'inventory.json',template=self.template,_on_locked=changed)
        self.assertFalse(self.c.exists())
    def test_non_object_identity_rejected(self):
        (self.f.d/'inventory.json').write_text('[]')
        with self.assertRaisesRegex(ValueError,'MUST_BE_OBJECT'):self.commit()
    def test_concurrent_conflicting_recoveries_cannot_fork(self):
        path,_=self.measurements((0,));other,vals=self.measurements((0,),name='other.json')
        vals['measurements'][1]['value']+=.01;other.write_text(json.dumps(vals))
        ctx=multiprocessing.get_context('fork');locked=ctx.Event();release=ctx.Event()
        def child():
            def hold():
                locked.set()
                if not release.wait(5):os._exit(99)
            self.recover(path,_on_locked=hold)
        worker=ctx.Process(target=child);worker.start()
        try:
            self.assertTrue(locked.wait(3))
            with self.assertRaisesRegex(BlockingIOError,'FRAME_BUSY'):self.recover(other,name='other_baseline.json')
            self.assertFalse((self.root/'other_baseline.json').exists())
        finally:
            release.set();worker.join(5)
            if worker.is_alive():worker.terminate();worker.join()
        self.assertEqual(worker.exitcode,0)
        with self.assertRaisesRegex(ValueError,'OBSERVATION_CHANGED'):self.recover(other,name='other_baseline.json')
        self.assertEqual(len(list(self.ledger.glob('*.baseline_recovery.*.json'))),1)
    def test_dead_process_releases_frame_without_deleting_lock_file(self):
        path,_=self.measurements((0,));ctx=multiprocessing.get_context('fork')
        def child():self.recover(path,_on_locked=lambda:os._exit(23))
        worker=ctx.Process(target=child);worker.start();worker.join(5)
        if worker.is_alive():worker.terminate();worker.join()
        self.assertEqual(worker.exitcode,23)
        self.assertEqual(len(self.recover(path)['baseline_predictions']),23)
    def test_original_recovery_module_remains_unmodified(self):
        import recover_baseline
        before=recover_baseline.load_backend
        path,_=self.measurements((0,));self.recover(path)
        self.assertIs(recover_baseline.load_backend,before)
    def test_completed_primary_prevents_later_recovery(self):
        path,_=self.measurements();lifecycle.execute('predict',**self.kw,measurements=path,output=self.root/'primary.json')
        path,_=self.measurements((0,),name='missing.json')
        with self.assertRaisesRegex(ValueError,'PRIMARY_RESULT_ALREADY'):self.recover(path)

if __name__=='__main__':unittest.main(verbosity=2)
