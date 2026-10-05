import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_verification_chronology import ChronologyError, verify


class VerificationChronologyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path(__file__).resolve().parents[2]

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        index = json.loads((self.source / "evidence/EVIDENCE_INDEX.json").read_text())
        receipt_path = index["verification_chronology"]["path"]
        receipt = json.loads((self.source / receipt_path).read_text())
        paths = ["evidence/EVIDENCE_INDEX.json", receipt_path]
        paths.extend(state["path"] for state in receipt["states"])
        paths.append(receipt["governance_milestone"]["path"])
        paths.extend(receipt["artifact_sha256"])
        for relative in dict.fromkeys(paths):
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.source / relative, target)

    def tearDown(self):
        self.tmp.cleanup()

    def test_current_state_passes(self):
        result = verify(self.root)
        self.assertEqual(result["latest_orchestrated_test_count"], 173)
        self.assertTrue(result["historical_receipts_preserved"])

    def test_latest_count_tamper_fails(self):
        path = self.root / "evidence/EVIDENCE_INDEX.json"
        value = json.loads(path.read_text())
        value["current_release_preflight"]["orchestrated_response_free_tests"] = 168
        path.write_text(json.dumps(value, indent=2) + "\n")
        with self.assertRaisesRegex(ChronologyError, "INDEX_CURRENT_TESTS"):
            verify(self.root)

    def test_historical_receipt_tamper_fails(self):
        index = json.loads((self.root / "evidence/EVIDENCE_INDEX.json").read_text())
        receipt = json.loads((self.root / index["verification_chronology"]["path"]).read_text())
        path = self.root / receipt["states"][0]["path"]
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaisesRegex(ChronologyError, "STATE_HASH"):
            verify(self.root)

    def test_biological_claim_in_chronology_fails(self):
        path = self.root / "docs/VERIFICATION_CHRONOLOGY.md"
        path.write_text(path.read_text().replace("not 173 biological experiments", "173 biological experiments"))
        self._rehash_artifact(path, "docs/VERIFICATION_CHRONOLOGY.md")
        with self.assertRaisesRegex(ChronologyError, "SOFTWARE_BIOLOGY_BOUNDARY"):
            verify(self.root)

    def test_stale_current_report_binding_fails_even_when_rehashed(self):
        path = self.root / "00_REVIEWER_START_HERE.md"
        path.write_text(path.read_text().replace(
            "current technical report is bound to this 173-test canonical state",
            "current technical report remains bound to its earlier 168-test receipt",
        ))
        self._rehash_artifact(path, "00_REVIEWER_START_HERE.md")
        with self.assertRaisesRegex(ChronologyError, "REVIEWER_CURRENT_REPORT_BINDING"):
            verify(self.root)

    def _rehash_artifact(self, path, relative):
        import hashlib
        index_path = self.root / "evidence/EVIDENCE_INDEX.json"
        index = json.loads(index_path.read_text())
        receipt_path = self.root / index["verification_chronology"]["path"]
        receipt = json.loads(receipt_path.read_text())
        receipt["artifact_sha256"][relative] = hashlib.sha256(path.read_bytes()).hexdigest()
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
        index["verification_chronology"]["sha256"] = hashlib.sha256(receipt_path.read_bytes()).hexdigest()
        index_path.write_text(json.dumps(index, indent=2) + "\n")


if __name__ == "__main__":
    unittest.main()
