import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from verify_finalist_rubric_evidence_current_scientific_reliability import (
    CurrentScientificReliabilityRubricEvidenceError,
    verify,
)


ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class CurrentScientificReliabilityRubricEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        index = json.loads((ROOT / "evidence/EVIDENCE_INDEX.json").read_text())
        record = index["current_scientific_reliability_finalist_rubric_evidence"]
        receipt = json.loads((ROOT / record["path"]).read_text())
        paths = {record["path"], *receipt["artifact_sha256"]}
        paths.update(binding["path"] for binding in receipt["evidence_bindings"].values())
        predecessor = json.loads((ROOT / receipt["evidence_bindings"]["predecessor"]["path"]).read_text())
        paths.update(predecessor["artifact_sha256"])
        paths.update(binding["path"] for binding in predecessor["evidence_bindings"].values())
        scientific = json.loads((ROOT / predecessor["evidence_bindings"]["current_scientific_successor"]["path"]).read_text())
        paths.update(binding["path"] for binding in scientific["evidence_bindings"].values())
        paths.update(artifact["path"] for artifact in scientific["presentation_artifacts"].values())
        paths.update(scientific["artifact_sha256"])
        clean = json.loads((ROOT / receipt["evidence_bindings"]["clean_scientific_package_execution"]["path"]).read_text())
        paths.add(clean["predecessor"]["path"])
        paths.update(clean["requirements"])
        paths.update(clean["artifact_sha256"])
        for relative in paths:
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, target)
        subset = {
            key: index[key] for key in (
                "current_scientific_reliability_finalist_rubric_evidence",
                "current_scientific_successor_finalist_rubric_evidence",
                "current_scientific_successor_evidence",
                "clean_scientific_successor_finalist_package_execution",
            )
        }
        path = self.root / "evidence/EVIDENCE_INDEX.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(subset, indent=2) + "\n")

    def tearDown(self):
        self.temporary.cleanup()

    def state(self):
        path = self.root / "evidence/EVIDENCE_INDEX.json"
        index = json.loads(path.read_text())
        receipt_path = self.root / index["current_scientific_reliability_finalist_rubric_evidence"]["path"]
        return path, index, receipt_path, json.loads(receipt_path.read_text())

    def write_receipt(self, receipt):
        path, index, receipt_path, _ = self.state()
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
        index["current_scientific_reliability_finalist_rubric_evidence"]["sha256"] = sha(receipt_path)
        path.write_text(json.dumps(index, indent=2) + "\n")

    def test_current_state_passes(self):
        self.assertEqual(verify(self.root)["coverage_90"], 0.9194915254237288)

    def test_unrehashable_receipt_tamper_fails(self):
        _, _, path, receipt = self.state()
        receipt["status"] = "FAIL"
        path.write_text(json.dumps(receipt, indent=2) + "\n")
        with self.assertRaisesRegex(CurrentScientificReliabilityRubricEvidenceError, "INDEX_RECEIPT_HASH"):
            verify(self.root)

    def test_predecessor_drift_fails(self):
        _, _, _, receipt = self.state()
        path = self.root / receipt["evidence_bindings"]["predecessor"]["path"]
        path.write_bytes(path.read_bytes() + b"\n")
        with self.assertRaisesRegex(CurrentScientificReliabilityRubricEvidenceError, "BINDING_HASH"):
            verify(self.root)

    def test_reliability_drift_fails(self):
        _, _, _, receipt = self.state()
        path = self.root / receipt["evidence_bindings"]["grouped_reliability"]["path"]
        path.write_bytes(path.read_bytes() + b"\n")
        with self.assertRaisesRegex(CurrentScientificReliabilityRubricEvidenceError, "BINDING_HASH"):
            verify(self.root)

    def test_clean_execution_drift_fails(self):
        _, _, _, receipt = self.state()
        path = self.root / receipt["evidence_bindings"]["clean_scientific_package_execution"]["path"]
        path.write_bytes(path.read_bytes() + b"\n")
        with self.assertRaisesRegex(CurrentScientificReliabilityRubricEvidenceError, "BINDING_HASH"):
            verify(self.root)

    def test_false_selection_adjustment_fails(self):
        _, _, _, receipt = self.state()
        receipt["limitations"]["grouped_reliability_selection_adjusted"] = True
        self.write_receipt(receipt)
        with self.assertRaisesRegex(CurrentScientificReliabilityRubricEvidenceError, "LIMITATION"):
            verify(self.root)

    def test_false_independent_validation_fails(self):
        _, _, _, receipt = self.state()
        receipt["limitations"]["independent_validation"] = True
        self.write_receipt(receipt)
        with self.assertRaisesRegex(CurrentScientificReliabilityRubricEvidenceError, "LIMITATION"):
            verify(self.root)

    def test_false_clean_machine_claim_fails(self):
        _, _, _, receipt = self.state()
        receipt["limitations"]["clean_new_machine_certification"] = True
        self.write_receipt(receipt)
        with self.assertRaisesRegex(CurrentScientificReliabilityRubricEvidenceError, "LIMITATION"):
            verify(self.root)

    def test_false_operational_replacement_fails(self):
        _, _, _, receipt = self.state()
        receipt["scientific_reliability"]["operational_demo_baseline_replaced"] = True
        self.write_receipt(receipt)
        with self.assertRaisesRegex(CurrentScientificReliabilityRubricEvidenceError, "NO_OPERATIONAL_REPLACEMENT"):
            verify(self.root)

    def test_false_self_score_fails(self):
        _, _, _, receipt = self.state()
        receipt["rubric"]["combined_self_score"] = 100
        self.write_receipt(receipt)
        with self.assertRaisesRegex(CurrentScientificReliabilityRubricEvidenceError, "NO_SELF_SCORE"):
            verify(self.root)

    def test_artifact_drift_fails(self):
        _, _, _, receipt = self.state()
        path = self.root / next(iter(receipt["artifact_sha256"]))
        path.write_bytes(path.read_bytes() + b"\n")
        with self.assertRaisesRegex(CurrentScientificReliabilityRubricEvidenceError, "ARTIFACT_HASH"):
            verify(self.root)


if __name__ == "__main__":
    unittest.main(verbosity=2)
