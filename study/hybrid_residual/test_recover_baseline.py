import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from additive_kernel import AdditiveKernel
from additive_inference import AdditiveModel
from additive_workflow import load_backend
from test_inference import fixture
from recover_baseline import recover, compute_baseline, BASE_KIND


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        self.modeldir = self.d/'model'; self.modeldir.mkdir()
        self.ledger = self.d/'ledger'; self.ledger.mkdir()
        a, plan, req, values = fixture(); a.pop('correction')
        rng = np.random.default_rng(21330)
        z = rng.normal(size=(18, 64)); r = rng.normal(size=(18, 24))*.02
        kernel = AdditiveKernel(z, r, np.ones(18)/18,
                                np.asarray(plan['coordinate_target_indices']))
        a.update(kernel.arrays(kernel.coefficients(1., .1)[0]))
        self.model = AdditiveModel(a, plan)
        self.values = values; self.request = req
        np.savez_compressed(self.modeldir/'model_private.npz', **a)
        (self.modeldir/'plan.json').write_text(json.dumps(plan))
        receipt = {'model_kind': AdditiveModel.MODEL_KIND, 'selected': [.1, 1.],
            'plan_sha256': hashlib.sha256((self.modeldir/'plan.json').read_bytes()).hexdigest(),
            'model_sha256': hashlib.sha256((self.modeldir/'model_private.npz').read_bytes()).hexdigest()}
        (self.modeldir/'CONSTRUCTION.json').write_text(json.dumps(receipt))
        self.anchor = hashlib.sha256((self.modeldir/'CONSTRUCTION.json').read_bytes()).hexdigest()
        self.w = load_backend()
        self.commitment_path = self.d/'commitment.json'
        self.measure_path = self.d/'measurements.json'
        self.output = self.d/'recovery.json'
        inv = {'schema': 'dosepilot.spectral_inventory.v1',
            'sample_id': req['sample_id'], 'run_id': req['run_id'], 'orientation': 'A',
            'plate_instances': {'p1': 'physical1', 'p2': 'physical2'},
            'treatment_wells': [{k: row[k] for k in ['native_id','drug_id','dose_nM','plate','well_id']}
                                for row in req['measurements']],
            'controls': [{'control_type':'vehicle','plate':'p1','well_id':'control1'},
                         {'control_type':'viability','plate':'p2','well_id':'control2'}]}
        ip = self.d/'inventory.json'; ip.write_text(json.dumps(inv))
        self.commitment = self.w.commit(self.modeldir, self.anchor, ip,
                                        self.commitment_path, self.d/'template.json', self.ledger)
        self.complete = json.loads((self.d/'template.json').read_text())
        for row, value in zip(self.complete['measurements'], values): row['value'] = float(value)
    def tearDown(self):
        self.tmp.cleanup()
    def partial(self, missing=(0,)):
        data = copy.deepcopy(self.complete)
        for i in missing: data['measurements'][i]['value'] = None
        return data
    def call(self, data, output=None, ack=True):
        self.measure_path.write_text(json.dumps(data))
        return recover(self.modeldir, self.anchor, self.commitment_path, self.measure_path,
                       self.output if output is None else output, self.ledger, ack)
    def test_explicit_acknowledgement(self):
        with self.assertRaisesRegex(ValueError, 'ACKNOWLEDGEMENT'):
            self.call(self.partial(), ack=False)
        self.assertFalse(self.output.exists())
    def test_complete_input_not_silently_downgraded(self):
        with self.assertRaisesRegex(ValueError, 'USE_PRIMARY'):
            self.call(self.complete)
    def test_all64_single_missing_cases_exact_baseline(self):
        z = (self.values-self.model.a['mean_x'])/self.model.a['scale_x']
        direct = self.model.a['mean_y']+z@self.model.a['beta']
        with patch.object(self.model, 'predict', side_effect=AssertionError('Primary called')):
            for i in range(64):
                data = self.partial((i,))
                r = compute_baseline(self.model, self.w, self.commitment, data)
                self.assertEqual(len(r['baseline_predictions']), 23)
                self.assertEqual(r['primary_predictions'], {})
                missing = self.model.targets[int(self.model.owner[i])]
                self.assertNotIn(missing, r['baseline_predictions'])
                for j, target in enumerate(self.model.targets):
                    if target != missing:
                        self.assertAlmostEqual(r['baseline_predictions'][target], float(direct[j]), places=13)
                        self.assertEqual(r['target_states'][target]['model_kind'], BASE_KIND)
    def test_same_and_different_head_missingness(self):
        for indices, expected in [((0,1),23), ((0,3),22), (tuple(range(64)),0)]:
            r = compute_baseline(self.model, self.w, self.commitment, self.partial(indices))
            self.assertEqual(len(r['baseline_predictions']), expected)
            self.assertFalse(r['kernel_prediction_called']); self.assertFalse(r['missing_values_imputed'])
    def test_all_identities_checked_even_missing_rows(self):
        for key, value in [('dose_nM','999'),('plate','wrong'),('drug_id','wrong'),('well_id','wrong')]:
            data = self.partial(); data['measurements'][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): self.call(data)
            self.assertFalse(self.output.exists())
    def test_nonfinite_bool_string_not_missing(self):
        for value in [True, 'missing', float('nan'), float('inf')]:
            data = self.partial(); data['measurements'][1]['value'] = value
            with self.subTest(value=value), self.assertRaises(ValueError): self.call(data)
    def test_missing_or_duplicate_records_rejected(self):
        for mode in ['removed','duplicate']:
            data = self.partial()
            if mode=='removed': data['measurements'].pop()
            else: data['measurements'][1] = copy.deepcopy(data['measurements'][0])
            with self.subTest(mode=mode), self.assertRaises(ValueError): self.call(data)
    def test_record_order(self):
        a = self.partial(); b = copy.deepcopy(a); b['measurements'].reverse()
        self.assertEqual(compute_baseline(self.model,self.w,self.commitment,a),
                         compute_baseline(self.model,self.w,self.commitment,b))
    def test_trust_anchor_required(self):
        self.anchor = '0'*64
        with self.assertRaisesRegex(ValueError,'TRUST_ANCHOR'): self.call(self.partial())
    def test_commitment_is_required(self):
        self.w.ledger_path(self.ledger,self.commitment['frame_id'],'.commitment.json').unlink()
        with self.assertRaisesRegex(ValueError,'NOT_IN_LEDGER'): self.call(self.partial())
    def test_export_failure_recovery(self):
        with self.assertRaises(OSError): self.call(self.partial(), self.d/'absent'/'result.json')
        self.assertEqual(len(list(self.ledger.glob('*.baseline_recovery.*.json'))),1)
        got = self.call(self.partial())
        self.output.unlink()
        again = self.call(self.partial())
        self.assertEqual(got,again)
        self.assertEqual(len(list(self.ledger.glob('*.baseline_recovery.*.json'))),1)
        self.assertFalse(list(self.ledger.glob('*.prediction.json')))
    def test_cannot_rewrite_existing_observation(self):
        first = self.call(self.partial())
        data = self.partial(); data['measurements'][1]['value'] += .01
        with self.assertRaisesRegex(ValueError,'OBSERVATION_CHANGED'):
            self.call(data,self.d/'second.json')
        self.assertEqual(json.loads(self.output.read_text()),first)
    def test_monotone_fill_allowed(self):
        first = self.call(self.partial((0,3)))
        second = self.call(self.partial((0,)),self.d/'second.json')
        self.assertEqual(len(first['baseline_predictions']),22)
        self.assertEqual(len(second['baseline_predictions']),23)
        self.assertEqual(len(list(self.ledger.glob('*.baseline_recovery.*.json'))),2)
    def test_prior_recovery_tampering_rejected(self):
        self.call(self.partial())
        path = next(self.ledger.glob('*.baseline_recovery.*.json'))
        old = json.loads(path.read_text()); old['baseline_predictions']['d01'] = 123.
        path.write_text(json.dumps(old))
        with self.assertRaisesRegex(ValueError,'DIGEST_MISMATCH'):
            self.call(self.partial(),self.d/'second.json')
    def test_primary_report_cannot_be_replaced(self):
        self.measure_path.write_text(json.dumps(self.complete))
        primary = self.w.predict(self.modeldir,self.anchor,self.commitment_path,
                                 self.measure_path,self.d/'primary.json',self.ledger)
        with self.assertRaisesRegex(ValueError,'PRIMARY_RESULT_ALREADY'):
            self.call(self.partial())
        self.assertEqual(json.loads((self.d/'primary.json').read_text()),primary)
    def test_output_collision(self):
        with self.assertRaisesRegex(ValueError,'PATH_COLLISION'):
            self.call(self.partial(),self.measure_path)
        self.assertFalse(list(self.ledger.glob('*.baseline_recovery.*.json')))
    def test_primary_still_rejects_incomplete(self):
        data = self.partial(); self.measure_path.write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            self.w.predict(self.modeldir,self.anchor,self.commitment_path,
                           self.measure_path,self.d/'primary.json',self.ledger)
        self.assertFalse((self.d/'primary.json').exists())
    def test_duplicate_json_keys_rejected(self):
        raw = json.dumps(self.partial())
        self.measure_path.write_text(raw[:-1]+',"schema":"duplicate"}')
        with self.assertRaisesRegex(ValueError,'DUPLICATE_JSON_KEY'):
            recover(self.modeldir,self.anchor,self.commitment_path,self.measure_path,
                    self.output,self.ledger,True)


if __name__ == '__main__':
    unittest.main(verbosity=2)
