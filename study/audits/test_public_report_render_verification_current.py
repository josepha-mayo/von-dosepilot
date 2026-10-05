import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from verify_public_report_render_verification_current import (
    CurrentPublicReportRenderVerificationError,
    verify,
)


ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class CurrentPublicReportRenderVerificationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        index = json.loads((ROOT / "evidence/EVIDENCE_INDEX.json").read_text())
        record = index["current_public_report_render_verification"]
        receipt = json.loads((ROOT / record["path"]).read_text())
        paths = [
            record["path"],
            receipt["predecessor"]["path"],
            receipt["exact_pdf"]["path"],
            *receipt["artifact_sha256"],
        ]
        for relative in paths:
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, target)
        index_path = self.root / "evidence/EVIDENCE_INDEX.json"
        index_path.write_text(json.dumps({"current_public_report_render_verification": record}, indent=2) + "\n")

    def tearDown(self):
        self.temporary.cleanup()

    def receipt(self):
        index_path = self.root / "evidence/EVIDENCE_INDEX.json"
        index = json.loads(index_path.read_text())
        receipt_path = self.root / index["current_public_report_render_verification"]["path"]
        return index_path, index, receipt_path, json.loads(receipt_path.read_text())

    def write_receipt(self, receipt):
        index_path, index, receipt_path, _ = self.receipt()
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
        index["current_public_report_render_verification"]["sha256"] = sha(receipt_path)
        index_path.write_text(json.dumps(index, indent=2) + "\n")

    def test_current_state_passes(self):
        result = verify(self.root)
        self.assertTrue(result["predecessor_hash_verified"])
        self.assertEqual(result["pdf_pages"], 10)

    def test_unrehashable_receipt_tamper_fails(self):
        _, _, receipt_path, receipt = self.receipt()
        receipt["status"] = "FAIL"
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
        with self.assertRaisesRegex(CurrentPublicReportRenderVerificationError, "INDEX_RECEIPT_HASH"):
            verify(self.root)

    def test_historical_pointer_fallback_fails(self):
        index_path, index, _, receipt = self.receipt()
        index["current_public_report_render_verification"]["path"] = receipt["predecessor"]["path"]
        index["current_public_report_render_verification"]["sha256"] = receipt["predecessor"]["sha256"]
        index_path.write_text(json.dumps(index, indent=2) + "\n")
        with self.assertRaisesRegex(CurrentPublicReportRenderVerificationError, "INDEX_CURRENT_PATH"):
            verify(self.root)

    def test_predecessor_drift_fails(self):
        _, _, _, receipt = self.receipt()
        path = self.root / receipt["predecessor"]["path"]
        path.write_bytes(path.read_bytes() + b"\n")
        with self.assertRaisesRegex(CurrentPublicReportRenderVerificationError, "PREDECESSOR_HASH"):
            verify(self.root)

    def test_changed_viewer_commit_fails_even_when_rehashed(self):
        _, _, _, receipt = self.receipt()
        receipt["embedded_viewer"]["commit_binding"] = "0" * 40
        self.write_receipt(receipt)
        with self.assertRaisesRegex(CurrentPublicReportRenderVerificationError, "EMBEDDED_VIEWER"):
            verify(self.root)

    def test_changed_page_marker_fails_even_when_rehashed(self):
        _, _, _, receipt = self.receipt()
        receipt["embedded_viewer"]["visible_page_markers"] = ["Page 5"]
        self.write_receipt(receipt)
        with self.assertRaisesRegex(CurrentPublicReportRenderVerificationError, "EMBEDDED_VIEWER"):
            verify(self.root)

    def test_inflated_page_count_fails_even_when_rehashed(self):
        _, _, _, receipt = self.receipt()
        receipt["exact_pdf"]["pages"] = 11
        self.write_receipt(receipt)
        with self.assertRaisesRegex(CurrentPublicReportRenderVerificationError, "EXACT_PDF"):
            verify(self.root)

    def test_false_download_claim_fails_even_when_rehashed(self):
        _, _, _, receipt = self.receipt()
        receipt["claim_boundary"]["raw_download_success_verified"] = True
        self.write_receipt(receipt)
        with self.assertRaisesRegex(CurrentPublicReportRenderVerificationError, "BOUNDARY_RAW_DOWNLOAD"):
            verify(self.root)

    def test_pdf_drift_fails(self):
        _, _, _, receipt = self.receipt()
        path = self.root / receipt["exact_pdf"]["path"]
        path.write_bytes(path.read_bytes() + b"\n")
        with self.assertRaisesRegex(CurrentPublicReportRenderVerificationError, "PDF_HASH"):
            verify(self.root)

    def test_artifact_drift_fails(self):
        _, _, _, receipt = self.receipt()
        relative = next(iter(receipt["artifact_sha256"]))
        path = self.root / relative
        path.write_bytes(path.read_bytes() + b"\n")
        with self.assertRaisesRegex(CurrentPublicReportRenderVerificationError, "ARTIFACT_HASH"):
            verify(self.root)


if __name__ == "__main__":
    unittest.main(verbosity=2)
