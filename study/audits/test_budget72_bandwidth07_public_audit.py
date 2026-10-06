import json
import shutil
import tempfile
import unittest
from pathlib import Path

from verify_budget72_bandwidth07_public_audit import Budget72PublicAuditError, verify


ROOT = Path(__file__).resolve().parents[2]


class Budget72PublicAuditTests(unittest.TestCase):
    def fixture(self, destination: Path) -> Path:
        audit_path = "evidence/budget72_bandwidth07_public_audit_20261006.json"
        audit = json.loads((ROOT / audit_path).read_text(encoding="utf-8"))
        paths = {audit_path}
        paths.update(item["path"] for item in audit["artifacts"].values())
        freeze = json.loads((ROOT / audit["artifacts"]["freeze_receipt"]["path"]).read_text(encoding="utf-8"))
        paths.update(freeze["source_sha256"])
        paths.update(freeze["dependency_sha256"])
        for relative_path in paths:
            source = ROOT / relative_path
            target = destination / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        return destination

    def mutate_audit(self, root: Path, mutation) -> None:
        path = root / "evidence/budget72_bandwidth07_public_audit_20261006.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        mutation(data)
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    def test_current_passes_with_tail_rejection(self):
        result = verify(ROOT)
        self.assertEqual(result["status"], "PASS")
        self.assertFalse(result["tail_gate_pass"])
        self.assertEqual(result["promotion_decision"], "REJECT_PRESERVE")

    def test_false_tail_pass_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.fixture(Path(directory))
            self.mutate_audit(root, lambda data: data["versus_current_64_well_scientific_successor"].update(tail_gate_pass=True))
            with self.assertRaises(Budget72PublicAuditError):
                verify(root)

    def test_false_promotion_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.fixture(Path(directory))
            self.mutate_audit(root, lambda data: data["decision"].update(candidate_promotion_allowed=True))
            with self.assertRaises(Budget72PublicAuditError):
                verify(root)

    def test_false_independent_replay_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.fixture(Path(directory))
            self.mutate_audit(root, lambda data: data["public_reproducibility"].update(independent_numerical_reproduction_claimed=True))
            with self.assertRaises(Budget72PublicAuditError):
                verify(root)

    def test_false_validation_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.fixture(Path(directory))
            self.mutate_audit(root, lambda data: data.update(independent_validation=True))
            with self.assertRaises(Budget72PublicAuditError):
                verify(root)

    def test_candidate_metric_tamper_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.fixture(Path(directory))
            path = root / "evidence/budget72_bandwidth07_residual_20261006.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["candidate"]["mse"] += 1e-6
            path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            with self.assertRaises(Budget72PublicAuditError):
                verify(root)

    def test_freeze_source_tamper_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.fixture(Path(directory))
            path = root / "study/budget72_bandwidth07_residual/PROTOCOL.md"
            path.write_text(path.read_text(encoding="utf-8") + "\ntamper\n", encoding="utf-8")
            with self.assertRaises(Budget72PublicAuditError):
                verify(root)

    def test_document_boundary_tamper_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.fixture(Path(directory))
            path = root / "docs/BUDGET72_BANDWIDTH07_PUBLIC_AUDIT_20261006.md"
            path.write_text(path.read_text(encoding="utf-8").replace("rejected for promotion", "promoted"), encoding="utf-8")
            with self.assertRaises(Budget72PublicAuditError):
                verify(root)

    def test_false_official_score_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.fixture(Path(directory))
            self.mutate_audit(root, lambda data: data.update(official_score=0.123))
            with self.assertRaises(Budget72PublicAuditError):
                verify(root)


if __name__ == "__main__":
    unittest.main(verbosity=2)
