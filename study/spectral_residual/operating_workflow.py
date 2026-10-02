#!/usr/bin/env python3
"""Commit, ingest and predict with a constructed spectral DosePilot model.

This wrapper adds an append-only evidence boundary around ``inference.py``.
It does not fit a model, read a source workbook, certify laboratory execution,
or make clinical claims.  A caller-declared inventory is checked for exact
drug/dose/plate/native identities before any measurement value is accepted.
"""
from __future__ import annotations

import argparse
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
from pathlib import Path
import sys

from inference import SpectralModel, digest


class WorkflowError(ValueError):
    pass


def _unique(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise WorkflowError("DUPLICATE_JSON_KEY: " + key)
        out[key] = value
    return out


def load_json(path):
    raw = Path(path).read_bytes()
    try:
        value = json.loads(
            raw,
            object_pairs_hook=_unique,
            parse_constant=lambda x: (_ for _ in ()).throw(
                WorkflowError("NONFINITE_JSON_CONSTANT: " + x)
            ),
        )
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise WorkflowError("INVALID_JSON") from exc
    return value, raw


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def sha256_bytes(value):
    return hashlib.sha256(value).hexdigest()


def exact_keys(value, keys, label):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise WorkflowError("SCHEMA_KEYS: " + label)


def text_id(value, label):
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or any(ord(char) < 32 for char in value)
    ):
        raise WorkflowError("INVALID_ID: " + label)
    return value


def exact_dose(value):
    if isinstance(value, bool):
        raise WorkflowError("BOOLEAN_DOSE")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise WorkflowError("INVALID_DOSE") from exc
    if not parsed.is_finite() or parsed <= 0:
        raise WorkflowError("INVALID_DOSE")
    return parsed


def write_new(path, value):
    path = Path(path)
    if path.exists():
        raise WorkflowError("OUTPUT_EXISTS: " + str(path))
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")


def model_receipt(model_dir, expected_construction_sha256):
    model_dir = Path(model_dir)
    actual_construction_sha256 = digest(model_dir / "CONSTRUCTION.json")
    if (
        not isinstance(expected_construction_sha256, str)
        or len(expected_construction_sha256) != 64
        or any(char not in "0123456789abcdef" for char in expected_construction_sha256)
        or actual_construction_sha256 != expected_construction_sha256
    ):
        raise WorkflowError("CONSTRUCTION_TRUST_ANCHOR_MISMATCH")
    receipt, _ = load_json(model_dir / "CONSTRUCTION.json")
    return {
        "construction_sha256": actual_construction_sha256,
        "plan_sha256": receipt["plan_sha256"],
        "model_sha256": receipt["model_sha256"],
    }


def frame_id(receipt, sample_id, run_id):
    return sha256_bytes(
        canonical([receipt["model_sha256"], receipt["plan_sha256"], sample_id, run_id])
    )


