import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from verify_finalist_rubric_evidence_current_package import (
    CurrentPackageRubricEvidenceError,
    verify,
)


ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class CurrentPackageFinalistRubricEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        index = json.loads((ROOT / "evidence/EVIDENCE_INDEX.json").read_text())
        record = index["current_package_finalist_rubric_evidence"]
        receipt = json.loads((ROOT / record["path"]).read_text())
        predecessor = json.loads((ROOT / receipt["evidence_bindings"]["predecessor"]["path"]).read_text())
        predecessor2 = json.loads((ROOT / predecessor["evidence_bindings"]["predecessor"]["path"]).read_text())
        historical = json.loads((ROOT / predecessor2["evidence_bindings"]["predecessor"]["path"]).read_text())
        paths = {record["path"], *receipt["artifact_sha256"]}
        paths.update(binding["path"] for binding in receipt["evidence_bindings"].values())
        paths.update(predecessor["artifact_sha256"])
        paths.update(binding["path"] for binding in predecessor["evidence_bindings"].values())
        paths.update(predecessor2["artifact_sha256"])
        paths.update(binding["path"] for binding in predecessor2["evidence_bindings"].values())
        paths.update(historical["artifact_sha256"])
        paths.add(historical["current_release_preflight"]["path"])
        for relative in paths:
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, target)
        (self.root / "evidence/EVIDENCE_INDEX.json").write_text(
            json.dumps({"current_package_finalist_rubric_evidence": record}, indent=2) + "\n"
        )

    def tearDown(self):
        self.temporary.cleanup()

    def state(self):
        index_path = self.root / "evidence/EVIDENCE_INDEX.json"
        index = json.loads(index_path.read_text())
        receipt_path = self.root / index["current_package_finalist_rubric_evidence"]["path"]
        return index_path, index, receipt_path, json.loads(receipt_path.read_text())

    def write_receipt(self, receipt):
        index_path, index, receipt_path, _ = self.state()
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
        index["current_package_finalist_rubric_evidence"]["sha256"] = sha(receipt_path)
        index_path.write_text(json.dumps(index, indent=2) + "\n")

    def mutate_binding(self, name, mutation):
        _, _, _, receipt = self.state()
        binding = receipt["evidence_bindings"][name]
        path = self.root / binding["path"]
        value = json.loads(path.read_text())
        mutation(value)
        path.write_text(json.dumps(value, indent=2) + "\n")
        binding["sha256"] = sha(path)
        self.write_receipt(receipt)

    def test_current_state_passes(self):
        result = verify(self.root)
        self.assertEqual(result["criteria"], 5)
        self.assertEqual(result["clean_current_package_checks"], 8)
        self.assertTrue(result["current_rubric_successor_checked"])

    def test_unrehashable_receipt_tamper_fails(self):
        _, _, receipt_path, receipt = self.state()
        receipt["status"] = "FAIL"
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
        with self.assertRaisesRegex(CurrentPackageRubricEvidenceError, "INDEX_RECEIPT_HASH"):
            verify(self.root)

    def test_predecessor_rebinding_fails(self):
        _, _, _, receipt = self.state()
        receipt["evidence_bindings"]["predecessor"]["sha256"] = "0" * 64
        self.write_receipt(receipt)
        with self.assertRaisesRegex(CurrentPackageRubricEvidenceError, "EVIDENCE_BINDINGS"):
            verify(self.root)

    def test_package_count_inflation_fails(self):
        self.mutate_binding("current_package_preflight", lambda value: value.__setitem__("package_check_count", 9))
        with self.assertRaisesRegex(CurrentPackageRubricEvidenceError, "EVIDENCE_BINDINGS"):
            verify(self.root)

    def test_package_rubric_fallback_fails(self):
        self.mutate_binding("current_package_preflight", lambda value: value.__setitem__("current_rubric_successor_checked", False))
        with self.assertRaisesRegex(CurrentPackageRubricEvidenceError, "EVIDENCE_BINDINGS"):
            verify(self.root)

    def test_clean_cache_disclosure_fails(self):
        self.mutate_binding("clean_current_package", lambda value: value["environment"].__setitem__("pip_artifacts_resolved_from_cache", False))
        with self.assertRaisesRegex(CurrentPackageRubricEvidenceError, "EVIDENCE_BINDINGS"):
            verify(self.root)

    def test_clean_clone_promotion_fails(self):
        self.mutate_binding("clean_current_package", lambda value: value["source"].__setitem__("fresh_public_clone", True))
        with self.assertRaisesRegex(CurrentPackageRubricEvidenceError, "EVIDENCE_BINDINGS"):
            verify(self.root)

    def test_clean_rubric_fallback_fails(self):
        self.mutate_binding("clean_current_package", lambda value: value["execution"].__setitem__("current_rubric_successor_checked", False))
        with self.assertRaisesRegex(CurrentPackageRubricEvidenceError, "EVIDENCE_BINDINGS"):
            verify(self.root)

    def test_claim_boundary_promotion_fails(self):
        _, _, _, receipt = self.state()
        receipt["claim_boundary"]["independent_validation_created"] = True
        self.write_receipt(receipt)
        with self.assertRaisesRegex(CurrentPackageRubricEvidenceError, "CLAIM_BOUNDARY"):
            verify(self.root)

    def test_artifact_drift_fails(self):
        _, _, _, receipt = self.state()
        relative = next(iter(receipt["artifact_sha256"]))
        path = self.root / relative
        path.write_bytes(path.read_bytes() + b"\n")
        with self.assertRaisesRegex(CurrentPackageRubricEvidenceError, "ARTIFACT_HASH"):
            verify(self.root)


if __name__ == "__main__":
    unittest.main(verbosity=2)
