import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from verify_finalist_rubric_evidence_current import CurrentRubricEvidenceError, verify


ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class CurrentFinalistRubricEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        index = json.loads((ROOT / "evidence/EVIDENCE_INDEX.json").read_text())
        record = index["current_finalist_rubric_evidence"]
        receipt = json.loads((ROOT / record["path"]).read_text())
        predecessor = json.loads((ROOT / receipt["evidence_bindings"]["predecessor"]["path"]).read_text())
        paths = {record["path"], *receipt["artifact_sha256"]}
        paths.update(binding["path"] for binding in receipt["evidence_bindings"].values())
        paths.update(predecessor["artifact_sha256"])
        paths.add(predecessor["current_release_preflight"]["path"])
        for relative in paths:
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, target)
        (self.root / "evidence/EVIDENCE_INDEX.json").write_text(
            json.dumps({"current_finalist_rubric_evidence": record}, indent=2) + "\n"
        )

    def tearDown(self):
        self.temporary.cleanup()

    def state(self):
        index_path = self.root / "evidence/EVIDENCE_INDEX.json"
        index = json.loads(index_path.read_text())
        receipt_path = self.root / index["current_finalist_rubric_evidence"]["path"]
        return index_path, index, receipt_path, json.loads(receipt_path.read_text())

    def write_receipt(self, receipt):
        index_path, index, receipt_path, _ = self.state()
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
        index["current_finalist_rubric_evidence"]["sha256"] = sha(receipt_path)
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
        self.assertEqual(result["weight_sum"], 100)
        self.assertEqual(result["external_routes_resolved"], 5)

    def test_unrehashable_receipt_tamper_fails(self):
        _, _, receipt_path, receipt = self.state()
        receipt["status"] = "FAIL"
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
        with self.assertRaisesRegex(CurrentRubricEvidenceError, "INDEX_RECEIPT_HASH"):
            verify(self.root)

    def test_weight_drift_fails(self):
        _, _, _, receipt = self.state()
        receipt["rubric"]["weights"]["presentation"] = 11
        self.write_receipt(receipt)
        with self.assertRaisesRegex(CurrentRubricEvidenceError, "RUBRIC_WEIGHTS"):
            verify(self.root)

    def test_self_score_fails(self):
        _, _, _, receipt = self.state()
        receipt["rubric"]["combined_self_score"] = 99
        self.write_receipt(receipt)
        with self.assertRaisesRegex(CurrentRubricEvidenceError, "NO_SELF_SCORE"):
            verify(self.root)

    def test_predecessor_rebinding_fails(self):
        _, _, _, receipt = self.state()
        receipt["evidence_bindings"]["predecessor"]["sha256"] = "0" * 64
        self.write_receipt(receipt)
        with self.assertRaisesRegex(CurrentRubricEvidenceError, "EVIDENCE_BINDINGS"):
            verify(self.root)

    def test_nested_selection_drift_fails(self):
        self.mutate_binding("nested_bandwidth_selection", lambda value: value["selection_counts"].__setitem__("0.7", 4))
        with self.assertRaisesRegex(CurrentRubricEvidenceError, "EVIDENCE_BINDINGS"):
            verify(self.root)

    def test_nested_validation_promotion_fails(self):
        self.mutate_binding("nested_bandwidth_selection", lambda value: value["claim_boundary"].__setitem__("independent_validation", True))
        with self.assertRaisesRegex(CurrentRubricEvidenceError, "EVIDENCE_BINDINGS"):
            verify(self.root)

    def test_control_gate_promotion_fails(self):
        self.mutate_binding("cooptimized_control", lambda value: value["candidate_vs_bandwidth07"].__setitem__("all_gates_passed", True))
        with self.assertRaisesRegex(CurrentRubricEvidenceError, "EVIDENCE_BINDINGS"):
            verify(self.root)

    def test_clean_package_count_inflation_fails(self):
        self.mutate_binding("clean_finalist_package", lambda value: value["execution"].__setitem__("package_checks", 9))
        with self.assertRaisesRegex(CurrentRubricEvidenceError, "EVIDENCE_BINDINGS"):
            verify(self.root)

    def test_route_count_inflation_fails(self):
        self.mutate_binding("external_routes", lambda value: value["verification"].__setitem__("routes_resolved", 6))
        with self.assertRaisesRegex(CurrentRubricEvidenceError, "EVIDENCE_BINDINGS"):
            verify(self.root)

    def test_false_raw_download_claim_fails(self):
        self.mutate_binding("public_report_render", lambda value: value["claim_boundary"].__setitem__("raw_download_success_verified", True))
        with self.assertRaisesRegex(CurrentRubricEvidenceError, "EVIDENCE_BINDINGS"):
            verify(self.root)

    def test_report_page_drift_fails(self):
        self.mutate_binding("current_report", lambda value: value["pdf"].__setitem__("pages", 11))
        with self.assertRaisesRegex(CurrentRubricEvidenceError, "EVIDENCE_BINDINGS"):
            verify(self.root)

    def test_claim_boundary_promotion_fails(self):
        _, _, _, receipt = self.state()
        receipt["claim_boundary"]["finalist_status_claimed"] = True
        self.write_receipt(receipt)
        with self.assertRaisesRegex(CurrentRubricEvidenceError, "CLAIM_BOUNDARY"):
            verify(self.root)

    def test_artifact_drift_fails(self):
        _, _, _, receipt = self.state()
        relative = next(iter(receipt["artifact_sha256"]))
        path = self.root / relative
        path.write_bytes(path.read_bytes() + b"\n")
        with self.assertRaisesRegex(CurrentRubricEvidenceError, "ARTIFACT_HASH"):
            verify(self.root)


if __name__ == "__main__":
    unittest.main(verbosity=2)

