import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_clean_reviewer_quickstart import CleanQuickstartError, verify


class CleanReviewerQuickstartTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path(__file__).resolve().parents[2]

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        index = json.loads((self.source / "evidence/EVIDENCE_INDEX.json").read_text())
        record = index["clean_reviewer_quickstart"]
        receipt = json.loads((self.source / record["path"]).read_text())
        paths = {
            "evidence/EVIDENCE_INDEX.json",
            record["path"],
            receipt["predecessor"]["path"],
            receipt["documentation"]["path"],
            receipt["verification_documentation"]["path"],
            *receipt["artifact_sha256"],
            *receipt["implementation_sha256"],
        }
        for relative in paths:
            destination = self.root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.source / relative, destination)

    def tearDown(self):
        self.tmp.cleanup()

    def rehash_release(self):
        index_path = self.root / "evidence/EVIDENCE_INDEX.json"
        index = json.loads(index_path.read_text())
        path = self.root / index["clean_reviewer_quickstart"]["path"]
        index["clean_reviewer_quickstart"]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        index_path.write_text(json.dumps(index, indent=2) + "\n")

    def mutate_original(self, mutation):
        index = json.loads((self.root / "evidence/EVIDENCE_INDEX.json").read_text())
        release_path = self.root / index["clean_reviewer_quickstart"]["path"]
        release = json.loads(release_path.read_text())
        original_path = self.root / release["predecessor"]["path"]
        original = json.loads(original_path.read_text())
        mutation(original)
        original_path.write_text(json.dumps(original, indent=2) + "\n")
        release["predecessor"]["sha256"] = hashlib.sha256(original_path.read_bytes()).hexdigest()
        release["artifact_sha256"][release["predecessor"]["path"]] = release["predecessor"]["sha256"]
        release_path.write_text(json.dumps(release, indent=2) + "\n")
        self.rehash_release()

    def test_current_state_passes(self):
        result = verify(self.root)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["orchestrated_response_free_tests"], 173)
        self.assertFalse(result["clean_new_machine_certification"])

    def test_index_receipt_hash_tamper_fails(self):
        index = json.loads((self.root / "evidence/EVIDENCE_INDEX.json").read_text())
        path = self.root / index["clean_reviewer_quickstart"]["path"]
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaisesRegex(CleanQuickstartError, "INDEX_RECEIPT_HASH"):
            verify(self.root)

    def test_predecessor_tamper_fails(self):
        index = json.loads((self.root / "evidence/EVIDENCE_INDEX.json").read_text())
        release = json.loads((self.root / index["clean_reviewer_quickstart"]["path"]).read_text())
        path = self.root / release["predecessor"]["path"]
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaisesRegex(CleanQuickstartError, "PREDECESSOR_HASH"):
            verify(self.root)

    def test_new_machine_promotion_fails_even_when_rehashed(self):
        self.mutate_original(lambda value: value["environment"].__setitem__("new_machine", True))
        with self.assertRaisesRegex(CleanQuickstartError, "NOT_NEW_MACHINE"):
            verify(self.root)

    def test_independent_validation_promotion_fails_even_when_rehashed(self):
        self.mutate_original(lambda value: value["scope"].__setitem__("independent_biological_validation", True))
        with self.assertRaisesRegex(CleanQuickstartError, "SCOPE_INDEPENDENT_BIOLOGICAL_VALIDATION"):
            verify(self.root)

    def test_preflight_count_inflation_fails_even_when_rehashed(self):
        self.mutate_original(lambda value: value["current_release_preflight"].__setitem__("orchestrated_response_free_tests", 174))
        with self.assertRaisesRegex(CleanQuickstartError, "PREFLIGHT_TESTS"):
            verify(self.root)

    def test_requirement_drift_fails(self):
        path = self.root / "requirements.txt"
        path.write_text("numpy==0\n")
        with self.assertRaisesRegex(CleanQuickstartError, "ARTIFACT_HASH|REQUIREMENTS_HASH"):
            verify(self.root)

    def test_accepted_entry_change_fails_even_when_rehashed(self):
        self.mutate_original(lambda value: value["scope"].__setitem__("accepted_kaggle_entry_changed", True))
        with self.assertRaisesRegex(CleanQuickstartError, "SCOPE_ACCEPTED_KAGGLE_ENTRY_CHANGED"):
            verify(self.root)


if __name__ == "__main__":
    unittest.main()
