import json, tempfile, unittest, shutil
from pathlib import Path
from verify_current_successor_grouped_conformal import ReliabilityError, verify

ROOT=Path(__file__).resolve().parents[2]

class ReliabilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        src=ROOT/"evidence/current_successor_grouped_conformal_20261006.json"
        dst=self.root/"evidence/current_successor_grouped_conformal_20261006.json"
        dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(src,dst)
    def tearDown(self): self.tmp.cleanup()
    def data(self):
        p=self.root/"evidence/current_successor_grouped_conformal_20261006.json"
        return p,json.loads(p.read_text(encoding="utf-8"))
    def write(self,j):
        p,_=self.data(); p.write_text(json.dumps(j,indent=2)+"\n",encoding="utf-8")
    def test_current_passes(self):
        self.assertEqual(verify(self.root)["targets_at_or_above_90"],24)
    def test_false_validation_fails(self):
        _,j=self.data(); j["independent_validation"]=True; self.write(j)
        with self.assertRaises(ReliabilityError): verify(self.root)
    def test_coverage_tamper_fails(self):
        _,j=self.data(); j["levels"]["0.90"]["coverage"]=0.99; self.write(j)
        with self.assertRaises(ReliabilityError): verify(self.root)
    def test_patient_rows_claim_fails(self):
        _,j=self.data(); j["patient_level_rows_published"]=True; self.write(j)
        with self.assertRaises(ReliabilityError): verify(self.root)
    def test_radius_tamper_fails(self):
        _,j=self.data(); j["deployment_preparation"]["radii"]["0.90"]["rows"][0]["orientation_A_radius"]=-1; self.write(j)
        with self.assertRaises(ReliabilityError): verify(self.root)

if __name__=="__main__": unittest.main(verbosity=2)
