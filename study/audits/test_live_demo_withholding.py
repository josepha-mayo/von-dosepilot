import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from verify_live_demo_withholding import WithholdingVerificationError, verify


ROOT = Path(__file__).resolve().parents[2]
RECEIPT = "evidence/live_demo_withholding_r2_20261004.json"


class LiveDemoWithholdingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        receipt = json.loads((ROOT / RECEIPT).read_text())
        required = {
            "evidence/EVIDENCE_INDEX.json",
            RECEIPT,
            receipt["predecessor"]["path"],
            *receipt["artifact_sha256"],
        }
        for relative in required:
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, target)

    def tearDown(self):
        self.temp.cleanup()

    def mutate_receipt(self, fn):
        path = self.root / RECEIPT
        value = json.loads(path.read_text())
        fn(value)
        path.write_text(json.dumps(value, indent=2) + "\n")
        index_path = self.root / "evidence/EVIDENCE_INDEX.json"
        index = json.loads(index_path.read_text())
        index["live_demo_withholding"]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        index_path.write_text(json.dumps(index, indent=2) + "\n")

    def test_current_passes(self):
        self.assertEqual(verify(self.root)["status"], "PASS")

    def test_rejects_predecessor_tampering(self):
        path = self.root / "evidence/live_demo_withholding_20261004.json"
        path.write_text(path.read_text() + " ")
        with self.assertRaises(WithholdingVerificationError):
            verify(self.root)

    def test_rejects_plan_hash_tampering(self):
        self.mutate_receipt(lambda x: x["trace_contract"].__setitem__("plan_sha256", "0" * 64))
        with self.assertRaises(WithholdingVerificationError):
            verify(self.root)

    def test_rejects_precompletion_measurement_claim(self):
        self.mutate_receipt(lambda x: x["trace_contract"].__setitem__("precompletion_measurement_hash_withheld", False))
        with self.assertRaises(WithholdingVerificationError):
            verify(self.root)

    def test_rejects_baseline_count_inflation(self):
        self.mutate_receipt(lambda x: x["production_browser_verification"].__setitem__("baseline_numeric_outputs", 24))
        with self.assertRaises(WithholdingVerificationError):
            verify(self.root)

    def test_rejects_nonready_deployment(self):
        self.mutate_receipt(lambda x: x["production_deployment"].__setitem__("state", "building"))
        with self.assertRaises(WithholdingVerificationError):
            verify(self.root)

    def test_rejects_app_drift(self):
        with (self.root / "site/app.js").open("a") as handle:
            handle.write("\n// drift\n")
        with self.assertRaises(WithholdingVerificationError):
            verify(self.root)

    def test_rejects_false_signed_claim(self):
        self.mutate_receipt(lambda x: x["limitations"].__setitem__("signed", True))
        with self.assertRaises(WithholdingVerificationError):
            verify(self.root)

    def test_rejects_false_competition_score(self):
        self.mutate_receipt(lambda x: x["claim_boundary"].__setitem__("official_competition_score", 1.0))
        with self.assertRaises(WithholdingVerificationError):
            verify(self.root)


if __name__ == "__main__":
    unittest.main()
