import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

import numpy as np

import operating_workflow as workflow
from operating_workflow import (
    WorkflowError,
    build_commitment,
    commit,
    measurement_template,
    model_receipt,
    predict,
    request_from_measurements,
    validate_commitment,
)
from inference import SpectralModel
from test_inference import fixture


class OperatingWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.model_dir = self.root / "model"
        self.model_dir.mkdir()
        arrays, plan, request, self.values = fixture()
        np.savez_compressed(self.model_dir / "model_private.npz", **arrays)
        (self.model_dir / "plan.json").write_text(json.dumps(plan))
        receipt = {
            "selected": [0.1, 1.0],
            "model_sha256": hashlib.sha256(
                (self.model_dir / "model_private.npz").read_bytes()
            ).hexdigest(),
            "plan_sha256": hashlib.sha256(
                (self.model_dir / "plan.json").read_bytes()
            ).hexdigest(),
        }
        (self.model_dir / "CONSTRUCTION.json").write_text(json.dumps(receipt))
        self.model = SpectralModel.load(self.model_dir)
        self.construction_sha256 = hashlib.sha256(
            (self.model_dir / "CONSTRUCTION.json").read_bytes()
        ).hexdigest()
        rows = []
        for item in request["measurements"]:
            rows.append(
                {
                    key: item[key]
                    for key in ("native_id", "drug_id", "dose_nM", "plate", "well_id")
                }
            )
        self.inventory = {
            "schema": "dosepilot.spectral_inventory.v1",
            "sample_id": "fictional",
            "run_id": "run1",
            "orientation": "A",
            "plate_instances": {"p1": "plate-A", "p2": "plate-B"},
            "treatment_wells": rows,
            "controls": [
                {"control_type": "vehicle", "plate": "p1", "well_id": "control-v"},
                {"control_type": "viability", "plate": "p2", "well_id": "control-c"},
            ],
        }
        self.receipt = model_receipt(self.model_dir, self.construction_sha256)

    def tearDown(self):
        self.tmp.cleanup()

    def commitment(self, inventory=None):
        return build_commitment(
            self.model, self.receipt, self.inventory if inventory is None else inventory
        )

    def complete_measurements(self, commitment=None):
        commitment = commitment or self.commitment()
        value = measurement_template(commitment)
        for index, row in enumerate(value["measurements"]):
            row["value"] = float(self.values[index])
        return value

    def test_end_to_end_matches_direct_predictor(self):
        ledger = self.root / "ledger"
        ledger.mkdir()
        inventory_path = self.root / "inventory.json"
        inventory_path.write_text(json.dumps(self.inventory))
        commitment_path = self.root / "commitment.json"
        template_path = self.root / "template.json"
        committed = commit(
            self.model_dir,
            self.construction_sha256,
            inventory_path,
            commitment_path,
            template_path,
            ledger,
        )
        measurements = self.complete_measurements(committed)
        measurements_path = self.root / "measurements.json"
        measurements_path.write_text(json.dumps(measurements))
        output = self.root / "prediction.json"
        result = predict(
            self.model_dir,
            self.construction_sha256,
            commitment_path,
            measurements_path,
            output,
            ledger,
        )
        direct = self.model.predict(
            request_from_measurements(self.model, committed, measurements)
        )
        self.assertEqual(result["predictions"], direct["predictions"])
        self.assertEqual(result["evidence"]["treatment_wells"], 64)
        self.assertTrue(result["evidence"]["all_values_present"])
        self.assertEqual(len(list(ledger.iterdir())), 2)

    def test_measurement_order_is_identity_based(self):
        commitment = self.commitment()
        measurements = self.complete_measurements(commitment)
        measurements["measurements"].reverse()
        request = request_from_measurements(self.model, commitment, measurements)
        self.assertEqual(self.model.predict(request)["status"], "COMPLETE")

    def test_exact_budget_and_controls(self):
        commitment = self.commitment()
        self.assertEqual(commitment["plate_counts"], {"p1": 32, "p2": 32})
        self.assertEqual(len(commitment["requests"]), 64)
        self.assertEqual(
            {row["control_type"] for row in commitment["controls_outside_treatment_budget"]},
            {"vehicle", "viability"},
        )

    def test_inventory_order_and_dose_representation_do_not_change_commitment(self):
        commitment = self.commitment()
        inventory = copy.deepcopy(self.inventory)
        inventory["treatment_wells"].reverse()
        inventory["controls"].reverse()
        inventory["treatment_wells"][0]["dose_nM"] = float(
            inventory["treatment_wells"][0]["dose_nM"]
        )
        reordered = self.commitment(inventory)
        self.assertEqual(reordered, commitment)

    def test_missing_or_duplicate_treatment_rejected(self):
        for mutate in (
            lambda value: value["treatment_wells"].pop(),
            lambda value: value["treatment_wells"].__setitem__(
                1, copy.deepcopy(value["treatment_wells"][0])
            ),
        ):
            inventory = copy.deepcopy(self.inventory)
            mutate(inventory)
            with self.subTest(rows=len(inventory["treatment_wells"])):
                with self.assertRaises(WorkflowError):
                    self.commitment(inventory)

    def test_wrong_drug_dose_or_plate_rejected(self):
        changes = [
            ("drug_id", "wrong"),
            ("dose_nM", "1.0000001"),
            ("plate", "p2"),
        ]
        for key, replacement in changes:
            inventory = copy.deepcopy(self.inventory)
            inventory["treatment_wells"][0][key] = replacement
            with self.subTest(key=key), self.assertRaises(WorkflowError):
                self.commitment(inventory)

    def test_control_requirements_and_collisions(self):
        inventory = copy.deepcopy(self.inventory)
        inventory["controls"].pop()
        with self.assertRaises(WorkflowError):
            self.commitment(inventory)
        inventory = copy.deepcopy(self.inventory)
        inventory["controls"][0]["well_id"] = inventory["treatment_wells"][0]["well_id"]
        inventory["controls"][0]["plate"] = inventory["treatment_wells"][0]["plate"]
        with self.assertRaises(WorkflowError):
            self.commitment(inventory)

    def test_tampered_commitment_rejected(self):
        commitment = self.commitment()
        commitment["requests"][0]["well_id"] = "tampered"
        with self.assertRaises(WorkflowError):
            validate_commitment(self.model, self.receipt, commitment)

    def test_missing_nonfinite_boolean_or_huge_value_rejected(self):
        commitment = self.commitment()
        for bad in (None, float("nan"), float("inf"), True, 10**309):
            measurements = self.complete_measurements(commitment)
            measurements["measurements"][0]["value"] = bad
            with self.subTest(value=bad), self.assertRaises(WorkflowError):
                request_from_measurements(self.model, commitment, measurements)

    def test_measurement_identity_tamper_rejected(self):
        commitment = self.commitment()
        for key, bad in (
            ("commitment_id", "0" * 64),
            ("sample_id", "wrong"),
            ("run_id", "wrong"),
            ("orientation", "B"),
        ):
            measurements = self.complete_measurements(commitment)
            measurements[key] = bad
            with self.subTest(key=key), self.assertRaises(WorkflowError):
                request_from_measurements(self.model, commitment, measurements)
        measurements = self.complete_measurements(commitment)
        measurements["measurements"][0]["well_id"] = "wrong"
        with self.assertRaises(WorkflowError):
            request_from_measurements(self.model, commitment, measurements)

    def test_uncommitted_prediction_rejected(self):
        commitment = self.commitment()
        commitment_path = self.root / "commitment.json"
        commitment_path.write_text(json.dumps(commitment))
        measurements_path = self.root / "measurements.json"
        measurements_path.write_text(json.dumps(self.complete_measurements(commitment)))
        ledger = self.root / "ledger"
        ledger.mkdir()
        with self.assertRaises(WorkflowError):
            predict(
                self.model_dir,
                self.construction_sha256,
                commitment_path,
                measurements_path,
                self.root / "output.json",
                ledger,
            )

    def test_exact_recovery_allowed_but_changed_frame_rejected(self):
        ledger = self.root / "ledger"
        ledger.mkdir()
        inventory_path = self.root / "inventory.json"
        inventory_path.write_text(json.dumps(self.inventory))
        commitment_path = self.root / "commitment.json"
        template_path = self.root / "template.json"
        commitment = commit(
            self.model_dir,
            self.construction_sha256,
            inventory_path,
            commitment_path,
            template_path,
            ledger,
        )
        recovered = commit(
            self.model_dir,
            self.construction_sha256,
            inventory_path,
            self.root / "commitment2.json",
            self.root / "template2.json",
            ledger,
        )
        self.assertEqual(recovered, commitment)
        changed_inventory = copy.deepcopy(self.inventory)
        changed_inventory["controls"][0]["well_id"] = "different-control"
        changed_inventory_path = self.root / "changed_inventory.json"
        changed_inventory_path.write_text(json.dumps(changed_inventory))
        with self.assertRaises(WorkflowError):
            commit(
                self.model_dir,
                self.construction_sha256,
                changed_inventory_path,
                self.root / "commitment3.json",
                self.root / "template3.json",
                ledger,
            )
        measurements_path = self.root / "measurements.json"
        measurements_path.write_text(json.dumps(self.complete_measurements(commitment)))
        predict(
            self.model_dir,
            self.construction_sha256,
            commitment_path,
            measurements_path,
            self.root / "prediction.json",
            ledger,
        )
        recovered_prediction = predict(
            self.model_dir,
            self.construction_sha256,
            commitment_path,
            measurements_path,
            self.root / "prediction2.json",
            ledger,
        )
        self.assertEqual(
            recovered_prediction,
            json.loads((self.root / "prediction.json").read_text()),
        )
        changed_measurements = self.complete_measurements(commitment)
        changed_measurements["measurements"][0]["value"] += 1.0
        changed_path = self.root / "changed_measurements.json"
        changed_path.write_text(json.dumps(changed_measurements))
        with self.assertRaises(WorkflowError):
            predict(
                self.model_dir,
                self.construction_sha256,
                commitment_path,
                changed_path,
                self.root / "changed_prediction.json",
                ledger,
            )

    def test_concurrent_changed_predictions_expose_at_most_one_output(self):
        ledger = self.root / "ledger"
        ledger.mkdir()
        inventory_path = self.root / "inventory.json"
        inventory_path.write_text(json.dumps(self.inventory))
        commitment_path = self.root / "commitment.json"
        template_path = self.root / "template.json"
        commitment = commit(
            self.model_dir,
            self.construction_sha256,
            inventory_path,
            commitment_path,
            template_path,
            ledger,
        )
        paths = []
        for index in range(2):
            measurements = self.complete_measurements(commitment)
            measurements["measurements"][0]["value"] += index
            path = self.root / f"measurements-{index}.json"
            path.write_text(json.dumps(measurements))
            paths.append(path)
        outputs = [self.root / "prediction-0.json", self.root / "prediction-1.json"]
        barrier = Barrier(2)
        original_write = workflow.write_new

        def synchronized_write(path, value):
            if str(path).endswith(".prediction.json"):
                barrier.wait(timeout=5)
            return original_write(path, value)

        def invoke(index):
            try:
                workflow.predict(
                    self.model_dir,
                    self.construction_sha256,
                    commitment_path,
                    paths[index],
                    outputs[index],
                    ledger,
                )
                return "ok"
            except (OSError, WorkflowError):
                return "rejected"

        with patch.object(workflow, "write_new", synchronized_write):
            with ThreadPoolExecutor(max_workers=2) as pool:
                statuses = list(pool.map(invoke, range(2)))
        self.assertEqual(sorted(statuses), ["ok", "rejected"])
        self.assertEqual(sum(path.exists() for path in outputs), 1)

    def test_constructed_model_tamper_rejected(self):
        commitment = self.commitment()
        commitment_path = self.root / "commitment.json"
        commitment_path.write_text(json.dumps(commitment))
        with (self.model_dir / "plan.json").open("a") as handle:
            handle.write(" ")
        with self.assertRaises(ValueError):
            SpectralModel.load(self.model_dir)

    def test_caller_trust_anchor_required(self):
        with self.assertRaises(WorkflowError):
            model_receipt(self.model_dir, "0" * 64)


if __name__ == "__main__":
    unittest.main(verbosity=2)
