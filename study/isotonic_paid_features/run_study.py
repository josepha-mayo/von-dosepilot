#!/usr/bin/env python3
"""Run the single prefrozen isotonic-paid-feature Lib1 study."""
from __future__ import annotations

import argparse
import datetime
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import time
import traceback

for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[name] = "1"

import numpy as np

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
sys.path[:0] = [str(HERE), str(STUDY), str(STUDY / "engine"),
                str(STUDY / "acceleration"), str(STUDY / "hybrid_residual")]

from bandwidth_additive import BandwidthAdditive
from isotonic_features import project_paid
from cross_patient_bandwidth.run_study import (
    bootstrap_delta, compare, gate, load_cache, metrics, patient_target_risk,
)

OPTIONS = [("identity", 0.0)] + [
    (fraction, ridge) for fraction in (0.1, 0.3, 0.6) for ridge in (0.1, 1.0, 10.0)
]
EXPECTED = {
    "bandwidth07": 0.0010582750420801538,
    "r13": 0.001144858681382854,
    "r18": 0.0011414048112341991,
}
CACHE_SHA256 = "2ccd4995699417db72316c8f403095b8ef560f94913b0c8a80fe7429a2d0cbef"
R18_SHA256 = "253998d20b9425c4ceade4269b94f4ed97cb7039ac5ec60838bb15794d47a6e2"
STUDY_LOCK_SHA256 = "8118b562b78b3f55866d6239a38280c942df2c7d81f0b7c4ce71ba0e39ce9ffc"
SOURCE_NAMES = ["isotonic_features.py", "run_study.py", "verify_study.py",
                "test_isotonic_features.py", "PROTOCOL.json", "PROPOSAL.json"]


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_new(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def verify_freeze(cache_path, r18_path):
    freeze = json.loads((HERE / "FREEZE.json").read_text())
    if freeze.get("state") != "FROZEN_BEFORE_FIRST_LIB1_FIT":
        raise ValueError("Study is not frozen before fitting")
    if sha(cache_path) != CACHE_SHA256 or freeze.get("cache_sha256") != CACHE_SHA256:
        raise ValueError("Authenticated Lib1 cache changed")
    if sha(r18_path) != R18_SHA256 or freeze.get("r18_sha256") != R18_SHA256:
        raise ValueError("Archived R18 identity changed")
    for name in SOURCE_NAMES:
        if freeze["source_sha256"].get(name) != sha(HERE / name):
            raise ValueError("Frozen study source changed: " + name)
    for relative, expected in freeze["parent_source_sha256"].items():
        if sha(STUDY.parent / relative) != expected:
            raise ValueError("Frozen parent source changed: " + relative)
    if freeze.get("options") != [[a, b] for a, b in OPTIONS]:
        raise ValueError("Frozen option order changed")
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
        "schema": "dosepilot.isotonic_paid_features.started.v1",
        "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "cache_sha256": sha(cache_path),
        "r18_expected_sha256": R18_SHA256,
        "source_sha256": {name: sha(HERE / name) for name in SOURCE_NAMES},
        "freeze_sha256": sha(HERE / "FREEZE.json"),
        "protocol_sha256": sha(HERE / "PROTOCOL.json"),
        "proposal_sha256": sha(HERE / "PROPOSAL.json"),
        "automatic_retry": False,
        "private_train_kit_used": True,
        "protected_response_access": False,
    })

    outer, _ = patient_folds(patients, 5, evaluate.SALT + "|outer")
    names = ("isotonic", "bandwidth07")
    predictions = {name: np.full((2, *y.shape), np.nan) for name in (*names, "r13")}
    records = []

    def build(indices):
        plan = plan_panel_fast(x[indices], y[indices], patients[indices], catalog)
        raw = [acquire(x[indices], plan, orientation) for orientation in ("A", "B")]
        projected = [project_paid(value, plan) for value in raw]
        identities, inverse, counts = np.unique(
            patients[indices], return_inverse=True, return_counts=True
        )
        weights = np.tile(1.0 / (len(identities) * counts[inverse]), 2) / 2.0
        owner = np.asarray(plan["coordinate_target_indices"])
        fitted = {}
        for name, pair in (("isotonic", projected), ("bandwidth07", raw)):
            context = fit_prediction_context(
                pair[0], pair[1], y[indices], patients[indices], plan, catalog.target_ids
            )
            base = CoveragePredictor(context, plan, 0.01)
            z = (np.r_[pair[0], pair[1]] - base.mean_x) / base.scale_x
            residual = np.r_[y[indices] - base.predict(pair[0]),
                             y[indices] - base.predict(pair[1])]
            model = BandwidthAdditive(z, residual, weights, owner, 0.7)
            coefficients = [np.zeros((len(z), 24))] + [
                model.coefficients(ridge, fraction)[0]
                for fraction, ridge in OPTIONS[1:]
            ]
            fitted[name] = (base, model, coefficients)
        adjustment = np.r_[projected[0] - raw[0], projected[1] - raw[1]]
        summary = {
            "value_fraction_changed": float(np.mean(np.abs(adjustment) > 1e-15)),
            "mean_squared_adjustment": float(np.mean(adjustment ** 2)),
            "maximum_absolute_adjustment": float(np.max(np.abs(adjustment))),
        }
        return plan, fitted, summary

    def choose(indices, salt):
        inner, _ = patient_folds(patients[indices], 3, salt)
        oof = {name: np.full((10, 2, len(indices), 24), np.nan) for name in names}
        for fold in range(3):
            train = indices[inner != fold]; validate = indices[inner == fold]
            if set(patients[train]) & set(patients[validate]):
                raise ValueError("Patient leakage")
            plan, fitted, _ = build(train)
            for orientation_index, orientation in enumerate(("A", "B")):
                raw = acquire(x[validate], plan, orientation)
                for name, paid in (("isotonic", project_paid(raw, plan)),
                                   ("bandwidth07", raw)):
                    base, model, coefficients = fitted[name]
                    z_query = (paid - base.mean_x) / base.scale_x
                    base_prediction = base.predict(paid)
                    cross = model.centered_cross(z_query)
                    for option_index, coefficient in enumerate(coefficients):
                        oof[name][option_index, orientation_index, inner == fold] = (
                            base_prediction + cross @ coefficient
                        )
        if not all(np.isfinite(value).all() for value in oof.values()):
            raise ValueError("Incomplete inner predictions")
        scores = {name: [float(patient_target_risk(item, y[indices], patients[indices]).mean())
                         for item in oof[name]] for name in names}
        selected = {name: min(range(10), key=lambda i: (scores[name][i], i)) for name in names}
        return selected, scores, inner

    with threadpool_limits(limits=1):
        for fold in range(5):
            train = np.flatnonzero(outer != fold); test = np.flatnonzero(outer == fold)
            selected, scores, inner = choose(train, evaluate.SALT + f"|inner|{fold}")
            plan, fitted, adjustment = build(train)
            folder = output / f"outer_{fold:02}"; folder.mkdir()
            write_new(folder / "plan.json", plan)
            native = np.asarray(plan["selected_native_indices"])
            for orientation_index, orientation in enumerate(("A", "B")):
                raw = acquire(x[test], plan, orientation)
                raw_base = fitted["bandwidth07"][0]
                predictions["r13"][orientation_index, test] = raw_base.predict(raw)
                plates = np.asarray(plan[f"orientation_{orientation}_plate_indices"])
                wells = arrays["well_ids"][test][:, native, plates]
                if ((plates == 0).sum() != 32 or (plates == 1).sum() != 32
                        or not all(len(set(row)) == 64 for row in wells)):
                    raise ValueError("Physical 64-well budget changed")
                masked = np.full_like(x[test], np.nan); masked[:, native, plates] = raw
                if not np.array_equal(acquire(masked, plan, orientation), raw):
                    raise ValueError("Unpaid values affected acquired inputs")
                for name, paid in (("isotonic", project_paid(raw, plan)),
                                   ("bandwidth07", raw)):
                    base, model, coefficients = fitted[name]
                    query = (paid - base.mean_x) / base.scale_x
                    predictions[name][orientation_index, test] = (
                        base.predict(paid) + model.centered_cross(query) @ coefficients[selected[name]]
                    )
            record = {
                "fold": fold,
                "selected": {name: OPTIONS[selected[name]] for name in names},
                "inner_scores": scores,
                "fitting_projection_summary": adjustment,
                "wells": 64,
                "per_plate": 32,
                "candidate_and_incumbent_plan_identical": True,
            }
            records.append(record); write_new(folder / "selection.json", record)
            print(json.dumps({"fold": fold, "selected": record["selected"]}), flush=True)

        if not all(np.isfinite(value).all() for value in predictions.values()):
            raise ValueError("Incomplete held-patient predictions")
        prediction_path = output / "predictions_private.npz"
        np.savez_compressed(prediction_path, **predictions, y=y, patients=patients,
                            folds=outer, sample_ids=arrays["sample_ids"],
                            drug_ids=arrays["drug_ids"], library_ids=arrays["library_ids"])
        prediction_sha = sha(prediction_path)
        write_new(output / "PREDICTIONS_COMMITTED.json", {
            "prediction_sha256": prediction_sha,
            "created_before_r18_access": True,
            "protected_response_access": False,
        })

        with np.load(r18_path, allow_pickle=False) as source:
            required = {"y", "sample_ids", "patient_ids", "drug_ids", "library_ids", "folds",
                        "candidate_A", "candidate_B", "r13_A", "r13_B", "r9"}
            if set(source.files) != required:
                raise ValueError("Archived R18 schema changed")
            for key, expected in (("y", y), ("sample_ids", arrays["sample_ids"]),
                                  ("patient_ids", patients), ("drug_ids", arrays["drug_ids"]),
                                  ("library_ids", arrays["library_ids"]), ("folds", outer)):
                if not np.array_equal(source[key], expected):
                    raise ValueError("Archived R18 identity mismatch: " + key)
            predictions["r18"] = np.stack((source["candidate_A"], source["candidate_B"]))

        metric_values = {name: metrics(value, y, patients, outer, arrays["drug_ids"])
                         for name, value in predictions.items()}
        expected_matches = {name: abs(metric_values[name]["mse"] - expected) <= 1e-12
                            for name, expected in EXPECTED.items()}
        if not all(expected_matches.values()):
            raise ValueError("Historical control failed exact reproduction")
        comparisons = {name: compare(predictions["isotonic"], predictions[name],
                                     metric_values["isotonic"], metric_values[name], y, patients)
                       for name in ("bandwidth07", "r13", "r18")}
        maximum_difference = float(np.max(np.abs(predictions["isotonic"] - predictions["bandwidth07"])))
        immediate_gate, historical_gate, promoted = gate(comparisons, maximum_difference <= 1e-12)
        candidate_targets = metric_values["isotonic"]["target_mse"]
        incumbent_targets = metric_values["bandwidth07"]["target_mse"]
        regressing_targets = [target for target in map(str, arrays["drug_ids"])
                              if candidate_targets[target] > incumbent_targets[target]]
        candidate_patient = patient_target_risk(predictions["isotonic"], y, patients).mean(1)
        incumbent_patient = patient_target_risk(predictions["bandwidth07"], y, patients).mean(1)
        result = {
            "schema": "dosepilot.isotonic_paid_features.result.v1",
            "status": "COMPLETE",
            "decision": "PROMOTE_PENDING_INDEPENDENT_REPRODUCTION" if promoted else "REJECT_RETAIN_BANDWIDTH07",
            "metrics": metric_values,
            "expected_control_matches": expected_matches,
            "comparisons": comparisons,
            "immediate_gate": immediate_gate,
            "historical_gate": historical_gate,
            "all_gates_passed": promoted,
            "maximum_absolute_prediction_difference_vs_bandwidth07": maximum_difference,
            "regressing_targets_vs_bandwidth07": regressing_targets,
            "regressing_target_count_vs_bandwidth07": len(regressing_targets),
            "regressing_patient_count_vs_bandwidth07": int(np.sum(candidate_patient > incumbent_patient)),
            "bootstrap_vs_bandwidth07": bootstrap_delta(predictions["isotonic"],
                                                         predictions["bandwidth07"], y, patients),
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
        print(json.dumps({"decision": result["decision"],
                          "mse": {k: v["mse"] for k, v in metric_values.items()},
                          "immediate_gate": immediate_gate}, indent=2))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--r18", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        execute(args.cache, args.r18, args.output)
    except BaseException as error:
        if args.output.exists() and not (args.output / "FAILURE.json").exists():
            write_new(args.output / "FAILURE.json", {
                "error": str(error), "traceback": traceback.format_exc(),
                "automatic_retry": False, "protected_response_access": False,
            })
        raise


if __name__ == "__main__":
    main()
