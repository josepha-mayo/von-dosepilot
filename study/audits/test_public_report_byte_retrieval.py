import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from verify_public_report_byte_retrieval import (
    PublicReportByteRetrievalError,
    verify,
)


ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class PublicReportByteRetrievalTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        index = json.loads((ROOT / "evidence/EVIDENCE_INDEX.json").read_text())
        record = index["public_report_byte_retrieval_verification"]
        receipt = json.loads((ROOT / record["path"]).read_text())
        paths = [record["path"], receipt["exact_tree_comparison"]["path"], *receipt["artifact_sha256"]]
        for relative in paths:
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, target)
        index_path = self.root / "evidence/EVIDENCE_INDEX.json"
        index_path.write_text(json.dumps({"public_report_byte_retrieval_verification": record}, indent=2) + "\n")

    def tearDown(self):
        self.temporary.cleanup()

    def receipt(self):
        index_path = self.root / "evidence/EVIDENCE_INDEX.json"
        index = json.loads(index_path.read_text())
        receipt_path = self.root / index["public_report_byte_retrieval_verification"]["path"]
        return index_path, index, receipt_path, json.loads(receipt_path.read_text())

    def write_receipt(self, receipt):
        index_path, index, receipt_path, _ = self.receipt()
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
        index["public_report_byte_retrieval_verification"]["sha256"] = sha(receipt_path)
        index_path.write_text(json.dumps(index, indent=2) + "\n")

    def test_current_state_passes(self):
        result = verify(self.root)
        self.assertEqual(result["pdf_bytes"], 92307)
        self.assertTrue(result["retrieved_bytes_match_exact_tree_pdf"])

    def test_unrehashable_receipt_tamper_fails(self):
        _, _, receipt_path, receipt = self.receipt()
        receipt["status"] = "FAIL"
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
        with self.assertRaisesRegex(PublicReportByteRetrievalError, "INDEX_RECEIPT_HASH"):
            verify(self.root)

    def test_commit_tamper_fails_even_when_rehashed(self):
        _, _, _, receipt = self.receipt()
        receipt["source"]["public_commit"] = "0" * 40
        self.write_receipt(receipt)
        with self.assertRaisesRegex(PublicReportByteRetrievalError, "SOURCE"):
            verify(self.root)

    def test_blob_tamper_fails_even_when_rehashed(self):
        _, _, _, receipt = self.receipt()
        receipt["retrieval"]["github_blob_sha"] = "0" * 40
        self.write_receipt(receipt)
        with self.assertRaisesRegex(PublicReportByteRetrievalError, "RETRIEVAL"):
            verify(self.root)

    def test_byte_count_tamper_fails_even_when_rehashed(self):
        _, _, _, receipt = self.receipt()
        receipt["retrieval"]["retrieved_bytes"] += 1
        self.write_receipt(receipt)
        with self.assertRaisesRegex(PublicReportByteRetrievalError, "RETRIEVAL"):
            verify(self.root)

    def test_digest_tamper_fails_even_when_rehashed(self):
        _, _, _, receipt = self.receipt()
        receipt["retrieval"]["retrieved_sha256"] = "0" * 64
        self.write_receipt(receipt)
        with self.assertRaisesRegex(PublicReportByteRetrievalError, "RETRIEVAL"):
            verify(self.root)

    def test_false_anonymous_raw_claim_fails_even_when_rehashed(self):
        _, _, _, receipt = self.receipt()
        receipt["claim_boundary"]["anonymous_raw_http_verified"] = True
        self.write_receipt(receipt)
        with self.assertRaisesRegex(PublicReportByteRetrievalError, "BOUNDARY_ANONYMOUS_RAW_HTTP"):
            verify(self.root)

    def test_false_browser_download_claim_fails_even_when_rehashed(self):
        _, _, _, receipt = self.receipt()
        receipt["claim_boundary"]["browser_download_button_verified"] = True
        self.write_receipt(receipt)
        with self.assertRaisesRegex(PublicReportByteRetrievalError, "BOUNDARY_BROWSER_DOWNLOAD_BUTTON"):
            verify(self.root)

    def test_pdf_drift_fails(self):
        _, _, _, receipt = self.receipt()
        path = self.root / receipt["exact_tree_comparison"]["path"]
        path.write_bytes(path.read_bytes() + b"\n")
        with self.assertRaisesRegex(PublicReportByteRetrievalError, "PDF_SIZE"):
            verify(self.root)

    def test_artifact_drift_fails(self):
        _, _, _, receipt = self.receipt()
        relative = next(iter(receipt["artifact_sha256"]))
        path = self.root / relative
        path.write_bytes(path.read_bytes() + b"\n")
        with self.assertRaisesRegex(PublicReportByteRetrievalError, "ARTIFACT_HASH"):
            verify(self.root)


if __name__ == "__main__":
    unittest.main(verbosity=2)