def build_commitment(model, receipt, inventory):
    exact_keys(
        inventory,
        [
            "schema",
            "sample_id",
            "run_id",
            "orientation",
            "plate_instances",
            "treatment_wells",
            "controls",
        ],
        "inventory",
    )
    if inventory["schema"] != "dosepilot.spectral_inventory.v1":
        raise WorkflowError("UNSUPPORTED_INVENTORY")
    sample_id = text_id(inventory["sample_id"], "sample_id")
    run_id = text_id(inventory["run_id"], "run_id")
    orientation = inventory["orientation"]
    if orientation not in ("A", "B"):
        raise WorkflowError("ORIENTATION_REQUIRED")
    exact_keys(inventory["plate_instances"], ["p1", "p2"], "plate_instances")
    instances = {
        plate: text_id(value, plate + "_instance")
        for plate, value in inventory["plate_instances"].items()
    }
    if instances["p1"] == instances["p2"]:
        raise WorkflowError("DUPLICATE_PLATE_INSTANCE")

    wells = inventory["treatment_wells"]
    if not isinstance(wells, list) or len(wells) != 64:
        raise WorkflowError("EXACT_64_TREATMENT_WELLS_REQUIRED")
    supplied = {}
    physical = set()
    for row in wells:
        exact_keys(
            row,
            ["native_id", "drug_id", "dose_nM", "plate", "well_id"],
            "treatment_well",
        )
        native_id = text_id(row["native_id"], "native_id")
        if native_id not in model.native or native_id in supplied:
            raise WorkflowError("UNKNOWN_OR_DUPLICATE_NATIVE_ID")
        index = model.native.index(native_id)
        expected_plate = "p" + str(int(model.plates[orientation][index]) + 1)
        if row["plate"] != expected_plate:
            raise WorkflowError("WRONG_PLATE: " + native_id)
        if row["drug_id"] != model.targets[int(model.owner[index])]:
            raise WorkflowError("WRONG_DRUG: " + native_id)
        if exact_dose(row["dose_nM"]) != model.doses[index]:
            raise WorkflowError("WRONG_DOSE: " + native_id)
        well_id = text_id(row["well_id"], "well_id")
        key = (instances[expected_plate], well_id)
        if key in physical:
            raise WorkflowError("DUPLICATE_PHYSICAL_TREATMENT_WELL")
        physical.add(key)
        supplied[native_id] = {
            "position": index,
            "native_id": native_id,
            "drug_id": row["drug_id"],
            "dose_nM": str(model.doses[index]),
            "plate": expected_plate,
            "plate_instance": instances[expected_plate],
            "well_id": well_id,
        }

    controls = inventory["controls"]
    if not isinstance(controls, list) or len(controls) < 2:
        raise WorkflowError("VEHICLE_AND_VIABILITY_CONTROLS_REQUIRED")
    control_types = set()
    control_records = []
    for row in controls:
        exact_keys(row, ["control_type", "plate", "well_id"], "control")
        control_type = row["control_type"]
        if control_type not in ("vehicle", "viability"):
            raise WorkflowError("UNSUPPORTED_CONTROL_TYPE")
        if row["plate"] not in ("p1", "p2"):
            raise WorkflowError("INVALID_CONTROL_PLATE")
        well_id = text_id(row["well_id"], "control_well_id")
        key = (instances[row["plate"]], well_id)
        if key in physical:
            raise WorkflowError("CONTROL_RESOURCE_COLLISION")
        physical.add(key)
        control_types.add(control_type)
        control_records.append(
            {
                "control_type": control_type,
                "plate": row["plate"],
                "plate_instance": instances[row["plate"]],
                "well_id": well_id,
            }
        )
    if control_types != {"vehicle", "viability"}:
        raise WorkflowError("VEHICLE_AND_VIABILITY_CONTROLS_REQUIRED")

    requests = [supplied[native_id] for native_id in model.native]
    plate_counts = {
        plate: sum(row["plate"] == plate for row in requests)
        for plate in ("p1", "p2")
    }
    if plate_counts != {"p1": 32, "p2": 32}:
        raise WorkflowError("PLATE_BUDGET_CHANGED")
    normalized_inventory = {
        "schema": "dosepilot.spectral_inventory.v1",
        "sample_id": sample_id,
        "run_id": run_id,
        "orientation": orientation,
        "plate_instances": instances,
        "treatment_wells": [
            {
                key: row[key]
                for key in ("native_id", "drug_id", "dose_nM", "plate", "well_id")
            }
            for row in requests
        ],
        "controls": [
            {
                key: row[key]
                for key in ("control_type", "plate", "well_id")
            }
            for row in sorted(
                control_records,
                key=lambda item: (
                    item["control_type"], item["plate_instance"], item["well_id"]
                ),
            )
        ],
    }
    body = {
        "schema": "dosepilot.spectral_commitment.v1",
        "sample_id": sample_id,
        "run_id": run_id,
        "orientation": orientation,
        "model_receipt": receipt,
        "treatment_wells": 64,
        "plate_counts": plate_counts,
        "controls_outside_treatment_budget": sorted(
            control_records,
            key=lambda row: (row["control_type"], row["plate_instance"], row["well_id"]),
        ),
        "requests": requests,
        "inventory": normalized_inventory,
        "limitations": {
            "caller_declared_inventory": True,
            "laboratory_execution_certified": False,
            "clinical_use_validated": False,
            "requires_all_64_values": True,
        },
    }
    body["frame_id"] = frame_id(receipt, sample_id, run_id)
    body["commitment_id"] = sha256_bytes(canonical(body))
    return body


def validate_commitment(model, receipt, commitment):
    if not isinstance(commitment, dict) or "inventory" not in commitment:
        raise WorkflowError("MALFORMED_COMMITMENT")
    rebuilt = build_commitment(model, receipt, commitment["inventory"])
    if rebuilt != commitment:
        raise WorkflowError("COMMITMENT_MISMATCH")
    return rebuilt


