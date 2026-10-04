import json
from pathlib import Path
import shutil
import tempfile
import unittest

from verify_nested_bandwidth_evidence import NestedBandwidthEvidenceError, verify


class NestedBandwidthEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.source = Path(__file__).resolve().parents[2]
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        for relative in (
            "evidence/nested_bandwidth_selection_20261004.json",
            "docs/NESTED_BANDWIDTH_EVALUATION.md",
            "docs/BANDWIDTH_SUCCESSOR.md",
            "study/nested_bandwidth_selection/PROTOCOL.md",
            "study/nested_bandwidth_selection/FREEZE.json",
            "study/nested_bandwidth_selection/run_study.py",
            "study/nested_bandwidth_selection/verify_study.py",
            "study/nested_bandwidth_selection/test_selection.py",
            "study/audits/verify_nested_bandwidth_evidence.py",
            "study/audits/test_nested_bandwidth_evidence.py",
        ):
            destination = self.root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.source / relative, destination)

    def tearDown(self):
        self.temp.cleanup()

    def mutate(self, function):
        path = self.root / "evidence/nested_bandwidth_selection_20261004.json"
        value = json.loads(path.read_text())
        function(value)
        path.write_text(json.dumps(value, indent=2) + "\n")

    def test_valid(self):
        self.assertEqual(verify(self.root)["status"], "PASS")

    def test_rejects_metric_change(self):
        self.mutate(lambda value: value["metrics"]["nested"].update(mse=0.0))
        with self.assertRaises(NestedBandwidthEvidenceError):
            verify(self.root)

    def test_rejects_selection_change(self):
        self.mutate(lambda value: value["foldwise_selections"][0].update(bandwidth=1.0))
        with self.assertRaises(NestedBandwidthEvidenceError):
            verify(self.root)

    def test_rejects_independent_validation_claim(self):
        self.mutate(lambda value: value["claim_boundary"].update(independent_validation=True))
        with self.assertRaises(NestedBandwidthEvidenceError):
            verify(self.root)

    def test_rejects_private_publication_claim(self):
        self.mutate(lambda value: value["verification"].update(
            private_prediction_arrays_published=True))
        with self.assertRaises(NestedBandwidthEvidenceError):
            verify(self.root)

    def test_rejects_artifact_tamper(self):
        path = self.root / "docs/NESTED_BANDWIDTH_EVALUATION.md"
        path.write_text(path.read_text() + "tamper\n")
        with self.assertRaises(NestedBandwidthEvidenceError):
            verify(self.root)


if __name__ == "__main__":
    unittest.main()
