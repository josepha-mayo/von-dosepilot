import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from verify_clean_scientific_successor_finalist_package_execution import (
    CleanScientificSuccessorFinalistPackageExecutionError,
    verify,
)


ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class CleanScientificSuccessorFinalistPackageExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        index = json.loads((ROOT / "evidence/EVIDENCE_INDEX.json").read_text())
        record = index["clean_scientific_successor_finalist_package_execution"]
        receipt = json.loads((ROOT / record["path"]).read_text())
        paths = [
            record["path"],
            receipt["predecessor"]["path"],
            *receipt["requirements"],
            *receipt["artifact_sha256"],
        ]
        for relative in paths:
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, target)
        index_path = self.root / "evidence/EVIDENCE_INDEX.json"
        index_path.write_text(
            json.dumps(
                {"clean_scientific_successor_finalist_package_execution": record},
                indent=2,
            )
            + "\n"
        )

    def tearDown(self):
        self.temporary.cleanup()

    def receipt(self):
        index_path = self.root / "evidence/EVIDENCE_INDEX.json"
        index = json.loads(index_path.read_text())
        receipt_path = self.root / index[
            "clean_scientific_successor_finalist_package_execution"
        ]["path"]
        return index_path, index, receipt_path, json.loads(receipt_path.read_text())

    def write_receipt(self, receipt):
        index_path, index, receipt_path, _ = self.receipt()
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
        index["clean_scientific_successor_finalist_package_execution"][
            "sha256"
        ] = sha(receipt_path)
        index_path.write_text(json.dumps(index, indent=2) + "\n")

    def test_current_state_passes(self):
        self.assertEqual(verify(self.root)["status"], "PASS")

    def test_unrehashable_receipt_tamper_fails(self):
        _, _, receipt_path, receipt = self.receipt()
        receipt["status"] = "FAIL"
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
        with self.assertRaisesRegex(
            CleanScientificSuccessorFinalistPackageExecutionError,
            "INDEX_RECEIPT_HASH",
        ):
            verify(self.root)

    def test_wrong_source_tree_fails_even_when_rehashed(self):
        _, _, _, receipt = self.receipt()
        receipt["source"]["public_tree"] = "0" * 40
        self.write_receipt(receipt)
        with self.assertRaisesRegex(
            CleanScientificSuccessorFinalistPackageExecutionError, "SOURCE_TREE"
        ):
            verify(self.root)

    def test_false_public_clone_claim_fails_even_when_rehashed(self):
        _, _, _, receipt = self.receipt()
        receipt["source"]["fresh_public_clone"] = True
        self.write_receipt(receipt)
        with self.assertRaisesRegex(
            CleanScientificSuccessorFinalistPackageExecutionError,
            "NOT_PUBLIC_CLONE",
        ):
            verify(self.root)

    def test_false_live_download_claim_fails_even_when_rehashed(self):
        _, _, _, receipt = self.receipt()
        receipt["environment"]["live_dependency_download_claimed"] = True
        self.write_receipt(receipt)
        with self.assertRaisesRegex(
            CleanScientificSuccessorFinalistPackageExecutionError,
            "NO_LIVE_DOWNLOAD_CLAIM",
        ):
            verify(self.root)

    def test_false_noncache_claim_fails_even_when_rehashed(self):
        _, _, _, receipt = self.receipt()
        receipt["environment"]["pip_artifacts_resolved_from_cache"] = False
        self.write_receipt(receipt)
        with self.assertRaisesRegex(
            CleanScientificSuccessorFinalistPackageExecutionError, "PIP_CACHE"
        ):
            verify(self.root)

    def test_inflated_test_count_fails_even_when_rehashed(self):
        _, _, _, receipt = self.receipt()
        receipt["execution"]["canonical_orchestrated_tests"] = 174
        self.write_receipt(receipt)
        with self.assertRaisesRegex(
            CleanScientificSuccessorFinalistPackageExecutionError,
            "CANONICAL_TESTS",
        ):
            verify(self.root)

    def test_removed_scientific_rubric_check_fails_even_when_rehashed(self):
        _, _, _, receipt = self.receipt()
        receipt["execution"]["current_scientific_successor_rubric_checked"] = False
        self.write_receipt(receipt)
        with self.assertRaisesRegex(
            CleanScientificSuccessorFinalistPackageExecutionError,
            "SCIENTIFIC_RUBRIC",
        ):
            verify(self.root)

    def test_candidate_mse_drift_fails_even_when_rehashed(self):
        _, _, _, receipt = self.receipt()
        receipt["execution"]["candidate_mse"] = 0.001
        self.write_receipt(receipt)
        with self.assertRaisesRegex(
            CleanScientificSuccessorFinalistPackageExecutionError, "CANDIDATE_MSE"
        ):
            verify(self.root)

    def test_false_operational_replacement_fails_even_when_rehashed(self):
        _, _, _, receipt = self.receipt()
        receipt["execution"]["operational_demo_baseline_replaced"] = True
        self.write_receipt(receipt)
        with self.assertRaisesRegex(
            CleanScientificSuccessorFinalistPackageExecutionError,
            "NO_OPERATIONAL_REPLACEMENT",
        ):
            verify(self.root)

    def test_false_independent_validation_fails_even_when_rehashed(self):
        _, _, _, receipt = self.receipt()
        receipt["execution"]["independent_validation"] = True
        self.write_receipt(receipt)
        with self.assertRaisesRegex(
            CleanScientificSuccessorFinalistPackageExecutionError,
            "NO_VALIDATION",
        ):
            verify(self.root)

    def test_false_biological_claim_fails_even_when_rehashed(self):
        _, _, _, receipt = self.receipt()
        receipt["claim_boundary"]["biological_accuracy_result_created"] = True
        self.write_receipt(receipt)
        with self.assertRaisesRegex(
            CleanScientificSuccessorFinalistPackageExecutionError,
            "BOUNDARY_BIOLOGICAL",
        ):
            verify(self.root)

    def test_requirement_drift_fails(self):
        _, _, _, receipt = self.receipt()
        path = self.root / next(iter(receipt["requirements"]))
        path.write_bytes(path.read_bytes() + b"\n")
        with self.assertRaisesRegex(
            CleanScientificSuccessorFinalistPackageExecutionError,
            "REQUIREMENTS_HASH",
        ):
            verify(self.root)

    def test_artifact_drift_fails(self):
        _, _, _, receipt = self.receipt()
        path = self.root / next(iter(receipt["artifact_sha256"]))
        path.write_bytes(path.read_bytes() + b"\n")
        with self.assertRaisesRegex(
            CleanScientificSuccessorFinalistPackageExecutionError,
            "ARTIFACT_HASH",
        ):
            verify(self.root)


if __name__ == "__main__":
    unittest.main(verbosity=2)