def measurement_template(commitment):
    return {
        "schema": "dosepilot.spectral_measurements.v1",
        "commitment_id": commitment["commitment_id"],
        "sample_id": commitment["sample_id"],
        "run_id": commitment["run_id"],
        "orientation": commitment["orientation"],
        "measurements": [
            {
                **{key: row[key] for key in (
                    "native_id", "drug_id", "dose_nM", "plate", "well_id"
                )},
                "value": None,
            }
            for row in commitment["requests"]
        ],
    }


def request_from_measurements(model, commitment, measurements):
    exact_keys(
        measurements,
        [
            "schema",
            "commitment_id",
            "sample_id",
            "run_id",
            "orientation",
            "measurements",
        ],
        "measurements",
    )
    if measurements["schema"] != "dosepilot.spectral_measurements.v1":
        raise WorkflowError("UNSUPPORTED_MEASUREMENT_SCHEMA")
    for key in ("commitment_id", "sample_id", "run_id", "orientation"):
        if measurements[key] != commitment[key]:
            raise WorkflowError("MEASUREMENT_FRAME_MISMATCH: " + key)
    rows = measurements["measurements"]
    if not isinstance(rows, list) or len(rows) != 64:
        raise WorkflowError("ALL_64_MEASUREMENTS_REQUIRED")
    expected = {row["native_id"]: row for row in commitment["requests"]}
    supplied = {}
    for row in rows:
        exact_keys(
            row,
            ["native_id", "drug_id", "dose_nM", "plate", "well_id", "value"],
            "measurement_row",
        )
        native_id = row["native_id"]
        if native_id not in expected or native_id in supplied:
            raise WorkflowError("UNKNOWN_OR_DUPLICATE_MEASUREMENT")
        identity = {key: row[key] for key in (
            "native_id", "drug_id", "dose_nM", "plate", "well_id"
        )}
        expected_identity = {key: expected[native_id][key] for key in identity}
        if identity != expected_identity:
            raise WorkflowError("MEASUREMENT_IDENTITY_MISMATCH: " + str(native_id))
        value = row["value"]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise WorkflowError("MISSING_OR_NONFINITE_VALUE: " + str(native_id))
        try:
            numeric = float(value)
        except OverflowError as exc:
            raise WorkflowError("MISSING_OR_NONFINITE_VALUE: " + str(native_id)) from exc
        if not math.isfinite(numeric):
            raise WorkflowError("MISSING_OR_NONFINITE_VALUE: " + str(native_id))
        supplied[native_id] = numeric
    return {
        "sample_id": commitment["sample_id"],
        "run_id": commitment["run_id"],
        "orientation": commitment["orientation"],
        "measurements": [
            {
                "sample_id": commitment["sample_id"],
                "run_id": commitment["run_id"],
                "native_id": row["native_id"],
                "drug_id": row["drug_id"],
                "dose_nM": row["dose_nM"],
                "plate": row["plate"],
                "well_id": row["well_id"],
                "value": supplied[row["native_id"]],
            }
            for row in commitment["requests"]
        ],
    }


def ledger_path(directory, frame, suffix):
    root = Path(directory)
    if not root.is_dir() or root.is_symlink():
        raise WorkflowError("LEDGER_DIRECTORY_REQUIRED")
    return root / (frame + suffix)


def commit(
    model_dir,
    construction_sha256,
    inventory_path,
    commitment_path,
    template_path,
    ledger_dir,
):
    receipt = model_receipt(model_dir, construction_sha256)
    model = SpectralModel.load(model_dir)
    inventory, _ = load_json(inventory_path)
    commitment = build_commitment(model, receipt, inventory)
    template = measurement_template(commitment)
    ledger = ledger_path(ledger_dir, commitment["frame_id"], ".commitment.json")
    user_paths = [Path(commitment_path), Path(template_path)]
    if len({path.resolve() for path in [*user_paths, ledger]}) != 3:
        raise WorkflowError("COMMITMENT_OUTPUT_PATHS_MUST_DIFFER")
    if ledger.exists():
        ledger_value, _ = load_json(ledger)
        if ledger_value != commitment:
            raise WorkflowError("FRAME_ALREADY_COMMITTED_DIFFERENTLY")
        for path, expected in ((user_paths[0], commitment), (user_paths[1], template)):
            if path.exists():
                actual, _ = load_json(path)
                if actual != expected:
                    raise WorkflowError("RECOVERY_OUTPUT_MISMATCH")
            else:
                write_new(path, expected)
        return commitment
    if any(path.exists() for path in user_paths):
        raise WorkflowError("UNLEDGERED_COMMITMENT_OUTPUT_EXISTS")
    # The ledger is authoritative and is created first. A rerun with the exact
    # same frame can recover either deterministic user-facing copy.
    write_new(ledger, commitment)
    write_new(commitment_path, commitment)
    write_new(template_path, template)
    return commitment


