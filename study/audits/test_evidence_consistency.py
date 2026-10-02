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

    def test_current_state_passes(self):
        result = verify(self.root)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["protected22_cells_reconciled"], 19642)

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
                with self.assertRaisesRegex(EvidenceError, "PINNED_DOCUMENT_HASH"):
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
