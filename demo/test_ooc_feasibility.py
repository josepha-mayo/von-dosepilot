import copy
import json
import tempfile
import unittest
from pathlib import Path

import dosepilot
import ooc_feasibility as ooc


HERE = Path(__file__).resolve().parent


class OocFeasibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        model_bytes = (HERE / "model.json").read_bytes()
        cls.model = json.loads(model_bytes)
        inventory = json.loads((HERE / "inventory.json").read_text())
        cls.plan = dosepilot.make_plan(
            cls.model,
            dosepilot.raw_hash(model_bytes),
            inventory,
            dosepilot.raw_hash(dosepilot.canonical(inventory)),
            64,
            "OOC_SYNTHETIC_TEST_NONCE",
        )

    def fixture(self):
        return ooc.make_synthetic_fixture(self.plan)

    def test_compatible_manifest_has_exact_resource_union(self):
        manifest = ooc.compile_manifest(self.plan, self.fixture())
        self.assertEqual(manifest["treatment_action_count"], 64)
        self.assertEqual(manifest["distinct_treatment_resources"], 64)
        self.assertEqual(manifest["separate_control_resource_count"], 2)
        self.assertFalse(manifest["controls_in_treatment_budget"])
        self.assertEqual(manifest["status"], "CONSTRAINT_COMPATIBLE_WITH_DECLARED_INVENTORY")

    def test_manifest_is_deterministic(self):
        a = ooc.compile_manifest(self.plan, self.fixture())
        b = ooc.compile_manifest(copy.deepcopy(self.plan), copy.deepcopy(self.fixture()))
        self.assertEqual(a, b)
        self.assertEqual(a["manifest_payload_sha256"], b["manifest_payload_sha256"])
        payload = dict(a)
        digest = payload.pop("manifest_payload_sha256")
        self.assertEqual(digest, ooc._sha256(payload))

    def test_plan_budget_and_controls_commitment_cannot_be_tampered(self):
        plan = copy.deepcopy(self.plan)
        plan["treatment_wells"] = 999
        plan["controls_included"] = True
        with self.assertRaisesRegex(ooc.FeasibilityError, "PLAN_BUDGET_OR_CONTROL_COMMITMENT"):
            ooc.compile_manifest(plan, self.fixture())

    def test_plan_plate_counts_cannot_be_tampered(self):
        plan = copy.deepcopy(self.plan)
        plan["plate_counts"] = {"p1": 64, "p2": 0}
        with self.assertRaisesRegex(ooc.FeasibilityError, "PLAN_PLATE_COUNT_MISMATCH"):
            ooc.compile_manifest(plan, self.fixture())

    def test_duplicate_native_id_is_rejected(self):
        plan = copy.deepcopy(self.plan)
        plan["measurements"][1]["native_id"] = plan["measurements"][0]["native_id"]
        with self.assertRaisesRegex(ooc.FeasibilityError, "DUPLICATE_NATIVE_ID"):
            ooc.compile_manifest(plan, self.fixture())

    def test_shared_flow_conflicting_exposure_is_rejected(self):
        fixture = self.fixture()
        fixture["actions"][1]["device_id"] = fixture["actions"][0]["device_id"]
        fixture["actions"][1]["circuit_id"] = fixture["actions"][0]["circuit_id"]
        fixture["actions"][1]["channel_id"] = "TREATMENT_2"
        with self.assertRaisesRegex(ooc.FeasibilityError, "SHARED_FLOW_EXPOSURE_CONFLICT"):
            ooc.compile_manifest(self.plan, fixture)

    def test_shared_reservoir_conflicting_exposure_is_rejected(self):
        fixture = self.fixture()
        fixture["actions"][1]["device_id"] = fixture["actions"][0]["device_id"]
        fixture["actions"][1]["reservoir_id"] = fixture["actions"][0]["reservoir_id"]
        fixture["actions"][1]["circuit_id"] = "CIRCUIT_2"
        with self.assertRaisesRegex(ooc.FeasibilityError, "SHARED_RESERVOIR_EXPOSURE_CONFLICT"):
            ooc.compile_manifest(self.plan, fixture)

    def test_exact_dose_substitution_is_rejected(self):
        fixture = self.fixture()
        fixture["actions"][4]["concentration_nM"] = "999"
        with self.assertRaisesRegex(ooc.FeasibilityError, "EXACT_EXPOSURE_MISMATCH"):
            ooc.compile_manifest(self.plan, fixture)

    def test_missing_treatment_is_rejected(self):
        fixture = self.fixture()
        fixture["actions"].pop()
        with self.assertRaisesRegex(ooc.FeasibilityError, "MISSING_OOC_ACTIONS"):
            ooc.compile_manifest(self.plan, fixture)

    def test_missing_separate_control_is_rejected(self):
        fixture = self.fixture()
        fixture["controls"] = fixture["controls"][:1]
        with self.assertRaisesRegex(ooc.FeasibilityError, "MISSING_SEPARATE_CONTROLS_FOR"):
            ooc.compile_manifest(self.plan, fixture)

    def test_required_control_policy_cannot_be_weakened(self):
        fixture = self.fixture()
        fixture["required_control_types"] = ["vehicle"]
        with self.assertRaisesRegex(ooc.FeasibilityError, "INVALID_REQUIRED_CONTROLS"):
            ooc.compile_manifest(self.plan, fixture)

    def test_control_cannot_reuse_treatment_channel(self):
        fixture = self.fixture()
        fixture["controls"][0].update({
            "device_id": fixture["actions"][0]["device_id"],
            "reservoir_id": fixture["actions"][0]["reservoir_id"],
            "circuit_id": fixture["actions"][0]["circuit_id"],
            "channel_id": fixture["actions"][0]["channel_id"],
        })
        with self.assertRaisesRegex(ooc.FeasibilityError, "CONTROL_RESOURCE_COLLISION"):
            ooc.compile_manifest(self.plan, fixture)

    def test_control_cannot_share_treatment_flow_circuit(self):
        fixture = self.fixture()
        fixture["controls"][0].update({
            "device_id": fixture["actions"][0]["device_id"],
            "reservoir_id": "CONTROL_RESERVOIR",
            "circuit_id": fixture["actions"][0]["circuit_id"],
            "channel_id": "CONTROL_2",
        })
        with self.assertRaisesRegex(ooc.FeasibilityError, "CONTROL_SHARED_FLOW_COLLISION"):
            ooc.compile_manifest(self.plan, fixture)

    def test_control_cannot_share_treatment_reservoir(self):
        fixture = self.fixture()
        fixture["controls"][0].update({
            "device_id": fixture["actions"][0]["device_id"],
            "reservoir_id": fixture["actions"][0]["reservoir_id"],
            "circuit_id": "CONTROL_CIRCUIT",
            "channel_id": "CONTROL_2",
        })
        with self.assertRaisesRegex(ooc.FeasibilityError, "CONTROL_SHARED_RESERVOIR_COLLISION"):
            ooc.compile_manifest(self.plan, fixture)

    def test_controls_cannot_share_flow_or_reservoir(self):
        fixture = self.fixture()
        fixture["controls"][1].update({
            "device_id": fixture["controls"][0]["device_id"],
            "reservoir_id": fixture["controls"][0]["reservoir_id"],
            "circuit_id": fixture["controls"][0]["circuit_id"],
            "channel_id": "CONTROL_2",
        })
        with self.assertRaisesRegex(ooc.FeasibilityError, "CONTROLS_SHARE_FLOW_CIRCUIT"):
            ooc.compile_manifest(self.plan, fixture)

    def test_duplicate_action_and_control_ids_are_rejected(self):
        fixture = self.fixture()
        fixture["actions"][1]["action_id"] = fixture["actions"][0]["action_id"]
        with self.assertRaisesRegex(ooc.FeasibilityError, "DUPLICATE_ACTION_ID"):
            ooc.compile_manifest(self.plan, fixture)
        fixture = self.fixture()
        fixture["controls"][1]["control_id"] = fixture["controls"][0]["control_id"]
        with self.assertRaisesRegex(ooc.FeasibilityError, "DUPLICATE_CONTROL_ID"):
            ooc.compile_manifest(self.plan, fixture)

    def test_cli_preserves_incompatibility_reason_and_no_output(self):
        fixture = self.fixture()
        fixture["controls"] = []
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan_path = root / "plan.json"
            inventory_path = root / "inventory.json"
            output_path = root / "manifest.json"
            plan_path.write_text(json.dumps(self.plan))
            inventory_path.write_text(json.dumps(fixture))
            old = __import__("sys").argv
            try:
                __import__("sys").argv = [
                    "ooc_feasibility.py", "compile", "--plan", str(plan_path),
                    "--inventory", str(inventory_path), "--output", str(output_path),
                ]
                self.assertEqual(ooc.main(), 2)
            finally:
                __import__("sys").argv = old
            self.assertFalse(output_path.exists())


if __name__ == "__main__":
    unittest.main()
