import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from verify_clean_retrieval_bound_finalist_package_execution import (
    CleanRetrievalBoundFinalistPackageExecutionError,
    verify,
)


ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class CleanRetrievalBoundFinalistPackageExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        index = json.loads((ROOT / "evidence/EVIDENCE_INDEX.json").read_text())
        record = index["clean_retrieval_bound_finalist_package_execution"]
        receipt = json.loads((ROOT / record["path"]).read_text())
        paths = [record["path"], receipt["predecessor"]["path"], *receipt["requirements"], *receipt["artifact_sha256"]]
        for relative in paths:
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, target)
        index_path = self.root / "evidence/EVIDENCE_INDEX.json"
        index_path.write_text(json.dumps({"clean_retrieval_bound_finalist_package_execution": record}, indent=2) + "\n")

    def tearDown(self):
        self.temporary.cleanup()

    def receipt(self):
        index_path = self.root / "evidence/EVIDENCE_INDEX.json"
        index = json.loads(index_path.read_text())
        receipt_path = self.root / index["clean_retrieval_bound_finalist_package_execution"]["path"]
        return index_path, index, receipt_path, json.loads(receipt_path.read_text())

    def write_receipt(self, receipt):
        index_path, index, receipt_path, _ = self.receipt()
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
        index["clean_retrieval_bound_finalist_package_execution"]["sha256"] = sha(receipt_path)
        index_path.write_text(json.dumps(index, indent=2) + "\n")

    def test_current_state_passes(self):
        self.assertEqual(verify(self.root)["status"], "PASS")

    def test_unrehashable_receipt_tamper_fails(self):
        _, _, receipt_path, receipt = self.receipt()
        receipt["status"] = "FAIL"
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
        with self.assertRaisesRegex(CleanRetrievalBoundFinalistPackageExecutionError, "INDEX_RECEIPT_HASH"):
            verify(self.root)

    def test_wrong_source_tree_fails_even_when_rehashed(self):
        _, _, _, receipt = self.receipt()
        receipt["source"]["public_tree"] = "0" * 40
        self.write_receipt(receipt)
        with self.assertRaisesRegex(CleanRetrievalBoundFinalistPackageExecutionError, "SOURCE_TREE"):
            verify(self.root)

    def test_false_public_clone_claim_fails_even_when_rehashed(self):
        _, _, _, receipt = self.receipt()
        receipt["source"]["fresh_public_clone"] = True
        self.write_receipt(receipt)
        with self.assertRaisesRegex(CleanRetrievalBoundFinalistPackageExecutionError, "NOT_PUBLIC_CLONE"):
            verify(self.root)

    def test_false_live_download_claim_fails_even_when_rehashed(self):
        _, _, _, receipt = self.receipt()
        receipt["environment"]["live_dependency_download_claimed"] = True
        self.write_receipt(receipt)
        with self.assertRaisesRegex(CleanRetrievalBoundFinalistPackageExecutionError, "NO_LIVE_DOWNLOAD_CLAIM"):
            verify(self.root)

    def test_false_noncache_claim_fails_even_when_rehashed(self):
        _, _, _, receipt = self.receipt()
        receipt["environment"]["pip_artifacts_resolved_from_cache"] = False
        self.write_receipt(receipt)
        with self.assertRaisesRegex(CleanRetrievalBoundFinalistPackageExecutionError, "PIP_CACHE"):
            verify(self.root)

    def test_inflated_test_count_fails_even_when_rehashed(self):
        _, _, _, receipt = self.receipt()
        receipt["execution"]["canonical_orchestrated_tests"] = 174
        self.write_receipt(receipt)
        with self.assertRaisesRegex(CleanRetrievalBoundFinalistPackageExecutionError, "CANONICAL_TESTS"):
            verify(self.root)

    def test_missing_repository_retrieval_fails_even_when_rehashed(self):
        _, _, _, receipt = self.receipt()
        receipt["execution"]["public_repository_file_bytes_retrieved"] = False
        self.write_receipt(receipt)
        with self.assertRaisesRegex(CleanRetrievalBoundFinalistPackageExecutionError, "REPOSITORY_BYTES"):
            verify(self.root)

    def test_false_anonymous_raw_claim_fails_even_when_rehashed(self):
        _, _, _, receipt = self.receipt()
        receipt["execution"]["anonymous_raw_http_verified"] = True
        self.write_receipt(receipt)
        with self.assertRaisesRegex(CleanRetrievalBoundFinalistPackageExecutionError, "NO_ANONYMOUS_RAW_HTTP"):
            verify(self.root)

    def test_false_browser_download_claim_fails_even_when_rehashed(self):
        _, _, _, receipt = self.receipt()
        receipt["execution"]["browser_download_button_verified"] = True
        self.write_receipt(receipt)
        with self.assertRaisesRegex(CleanRetrievalBoundFinalistPackageExecutionError, "NO_BROWSER_DOWNLOAD_BUTTON"):
            verify(self.root)

    def test_false_generic_download_claim_fails_even_when_rehashed(self):
        _, _, _, receipt = self.receipt()
        receipt["execution"]["raw_download_verified"] = True
        self.write_receipt(receipt)
        with self.assertRaisesRegex(CleanRetrievalBoundFinalistPackageExecutionError, "NO_RAW_DOWNLOAD"):
            verify(self.root)

    def test_false_biological_claim_fails_even_when_rehashed(self):
        _, _, _, receipt = self.receipt()
        receipt["claim_boundary"]["biological_accuracy_result_created"] = True
        self.write_receipt(receipt)
        with self.assertRaisesRegex(CleanRetrievalBoundFinalistPackageExecutionError, "BOUNDARY_BIOLOGICAL"):
            verify(self.root)

    def test_requirement_drift_fails(self):
        _, _, _, receipt = self.receipt()
        path = self.root / next(iter(receipt["requirements"]))
        path.write_bytes(path.read_bytes() + b"\n")
        with self.assertRaisesRegex(CleanRetrievalBoundFinalistPackageExecutionError, "REQUIREMENTS_HASH"):
            verify(self.root)

    def test_artifact_drift_fails(self):
        _, _, _, receipt = self.receipt()
        path = self.root / next(iter(receipt["artifact_sha256"]))
        path.write_bytes(path.read_bytes() + b"\n")
        with self.assertRaisesRegex(CleanRetrievalBoundFinalistPackageExecutionError, "ARTIFACT_HASH"):
            verify(self.root)


if __name__ == "__main__":
    unittest.main(verbosity=2)