def predict(
    model_dir,
    construction_sha256,
    commitment_path,
    measurements_path,
    output_path,
    ledger_dir,
):
    receipt = model_receipt(model_dir, construction_sha256)
    model = SpectralModel.load(model_dir)
    commitment, commitment_raw = load_json(commitment_path)
    validate_commitment(model, receipt, commitment)
    ledger = ledger_path(ledger_dir, commitment["frame_id"], ".commitment.json")
    if not ledger.is_file() or ledger.is_symlink():
        raise WorkflowError("COMMITMENT_NOT_IN_LEDGER")
    ledger_value, _ = load_json(ledger)
    if ledger_value != commitment:
        raise WorkflowError("LEDGER_COMMITMENT_MISMATCH")
    measurements, measurements_raw = load_json(measurements_path)
    request = request_from_measurements(model, commitment, measurements)
    prediction = model.predict(request)
    result = {
        "schema": "dosepilot.spectral_operating_result.v1",
        **prediction,
        "evidence": {
            **receipt,
            "commitment_id": commitment["commitment_id"],
            "commitment_file_sha256": sha256_bytes(commitment_raw),
            "measurements_file_sha256": sha256_bytes(measurements_raw),
            "treatment_wells": 64,
            "controls_declared": len(commitment["controls_outside_treatment_budget"]),
            "all_values_present": True,
        },
        "limitations": commitment["limitations"],
    }
    prediction_ledger = ledger_path(
        ledger_dir, commitment["frame_id"], ".prediction.json"
    )
    if prediction_ledger.exists():
        recorded, _ = load_json(prediction_ledger)
        if recorded != result:
            raise WorkflowError("FRAME_ALREADY_PREDICTED_FROM_DIFFERENT_MEASUREMENTS")
        if Path(output_path).exists():
            visible, _ = load_json(output_path)
            if visible != result:
                raise WorkflowError("RECOVERY_OUTPUT_MISMATCH")
        else:
            write_new(output_path, result)
        return result
    if Path(output_path).exists():
        raise WorkflowError("UNLEDGERED_PREDICTION_OUTPUT_EXISTS")
    # Record the authoritative result before exporting its recoverable copy.
    write_new(prediction_ledger, result)
    write_new(output_path, result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    commit_parser = sub.add_parser("commit")
    commit_parser.add_argument("--model-dir", required=True, type=Path)
    commit_parser.add_argument("--construction-sha256", required=True)
    commit_parser.add_argument("--inventory", required=True, type=Path)
    commit_parser.add_argument("--commitment", required=True, type=Path)
    commit_parser.add_argument("--template", required=True, type=Path)
    commit_parser.add_argument("--ledger-dir", required=True, type=Path)
    predict_parser = sub.add_parser("predict")
    predict_parser.add_argument("--model-dir", required=True, type=Path)
    predict_parser.add_argument("--construction-sha256", required=True)
    predict_parser.add_argument("--commitment", required=True, type=Path)
    predict_parser.add_argument("--measurements", required=True, type=Path)
    predict_parser.add_argument("--output", required=True, type=Path)
    predict_parser.add_argument("--ledger-dir", required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.command == "commit":
            result = commit(
                args.model_dir,
                args.construction_sha256,
                args.inventory,
                args.commitment,
                args.template,
                args.ledger_dir,
            )
            summary = {
                "status": "COMMITTED",
                "commitment_id": result["commitment_id"],
                "treatment_wells": 64,
                "plate_counts": result["plate_counts"],
            }
        else:
            result = predict(
                args.model_dir,
                args.construction_sha256,
                args.commitment,
                args.measurements,
                args.output,
                args.ledger_dir,
            )
            summary = {
                "status": result["status"],
                "commitment_id": result["evidence"]["commitment_id"],
                "outputs": len(result["predictions"]),
            }
        print(json.dumps(summary, sort_keys=True))
        return 0
    except (WorkflowError, ValueError, KeyError, TypeError, OSError) as exc:
        print(json.dumps({"status": "REJECTED", "reason": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
