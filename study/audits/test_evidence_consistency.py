import copy
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_evidence_consistency import EvidenceError, verify


class EvidenceConsistencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path(__file__).resolve().parents[2]

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "evidence").mkdir()
        (self.root / "docs").mkdir()
        index = json.loads((self.source / "evidence/EVIDENCE_INDEX.json").read_text())
        shutil.copy2(self.source / "evidence/EVIDENCE_INDEX.json", self.root / "evidence/EVIDENCE_INDEX.json")
        for record in index["canonical_receipts"].values():
            shutil.copy2(self.source / record["path"], self.root / record["path"])
        report_index = index["current_technical_report"]
        report_receipt_path = report_index["path"]
        shutil.copy2(self.source / report_receipt_path, self.root / report_receipt_path)
        report_preflight_path = report_index["preflight_path"]
        shutil.copy2(self.source / report_preflight_path, self.root / report_preflight_path)
        report = json.loads((self.source / report_receipt_path).read_text())
        report_paths = [report[part]["path"] for part in ("entrypoint", "source", "pdf", "renderer")]
        report_paths.append(report["historical_submitted_pdf"]["path"])
        for relative in report_paths:
            destination = self.root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.source / relative, destination)
        target_release = json.loads(
            (self.source / "evidence/target_definitions_release_20261003.json").read_text()
        )
        for relative in target_release["source_sha256"]:
            destination = self.root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.source / relative, destination)
        reviewer_path = index["canonical_receipts"]["reviewer_path_release"]["path"]
        reviewer_release = json.loads((self.source / reviewer_path).read_text())
        reviewer_paths = [
            reviewer_release["predecessor"]["path"],
            reviewer_release["entrypoint"]["path"],
        ]
        reviewer_paths.extend(reviewer_release["bound_artifacts"])
        for relative in reviewer_paths:
            destination = self.root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.source / relative, destination)
        current_preflight_path = index["current_release_preflight"]["path"]
        shutil.copy2(self.source / current_preflight_path, self.root / current_preflight_path)
        predecessor_path = index["current_release_preflight"]["predecessor_path"]
        shutil.copy2(self.source / predecessor_path, self.root / predecessor_path)
        lifecycle = json.loads(
            (self.source / "evidence/bandwidth_lifecycle_20261003.json").read_text()
        )
        for relative in lifecycle["code_sha256"]:
            destination = self.root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.source / relative, destination)
        frozen_path = index["canonical_receipts"]["frozen_ooc_release_binding"]["path"]
        frozen = json.loads((self.source / frozen_path).read_text())
        frozen_paths = [frozen["predecessor"]["path"], frozen["schedule_receipt"]["path"]]
        for group in ("source_files_sha256", "audit_code_sha256", "public_surface_sha256"):
            frozen_paths.extend(frozen[group])
        for relative in frozen_paths:
            destination = self.root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.source / relative, destination)
        shutil.copy2(self.source / "docs/EVIDENCE_LEDGER.md", self.root / "docs/EVIDENCE_LEDGER.md")
        shutil.copy2(self.source / "docs/KAGGLE_WRITEUP.md", self.root / "docs/KAGGLE_WRITEUP.md")

    def tearDown(self):
        self.tmp.cleanup()

    def mutate_receipt(self, name, mutation):
        index = json.loads((self.root / "evidence/EVIDENCE_INDEX.json").read_text())
        path = self.root / index["canonical_receipts"][name]["path"]
        value = json.loads(path.read_text())
        mutation(value)
        path.write_text(json.dumps(value, indent=2) + "\n")
        import hashlib
        index["canonical_receipts"][name]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        (self.root / "evidence/EVIDENCE_INDEX.json").write_text(json.dumps(index, indent=2) + "\n")

    def mutate_index(self, mutation):
        path = self.root / "evidence/EVIDENCE_INDEX.json"
        value = json.loads(path.read_text())
        mutation(value)
        path.write_text(json.dumps(value, indent=2) + "\n")

    def test_current_state_passes(self):
        result = verify(self.root)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["canonical_receipts"], 12)
        self.assertEqual(result["protected22_cells_reconciled"], 19642)
        self.assertAlmostEqual(result["additive_incumbent_mse"], 0.001060552730112811)
        self.assertAlmostEqual(result["bandwidth_successor_mse"], 0.0010582750420801538)
        self.assertEqual(result["raw_ak_decision"], "REJECT_RETAIN_ADDITIVE")
        self.assertEqual(result["durable_runtime_tests"], 55)
        self.assertEqual(result["bandwidth_lifecycle_tests"], 65)
        self.assertEqual(result["frozen_ooc_schedule_rows"], 64)
        self.assertEqual(result["frozen_ooc_schedule_tamper_tests"], 5)
        self.assertEqual(result["current_report_pages"], 10)
        self.assertTrue(result["current_report_deterministic"])
        self.assertEqual(result["target_definitions_verified"], 24)
        self.assertEqual(result["reviewer_path_seconds"], 90)
        self.assertEqual(result["current_preflight_tests"], 155)

    def test_changed_receipt_byte_fails_hash(self):
        path = self.root / "evidence/PROTECTED22_ACCESS_STATUS.json"
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaisesRegex(EvidenceError, "RECEIPT_HASH"):
            verify(self.root, enforce_pins=False)

    def test_cell_arithmetic_contradiction_fails(self):
        self.mutate_receipt("protected22_completed", lambda value: value["access"].__setitem__("numeric_cells", 19636))
        with self.assertRaises(EvidenceError):
            verify(self.root, enforce_pins=False)

    def test_nonnull_primary_or_confirmation_pass_fails(self):
        for key, value in (("primary", {}), ("confirmation_passed", True)):
            with self.subTest(key=key):
                self.tearDown()
                self.setUp()
                self.mutate_receipt("protected22_completed", lambda receipt, k=key, v=value: receipt.__setitem__(k, v))
                with self.assertRaises(EvidenceError):
                    verify(self.root, enforce_pins=False)

    def test_missing_prior_exposure_link_fails(self):
        self.mutate_receipt(
            "protected22_completed",
            lambda value: value["prior_project_exposure"].__setitem__("source_receipt", "missing.json"),
        )
        with self.assertRaises(EvidenceError):
            verify(self.root, enforce_pins=False)

    def test_index_cannot_promote_conditional_to_primary(self):
        path = self.root / "evidence/EVIDENCE_INDEX.json"
        value = json.loads(path.read_text())
        value["protected22"]["completed_missingness_execution"]["conditional_diagnostic_is_primary"] = True
        path.write_text(json.dumps(value, indent=2) + "\n")
        with self.assertRaises(EvidenceError):
            verify(self.root)

    def test_index_cannot_label_s2_independent(self):
        path = self.root / "evidence/EVIDENCE_INDEX.json"
        value = json.loads(path.read_text())
        value["spectral_successor"]["independent_validation"] = True
        path.write_text(json.dumps(value, indent=2) + "\n")
        with self.assertRaises(EvidenceError):
            verify(self.root)

    def test_index_conditional_metric_must_match_receipt(self):
        path = self.root / "evidence/EVIDENCE_INDEX.json"
        value = json.loads(path.read_text())
        value["protected22"]["completed_missingness_execution"]["conditional_diagnostic"]["candidate_mse"] = 999
        path.write_text(json.dumps(value, indent=2) + "\n")
        with self.assertRaises(EvidenceError):
            verify(self.root)

    def test_index_spectral_wins_must_match_receipt(self):
        path = self.root / "evidence/EVIDENCE_INDEX.json"
        value = json.loads(path.read_text())
        value["spectral_successor"]["patient_wins_vs_r13"] = 0
        path.write_text(json.dumps(value, indent=2) + "\n")
        with self.assertRaises(EvidenceError):
            verify(self.root)

    def test_index_cannot_replace_bandwidth_incumbent(self):
        self.mutate_index(
            lambda value: value["bandwidth_successor"].update(
                {"mse": 9.0, "current_internal_incumbent": False}
            )
        )
        with self.assertRaisesRegex(EvidenceError, "INDEX_BANDWIDTH"):
            verify(self.root)

    def test_index_cannot_promote_raw_ak(self):
        self.mutate_index(
            lambda value: value["raw_ak_challenger"].update(
                {"decision": "PROMOTE", "passes_incumbent_gate": True}
            )
        )
        with self.assertRaisesRegex(EvidenceError, "INDEX_RAW_AK"):
            verify(self.root)

    def test_index_cannot_turn_lifecycle_into_biological_evidence(self):
        self.mutate_index(
            lambda value: value["durable_lifecycle"].update(
                {
                    "role": "INDEPENDENT_BIOLOGICAL_VALIDATION",
                    "new_biological_accuracy_improvement": True,
                    "end_to_end_cli_speedup_claimed": True,
                }
            )
        )
        with self.assertRaisesRegex(EvidenceError, "INDEX_LIFECYCLE"):
            verify(self.root)

    def test_index_cannot_relabel_current_bandwidth_lifecycle(self):
        self.mutate_index(
            lambda value: value["bandwidth_lifecycle"].update(
                {"model_kind": "dosepilot.additive_kernel.v1",
                 "new_biological_accuracy_improvement": True}
            )
        )
        with self.assertRaisesRegex(EvidenceError, "INDEX_BANDWIDTH_LIFECYCLE"):
            verify(self.root)

    def test_index_cannot_promote_frozen_schedule_to_validation(self):
        self.mutate_index(
            lambda value: value["frozen_ooc_release_binding"].update(
                {"prospective_experiment_executed": True,
                 "biological_validation_created": True}
            )
        )
        with self.assertRaisesRegex(EvidenceError, "INDEX_FROZEN_SCHEDULE"):
            verify(self.root)

    def test_frozen_schedule_public_surface_tamper_fails(self):
        path = self.root / "site/frozen_schedule.js"
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaisesRegex(EvidenceError, "FROZEN_SCHEDULE_FILE_HASH"):
            verify(self.root)

    def test_receipt_cannot_replace_additive_incumbent(self):
        self.mutate_receipt(
            "structured_additive",
            lambda value: value["research"]["mse"].__setitem__("recovered_additive_control", 9.0),
        )
        with self.assertRaisesRegex(EvidenceError, "ADDITIVE_MSE"):
            verify(self.root, enforce_pins=False)

    def test_receipt_cannot_fake_bandwidth_successor(self):
        self.mutate_receipt(
            "bandwidth_successor",
            lambda value: value["metrics"]["bandwidth07"].__setitem__("mse", 9.0),
        )
        with self.assertRaisesRegex(EvidenceError, "BANDWIDTH_MSE"):
            verify(self.root, enforce_pins=False)

    def test_receipt_cannot_promote_raw_ak(self):
        self.mutate_receipt(
            "aligned_additive",
            lambda value: value.__setitem__("decision", "PROMOTE"),
        )
        with self.assertRaisesRegex(EvidenceError, "RAW_AK_DECISION"):
            verify(self.root, enforce_pins=False)

    def test_receipt_cannot_expand_lifecycle_scope(self):
        self.mutate_receipt(
            "lifecycle_acquisition",
            lambda value: value.__setitem__("new_biological_accuracy_improvement", True),
        )
        with self.assertRaisesRegex(EvidenceError, "INDEX_LIFECYCLE"):
            verify(self.root, enforce_pins=False)

    def test_receipt_cannot_fake_bandwidth_lifecycle(self):
        self.mutate_receipt(
            "bandwidth_lifecycle",
            lambda value: value["verification"].__setitem__(
                "wrong_bandwidth_rejected", False
            ),
        )
        with self.assertRaisesRegex(EvidenceError, "BANDWIDTH_LIFECYCLE"):
            verify(self.root, enforce_pins=False)

    def test_stale_ledger_claim_fails(self):
        path = self.root / "docs/EVIDENCE_LEDGER.md"
        path.write_text(path.read_text() + "\nThe project therefore has **no Lib2 efficacy score**.\n")
        with self.assertRaises(EvidenceError):
            verify(self.root)

    def test_any_judge_facing_document_byte_change_fails_pin(self):
        for relative in ("docs/EVIDENCE_LEDGER.md", "docs/KAGGLE_WRITEUP.md"):
            with self.subTest(path=relative):
                self.tearDown()
                self.setUp()
                path = self.root / relative
                path.write_bytes(path.read_bytes() + b" ")
                with self.assertRaisesRegex(
                    EvidenceError,
                    "PINNED_DOCUMENT_HASH|FROZEN_SCHEDULE_FILE_HASH|REVIEWER_PATH_FILE_HASH",
                ):
                    verify(self.root)

    def test_future_interpretation_is_exact(self):
        path = self.root / "evidence/EVIDENCE_INDEX.json"
        value = json.loads(path.read_text())
        value["protected22"]["future_interpretation"] = "Protected22 may be reopened."
        path.write_text(json.dumps(value, indent=2) + "\n")
        with self.assertRaisesRegex(EvidenceError, "INDEX_FUTURE_INTERPRETATION"):
            verify(self.root)

    def test_paired_receipt_and_index_change_fails_external_pin(self):
        self.mutate_receipt(
            "spectral_successor",
            lambda value: value["comparisons"]["r13"].__setitem__("patient_wins", 1),
        )
        with self.assertRaisesRegex(EvidenceError, "PINNED_RECEIPT_HASH"):
            verify(self.root)

    def test_ledger_numeric_claim_must_match(self):
        path = self.root / "docs/EVIDENCE_LEDGER.md"
        path.write_text(path.read_text().replace("49/59 and 47/59", "59/59 and 59/59"))
        with self.assertRaises(EvidenceError):
            verify(self.root)

    def test_writeup_false_validation_claim_fails(self):
        path = self.root / "docs/KAGGLE_WRITEUP.md"
        path.write_text(path.read_text() + "\nS2 is independent prospective confirmation.\n")
        with self.assertRaises(EvidenceError):
            verify(self.root)


if __name__ == "__main__":
    unittest.main(verbosity=2)
