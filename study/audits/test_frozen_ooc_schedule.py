import csv
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_frozen_ooc_schedule import verify


class FrozenOocScheduleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path(__file__).resolve().parents[2]

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        for directory in ("evidence", "demo", "site", "docs"):
            (self.repo / directory).mkdir()
        evidence_files = [
            "bandwidth_successor_20261003.json",
            "frozen_ooc_execution_schedule_20261003.json",
            "frozen_bandwidth_orientation_A_plan_20261003.json",
            "frozen_bandwidth_orientation_B_plan_20261003.json",
            "prospective_ooc_binding_template_A_20261003.csv",
            "prospective_ooc_binding_template_B_20261003.csv",
        ]
        for name in evidence_files:
            shutil.copy2(self.source / "evidence" / name, self.repo / "evidence" / name)
        shutil.copy2(self.source / "demo/ooc_feasibility.py", self.repo / "demo/ooc_feasibility.py")
        shutil.copy2(self.source / "site/frozen_schedule.js", self.repo / "site/frozen_schedule.js")
        shutil.copy2(self.source / "site/index.html", self.repo / "site/index.html")
        shutil.copy2(
            self.source / "docs/FROZEN_OOC_EXECUTION_MANIFEST.md",
            self.repo / "docs/FROZEN_OOC_EXECUTION_MANIFEST.md",
        )
        shutil.copy2(
            self.source / "docs/KAGGLE_WRITEUP.md",
            self.repo / "docs/KAGGLE_WRITEUP.md",
        )

    def tearDown(self):
        self.tmp.cleanup()

    def summary(self):
        path = self.repo / "evidence/frozen_ooc_execution_schedule_20261003.json"
        return path, json.loads(path.read_text())

    def save_summary(self, value):
        path = self.repo / "evidence/frozen_ooc_execution_schedule_20261003.json"
        path.write_text(json.dumps(value, indent=2) + "\n")

    @staticmethod
    def digest(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def test_current_schedule_and_public_surface_pass(self):
        result = verify(self.repo / "evidence", self.repo)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["public_schedule_rows"], 64)
        self.assertTrue(result["public_site_schedule_exact"])
        self.assertTrue(result["manifest_table_exact"])
        self.assertEqual(result["transport_escape_literals"], 0)

    def test_site_schedule_copy_cannot_drift_from_plan(self):
        path = self.repo / "site/frozen_schedule.js"
        path.write_text(path.read_text().replace('"dose":"1000"', '"dose":"999"', 1))
        with self.assertRaisesRegex(ValueError, "SITE_SCHEDULE_MISMATCH"):
            verify(self.repo / "evidence", self.repo)

    def test_literal_transport_escape_is_rejected(self):
        path = self.repo / "docs/KAGGLE_WRITEUP.md"
        path.write_text(path.read_text() + "\\ntransport artifact\n")
        with self.assertRaisesRegex(ValueError, "TRANSPORT_ESCAPE_WRITEUP"):
            verify(self.repo / "evidence", self.repo)

    def test_claim_boundary_cannot_be_promoted(self):
        _, summary = self.summary()
        summary["prospective_experiment_executed"] = True
        self.save_summary(summary)
        with self.assertRaisesRegex(ValueError, "CLAIM_SCOPE"):
            verify(self.repo / "evidence", self.repo)

    def test_ab_complementarity_survives_paired_hash_updates(self):
        plan_path = self.repo / "evidence/frozen_bandwidth_orientation_B_plan_20261003.json"
        plan = json.loads(plan_path.read_text())
        for index in (0, 1):
            row = plan["measurements"][index]
            row["plate"] = "p1" if row["plate"] == "p2" else "p2"
            row["plate_instance"] = "PROSPECTIVE_B_" + row["plate"].upper()
        plan_path.write_text(json.dumps(plan, indent=2) + "\n")

        csv_path = self.repo / "evidence/prospective_ooc_binding_template_B_20261003.csv"
        with csv_path.open(newline="") as handle:
            rows = list(csv.DictReader(handle))
            fields = list(rows[0])
        for index in (0, 1):
            rows[index]["source_plate"] = plan["measurements"][index]["plate"]
            rows[index]["source_plate_instance"] = plan["measurements"][index]["plate_instance"]
        with csv_path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

        _, summary = self.summary()
        summary["orientations"]["B"]["plan_sha256"] = self.digest(plan_path)
        summary["orientations"]["B"]["binding_template_sha256"] = self.digest(csv_path)
        self.save_summary(summary)
        with self.assertRaisesRegex(ValueError, "AB_NOT_COMPLEMENTARY"):
            verify(self.repo / "evidence", self.repo)


if __name__ == "__main__":
    unittest.main(verbosity=2)
