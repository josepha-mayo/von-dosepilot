[Reading 61 lines from start (total: 61 lines, 0 remaining)]

import copy,json,shutil,tempfile,unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from verify_target_definitions import verify

class TargetDefinitionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=Path(__file__).resolve().parents[2]
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        for d in ('evidence','study','docs'):(self.root/d).mkdir()
        files=[
          'evidence/target_definitions_20261003.json',
          'evidence/frozen_bandwidth_orientation_A_plan_20261003.json',
          'evidence/frozen_bandwidth_orientation_B_plan_20261003.json',
          'evidence/bandwidth_successor_20261003.json',
          'evidence/frozen_ooc_execution_schedule_20261003.json',
          'study/TRAIN_CATALOG.json','docs/TARGET_DEFINITIONS.md']
        for rel in files:
            shutil.copy2(self.source/rel,self.root/rel)
    def tearDown(self):self.tmp.cleanup()
    def load(self,rel):
        p=self.root/rel;return p,json.loads(p.read_text())
    def save(self,p,v):p.write_text(json.dumps(v,indent=2)+'\n')
    def test_current_contract_passes(self):
        r=verify(self.root)
        self.assertEqual(r['status'],'PASS');self.assertEqual(r['targets'],24)
        self.assertEqual(r['full_source_treatment_measurements_two_plates'],416)
        self.assertEqual(r['selected_measurements_per_deployment'],64)
    def test_quadrature_tamper_fails(self):
        p,j=self.load('evidence/target_definitions_20261003.json')
        j['definitions'][0]['nonzero_reference_quadrature'][0]['weight']+=.001
        self.save(p,j)
        with self.assertRaisesRegex(ValueError,'QUADRATURE'):verify(self.root)
    def test_full_grid_tamper_fails(self):
        p,j=self.load('evidence/target_definitions_20261003.json')
        j['definitions'][2]['full_source_dose_grid_nM'][0]='0.11'
        self.save(p,j)
        with self.assertRaisesRegex(ValueError,'QUADRATURE|BOUNDS|GRID|DOC_ROW'):verify(self.root)
    def test_selected_input_tamper_fails(self):
        p,j=self.load('evidence/target_definitions_20261003.json')
        j['definitions'][0]['selected_predictor_inputs'][0]['dose_nM']='999'
        self.save(p,j)
        with self.assertRaisesRegex(ValueError,'SELECTED_INPUTS'):verify(self.root)
    def test_document_cannot_hide_endpoint_scope(self):
        p=self.root/'docs/TARGET_DEFINITIONS.md'
        p.write_text(p.read_text().replace('not IC50','not half-maximal concentration'))
        with self.assertRaisesRegex(ValueError,'DOC_SCOPE'):verify(self.root)
    def test_ab_plan_cannot_be_made_same_plate(self):
        p,j=self.load('evidence/frozen_bandwidth_orientation_B_plan_20261003.json')
        j['measurements'][0]['plate']=json.loads((self.root/'evidence/frozen_bandwidth_orientation_A_plan_20261003.json').read_text())['measurements'][0]['plate']
        self.save(p,j)
        # Hash binding fails even before complementarity.
        with self.assertRaisesRegex(ValueError,'PLAN_B_HASH'):verify(self.root)
    def test_false_population_count_fails(self):
        p,j=self.load('evidence/target_definitions_20261003.json');j['samples']=120;self.save(p,j)
        with self.assertRaisesRegex(ValueError,'POPULATION'):verify(self.root)

if __name__=='__main__':unittest.main(verbosity=2)
