import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from verify_current_scientific_successor_evidence import (
    CurrentScientificSuccessorEvidenceError,
    verify,
)


ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class CurrentScientificSuccessorEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        index = json.loads((ROOT / "evidence/EVIDENCE_INDEX.json").read_text())
        record = index["current_scientific_successor_evidence"]
        receipt = json.loads((ROOT / record["path"]).read_text())
        paths = {
            record["path"],
            *[binding["path"] for binding in receipt["evidence_bindings"].values()],
            *[artifact["path"] for artifact in receipt["presentation_artifacts"].values()],
            *receipt["artifact_sha256"],
        }
        for relative in paths:
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, target)
        index_path = self.root / "evidence/EVIDENCE_INDEX.json"
        index_path.parent.mkdir(parents=True, exist_ok=True)
        index_path.write_text(json.dumps({"current_scientific_successor_evidence": record}, indent=2) + "\n")

    def tearDown(self):
        self.temporary.cleanup()

    def state(self):
        index_path = self.root / "evidence/EVIDENCE_INDEX.json"
        index = json.loads(index_path.read_text())
        receipt_path = self.root / index["current_scientific_successor_evidence"]["path"]
        return index_path, index, receipt_path, json.loads(receipt_path.read_text())

    def write_receipt(self, receipt):
        index_path, index, receipt_path, _ = self.state()
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
        index["current_scientific_successor_evidence"]["sha256"] = sha(receipt_path)
        index_path.write_text(json.dumps(index, indent=2) + "\n")

    def test_current_state_passes(self):
        self.assertEqual(verify(self.root)["target_losses"], 5)

    def test_unrehashable_receipt_tamper_fails(self):
        _, _, receipt_path, receipt = self.state()
        receipt["status"] = "FAIL"
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
        with self.assertRaisesRegex(CurrentScientificSuccessorEvidenceError, "INDEX_RECEIPT_HASH"):
            verify(self.root)

    def test_candidate_drift_fails(self):
        _, _, _, receipt = self.state()
        path = self.root / receipt["evidence_bindings"]["candidate"]["path"]
        path.write_bytes(path.read_bytes() + b"\n")
        with self.assertRaisesRegex(CurrentScientificSuccessorEvidenceError, "BINDING_HASH"):
            verify(self.root)

    def test_candidate_hash_transcription_fallback_fails(self):
        _, _, _, receipt = self.state()
        receipt["evidence_bindings"]["candidate"]["sha256"] = "c3548e944a380432e17e84d442bd8fa2eb0f3738ad832bb3d8035b44a667f363"
        self.write_receipt(receipt)
        with self.assertRaisesRegex(CurrentScientificSuccessorEvidenceError, "EVIDENCE_BINDINGS"):
            verify(self.root)

    def test_bootstrap_drift_fails(self):
        _, _, _, receipt = self.state()
        path = self.root / receipt["evidence_bindings"]["descriptive_bootstrap"]["path"]
        path.write_bytes(path.read_bytes() + b"\n")
        with self.assertRaisesRegex(CurrentScientificSuccessorEvidenceError, "BINDING_HASH"):
            verify(self.root)

    def test_target_json_drift_fails(self):
        _, _, _, receipt = self.state()
        path = self.root / receipt["evidence_bindings"]["target_deltas_json"]["path"]
        path.write_bytes(path.read_bytes() + b"\n")
        with self.assertRaisesRegex(CurrentScientificSuccessorEvidenceError, "BINDING_HASH"):
            verify(self.root)

    def test_target_csv_drift_fails(self):
        _, _, _, receipt = self.state()
        path = self.root / receipt["evidence_bindings"]["target_deltas_csv"]["path"]
        path.write_bytes(path.read_bytes() + b"\n")
        with self.assertRaisesRegex(CurrentScientificSuccessorEvidenceError, "BINDING_HASH"):
            verify(self.root)

    def test_false_independent_validation_fails(self):
        _, _, _, receipt = self.state()
        receipt["claim_boundary"]["independent_validation_created"] = True
        self.write_receipt(receipt)
        with self.assertRaisesRegex(CurrentScientificSuccessorEvidenceError, "CLAIM_BOUNDARY"):
            verify(self.root)

    def test_false_bootstrap_recomputation_fails(self):
        _, _, _, receipt = self.state()
        receipt["claim_boundary"]["bootstrap_independently_recomputed"] = True
        self.write_receipt(receipt)
        with self.assertRaisesRegex(CurrentScientificSuccessorEvidenceError, "CLAIM_BOUNDARY"):
            verify(self.root)

    def test_false_windows_replay_receipt_fails(self):
        _, _, _, receipt = self.state()
        receipt["claim_boundary"]["windows_replay_machine_receipt_public"] = True
        self.write_receipt(receipt)
        with self.assertRaisesRegex(CurrentScientificSuccessorEvidenceError, "CLAIM_BOUNDARY"):
            verify(self.root)

    def test_false_protected_access_fails(self):
        _, _, _, receipt = self.state()
        receipt["claim_boundary"]["protected22_access"] = True
        self.write_receipt(receipt)
        with self.assertRaisesRegex(CurrentScientificSuccessorEvidenceError, "CLAIM_BOUNDARY"):
            verify(self.root)

    def test_presentation_drift_fails(self):
        _, _, _, receipt = self.state()
        path = self.root / receipt["presentation_artifacts"]["visual"]["path"]
        path.write_bytes(path.read_bytes() + b"\n")
        with self.assertRaisesRegex(CurrentScientificSuccessorEvidenceError, "PRESENTATION_HASH"):
            verify(self.root)

    def test_artifact_drift_fails(self):
        _, _, _, receipt = self.state()
        relative = next(iter(receipt["artifact_sha256"]))
        path = self.root / relative
        path.write_bytes(path.read_bytes() + b"\n")
        with self.assertRaisesRegex(CurrentScientificSuccessorEvidenceError, "ARTIFACT_HASH"):
            verify(self.root)


if __name__ == "__main__":
    unittest.main(verbosity=2)
