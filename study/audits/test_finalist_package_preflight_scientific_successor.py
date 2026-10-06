import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from verify_finalist_package_preflight_scientific_successor import (
    ScientificSuccessorFinalistPackagePreflightError,
    verify,
)


ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class ScientificSuccessorFinalistPackagePreflightTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        index = json.loads((ROOT / "evidence/EVIDENCE_INDEX.json").read_text())
        record = index["current_scientific_successor_finalist_package_preflight"]
        receipt = json.loads((ROOT / record["path"]).read_text())
        paths = [
            record["path"], receipt["predecessor"]["path"],
            receipt["current_scientific_successor_rubric"]["path"], *receipt["artifact_sha256"],
        ]
        for relative in paths:
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, target)
        index_path = self.root / "evidence/EVIDENCE_INDEX.json"
        index_path.write_text(json.dumps({"current_scientific_successor_finalist_package_preflight": record}, indent=2) + "\n")

    def tearDown(self):
        self.temporary.cleanup()

    def state(self):
        index_path = self.root / "evidence/EVIDENCE_INDEX.json"
        index = json.loads(index_path.read_text())
        receipt_path = self.root / index["current_scientific_successor_finalist_package_preflight"]["path"]
        return index_path, index, receipt_path, json.loads(receipt_path.read_text())

    def write_receipt(self, receipt):
        index_path, index, receipt_path, _ = self.state()
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
        index["current_scientific_successor_finalist_package_preflight"]["sha256"] = sha(receipt_path)
        index_path.write_text(json.dumps(index, indent=2) + "\n")

    def test_current_state_passes(self):
        self.assertEqual(verify(self.root)["package_checks"], 8)

    def test_receipt_tamper_fails(self):
        _, _, receipt_path, receipt = self.state()
        receipt["status"] = "FAIL"
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
        with self.assertRaisesRegex(ScientificSuccessorFinalistPackagePreflightError, "INDEX_RECEIPT_HASH"):
            verify(self.root)

    def test_inflated_test_count_fails(self):
        _, _, _, receipt = self.state()
        receipt["canonical_orchestrated_test_count"] = 174
        self.write_receipt(receipt)
        with self.assertRaisesRegex(ScientificSuccessorFinalistPackagePreflightError, "CANONICAL_TEST_COUNT"):
            verify(self.root)

    def test_r6_fallback_fails(self):
        _, _, _, receipt = self.state()
        receipt["checks"][-1]["name"] = "current_report_retrieval_finalist_rubric_evidence"
        self.write_receipt(receipt)
        with self.assertRaisesRegex(ScientificSuccessorFinalistPackagePreflightError, "CHECK_ORDER"):
            verify(self.root)

    def test_removed_check_fails(self):
        _, _, _, receipt = self.state()
        receipt["checks"].pop()
        self.write_receipt(receipt)
        with self.assertRaisesRegex(ScientificSuccessorFinalistPackagePreflightError, "CHECK_ORDER"):
            verify(self.root)

    def test_rubric_drift_fails(self):
        _, _, _, receipt = self.state()
        path = self.root / receipt["current_scientific_successor_rubric"]["path"]
        path.write_bytes(path.read_bytes() + b"\n")
        with self.assertRaisesRegex(ScientificSuccessorFinalistPackagePreflightError, "SCIENTIFIC_RUBRIC_HASH"):
            verify(self.root)

    def test_false_independent_validation_fails(self):
        _, _, _, receipt = self.state()
        receipt["independent_validation_created"] = True
        self.write_receipt(receipt)
        with self.assertRaisesRegex(ScientificSuccessorFinalistPackagePreflightError, "BOUNDARY_INDEPENDENT"):
            verify(self.root)

    def test_false_operational_replacement_fails(self):
        _, _, _, receipt = self.state()
        receipt["operational_demo_baseline_replaced"] = True
        self.write_receipt(receipt)
        with self.assertRaisesRegex(ScientificSuccessorFinalistPackagePreflightError, "RECEIPT_NO_OPERATIONAL_REPLACEMENT"):
            verify(self.root)

    def test_false_kaggle_change_fails(self):
        _, _, _, receipt = self.state()
        receipt["accepted_kaggle_entry_changed"] = True
        self.write_receipt(receipt)
        with self.assertRaisesRegex(ScientificSuccessorFinalistPackagePreflightError, "BOUNDARY_ACCEPTED_KAGGLE"):
            verify(self.root)

    def test_artifact_drift_fails(self):
        _, _, _, receipt = self.state()
        relative = next(iter(receipt["artifact_sha256"]))
        path = self.root / relative
        path.write_bytes(path.read_bytes() + b"\n")
        with self.assertRaisesRegex(ScientificSuccessorFinalistPackagePreflightError, "ARTIFACT_HASH"):
            verify(self.root)


if __name__ == "__main__":
    unittest.main(verbosity=2)
