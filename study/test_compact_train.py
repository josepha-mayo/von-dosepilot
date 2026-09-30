"""Invented-data tests; no source workbook or biological measurements."""
import copy
import csv
import io
import json
from pathlib import Path
import sys
import unittest
import numpy as np
from compact_train import FIELDS, from_curve_bytes, read_catalog, dose_key, integrate

HERE = Path(__file__).resolve().parent


def encode(rows, fields=FIELDS):
    f = io.StringIO(newline='')
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader(); w.writerows(rows)
    return f.getvalue().encode()


class CompactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = read_catalog(HERE/'TRAIN_CATALOG.json')
        cls.rows = []
        s = cls.spec
        for sample_index in range(2):
            sample = f'Pt90000{sample_index}_invented'
            slot = 0
            for j, drug in enumerate(s['target_ids']):
                doses = {dose_key(d) for d, owner in zip(s['native_concentrations_nM'], s['native_target_indices']) if owner == j}
                doses |= {dose_key(d) for d in s['target_bounds_nM'][drug]}
                for d in sorted(doses):
                    for plate in ('p1', 'p2'):
                        cls.rows.append(dict(zip(FIELDS, (sample, f'Pt90000{sample_index}', 'lib1', 'run1', drug, plate, str(d), '0.75', 'A', str(slot), 'fictional'))))
                    slot += 1
        cls.spec = copy.deepcopy(s)
        cls.spec.update(expected_samples=2, expected_patients=2, expected_train_curve_rows=len(cls.rows))

    def load(self, rows=None, spec=None):
        return from_curve_bytes(encode(self.rows if rows is None else rows), self.spec if spec is None else spec, require_pin=False)

    def changed(self, key, value):
        r = copy.deepcopy(self.rows); r[0][key] = value; return r

    def test_valid_complete(self):
        d, f, rep = self.load()
        self.assertEqual(d['y'].shape, (2, 24)); self.assertEqual(f['x_replicates'].shape, (2,164,2))
        np.testing.assert_allclose(d['y'], .75, atol=1e-15)
        self.assertEqual(f['audit']['lib2_response_values_converted'], 0)

    def test_hash_required(self):
        with self.assertRaisesRegex(ValueError,'fixed Lib1 TRAIN curve bytes'):
            from_curve_bytes(encode(self.rows), self.spec)

    def test_lib2_before_response(self):
        rows=self.changed('library_id','lib2');rows[0]['viability']='not-a-number'
        with self.assertRaisesRegex(ValueError,'Only the previously released Lib1'):
            self.load(rows)

    def test_patient_identity(self):
        with self.assertRaisesRegex(ValueError,'patient identity'): self.load(self.changed('patient_id','Pt777777'))

    def test_unknown_target(self):
        with self.assertRaisesRegex(ValueError,'Unknown plate or target'):self.load(self.changed('drug_id','UNDECLARED'))

    def test_unknown_plate(self):
        with self.assertRaisesRegex(ValueError,'Unknown plate or target'):self.load(self.changed('plate','p3'))

    def test_repeated_physical_well(self):
        with self.assertRaisesRegex(ValueError,'Repeated physical'):self.load(self.rows+[self.rows[0]])

    def test_repeated_dose_other_well(self):
        r=copy.deepcopy(self.rows[0]);r['dcol']='other'
        with self.assertRaisesRegex(ValueError,'Repeated native dose'):self.load(self.rows+[r])

    def test_nonfinite(self):
        for v in ('nan','inf','-inf'):
            with self.subTest(v=v), self.assertRaisesRegex(ValueError,'nonfinite'):self.load(self.changed('viability',v))

    def test_nonnumeric(self):
        with self.assertRaisesRegex(ValueError,'nonnumeric'):self.load(self.changed('viability','bad'))

    def test_nonpositive_dose(self):
        for v in ('0','-1','nan','Infinity'):
            with self.subTest(v=v), self.assertRaises(ValueError):self.load(self.changed('dose_nM',v))

    def test_incomplete_population(self):
        with self.assertRaisesRegex(ValueError,'denominator changed'):self.load(self.rows[:-1])

    def test_inconsistent_run(self):
        with self.assertRaisesRegex(ValueError,'run identities'):self.load(self.changed('run_id','other_run'))

    def test_schema(self):
        with self.assertRaisesRegex(ValueError,'schema changed'):
            from_curve_bytes(encode(self.rows, FIELDS[::-1]), self.spec, require_pin=False)

    def test_dose_alias(self):
        rows=copy.deepcopy(self.rows)
        for row in rows:row['dose_nM']=format(float(row['dose_nM']),'.12e')
        a,b,_=self.load();c,d,_=self.load(rows)
        np.testing.assert_array_equal(a['y'],c['y'])
        np.testing.assert_array_equal(b['x_replicates'],d['x_replicates'])

    def test_reference_integral(self):
        self.assertAlmostEqual(integrate([1,10,100],[0,.5,1],['1','100']),.5)
        with self.assertRaises(ValueError):integrate([1,10],[1,0],['.1','10'])

if __name__ == '__main__':
    unittest.main()
