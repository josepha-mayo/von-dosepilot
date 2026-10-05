import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.parse import unquote, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_reviewer_routes import AUDITED_SURFACES, GITHUB_BLOB_PREFIX, MARKDOWN_LINK, split_markdown_target
from verify_reviewer_trace_discovery import ReviewerTraceDiscoveryError, verify


class ReviewerTraceDiscoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path(__file__).resolve().parents[2]

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        index = json.loads((self.source / "evidence/EVIDENCE_INDEX.json").read_text())
        receipt_relative = index["reviewer_route_integrity"]["path"]
        receipt = json.loads((self.source / receipt_relative).read_text())
        paths = {
            "evidence/EVIDENCE_INDEX.json",
            receipt_relative,
            receipt["predecessor"]["path"],
            receipt["live_demo_trace"]["path"],
            receipt["downloaded_trace_verifier"]["path"],
            receipt["finalist_package_preflight"]["path"],
            receipt["clean_finalist_package_execution"]["path"],
            receipt["cooptimized_control"]["path"],
            receipt["current_finalist_rubric_evidence"]["path"],
            *receipt["artifact_sha256"],
            *AUDITED_SURFACES,
        }
        directories = set()
        for relative in AUDITED_SURFACES:
            source = self.source / relative
            for match in MARKDOWN_LINK.finditer(source.read_text()):
                path_part, _ = split_markdown_target(match.group(1))
                parsed = urlsplit(path_part)
                if parsed.scheme in ("http", "https"):
                    if parsed.netloc == "github.com" and parsed.path.startswith(GITHUB_BLOB_PREFIX):
                        paths.add(unquote(parsed.path[len(GITHUB_BLOB_PREFIX):]))
                elif path_part:
                    target = (source.parent / path_part).resolve()
                    relative_target = target.relative_to(self.source)
                    if target.is_dir():
                        directories.add(str(relative_target))
                    else:
                        paths.add(str(relative_target))
        for relative in paths:
            destination = self.root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.source / relative, destination)
        for relative in directories:
            (self.root / relative).mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self.tmp.cleanup()

    def receipt(self):
        index = json.loads((self.root / "evidence/EVIDENCE_INDEX.json").read_text())
        path = self.root / index["reviewer_route_integrity"]["path"]
        return index, path, json.loads(path.read_text())

    def rehash_receipt(self, receipt):
        index, path, _ = self.receipt()
        path.write_text(json.dumps(receipt, indent=2) + "\n")
        index["reviewer_route_integrity"]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        (self.root / "evidence/EVIDENCE_INDEX.json").write_text(json.dumps(index, indent=2) + "\n")

    def rehash_surface(self, relative, receipt):
        receipt["audited_surfaces"][relative] = hashlib.sha256((self.root / relative).read_bytes()).hexdigest()
        self.rehash_receipt(receipt)

    def test_current_state_passes(self):
        result = verify(self.root)
        self.assertEqual(result["status"], "PASS")
        self.assertTrue(result["downloadable_trace_linked"])
        self.assertTrue(result["offline_downloaded_trace_verifier_linked"])
        self.assertTrue(result["finalist_package_preflight_linked"])
        self.assertTrue(result["clean_finalist_package_execution_linked"])
        self.assertTrue(result["cooptimized_control_linked"])
        self.assertTrue(result["current_finalist_rubric_evidence_linked"])
        self.assertFalse(result["current_finalist_rubric_self_score_assigned"])
        self.assertFalse(result["current_finalist_probability_estimated"])
        self.assertEqual(result["cooptimized_control_decision"], "REJECT_RETAIN_BANDWIDTH07")

    def test_receipt_tamper_fails(self):
        _, path, _ = self.receipt()
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaisesRegex(ReviewerTraceDiscoveryError, "INDEX_RECEIPT_HASH"):
            verify(self.root)

    def test_predecessor_tamper_fails(self):
        _, _, receipt = self.receipt()
        path = self.root / receipt["predecessor"]["path"]
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaisesRegex(ReviewerTraceDiscoveryError, "PREDECESSOR_HASH"):
            verify(self.root)

    def test_readme_trace_link_removal_fails_even_when_rehashed(self):
        _, _, receipt = self.receipt()
        path = self.root / "README.md"
        path.write_text(path.read_text().replace("docs/LIVE_DEMO_TRACE_EXPORT.md", "docs/FINALIST_AUDIT.md", 1))
        self.rehash_surface("README.md", receipt)
        with self.assertRaisesRegex(ReviewerTraceDiscoveryError, "README_TRACE_LINK"):
            verify(self.root)

    def test_reviewer_boundary_removal_fails_even_when_rehashed(self):
        _, _, receipt = self.receipt()
        path = self.root / "00_REVIEWER_START_HERE.md"
        path.write_text(path.read_text().replace("no raw readings or model outputs", "opaque trace payload", 1))
        self.rehash_surface("00_REVIEWER_START_HERE.md", receipt)
        with self.assertRaisesRegex(ReviewerTraceDiscoveryError, "REVIEWER_TRACE_BOUNDARY"):
            verify(self.root)

    def test_writeup_offline_trace_link_removal_fails_even_when_rehashed(self):
        _, _, receipt = self.receipt()
        path = self.root / "docs/KAGGLE_WRITEUP.md"
        path.write_text(path.read_text().replace("docs/VERIFY_DOWNLOADED_TRACE.md", "docs/FINALIST_AUDIT.md", 1))
        self.rehash_surface("docs/KAGGLE_WRITEUP.md", receipt)
        with self.assertRaisesRegex(ReviewerTraceDiscoveryError, "WRITEUP_OFFLINE_TRACE_LINK"):
            verify(self.root)

    def test_writeup_finalist_preflight_link_removal_fails_even_when_rehashed(self):
        _, _, receipt = self.receipt()
        path = self.root / "docs/KAGGLE_WRITEUP.md"
        path.write_text(path.read_text().replace("docs/FINALIST_PACKAGE_PREFLIGHT.md", "docs/FINALIST_AUDIT.md", 1))
        self.rehash_surface("docs/KAGGLE_WRITEUP.md", receipt)
        with self.assertRaisesRegex(ReviewerTraceDiscoveryError, "WRITEUP_FINALIST_PREFLIGHT_LINK"):
            verify(self.root)

    def test_writeup_clean_package_link_removal_fails_even_when_rehashed(self):
        _, _, receipt = self.receipt()
        path = self.root / "docs/KAGGLE_WRITEUP.md"
        path.write_text(path.read_text().replace("docs/CLEAN_FINALIST_PACKAGE_EXECUTION.md", "docs/FINALIST_AUDIT.md", 1))
        self.rehash_surface("docs/KAGGLE_WRITEUP.md", receipt)
        with self.assertRaisesRegex(ReviewerTraceDiscoveryError, "WRITEUP_CLEAN_PACKAGE_LINK"):
            verify(self.root)

    def test_nonportable_writeup_link_fails_even_when_rehashed(self):
        _, _, receipt = self.receipt()
        path = self.root / "docs/KAGGLE_WRITEUP.md"
        path.write_text(path.read_text() + "\n[bad](../README.md)\n")
        self.rehash_surface("docs/KAGGLE_WRITEUP.md", receipt)
        with self.assertRaisesRegex(ReviewerTraceDiscoveryError, "KAGGLE_WRITEUP_NONPORTABLE_LINK"):
            verify(self.root)

    def test_readme_nested_link_removal_fails_even_when_rehashed(self):
        _, _, receipt = self.receipt()
        path = self.root / "README.md"
        path.write_text(path.read_text().replace("docs/NESTED_BANDWIDTH_EVALUATION.md", "docs/BANDWIDTH_SUCCESSOR.md", 1))
        self.rehash_surface("README.md", receipt)
        with self.assertRaisesRegex(ReviewerTraceDiscoveryError, "README_NESTED_LINK"):
            verify(self.root)

    def test_readme_current_rubric_link_removal_fails_even_when_rehashed(self):
        _, _, receipt = self.receipt()
        path = self.root / "README.md"
        text = path.read_text().replace("docs/FINALIST_RUBRIC_EVIDENCE_CURRENT.md", "docs/FINALIST_RUBRIC_EVIDENCE.md", 1)
        path.write_text(text)
        self.rehash_surface("README.md", receipt)
        with self.assertRaisesRegex(ReviewerTraceDiscoveryError, "README_CURRENT_RUBRIC_LINK"):
            verify(self.root)

    def test_writeup_current_rubric_link_removal_fails_even_when_rehashed(self):
        _, _, receipt = self.receipt()
        path = self.root / "docs/KAGGLE_WRITEUP.md"
        text = path.read_text().replace("docs/FINALIST_RUBRIC_EVIDENCE_CURRENT.md", "docs/FINALIST_RUBRIC_EVIDENCE.md", 1)
        path.write_text(text)
        self.rehash_surface("docs/KAGGLE_WRITEUP.md", receipt)
        with self.assertRaisesRegex(ReviewerTraceDiscoveryError, "WRITEUP_CURRENT_RUBRIC_LINK"):
            verify(self.root)

    def test_current_rubric_self_score_tamper_fails(self):
        _, _, receipt = self.receipt()
        path = self.root / receipt["current_finalist_rubric_evidence"]["path"]
        data = json.loads(path.read_text())
        data["rubric"]["combined_self_score"] = 100
        path.write_text(json.dumps(data, indent=2) + "\n")
        with self.assertRaisesRegex(ReviewerTraceDiscoveryError, "ARTIFACT_HASH"):
            verify(self.root)

    def test_reviewer_nested_link_removal_fails_even_when_rehashed(self):
        _, _, receipt = self.receipt()
        path = self.root / "00_REVIEWER_START_HERE.md"
        path.write_text(path.read_text().replace("docs/NESTED_BANDWIDTH_EVALUATION.md", "docs/BANDWIDTH_SUCCESSOR.md", 1))
        self.rehash_surface("00_REVIEWER_START_HERE.md", receipt)
        with self.assertRaisesRegex(ReviewerTraceDiscoveryError, "REVIEWER_NESTED_LINK"):
            verify(self.root)

    def test_writeup_nested_link_removal_fails_even_when_rehashed(self):
        _, _, receipt = self.receipt()
        path = self.root / "docs/KAGGLE_WRITEUP.md"
        path.write_text(path.read_text().replace("docs/NESTED_BANDWIDTH_EVALUATION.md", "docs/BANDWIDTH_SUCCESSOR.md"))
        self.rehash_surface("docs/KAGGLE_WRITEUP.md", receipt)
        with self.assertRaisesRegex(ReviewerTraceDiscoveryError, "WRITEUP_NESTED_LINK"):
            verify(self.root)

    def test_live_trace_receipt_tamper_fails(self):
        _, _, receipt = self.receipt()
        path = self.root / receipt["live_demo_trace"]["path"]
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaisesRegex(ReviewerTraceDiscoveryError, "ARTIFACT_HASH|LIVE_TRACE_RECEIPT_HASH"):
            verify(self.root)

    def test_false_export_boundary_fails_even_when_rehashed(self):
        _, _, receipt = self.receipt()
        receipt["claim_boundary"]["export_contains_raw_readings_or_outputs"] = True
        self.rehash_receipt(receipt)
        with self.assertRaisesRegex(ReviewerTraceDiscoveryError, "BOUNDARY_EXPORT_CONTAINS_RAW_READINGS_OR_OUTPUTS"):
            verify(self.root)

    def test_false_kaggle_change_fails_even_when_rehashed(self):
        _, _, receipt = self.receipt()
        receipt["claim_boundary"]["accepted_kaggle_entry_changed"] = True
        self.rehash_receipt(receipt)
        with self.assertRaisesRegex(ReviewerTraceDiscoveryError, "BOUNDARY_ACCEPTED_KAGGLE_ENTRY_CHANGED"):
            verify(self.root)

    def test_current_report_clean_package_claim_tamper_fails_even_when_rehashed(self):
        _, _, receipt = self.receipt()
        report_path = self.root / receipt["current_report"]["path"]
        report = json.loads(report_path.read_text())
        report["claim_checks"]["clean_finalist_package_checks"] = 7
        report_path.write_text(json.dumps(report, indent=2) + "\n")
        receipt["current_report"]["sha256"] = hashlib.sha256(report_path.read_bytes()).hexdigest()
        receipt["artifact_sha256"][receipt["current_report"]["path"]] = receipt["current_report"]["sha256"]
        self.rehash_receipt(receipt)
        with self.assertRaisesRegex(ReviewerTraceDiscoveryError, "CURRENT_REPORT_CLEAN_PACKAGE_CHECKS"):
            verify(self.root)

    def test_stale_current_report_test_binding_fails_even_when_rehashed(self):
        _, _, receipt = self.receipt()
        path = self.root / "00_REVIEWER_START_HERE.md"
        path.write_text(path.read_text().replace(
            "current technical report is bound to this 173-test canonical state",
            "current technical report remains bound to its earlier 168-test receipt",
        ))
        self.rehash_surface("00_REVIEWER_START_HERE.md", receipt)
        with self.assertRaisesRegex(ReviewerTraceDiscoveryError, "REVIEWER_CURRENT_REPORT_BINDING"):
            verify(self.root)


if __name__ == "__main__":
    unittest.main()
