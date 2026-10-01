#!/usr/bin/env python3
"""Check an acquired DosePilot plan against declared organ-on-chip constraints.

This is a response-free logical resource check.  It does not predict biology,
prove physical feasibility, certify a device, or turn plate wells into chip runs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path


class FeasibilityError(ValueError):
    pass


def _unique(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise FeasibilityError("DUPLICATE_JSON_KEY: " + key)
        out[key] = value
    return out


def _load(path):
    try:
        return json.loads(
            Path(path).read_text(encoding="utf-8"),
            object_pairs_hook=_unique,
            parse_constant=lambda value: (_ for _ in ()).throw(
                FeasibilityError("NONFINITE_JSON: " + value)
            ),
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise FeasibilityError("INVALID_JSON") from exc


def _canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _sha256(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def _identity(value, label):
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or any(ord(char) < 32 for char in value)
    ):
        raise FeasibilityError("INVALID_ID: " + label)
    return value


def _dose(value):
    if not isinstance(value, str) or value != value.strip():
        raise FeasibilityError("DOSE_MUST_BE_EXACT_DECIMAL_STRING")
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise FeasibilityError("INVALID_DOSE") from exc
    if not parsed.is_finite() or parsed <= 0:
        raise FeasibilityError("INVALID_DOSE")
    return parsed


def _positive_number(value, label):
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        raise FeasibilityError("INVALID_POSITIVE_NUMBER: " + label)
    return float(value)


def _validate_plan(plan):
    if not isinstance(plan, dict) or plan.get("schema") != "von.acquisition.v1":
        raise FeasibilityError("UNSUPPORTED_PLAN")
    rows = plan.get("measurements")
    if not isinstance(rows, list) or len(rows) != 64:
        raise FeasibilityError("EXACT_64_TREATMENT_ACTIONS_REQUIRED")
    if plan.get("treatment_wells") != 64 or plan.get("controls_included") is not False:
        raise FeasibilityError("PLAN_BUDGET_OR_CONTROL_COMMITMENT")
    plate_counts = plan.get("plate_counts")
    if not isinstance(plate_counts, dict) or set(plate_counts) != {"p1", "p2"}:
        raise FeasibilityError("PLAN_PLATE_COUNTS")
    positions = set()
    physical = set()
    native_ids = set()
    observed_plates = {"p1": 0, "p2": 0}
    for row in rows:
        if not isinstance(row, dict):
            raise FeasibilityError("INVALID_PLAN_ROW")
        position = row.get("position")
        if type(position) is not int or position < 0 or position >= 64 or position in positions:
            raise FeasibilityError("INVALID_PLAN_POSITION")
        positions.add(position)
        native_id = _identity(row.get("native_id"), "native id")
        if native_id in native_ids:
            raise FeasibilityError("DUPLICATE_NATIVE_ID")
        native_ids.add(native_id)
        _identity(row.get("drug_id"), "plan drug")
        _dose(row.get("concentration_nM"))
        if row.get("unit") != "nM":
            raise FeasibilityError("PLAN_UNIT_NOT_NM")
        plate = row.get("plate")
        if plate not in observed_plates:
            raise FeasibilityError("PLAN_PLATE_ID")
        observed_plates[plate] += 1
        well = (_identity(row.get("plate_instance"), "plate"), _identity(row.get("well"), "well"))
        if well in physical:
            raise FeasibilityError("DUPLICATE_PLAN_WELL")
        physical.add(well)
    if positions != set(range(64)):
        raise FeasibilityError("PLAN_POSITION_GAP")
    if plate_counts != observed_plates or sum(plate_counts.values()) != 64:
        raise FeasibilityError("PLAN_PLATE_COUNT_MISMATCH")
    return sorted(rows, key=lambda row: row["position"])


def _validate_inventory(inventory):
    if not isinstance(inventory, dict) or inventory.get("schema") != "von.ooc.inventory.v1":
        raise FeasibilityError("UNSUPPORTED_OOC_INVENTORY")
    if inventory.get("assay_context") not in ("synthetic_protocol_fixture", "declared_external_protocol"):
        raise FeasibilityError("ASSAY_CONTEXT_REQUIRED")
    _identity(inventory.get("source_note"), "source note")
    required = inventory.get("required_control_types")
    if (
        not isinstance(required, list)
        or not required
        or len(set(required)) != len(required)
        or set(required) != {"vehicle", "viability"}
        or len(required) != 2
    ):
        raise FeasibilityError("INVALID_REQUIRED_CONTROLS")
    actions = inventory.get("actions")
    controls = inventory.get("controls")
    if not isinstance(actions, list) or not isinstance(controls, list):
        raise FeasibilityError("ACTIONS_AND_CONTROLS_REQUIRED")

    physical = set()
    by_position = {}
    circuits = {}
    reservoirs = {}
    action_ids = set()
    for action in actions:
        required_keys = {
            "action_id", "source_position", "run_id", "device_id", "reservoir_id", "circuit_id",
            "channel_id", "compartment_id", "tissue", "drug_id", "concentration_nM",
            "unit", "exposure_hours", "timepoint_hours",
        }
        if not isinstance(action, dict) or set(action) != required_keys:
            raise FeasibilityError("ACTION_SCHEMA_KEYS")
        for key in ("action_id", "run_id", "device_id", "reservoir_id", "circuit_id", "channel_id", "compartment_id", "tissue", "drug_id"):
            _identity(action[key], "action " + key)
        if action["action_id"] in action_ids:
            raise FeasibilityError("DUPLICATE_ACTION_ID")
        action_ids.add(action["action_id"])
        position = action["source_position"]
        if type(position) is not int or position < 0 or position >= 64 or position in by_position:
            raise FeasibilityError("DUPLICATE_OR_INVALID_SOURCE_POSITION")
        if action["unit"] != "nM":
            raise FeasibilityError("ACTION_UNIT_NOT_NM")
        concentration = _dose(action["concentration_nM"])
        exposure = _positive_number(action["exposure_hours"], "exposure_hours")
        timepoint = _positive_number(action["timepoint_hours"], "timepoint_hours")
        if timepoint < exposure:
            raise FeasibilityError("TIMEPOINT_BEFORE_EXPOSURE_END")
        point = (action["device_id"], action["circuit_id"], action["channel_id"])
        if point in physical:
            raise FeasibilityError("DUPLICATE_PHYSICAL_CHANNEL")
        physical.add(point)
        exposure_key = (action["drug_id"], concentration, action["unit"], exposure, timepoint)
        circuit_key = (action["run_id"], action["device_id"], action["circuit_id"])
        previous = circuits.setdefault(circuit_key, exposure_key)
        if previous != exposure_key:
            raise FeasibilityError("SHARED_FLOW_EXPOSURE_CONFLICT")
        reservoir_key = (action["run_id"], action["device_id"], action["reservoir_id"])
        previous = reservoirs.setdefault(reservoir_key, exposure_key)
        if previous != exposure_key:
            raise FeasibilityError("SHARED_RESERVOIR_EXPOSURE_CONFLICT")
        by_position[position] = action

    treatment_circuits = set(circuits)
    treatment_reservoirs = set(reservoirs)
    action_runs = {action["run_id"] for action in actions}
    observed_controls = {run_id: set() for run_id in action_runs}
    control_physical = set()
    control_circuits = set()
    control_reservoirs = set()
    control_ids = set()
    for control in controls:
        required_keys = {
            "control_id", "control_type", "run_id", "device_id", "reservoir_id", "circuit_id", "channel_id"
        }
        if not isinstance(control, dict) or set(control) != required_keys:
            raise FeasibilityError("CONTROL_SCHEMA_KEYS")
        for key in ("control_id", "run_id", "device_id", "reservoir_id", "circuit_id", "channel_id"):
            _identity(control[key], "control " + key)
        if control["control_id"] in control_ids:
            raise FeasibilityError("DUPLICATE_CONTROL_ID")
        control_ids.add(control["control_id"])
        kind = control["control_type"]
        if kind not in ("vehicle", "viability"):
            raise FeasibilityError("INVALID_CONTROL_TYPE")
        point = (control["device_id"], control["circuit_id"], control["channel_id"])
        if point in physical or point in control_physical:
            raise FeasibilityError("CONTROL_RESOURCE_COLLISION")
        circuit = (control["run_id"], control["device_id"], control["circuit_id"])
        if circuit in treatment_circuits:
            raise FeasibilityError("CONTROL_SHARED_FLOW_COLLISION")
        if circuit in control_circuits:
            raise FeasibilityError("CONTROLS_SHARE_FLOW_CIRCUIT")
        control_circuits.add(circuit)
        reservoir = (control["run_id"], control["device_id"], control["reservoir_id"])
        if reservoir in treatment_reservoirs:
            raise FeasibilityError("CONTROL_SHARED_RESERVOIR_COLLISION")
        if reservoir in control_reservoirs:
            raise FeasibilityError("CONTROLS_SHARE_RESERVOIR")
        control_reservoirs.add(reservoir)
        if control["run_id"] not in observed_controls:
            raise FeasibilityError("CONTROL_FOR_UNKNOWN_RUN")
        control_physical.add(point)
        observed_controls[control["run_id"]].add(kind)
    for run_id, observed in sorted(observed_controls.items()):
        missing_controls = sorted(set(required) - observed)
        if missing_controls:
            raise FeasibilityError(
                "MISSING_SEPARATE_CONTROLS_FOR_%s: %s"
                % (run_id, ",".join(missing_controls))
            )
    return by_position, physical, control_physical


def compile_manifest(plan, inventory):
    rows = _validate_plan(plan)
    by_position, treatment_resources, control_resources = _validate_inventory(inventory)
    missing = sorted(set(range(64)) - set(by_position))
    if missing:
        raise FeasibilityError("MISSING_OOC_ACTIONS: " + ",".join(map(str, missing)))
    compiled = []
    for row in rows:
        action = by_position[row["position"]]
        if (
            action["drug_id"] != row["drug_id"]
            or _dose(action["concentration_nM"]) != _dose(row["concentration_nM"])
            or action["unit"] != row["unit"]
        ):
            raise FeasibilityError("EXACT_EXPOSURE_MISMATCH_AT_POSITION_%d" % row["position"])
        compiled.append({
            "source_position": row["position"],
            "native_id": row["native_id"],
            "plate_source": {"plate_instance": row["plate_instance"], "well": row["well"]},
            "ooc_action": action,
        })
    manifest = {
        "schema": "von.ooc.manifest.v1",
        "status": "CONSTRAINT_COMPATIBLE_WITH_DECLARED_INVENTORY",
        "plan_sha256": _sha256(plan),
        "inventory_sha256": _sha256(inventory),
        "treatment_action_count": len(compiled),
        "distinct_treatment_resources": len(treatment_resources),
        "separate_control_resource_count": len(control_resources),
        "controls_in_treatment_budget": False,
        "compiled_actions": compiled,
        "limitations": [
            "Response-free logical resource consistency only; no biological outcome was evaluated.",
            "The caller-declared inventory is unauthenticated; this is not proof of physical feasibility or vendor certification.",
            "Flow rate, volume, materials, adsorption, pump availability and tissue compatibility are not represented.",
            "The original 64-well predictive evidence is not organ-on-chip validation.",
        ],
    }
    manifest["manifest_payload_sha256"] = _sha256(manifest)
    return manifest


def make_synthetic_fixture(plan):
    rows = _validate_plan(plan)
    actions = []
    for row in rows:
        position = row["position"]
        actions.append({
            "action_id": "SYNTHETIC_ACTION_%02d" % position,
            "source_position": position,
            "run_id": "SYNTHETIC_OOC_RUN",
            "device_id": "SYNTHETIC_DEVICE_%02d" % position,
            "reservoir_id": "RESERVOIR_1",
            "circuit_id": "CIRCUIT_1",
            "channel_id": "TREATMENT_1",
            "compartment_id": "TUMOR_COMPARTMENT",
            "tissue": "synthetic_tumor_organoid_fixture",
            "drug_id": row["drug_id"],
            "concentration_nM": row["concentration_nM"],
            "unit": row["unit"],
            "exposure_hours": 96,
            "timepoint_hours": 96,
        })
    controls = [
        {
            "control_id": "SYNTHETIC_VEHICLE_CONTROL",
            "control_type": "vehicle",
            "run_id": "SYNTHETIC_OOC_RUN",
            "device_id": "SYNTHETIC_CONTROL_DEVICE_1",
            "reservoir_id": "RESERVOIR_1",
            "circuit_id": "CIRCUIT_1",
            "channel_id": "CONTROL_1",
        },
        {
            "control_id": "SYNTHETIC_VIABILITY_CONTROL",
            "control_type": "viability",
            "run_id": "SYNTHETIC_OOC_RUN",
            "device_id": "SYNTHETIC_CONTROL_DEVICE_2",
            "reservoir_id": "RESERVOIR_1",
            "circuit_id": "CIRCUIT_1",
            "channel_id": "CONTROL_1",
        },
    ]
    return {
        "schema": "von.ooc.inventory.v1",
        "assay_context": "synthetic_protocol_fixture",
        "source_note": "Invented one-independent-circuit-per-treatment fixture; not a commercial device or laboratory protocol.",
        "required_control_types": ["vehicle", "viability"],
        "actions": actions,
        "controls": controls,
    }


def _write_new(path, value):
    target = Path(path)
    if target.exists():
        raise FeasibilityError("OUTPUT_EXISTS")
    target.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    fixture = commands.add_parser("make-synthetic-fixture")
    fixture.add_argument("--plan", required=True)
    fixture.add_argument("--output", required=True)
    compile_command = commands.add_parser("compile")
    compile_command.add_argument("--plan", required=True)
    compile_command.add_argument("--inventory", required=True)
    compile_command.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        plan = _load(args.plan)
        if args.command == "make-synthetic-fixture":
            value = make_synthetic_fixture(plan)
        else:
            value = compile_manifest(plan, _load(args.inventory))
        _write_new(args.output, value)
        print(json.dumps({"status": "COMPLETE", "output": args.output, "canonical_output_sha256": _sha256(value)}, sort_keys=True))
        return 0
    except (FeasibilityError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "INCOMPATIBLE", "reason": str(exc)}, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
