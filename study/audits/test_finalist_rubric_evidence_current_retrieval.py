import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from verify_finalist_rubric_evidence_current_retrieval import (
    CurrentRetrievalRubricEvidenceError,
    verify,
)


ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class CurrentRetrievalRubricEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        index = json.loads((ROOT / "evidence/EVIDENCE_INDEX.json").read_text())
        record = index["current_report_retrieval_finalist_rubric_evidence"]
        receipt = json.loads((ROOT / record["path"]).read_text())
        paths = [
            record["path"],
            *(binding["path"] for binding in receipt["evidence_bindings"].values()),
            "docs/DosePilot_Technical_Report_Current.pdf",
            *receipt["artifact_sha256"],
        ]
        for relative in paths:
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, target)
        index_path = self.root / "evidence/EVIDENCE_INDEX.json"
        index_path.write_text(
            json.dumps({"current_report_retrieval_finalist_rubric_evidence": record}, indent=2)
            + "\n"
        )

    def tearDown(self):
        self.temporary.cleanup()

    def receipt(self):
        index_path = self.root / "evidence/EVIDENCE_INDEX.json"
        index = json.loads(index_path.read_text())
        receipt_path = self.root / index["current_report_retrieval_finalist_rubric_evidence"]["path"]
        return index_path, index, receipt_path, json.loads(receipt_path.read_text())

    def write_receipt(self, receipt):
        index_path, index, receipt_path, _ = self.receipt()
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
        index["current_report_retrieval_finalist_rubric_evidence"]["sha256"] = sha(receipt_path)
        index_path.write_text(json.dumps(index, indent=2) + "\n")

    def test_current_state_passes(self):
        result = verify(self.root)
        self.assertTrue(result["predecessor_hash_verified"])
        self.assertTrue(result["byte_retrieval_receipt_hash_verified"])

    def test_unrehashable_receipt_tamper_fails(self):
        _, _, receipt_path, receipt = self.receipt()
        receipt["status"] = "FAIL"
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
        with self.assertRaisesRegex(CurrentRetrievalRubricEvidenceError, "INDEX_RECEIPT_HASH"):
            verify(self.root)

    def test_predecessor_pointer_fallback_fails(self):
        index_path, index, _, receipt = self.receipt()
        binding = receipt["evidence_bindings"]["predecessor"]
        index["current_report_retrieval_finalist_rubric_evidence"]["path"] = binding["path"]
        index["current_report_retrieval_finalist_rubric_evidence"]["sha256"] = binding["sha256"]
        index_path.write_text(json.dumps(index, indent=2) + "\n")
        with self.assertRaisesRegex(CurrentRetrievalRubricEvidenceError, "INDEX_CURRENT_PATH"):
            verify(self.root)

    def test_predecessor_drift_fails(self):
        _, _, _, receipt = self.receipt()
        path = self.root / receipt["evidence_bindings"]["predecessor"]["path"]
        path.write_bytes(path.read_bytes() + b"\n")
        with self.assertRaisesRegex(CurrentRetrievalRubricEvidenceError, "BINDING_HASH"):
            verify(self.root)

    def test_byte_retrieval_receipt_drift_fails(self):
        _, _, _, receipt = self.receipt()
        path = self.root / receipt["evidence_bindings"]["public_report_byte_retrieval"]["path"]
        path.write_bytes(path.read_bytes() + b"\n")
        with self.assertRaisesRegex(CurrentRetrievalRubricEvidenceError, "BINDING_HASH"):
            verify(self.root)

    def test_old_pdf_fallback_fails_even_when_rehashed(self):
        _, _, _, receipt = self.receipt()
        receipt["presentation_retrieval_successor"]["current_report_sha256"] = (
            "1d5d7098d53838373ab57ad32ab01d61d3dcfe8d577f8b3bfb09f33f1b4a0ff2"
        )
        self.write_receipt(receipt)
        with self.assertRaisesRegex(CurrentRetrievalRubricEvidenceError, "PRESENTATION_PDF_HASH"):
            verify(self.root)

    def test_false_anonymous_raw_claim_fails_even_when_rehashed(self):
        _, _, _, receipt = self.receipt()
        receipt["claim_boundary"]["anonymous_raw_http_verified"] = True
        self.write_receipt(receipt)
        with self.assertRaisesRegex(CurrentRetrievalRubricEvidenceError, "CLAIM_BOUNDARY"):
            verify(self.root)

    def test_false_browser_button_claim_fails_even_when_rehashed(self):
        _, _, _, receipt = self.receipt()
        receipt["claim_boundary"]["browser_download_button_verified"] = True
        self.write_receipt(receipt)
        with self.assertRaisesRegex(CurrentRetrievalRubricEvidenceError, "CLAIM_BOUNDARY"):
            verify(self.root)

    def test_false_generic_download_claim_fails_even_when_rehashed(self):
        _, _, _, receipt = self.receipt()
        receipt["claim_boundary"]["raw_pdf_download_verified"] = True
        self.write_receipt(receipt)
        with self.assertRaisesRegex(CurrentRetrievalRubricEvidenceError, "CLAIM_BOUNDARY"):
            verify(self.root)

    def test_false_independent_validation_fails_even_when_rehashed(self):
        _, _, _, receipt = self.receipt()
        receipt["claim_boundary"]["independent_validation_created"] = True
        self.write_receipt(receipt)
        with self.assertRaisesRegex(CurrentRetrievalRubricEvidenceError, "CLAIM_BOUNDARY"):
            verify(self.root)

    def test_current_pdf_drift_fails(self):
        path = self.root / "docs/DosePilot_Technical_Report_Current.pdf"
        path.write_bytes(path.read_bytes() + b"\n")
        with self.assertRaisesRegex(CurrentRetrievalRubricEvidenceError, "CURRENT_PDF_HASH"):
            verify(self.root)

    def test_artifact_drift_fails(self):
        _, _, _, receipt = self.receipt()
        relative = next(iter(receipt["artifact_sha256"]))
        path = self.root / relative
        path.write_bytes(path.read_bytes() + b"\n")
        with self.assertRaisesRegex(CurrentRetrievalRubricEvidenceError, "ARTIFACT_HASH"):
            verify(self.root)


if __name__ == "__main__":
    unittest.main(verbosity=2)
