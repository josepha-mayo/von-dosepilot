import json,shutil,tempfile,unittest
from pathlib import Path
from verify_budget_upgrade_curve import CurveEvidenceError,verify
ROOT=Path(__file__).resolve().parents[2]
class CurveEvidenceTests(unittest.TestCase):
    def test_current_passes(self):
        self.assertEqual(verify(ROOT)["budget_count"],7)
    def test_false_validation_fails(self):
        with tempfile.TemporaryDirectory() as td:
            r=Path(td);(r/"evidence").mkdir();(r/"study/budget_upgrade_curve").mkdir(parents=True)
            shutil.copy2(ROOT/"evidence/budget_upgrade_curve_20261006.json",r/"evidence/budget_upgrade_curve_20261006.json")
            shutil.copytree(ROOT/"study/budget_upgrade_curve",r/"study/budget_upgrade_curve",dirs_exist_ok=True)
            fr=json.loads((ROOT/"study/budget_upgrade_curve/FREEZE.json").read_text())
            for rel in fr["source_sha256"]:
                src=ROOT/rel;dst=r/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
            j=json.loads((r/"evidence/budget_upgrade_curve_20261006.json").read_text());j["independent_validation"]=True
            (r/"evidence/budget_upgrade_curve_20261006.json").write_text(json.dumps(j))
            with self.assertRaises(CurveEvidenceError):verify(r)
if __name__=="__main__":unittest.main(verbosity=2)
