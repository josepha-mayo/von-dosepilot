import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from verify_finalist_rubric_evidence_current_scientific_successor import (
    CurrentScientificSuccessorRubricEvidenceError,
    verify,
)


ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class CurrentScientificSuccessorRubricEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        index = json.loads((ROOT / "evidence/EVIDENCE_INDEX.json").read_text())
        record = index["current_scientific_successor_finalist_rubric_evidence"]
        receipt = json.loads((ROOT / record["path"]).read_text())
        scientific = json.loads((ROOT / receipt["evidence_bindings"]["current_scientific_successor"]["path"]).read_text())
        paths = {
            record["path"],
            *[binding["path"] for binding in receipt["evidence_bindings"].values()],
            *receipt["artifact_sha256"],
            *[binding["path"] for binding in scientific["evidence_bindings"].values()],
            *[artifact["path"] for artifact in scientific["presentation_artifacts"].values()],
            *scientific["artifact_sha256"],
        }
        for relative in paths:
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, target)
        index_path = self.root / "evidence/EVIDENCE_INDEX.json"
        index_path.parent.mkdir(parents=True, exist_ok=True)
        index_path.write_text(json.dumps({
            "current_scientific_successor_finalist_rubric_evidence": record,
            "current_scientific_successor_evidence": index["current_scientific_successor_evidence"],
        }, indent=2) + "\n")

    def tearDown(self):
        self.temporary.cleanup()

    def state(self):
        index_path = self.root / "evidence/EVIDENCE_INDEX.json"
        index = json.loads(index_path.read_text())
        receipt_path = self.root / index["current_scientific_successor_finalist_rubric_evidence"]["path"]
        return index_path, index, receipt_path, json.loads(receipt_path.read_text())

    def write_receipt(self, receipt):
        index_path, index, receipt_path, _ = self.state()
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
        index["current_scientific_successor_finalist_rubric_evidence"]["sha256"] = sha(receipt_path)
        index_path.write_text(json.dumps(index, indent=2) + "\n")

    def test_current_state_passes(self):
        self.assertEqual(verify(self.root)["candidate_mse"], 0.001042745722096212)

    def test_unrehashable_receipt_tamper_fails(self):
        _, _, receipt_path, receipt = self.state()
        receipt["status"] = "FAIL"
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
        with self.assertRaisesRegex(CurrentScientificSuccessorRubricEvidenceError, "INDEX_RECEIPT_HASH"):
            verify(self.root)

    def test_predecessor_drift_fails(self):
        _, _, _, receipt = self.state()
        path = self.root / receipt["evidence_bindings"]["predecessor"]["path"]
        path.write_bytes(path.read_bytes() + b"\n")
        with self.assertRaisesRegex(CurrentScientificSuccessorRubricEvidenceError, "BINDING_HASH"):
            verify(self.root)

    def test_scientific_map_drift_fails(self):
        _, _, _, receipt = self.state()
        path = self.root / receipt["evidence_bindings"]["current_scientific_successor"]["path"]
        path.write_bytes(path.read_bytes() + b"\n")
        with self.assertRaisesRegex(CurrentScientificSuccessorRubricEvidenceError, "BINDING_HASH"):
            verify(self.root)

    def test_false_independent_validation_fails(self):
        _, _, _, receipt = self.state()
        receipt["limitations"]["independent_validation"] = True
        self.write_receipt(receipt)
        with self.assertRaisesRegex(CurrentScientificSuccessorRubricEvidenceError, "LIMITATION"):
            verify(self.root)

    def test_false_bootstrap_recomputation_fails(self):
        _, _, _, receipt = self.state()
        receipt["limitations"]["bootstrap_independently_recomputed"] = True
        self.write_receipt(receipt)
        with self.assertRaisesRegex(CurrentScientificSuccessorRubricEvidenceError, "LIMITATION"):
            verify(self.root)

    def test_false_windows_receipt_fails(self):
        _, _, _, receipt = self.state()
        receipt["limitations"]["windows_replay_machine_receipt_public"] = True
        self.write_receipt(receipt)
        with self.assertRaisesRegex(CurrentScientificSuccessorRubricEvidenceError, "LIMITATION"):
            verify(self.root)

    def test_false_operational_replacement_fails(self):
        _, _, _, receipt = self.state()
        receipt["scientific_successor"]["operational_demo_baseline_replaced"] = True
        self.write_receipt(receipt)
        with self.assertRaisesRegex(CurrentScientificSuccessorRubricEvidenceError, "SUCCESSOR_NO_OPERATIONAL_REPLACEMENT"):
            verify(self.root)

    def test_false_self_score_fails(self):
        _, _, _, receipt = self.state()
        receipt["rubric"]["combined_self_score"] = 100
        self.write_receipt(receipt)
        with self.assertRaisesRegex(CurrentScientificSuccessorRubricEvidenceError, "NO_SELF_SCORE"):
            verify(self.root)

    def test_artifact_drift_fails(self):
        _, _, _, receipt = self.state()
        relative = next(iter(receipt["artifact_sha256"]))
        path = self.root / relative
        path.write_bytes(path.read_bytes() + b"\n")
        with self.assertRaisesRegex(CurrentScientificSuccessorRubricEvidenceError, "ARTIFACT_HASH"):
            verify(self.root)


if __name__ == "__main__":
    unittest.main(verbosity=2)
