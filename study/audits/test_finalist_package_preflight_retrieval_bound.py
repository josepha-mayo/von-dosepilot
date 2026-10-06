import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from verify_finalist_package_preflight_retrieval_bound import (
    RetrievalBoundFinalistPackagePreflightError,
    verify,
)


ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class RetrievalBoundFinalistPackagePreflightTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        index = json.loads((ROOT / "evidence/EVIDENCE_INDEX.json").read_text())
        record = index["current_report_retrieval_finalist_package_preflight"]
        receipt = json.loads((ROOT / record["path"]).read_text())
        paths = [
            record["path"],
            receipt["predecessor"]["path"],
            receipt["current_report_retrieval_rubric"]["path"],
            *receipt["artifact_sha256"],
        ]
        for relative in paths:
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, target)
        index_path = self.root / "evidence/EVIDENCE_INDEX.json"
        index_path.write_text(
            json.dumps(
                {"current_report_retrieval_finalist_package_preflight": record}, indent=2
            )
            + "\n"
        )

    def tearDown(self):
        self.temporary.cleanup()

    def receipt(self):
        index_path = self.root / "evidence/EVIDENCE_INDEX.json"
        index = json.loads(index_path.read_text())
        receipt_path = self.root / index[
            "current_report_retrieval_finalist_package_preflight"
        ]["path"]
        return index_path, index, receipt_path, json.loads(receipt_path.read_text())

    def write_receipt(self, receipt):
        index_path, index, receipt_path, _ = self.receipt()
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
        index["current_report_retrieval_finalist_package_preflight"]["sha256"] = sha(
            receipt_path
        )
        index_path.write_text(json.dumps(index, indent=2) + "\n")

    def test_current_state_passes(self):
        self.assertEqual(verify(self.root)["status"], "PASS")

    def test_receipt_tamper_fails(self):
        _, _, receipt_path, receipt = self.receipt()
        receipt["status"] = "FAIL"
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
        with self.assertRaisesRegex(
            RetrievalBoundFinalistPackagePreflightError, "INDEX_RECEIPT_HASH"
        ):
            verify(self.root)

    def test_inflated_canonical_count_fails_even_when_rehashed(self):
        _, _, _, receipt = self.receipt()
        receipt["canonical_orchestrated_test_count"] = 174
        self.write_receipt(receipt)
        with self.assertRaisesRegex(
            RetrievalBoundFinalistPackagePreflightError, "CANONICAL_TEST_COUNT"
        ):
            verify(self.root)

    def test_render_only_rubric_fallback_fails_even_when_rehashed(self):
        _, _, _, receipt = self.receipt()
        receipt["checks"][-1]["name"] = "current_report_finalist_rubric_evidence"
        receipt["current_report_retrieval_rubric_successor_checked"] = False
        self.write_receipt(receipt)
        with self.assertRaisesRegex(RetrievalBoundFinalistPackagePreflightError, "CHECK_ORDER"):
            verify(self.root)

    def test_removed_check_fails_even_when_rehashed(self):
        _, _, _, receipt = self.receipt()
        receipt["checks"].pop()
        self.write_receipt(receipt)
        with self.assertRaisesRegex(RetrievalBoundFinalistPackagePreflightError, "CHECK_ORDER"):
            verify(self.root)

    def test_false_biological_claim_fails_even_when_rehashed(self):
        _, _, _, receipt = self.receipt()
        receipt["biological_accuracy_result_created"] = True
        self.write_receipt(receipt)
        with self.assertRaisesRegex(
            RetrievalBoundFinalistPackagePreflightError, "BOUNDARY_BIOLOGICAL"
        ):
            verify(self.root)

    def test_false_repository_retrieval_fails_even_when_rehashed(self):
        _, _, _, receipt = self.receipt()
        receipt["current_report_retrieval_rubric"][
            "public_repository_file_bytes_retrieved"
        ] = False
        self.write_receipt(receipt)
        with self.assertRaisesRegex(
            RetrievalBoundFinalistPackagePreflightError, "REPOSITORY_BYTES_RETRIEVED"
        ):
            verify(self.root)

    def test_false_anonymous_raw_claim_fails_even_when_rehashed(self):
        _, _, _, receipt = self.receipt()
        receipt["anonymous_raw_http_verified"] = True
        self.write_receipt(receipt)
        with self.assertRaisesRegex(RetrievalBoundFinalistPackagePreflightError, "RECEIPT_NO_RAW_HTTP"):
            verify(self.root)

    def test_false_browser_button_claim_fails_even_when_rehashed(self):
        _, _, _, receipt = self.receipt()
        receipt["browser_download_button_verified"] = True
        self.write_receipt(receipt)
        with self.assertRaisesRegex(RetrievalBoundFinalistPackagePreflightError, "RECEIPT_NO_BUTTON"):
            verify(self.root)

    def test_false_generic_download_claim_fails_even_when_rehashed(self):
        _, _, _, receipt = self.receipt()
        receipt["raw_download_verified"] = True
        self.write_receipt(receipt)
        with self.assertRaisesRegex(
            RetrievalBoundFinalistPackagePreflightError, "RECEIPT_NO_GENERIC_DOWNLOAD"
        ):
            verify(self.root)

    def test_current_retrieval_rubric_tamper_fails(self):
        _, _, _, receipt = self.receipt()
        path = self.root / receipt["current_report_retrieval_rubric"]["path"]
        path.write_bytes(path.read_bytes() + b"\n")
        with self.assertRaisesRegex(
            RetrievalBoundFinalistPackagePreflightError, "CURRENT_RETRIEVAL_RUBRIC_HASH"
        ):
            verify(self.root)

    def test_artifact_drift_fails(self):
        _, _, _, receipt = self.receipt()
        relative = next(iter(receipt["artifact_sha256"]))
        path = self.root / relative
        path.write_bytes(path.read_bytes() + b"\n")
        with self.assertRaisesRegex(RetrievalBoundFinalistPackagePreflightError, "ARTIFACT_HASH"):
            verify(self.root)


if __name__ == "__main__":
    unittest.main(verbosity=2)
