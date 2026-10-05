import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from verify_external_reviewer_route_availability import (
    ExternalReviewerRouteAvailabilityError,
    verify,
)


ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class ExternalReviewerRouteAvailabilityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        index = json.loads((ROOT / "evidence/EVIDENCE_INDEX.json").read_text())
        record = index["external_reviewer_route_availability"]
        receipt = json.loads((ROOT / record["path"]).read_text())
        for relative in [record["path"], *receipt["artifact_sha256"]]:
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, target)
        index_path = self.root / "evidence/EVIDENCE_INDEX.json"
        index_path.write_text(json.dumps({"external_reviewer_route_availability": record}, indent=2) + "\n")

    def tearDown(self):
        self.temporary.cleanup()

    def receipt(self):
        index_path = self.root / "evidence/EVIDENCE_INDEX.json"
        index = json.loads(index_path.read_text())
        receipt_path = self.root / index["external_reviewer_route_availability"]["path"]
        return index_path, index, receipt_path, json.loads(receipt_path.read_text())

    def write_receipt(self, receipt):
        index_path, index, receipt_path, _ = self.receipt()
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
        index["external_reviewer_route_availability"]["sha256"] = sha(receipt_path)
        index_path.write_text(json.dumps(index, indent=2) + "\n")

    def test_current_state_passes(self):
        self.assertEqual(verify(self.root)["routes_resolved"], 5)

    def test_unrehashable_receipt_tamper_fails(self):
        _, _, receipt_path, receipt = self.receipt()
        receipt["status"] = "FAIL"
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
        with self.assertRaisesRegex(ExternalReviewerRouteAvailabilityError, "INDEX_RECEIPT_HASH"):
            verify(self.root)

    def test_changed_resolved_url_fails_even_when_rehashed(self):
        _, _, _, receipt = self.receipt()
        receipt["routes"]["demo_video"]["resolved_url"] = "https://example.invalid/"
        self.write_receipt(receipt)
        with self.assertRaisesRegex(ExternalReviewerRouteAvailabilityError, "ROUTES"):
            verify(self.root)

    def test_changed_title_fails_even_when_rehashed(self):
        _, _, _, receipt = self.receipt()
        receipt["routes"]["current_report"]["title"] = "wrong"
        self.write_receipt(receipt)
        with self.assertRaisesRegex(ExternalReviewerRouteAvailabilityError, "ROUTES"):
            verify(self.root)

    def test_missing_route_fails_even_when_rehashed(self):
        _, _, _, receipt = self.receipt()
        del receipt["routes"]["reviewer_entrypoint"]
        self.write_receipt(receipt)
        with self.assertRaisesRegex(ExternalReviewerRouteAvailabilityError, "ROUTES"):
            verify(self.root)

    def test_false_playback_claim_fails_even_when_rehashed(self):
        _, _, _, receipt = self.receipt()
        receipt["claim_boundary"]["uninterrupted_video_playback_verified"] = True
        self.write_receipt(receipt)
        with self.assertRaisesRegex(ExternalReviewerRouteAvailabilityError, "BOUNDARY_UNINTERRUPTED"):
            verify(self.root)

    def test_false_future_uptime_claim_fails_even_when_rehashed(self):
        _, _, _, receipt = self.receipt()
        receipt["claim_boundary"]["future_uptime_verified"] = True
        self.write_receipt(receipt)
        with self.assertRaisesRegex(ExternalReviewerRouteAvailabilityError, "BOUNDARY_FUTURE"):
            verify(self.root)

    def test_artifact_drift_fails(self):
        _, _, _, receipt = self.receipt()
        relative = next(iter(receipt["artifact_sha256"]))
        path = self.root / relative
        path.write_bytes(path.read_bytes() + b"\n")
        with self.assertRaisesRegex(ExternalReviewerRouteAvailabilityError, "ARTIFACT_HASH"):
            verify(self.root)


if __name__ == "__main__":
    unittest.main(verbosity=2)
