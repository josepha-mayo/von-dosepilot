import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_finalist_rubric_evidence import RubricEvidenceError, verify


class FinalistRubricEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path(__file__).resolve().parents[2]

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        receipt_path = self.source / "evidence/finalist_rubric_evidence_20261004.json"
        receipt = json.loads(receipt_path.read_text())
        paths = set(receipt["artifact_sha256"])
        paths.add("evidence/finalist_rubric_evidence_20261004.json")
        paths.add(receipt["current_release_preflight"]["path"])
        for relative in paths:
            destination = self.root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.source / relative, destination)

    def tearDown(self):
        self.tmp.cleanup()

    def mutate_receipt(self, mutation):
        path = self.root / "evidence/finalist_rubric_evidence_20261004.json"
        value = json.loads(path.read_text())
        mutation(value)
        path.write_text(json.dumps(value, indent=2) + "\n")

    def mutate_json(self, relative, mutation):
        path = self.root / relative
        value = json.loads(path.read_text())
        mutation(value)
        path.write_text(json.dumps(value, indent=2) + "\n")
        receipt_path = self.root / "evidence/finalist_rubric_evidence_20261004.json"
        receipt = json.loads(receipt_path.read_text())
        import hashlib
        receipt["artifact_sha256"][relative] = hashlib.sha256(path.read_bytes()).hexdigest()
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")

    def test_current_state_passes(self):
        result = verify(self.root)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["criteria"], 5)
        self.assertEqual(result["weight_sum"], 100)
        self.assertEqual(result["treatment_measurements"], 64)
        self.assertEqual(result["outputs"], 24)
        self.assertEqual(result["protected22_primary"], "NOT_ESTIMABLE")
        self.assertIsNone(result["official_competition_score"])

    def test_weight_drift_fails(self):
        self.mutate_receipt(lambda value: value["rubric"]["weights"].__setitem__("presentation", 11))
        with self.assertRaisesRegex(RubricEvidenceError, "RUBRIC_WEIGHTS"):
            verify(self.root)

    def test_self_score_fails(self):
        self.mutate_receipt(lambda value: value["rubric"].__setitem__("combined_self_score", 99))
        with self.assertRaisesRegex(RubricEvidenceError, "NO_SELF_SCORE"):
            verify(self.root)

    def test_artifact_tamper_fails(self):
        path = self.root / "docs/FINALIST_RUBRIC_EVIDENCE.md"
        path.write_text(path.read_text() + "tamper\n")
        with self.assertRaisesRegex(RubricEvidenceError, "ARTIFACT_HASH"):
            verify(self.root)

    def test_budget_inflation_fails(self):
        self.mutate_json(
            "evidence/target_definitions_release_20261003.json",
            lambda value: value["measurement_accounting"].__setitem__("selected_measurements_per_deployment", 63),
        )
        with self.assertRaisesRegex(RubricEvidenceError, "SELECTED_MEASUREMENTS"):
            verify(self.root)

    def test_incumbent_metric_drift_fails(self):
        self.mutate_json(
            "evidence/bandwidth_successor_20261003.json",
            lambda value: value["metrics"]["bandwidth07"].__setitem__("mse", 0.0),
        )
        with self.assertRaisesRegex(RubricEvidenceError, "INCUMBENT_MSE"):
            verify(self.root)

    def test_independent_validation_promotion_fails(self):
        self.mutate_json(
            "evidence/bandwidth_successor_20261003.json",
            lambda value: value.__setitem__("independent_validation", True),
        )
        with self.assertRaisesRegex(RubricEvidenceError, "NO_INDEPENDENT_VALIDATION"):
            verify(self.root)

    def test_protected22_rescue_fails(self):
        self.mutate_json(
            "evidence/PROTECTED22_ACCESS_STATUS.json",
            lambda value: value.__setitem__("primary", {"mse": 0.1}),
        )
        with self.assertRaisesRegex(RubricEvidenceError, "PROTECTED22_PRIMARY"):
            verify(self.root)

    def test_stroma_scope_erasure_fails(self):
        self.mutate_json(
            "evidence/stroma_context_confirmation_20260930.json",
            lambda value: value.__setitem__("limitations", ["none"]),
        )
        with self.assertRaisesRegex(RubricEvidenceError, "STROMA_SCOPE"):
            verify(self.root)

    def test_runtime_physical_certification_fails(self):
        self.mutate_json(
            "evidence/bandwidth_lifecycle_20261003.json",
            lambda value: value["physical_contract"].__setitem__("physical_execution_certified", True),
        )
        with self.assertRaisesRegex(RubricEvidenceError, "NO_PHYSICAL_CERTIFICATION"):
            verify(self.root)

    def test_claim_boundary_promotion_fails(self):
        self.mutate_receipt(lambda value: value["claim_boundary"].__setitem__("finalist_status_claimed", True))
        with self.assertRaisesRegex(RubricEvidenceError, "CLAIM_BOUNDARY"):
            verify(self.root)

    def test_refresh_claim_fails(self):
        self.mutate_receipt(lambda value: value["rubric"].__setitem__("current_run_public_retrieval", "PASS"))
        with self.assertRaisesRegex(RubricEvidenceError, "RUBRIC_REFRESH_BOUNDARY"):
            verify(self.root)


if __name__ == "__main__":
    unittest.main()
