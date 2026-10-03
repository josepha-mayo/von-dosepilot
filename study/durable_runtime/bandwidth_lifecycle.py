#!/usr/bin/env python3
"""Commit, recover and predict with the bandwidth-0.7 DosePilot model.

The fitted model and 64-well plan are inputs; this interface does not fit,
select or validate a biological model.  A fresh commitment is mandatory.
"""
from pathlib import Path
import argparse
import importlib.util
import json
import sys

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
sys.path[:0] = [str(HERE), str(STUDY / "hybrid_residual")]

from bandwidth_workflow import load_backend as bandwidth_backend
from frame_lock import frame_lock

POLICY = "dosepilot.bandwidth07_complete_lifecycle.v1"


def load_backend():
    backend = bandwidth_backend()
    previous = backend.model_receipt
    hashes = {
        name: backend.digest(path)
        for name, path in {
            "lifecycle": HERE / "bandwidth_lifecycle.py",
            "frame_lock": HERE / "frame_lock.py",
            "baseline_recovery": STUDY / "hybrid_residual" / "recover_baseline.py",
            "recovery_completion": STUDY / "hybrid_residual" / "complete_recovery.py",
        }.items()
    }

    def receipt(model_dir, construction_sha256):
        return dict(
            previous(model_dir, construction_sha256),
            lifecycle_policy=POLICY,
            lifecycle_code_sha256=hashes,
        )

    backend.model_receipt = receipt
    return backend


def _recovery_module(name, backend):
    path = STUDY / "hybrid_residual" / (name + ".py")
    spec = importlib.util.spec_from_file_location(
        "_dosepilot_bandwidth_lifecycle_" + name, path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # This module instance is isolated.  The historical additive entry points
    # and their imported model class remain unchanged.
    module.load_backend = lambda: backend
    module.AdditiveModel = backend.SpectralModel
    return module


def execute(
    command,
    *,
    model_dir,
    construction_sha256,
    ledger_dir,
    commitment,
    inventory=None,
    template=None,
    measurements=None,
    output=None,
    acknowledge_baseline_only=False,
    _on_locked=None,
):
    if command not in ("commit", "recover", "predict"):
        raise ValueError("UNKNOWN_LIFECYCLE_COMMAND")
    backend = load_backend()
    receipt = backend.model_receipt(model_dir, construction_sha256)
    if command == "commit":
        if inventory is None or template is None:
            raise ValueError("INVENTORY_AND_TEMPLATE_REQUIRED")
        identity, _ = backend.load_json(inventory)
    else:
        if measurements is None or output is None:
            raise ValueError("MEASUREMENTS_AND_OUTPUT_REQUIRED")
        identity, _ = backend.load_json(commitment)
    if not isinstance(identity, dict):
        raise ValueError("IDENTITY_DOCUMENT_MUST_BE_OBJECT")
    sample = backend.text_id(identity.get("sample_id"), "sample_id")
    run = backend.text_id(identity.get("run_id"), "run_id")
    frame = backend.frame_id(receipt, sample, run)
    with frame_lock(ledger_dir, frame):
        if _on_locked is not None:
            _on_locked()
        snapshot = inventory if command == "commit" else commitment
        current_identity, _ = backend.load_json(snapshot)
        if current_identity != identity:
            raise ValueError("IDENTITY_CHANGED_DURING_LOCK_ACQUISITION")
        if command == "commit":
            return backend.commit(
                model_dir,
                construction_sha256,
                inventory,
                commitment,
                template,
                ledger_dir,
            )
        if command == "recover":
            recovery = _recovery_module("recover_baseline", backend)
            return recovery.recover(
                model_dir,
                construction_sha256,
                commitment,
                measurements,
                output,
                ledger_dir,
                acknowledge_baseline_only,
            )
        history = list(Path(ledger_dir).glob(frame + ".baseline_recovery.*.json"))
        if history:
            completion = _recovery_module("complete_recovery", backend)
            return completion.complete(
                model_dir,
                construction_sha256,
                commitment,
                measurements,
                output,
                ledger_dir,
            )
        return backend.predict(
            model_dir,
            construction_sha256,
            commitment,
            measurements,
            output,
            ledger_dir,
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("commit", "recover", "predict"):
        item = sub.add_parser(command)
        for name in ("model-dir", "ledger-dir", "commitment"):
            item.add_argument("--" + name, required=True, type=Path)
        item.add_argument("--construction-sha256", required=True)
        if command == "commit":
            item.add_argument("--inventory", required=True, type=Path)
            item.add_argument("--template", required=True, type=Path)
        else:
            item.add_argument("--measurements", required=True, type=Path)
            item.add_argument("--output", required=True, type=Path)
        if command == "recover":
            item.add_argument("--acknowledge-baseline-only", action="store_true")
    args = parser.parse_args()
    try:
        values = vars(args).copy()
        command = values.pop("command")
        result = execute(command, **values)
        if command == "commit":
            summary = {
                "status": "COMMITTED",
                "commitment_id": result["commitment_id"],
                "model_kind": result["model_receipt"]["model_kind"],
                "bandwidth_multiplier": result["model_receipt"]["bandwidth_multiplier"],
                "treatment_wells": 64,
                "plate_counts": result["plate_counts"],
            }
        elif command == "recover":
            summary = {
                "status": result["status"],
                "baseline_outputs": len(result["baseline_predictions"]),
                "primary_outputs": 0,
                "recovery_id": result["recovery_id"],
            }
        else:
            summary = {
                "status": result["status"],
                "primary_outputs": len(result["predictions"]),
                "model_kind": result["model_kind"],
                "recovery_history_verified": bool(
                    result["evidence"].get("lifecycle_policy") == POLICY
                ),
            }
        print(json.dumps(summary, sort_keys=True))
        return 0
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print(json.dumps({"status": "REJECTED", "reason": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
