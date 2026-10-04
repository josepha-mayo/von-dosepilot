#!/usr/bin/env python3
"""Run the single prefrozen patient-balanced simplex-stacking Lib1 study."""
from __future__ import annotations

import argparse
import datetime
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[name] = "1"

import numpy as np

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
sys.path[:0] = [
    str(HERE),
    str(STUDY),
    str(STUDY / "engine"),
    str(STUDY / "acceleration"),
    str(STUDY / "hybrid_residual"),
]

from additive_kernel import AdditiveKernel
from bandwidth_additive import BandwidthAdditive
from simplex_stack import combine_coefficients, fit_simplex
from cross_patient_bandwidth.run_study import (
    bootstrap_delta,
    compare,
    gate,
    load_cache,
    metrics,
    patient_target_risk,
)


OPTIONS = [("identity", 0.0)] + [
    (fraction, ridge)
    for fraction in (0.1, 0.3, 0.6)
    for ridge in (0.1, 1.0, 10.0)
]
EXPECTED = {
    "bandwidth07": 0.0010582750420801538,
    "additive": 0.001060552730112811,
    "r13": 0.001144858681382854,
    "r18": 0.0011414048112341991,
}
CACHE_SHA256 = "2ccd4995699417db72316c8f403095b8ef560f94913b0c8a80fe7429a2d0cbef"
R18_SHA256 = "253998d20b9425c4ceade4269b94f4ed97cb7039ac5ec60838bb15794d47a6e2"
STUDY_LOCK_SHA256 = "8118b562b78b3f55866d6239a38280c942df2c7d81f0b7c4ce71ba0e39ce9ffc"
BASE_COMMIT = "73d410a5fabadb2fc1d9b1c60dcd84ab082cb9a0"
SOURCE_NAMES = [
    "simplex_stack.py", "run_study.py", "verify_study.py",
    "test_simplex_stack.py", "test_study_contract.py", "PROTOCOL.md", "FREEZE.json",
]


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_new(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def verify_freeze(cache_path, r18_path):
    freeze = json.loads((HERE / "FREEZE.json").read_text())
    if freeze["state"] != "FROZEN_BEFORE_FIRST_LIB1_FIT":
        raise ValueError("Study is not frozen before fitting")
    if freeze["base_public_commit"] != BASE_COMMIT:
        raise ValueError("Frozen base commit changed")
    current = subprocess.check_output(
        ["git", "-C", str(STUDY.parent), "rev-parse", "HEAD"], text=True
    ).strip()
    if current != BASE_COMMIT:
        raise ValueError("Worktree moved after study freeze")
    if freeze["cache_sha256"] != sha(cache_path) or sha(cache_path) != CACHE_SHA256:
        raise ValueError("Frozen Lib1 cache identity changed")
    if freeze["r18_sha256"] != sha(r18_path) or sha(r18_path) != R18_SHA256:
        raise ValueError("Frozen R18 identity changed")
    for relative, expected in freeze["source_sha256"].items():
        if sha(STUDY.parent / relative) != expected:
            raise ValueError("Frozen source changed: " + relative)
    for relative, expected in freeze["parent_source_sha256"].items():
        if sha(STUDY.parent / relative) != expected:
            raise ValueError("Frozen parent source changed: " + relative)
    if freeze["options"] != [[name, value] for name, value in OPTIONS]:
        raise ValueError("Frozen option order changed")
    expected_gate = {
        "bandwidth07": {
            "mse": "strictly_lower", "patient_wins": 30,
            "fold_wins": 5, "p90": "nonworse",
        },
        "r13_and_r18": {
            "relative_gain": 0.05, "patient_wins": 40,
            "fold_wins": 4, "p90": "nonworse",
            "both_orientations_below_reference_mse": True,
        },
        "prediction_equivalence_atol": 1e-12,
    }
    if freeze["promotion_gate"] != expected_gate:
        raise ValueError("Frozen promotion gate changed")
    return freeze


def execute(cache_path, r18_path, output):
    from threadpoolctl import threadpool_limits
    from coverage_methods import acquire, fit_prediction_context, CoveragePredictor
    from fast_coverage import plan_panel_fast
    from methods import patient_folds
    import evaluate

    output = Path(output)
    if output.exists():
        raise ValueError("Output exists; choose a fresh directory")
    freeze = verify_freeze(cache_path, r18_path)
    if sha(STUDY / "STUDY_LOCK.json") != STUDY_LOCK_SHA256:
        raise ValueError("Historical study lock changed")
    lock = json.loads((STUDY / "STUDY_LOCK.json").read_text())
    for name, expected in lock["engine_files"].items():
        if Path(name).name != name or sha(STUDY / "engine" / name) != expected:
            raise ValueError("Historical scientific engine changed: " + name)
    for name, version in lock["deps"].items():
        if importlib.metadata.version(name) != version:
            raise ValueError("Pinned dependency required: " + name + "==" + version)

    arrays, catalog = load_cache(cache_path)
    x, y = arrays["x"], arrays["y"]
    patients = arrays["patient_ids"].astype(str)
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    write_new(output / "STARTED.json", {
        "schema": "dosepilot.simplex_stacking.started.v1",
        "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "cache_sha256": sha(cache_path),
        "r18_expected_sha256": R18_SHA256,
        "source_sha256": {name: sha(HERE / name) for name in SOURCE_NAMES},
        "freeze_sha256": sha(HERE / "FREEZE.json"),
        "base_public_commit": freeze["base_public_commit"],
        "options": OPTIONS,
        "automatic_retry": False,
        "private_train_kit_used": True,
        "protected_response_access": False,
    })

    outer, _ = patient_folds(patients, 5, evaluate.SALT + "|outer")
    names = ("simplex_stack", "bandwidth07", "additive")
    predictions = {name: np.full((2, *y.shape), np.nan) for name in (*names, "r13")}
    records = []

    def build(indices):
        plan = plan_panel_fast(x[indices], y[indices], patients[indices], catalog)
        paid_a, paid_b = [acquire(x[indices], plan, orientation) for orientation in ("A", "B")]
        context = fit_prediction_context(
            paid_a, paid_b, y[indices], patients[indices], plan, catalog.target_ids
        )
        base = CoveragePredictor(context, plan, 0.01)
        z = (np.r_[paid_a, paid_b] - base.mean_x) / base.scale_x
        residual = np.r_[y[indices] - base.predict(paid_a), y[indices] - base.predict(paid_b)]
        identities, inverse, counts = np.unique(
            patients[indices], return_inverse=True, return_counts=True
        )
        weights = np.tile(1.0 / (len(identities) * counts[inverse]), 2) / 2.0
        owner = np.asarray(plan["coordinate_target_indices"])
        models = {
            "bandwidth07": BandwidthAdditive(z, residual, weights, owner, 0.7),
            "additive": AdditiveKernel(z, residual, weights, owner),
        }
        fitted = {
            name: (model, [np.zeros((len(z), 24))] + [
                model.coefficients(ridge, fraction)[0]
                for fraction, ridge in OPTIONS[1:]
            ])
            for name, model in models.items()
        }
        return plan, base, fitted

    def choose(indices, salt):
        inner, _ = patient_folds(patients[indices], 3, salt)
        oof = {
            name: np.full((10, 2, len(indices), 24), np.nan)
            for name in ("bandwidth07", "additive")
        }
        for fold in range(3):
            train = indices[inner != fold]
            validate = indices[inner == fold]
            if set(patients[train]) & set(patients[validate]):
                raise ValueError("Patient leakage")
            plan, base, models = build(train)
            for orientation_index, orientation in enumerate(("A", "B")):
                paid = acquire(x[validate], plan, orientation)
                z_query = (paid - base.mean_x) / base.scale_x
                base_prediction = base.predict(paid)
                for name, (model, coefficients) in models.items():
                    cross = model.centered_cross(z_query)
                    for option_index, coefficient in enumerate(coefficients):
                        oof[name][option_index, orientation_index, inner == fold] = (
                            base_prediction + cross @ coefficient
                        )
        if not all(np.isfinite(value).all() for value in oof.values()):
            raise ValueError("Incomplete inner predictions")
        scores = {
            name: [
                float(patient_target_risk(item, y[indices], patients[indices]).mean())
                for item in oof[name]
            ]
            for name in oof
        }
        selected = {name: min(range(10), key=lambda i: (scores[name][i], i)) for name in oof}
        stack_weights, stack_loss = fit_simplex(
            oof["bandwidth07"], y[indices], patients[indices]
        )
        return selected, scores, stack_weights, stack_loss, oof, inner

    with threadpool_limits(limits=1):
        for fold in range(5):
            train = np.flatnonzero(outer != fold)
            test = np.flatnonzero(outer == fold)
            selected, scores, stack_weights, stack_loss, oof, inner = choose(
                train, evaluate.SALT + f"|inner|{fold}"
            )
            plan, base, models = build(train)
            folder = output / f"outer_{fold:02}"
            folder.mkdir()
            write_new(folder / "plan.json", plan)
            np.savez_compressed(
                folder / "inner_predictions_private.npz",
                **oof,
                y=y[train], patients=patients[train], folds=inner,
                stacking_weights=stack_weights,
            )
            bandwidth_model, bandwidth_coefficients = models["bandwidth07"]
            combined = combine_coefficients(np.asarray(bandwidth_coefficients), stack_weights)
            np.savez_compressed(
                folder / "simplex_stack_model_private.npz",
                **base.arrays(), **bandwidth_model.arrays(combined),
                stacking_weights=stack_weights,
                stacking_component_coefficients=np.asarray(bandwidth_coefficients),
                stacking_options=np.asarray([
                    (-1.0, 0.0) if fraction == "identity" else (fraction, ridge)
                    for fraction, ridge in OPTIONS
                ], dtype=float),
            )
            for name in ("bandwidth07", "additive"):
                model, coefficients = models[name]
                np.savez_compressed(
                    folder / (name + "_model_private.npz"),
                    **base.arrays(), **model.arrays(coefficients[selected[name]]),
                )
            native = np.asarray(plan["selected_native_indices"])
            for orientation_index, orientation in enumerate(("A", "B")):
                paid = acquire(x[test], plan, orientation)
                z_query = (paid - base.mean_x) / base.scale_x
                base_prediction = base.predict(paid)
                predictions["r13"][orientation_index, test] = base_prediction
                plates = np.asarray(plan[f"orientation_{orientation}_plate_indices"])
                wells = arrays["well_ids"][test][:, native, plates]
                if (
                    (plates == 0).sum() != 32 or (plates == 1).sum() != 32
                    or not all(len(set(row)) == 64 for row in wells)
                ):
                    raise ValueError("Physical 64-well budget changed")
                masked = np.full_like(x[test], np.nan)
                masked[:, native, plates] = paid
                if not np.array_equal(acquire(masked, plan, orientation), paid):
                    raise ValueError("Unpaid values affected acquired inputs")
                cross = bandwidth_model.centered_cross(z_query)
                predictions["simplex_stack"][orientation_index, test] = base_prediction + cross @ combined
                for name in ("bandwidth07", "additive"):
                    model, coefficients = models[name]
                    predictions[name][orientation_index, test] = (
                        base_prediction + model.centered_cross(z_query) @ coefficients[selected[name]]
                    )
            record = {
                "fold": fold,
                "selected": {name: OPTIONS[selected[name]] for name in selected},
                "inner_scores": scores,
                "stacking_weights": list(map(float, stack_weights)),
                "stacking_active_options": int(np.sum(stack_weights > 1e-10)),
                "stacking_inner_mse": float(stack_loss),
                "stacking_inner_gain_vs_hard_selection": float(
                    1.0 - stack_loss / scores["bandwidth07"][selected["bandwidth07"]]
                ),
                "wells": 64,
                "per_plate": 32,
                "candidate_and_incumbent_plan_identical": True,
            }
            records.append(record)
            write_new(folder / "selection.json", record)
            print(json.dumps({
                "fold": fold,
                "incumbent_selected": record["selected"]["bandwidth07"],
                "stacking_active_options": record["stacking_active_options"],
                "stacking_inner_gain": record["stacking_inner_gain_vs_hard_selection"],
            }), flush=True)

        if not all(np.isfinite(value).all() for value in predictions.values()):
            raise ValueError("Incomplete held-patient predictions")
        prediction_path = output / "predictions_private.npz"
        np.savez_compressed(
            prediction_path, **predictions, y=y, patients=patients, folds=outer,
            sample_ids=arrays["sample_ids"], drug_ids=arrays["drug_ids"],
            library_ids=arrays["library_ids"],
        )
        prediction_sha = sha(prediction_path)
        write_new(output / "PREDICTIONS_COMMITTED.json", {
            "prediction_sha256": prediction_sha,
            "created_before_r18_access": True,
            "protected_response_access": False,
        })

        if sha(r18_path) != R18_SHA256:
            raise ValueError("Archived R18 predictions changed")
        with np.load(r18_path, allow_pickle=False) as source:
            required = {
                "y", "sample_ids", "patient_ids", "drug_ids", "library_ids", "folds",
                "candidate_A", "candidate_B", "r13_A", "r13_B", "r9",
            }
            if set(source.files) != required:
                raise ValueError("Archived R18 schema changed")
            for key, expected in (
                ("y", y), ("sample_ids", arrays["sample_ids"]),
                ("patient_ids", patients), ("drug_ids", arrays["drug_ids"]),
                ("library_ids", arrays["library_ids"]), ("folds", outer),
            ):
                if not np.array_equal(source[key], expected):
                    raise ValueError("Archived R18 identity mismatch: " + key)
            predictions["r18"] = np.stack((source["candidate_A"], source["candidate_B"]))

        metric_values = {
            name: metrics(value, y, patients, outer, arrays["drug_ids"])
            for name, value in predictions.items()
        }
        expected_matches = {
            name: abs(metric_values[name]["mse"] - expected) <= 1e-12
            for name, expected in EXPECTED.items()
        }
        if not all(expected_matches.values()):
            raise ValueError("Historical control failed exact reproduction")
        comparisons = {
            name: compare(
                predictions["simplex_stack"], predictions[name],
                metric_values["simplex_stack"], metric_values[name], y, patients,
            )
            for name in ("bandwidth07", "additive", "r13", "r18")
        }
        maximum_difference = float(np.max(np.abs(
            predictions["simplex_stack"] - predictions["bandwidth07"]
        )))
        equivalent = maximum_difference <= 1e-12
        immediate_gate, historical_gate, promoted = gate(comparisons, equivalent)
        candidate_targets = metric_values["simplex_stack"]["target_mse"]
        incumbent_targets = metric_values["bandwidth07"]["target_mse"]
        regressing_targets = [
            target for target in map(str, arrays["drug_ids"])
            if candidate_targets[target] > incumbent_targets[target]
        ]
        result = {
            "schema": "dosepilot.simplex_stacking.result.v1",
            "status": "COMPLETE",
            "decision": "PROMOTE_PENDING_INDEPENDENT_REPRODUCTION" if promoted else "REJECT_RETAIN_BANDWIDTH07",
            "metrics": metric_values,
            "expected_control_matches": expected_matches,
            "comparisons": comparisons,
            "immediate_gate": immediate_gate,
            "historical_gate": historical_gate,
            "all_gates_passed": promoted,
            "maximum_absolute_prediction_difference_vs_bandwidth07": maximum_difference,
            "prediction_equivalent_to_bandwidth07": equivalent,
            "regressing_targets_vs_bandwidth07": regressing_targets,
            "regressing_target_count_vs_bandwidth07": len(regressing_targets),
            "bootstrap_vs_bandwidth07": bootstrap_delta(
                predictions["simplex_stack"], predictions["bandwidth07"], y, patients
            ),
            "selections": records,
            "prediction_sha256": prediction_sha,
            "cache_sha256": sha(cache_path),
            "r18_sha256": sha(r18_path),
            "source_sha256": {name: sha(HERE / name) for name in SOURCE_NAMES},
            "seconds": time.monotonic() - started,
            "same_task_repeated_adaptive_development": True,
            "independent_validation": False,
            "protected_response_access": False,
            "accepted_kaggle_entry_changed": False,
            "official_competition_score": None,
        }
        write_new(output / "RESULT.json", result)
        print(json.dumps({
            "status": result["status"], "decision": result["decision"],
            "mse": {name: value["mse"] for name, value in metric_values.items()},
            "immediate_gate": immediate_gate, "historical_gate": historical_gate,
        }, indent=2))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--r18", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    if arguments.output.exists():
        parser.error("Output exists; choose a fresh path")
    try:
        execute(arguments.cache, arguments.r18, arguments.output)
    except BaseException as error:
        if arguments.output.exists():
            write_new(arguments.output / "FAILURE.json", {
                "error": str(error), "traceback": traceback.format_exc(),
                "automatic_retry": False, "protected_response_access": False,
            })
        raise


if __name__ == "__main__":
    main()
