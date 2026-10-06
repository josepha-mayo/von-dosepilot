import json,shutil,tempfile,unittest
from pathlib import Path
from verify_budget48_two_dose_ablation import BudgetEvidenceError,verify
ROOT=Path(__file__).resolve().parents[2]

class BudgetEvidenceTests(unittest.TestCase):
    def test_current_passes(self):
        self.assertEqual(verify(ROOT)["status"],"PASS")
    def test_false_validation_fails(self):
        with tempfile.TemporaryDirectory() as td:
            r=Path(td); (r/"evidence").mkdir(); (r/"study/budget48_two_dose_ablation").mkdir(parents=True)
            shutil.copy2(ROOT/"evidence/budget48_two_dose_ablation_20261006.json",r/"evidence/budget48_two_dose_ablation_20261006.json")
            shutil.copytree(ROOT/"study/budget48_two_dose_ablation",r/"study/budget48_two_dose_ablation",dirs_exist_ok=True)
            fr=json.loads((ROOT/"study/budget48_two_dose_ablation/FREEZE.json").read_text())
            for rel in fr["source_sha256"]:
                src=ROOT/rel; dst=r/rel; dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,dst)
            j=json.loads((r/"evidence/budget48_two_dose_ablation_20261006.json").read_text()); j["independent_validation"]=True
            (r/"evidence/budget48_two_dose_ablation_20261006.json").write_text(json.dumps(j))
            with self.assertRaises(BudgetEvidenceError): verify(r)

if __name__=="__main__": unittest.main(verbosity=2)
