import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from verify_live_demo_withholding import WithholdingVerificationError, verify


ROOT = Path(__file__).resolve().parents[2]
RECEIPT = "evidence/live_demo_withholding_r4_20261004.json"


class LiveDemoWithholdingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        receipt = json.loads((ROOT / RECEIPT).read_text())
        required = {
            "evidence/EVIDENCE_INDEX.json", RECEIPT, receipt["predecessor"]["path"],
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
        path = self.root / "evidence/live_demo_withholding_r3_20261004.json"
        path.write_text(path.read_text() + " ")
        with self.assertRaises(WithholdingVerificationError):
            verify(self.root)

    def test_rejects_syntactically_valid_wrong_baseline_digest(self):
        self.mutate_receipt(lambda x: x["trace_contract"].__setitem__("baseline_result_sha256", "1" * 64))
        with self.assertRaises(WithholdingVerificationError):
            verify(self.root)

    def test_rejects_browser_digest_disagreement(self):
        self.mutate_receipt(lambda x: x["production_browser_verification"].__setitem__("baseline_result_sha256", "2" * 64))
        with self.assertRaises(WithholdingVerificationError):
            verify(self.root)

    def test_rejects_missing_null_semantics_rewrite(self):
        self.mutate_receipt(lambda x: x["production_browser_verification"].__setitem__("missing_measurement_sha256", "WITHHELD"))
        with self.assertRaises(WithholdingVerificationError):
            verify(self.root)

    def test_rejects_false_full_record_claim(self):
        self.mutate_receipt(lambda x: x["local_state_verification"].__setitem__("full_record_inspectable", False))
        with self.assertRaises(WithholdingVerificationError):
            verify(self.root)

    def test_rejects_public_schedule_drift(self):
        with (self.root / "site/frozen_schedule.js").open("a") as handle:
            handle.write("\n// drift\n")
        with self.assertRaises(WithholdingVerificationError):
            verify(self.root)

    def test_rejects_harness_drift(self):
        with (self.root / "site/test_app_state.js").open("a") as handle:
            handle.write("\n// drift\n")
        with self.assertRaises(WithholdingVerificationError):
            verify(self.root)

    def test_rejects_hidden_predecessor_correction(self):
        self.mutate_receipt(lambda x: x["predecessor"].__setitem__("baseline_digest_record_correct", False))
        with self.assertRaises(WithholdingVerificationError):
            verify(self.root)

    def test_rejects_false_downloadable_claim(self):
        self.mutate_receipt(lambda x: x["local_state_verification"].__setitem__("exact_record_downloadable", False))
        with self.assertRaises(WithholdingVerificationError):
            verify(self.root)

    def test_rejects_export_visible_record_mismatch(self):
        self.mutate_receipt(lambda x: x["production_browser_verification"].__setitem__("complete_export_matches_visible_record", False))
        with self.assertRaises(WithholdingVerificationError):
            verify(self.root)

    def test_rejects_raw_reading_export_claim(self):
        self.mutate_receipt(lambda x: x["export_contract"].__setitem__("contains_raw_readings", True))
        with self.assertRaises(WithholdingVerificationError):
            verify(self.root)

    def test_rejects_export_filename_drift(self):
        self.mutate_receipt(lambda x: x["production_browser_verification"].__setitem__("recovery_export_filename", "dosepilot-trace-complete.json"))
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
