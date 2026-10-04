import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.parse import unquote, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_reviewer_routes import (
    AUDITED_SURFACES,
    GITHUB_BLOB_PREFIX,
    MARKDOWN_LINK,
    ReviewerRouteError,
    split_markdown_target,
    verify,
)


class ReviewerRouteTests(unittest.TestCase):
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
            receipt["documentation"]["path"],
            *receipt["implementation_sha256"],
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

    def rehash_surface_and_receipt(self, relative):
        index_path = self.root / "evidence/EVIDENCE_INDEX.json"
        index = json.loads(index_path.read_text())
        receipt_path = self.root / index["reviewer_route_integrity"]["path"]
        receipt = json.loads(receipt_path.read_text())
        receipt["audited_surfaces"][relative] = hashlib.sha256((self.root / relative).read_bytes()).hexdigest()
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
        index["reviewer_route_integrity"]["sha256"] = hashlib.sha256(receipt_path.read_bytes()).hexdigest()
        index_path.write_text(json.dumps(index, indent=2) + "\n")

    def rehash_receipt(self):
        index_path = self.root / "evidence/EVIDENCE_INDEX.json"
        index = json.loads(index_path.read_text())
        receipt_path = self.root / index["reviewer_route_integrity"]["path"]
        index["reviewer_route_integrity"]["sha256"] = hashlib.sha256(receipt_path.read_bytes()).hexdigest()
        index_path.write_text(json.dumps(index, indent=2) + "\n")

    def test_current_state_passes(self):
        result = verify(self.root)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["network_requests"], 0)
        self.assertFalse(result["external_playback_verified"])

    def test_index_receipt_hash_tamper_fails(self):
        index = json.loads((self.root / "evidence/EVIDENCE_INDEX.json").read_text())
        path = self.root / index["reviewer_route_integrity"]["path"]
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaisesRegex(ReviewerRouteError, "INDEX_RECEIPT_HASH"):
            verify(self.root)

    def test_missing_local_target_fails(self):
        path = self.root / "README.md"
        path.write_text(path.read_text().replace("docs/FINALIST_AUDIT.md", "docs/DOES_NOT_EXIST.md", 1))
        self.rehash_surface_and_receipt("README.md")
        with self.assertRaisesRegex(ReviewerRouteError, "MISSING_LOCAL_TARGET"):
            verify(self.root)

    def test_outside_repo_target_fails(self):
        path = self.root / "README.md"
        path.write_text(path.read_text() + "\n[escape](../outside.md)\n")
        self.rehash_surface_and_receipt("README.md")
        with self.assertRaisesRegex(ReviewerRouteError, "LOCAL_TARGET_OUTSIDE_REPO"):
            verify(self.root)

    def test_missing_github_master_target_fails(self):
        path = self.root / "docs/KAGGLE_WRITEUP.md"
        path.write_text(path.read_text().replace("docs/FINALIST_AUDIT.md", "docs/DOES_NOT_EXIST.md", 1))
        self.rehash_surface_and_receipt("docs/KAGGLE_WRITEUP.md")
        with self.assertRaisesRegex(ReviewerRouteError, "MISSING_GITHUB_TARGET"):
            verify(self.root)

    def test_missing_anchor_fails(self):
        path = self.root / "README.md"
        path.write_text(path.read_text().replace("#1-new-acquisition-experiment-rejected", "#missing-anchor", 1))
        self.rehash_surface_and_receipt("README.md")
        with self.assertRaisesRegex(ReviewerRouteError, "MISSING_ANCHOR"):
            verify(self.root)

    def test_required_video_removal_fails(self):
        for relative in ("README.md", "00_REVIEWER_START_HERE.md", "docs/KAGGLE_WRITEUP.md"):
            path = self.root / relative
            path.write_text(path.read_text().replace("https://youtu.be/QeOGJIgx378", "https://example.invalid/video"))
            self.rehash_surface_and_receipt(relative)
        with self.assertRaisesRegex(ReviewerRouteError, "REQUIRED_URL_MISSING: demo_video"):
            verify(self.root)

    def test_playback_claim_promotion_fails_even_when_rehashed(self):
        index = json.loads((self.root / "evidence/EVIDENCE_INDEX.json").read_text())
        receipt_path = self.root / index["reviewer_route_integrity"]["path"]
        receipt = json.loads(receipt_path.read_text())
        receipt["claim_boundary"]["external_playback_verified"] = True
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
        self.rehash_receipt()
        with self.assertRaisesRegex(ReviewerRouteError, "BOUNDARY_EXTERNAL_PLAYBACK_VERIFIED"):
            verify(self.root)


if __name__ == "__main__":
    unittest.main()
