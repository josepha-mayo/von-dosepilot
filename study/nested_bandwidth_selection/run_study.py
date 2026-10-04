#!/usr/bin/env python3
"""Retrospective fully nested replay of the opened additive-bandwidth menu."""
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
ROOT = STUDY.parent
sys.path[:0] = [str(STUDY), str(STUDY / "engine"), str(STUDY / "acceleration"),
                str(STUDY / "hybrid_residual")]

from additive_kernel import AdditiveKernel
from bandwidth_additive import BandwidthAdditive
from cross_patient_bandwidth.run_study import load_cache, metrics, compare, patient_target_risk

MULTIPLIERS = (0.7, 1.0, 1.4)
OPTIONS = [("identity", 0.0)] + [
    (fraction, ridge) for fraction in (0.1, 0.3, 0.6) for ridge in (0.1, 1.0, 10.0)
]
EXPECTED = {
    "bandwidth07": 0.0010582750420801538,
    "bandwidth10": 0.001060552730112811,
    "bandwidth14": 0.00106370935859072,
    "r13": 0.001144858681382854,
    "r18": 0.0011414048112341991,
}
CACHE_SHA256 = "2ccd4995699417db72316c8f403095b8ef560f94913b0c8a80fe7429a2d0cbef"
R18_SHA256 = "253998d20b9425c4ceade4269b94f4ed97cb7039ac5ec60838bb15794d47a6e2"
LOCK_SHA256 = "8118b562b78b3f55866d6239a38280c942df2c7d81f0b7c4ce71ba0e39ce9ffc"
BOOTSTRAP_SEED = 20261004
BOOTSTRAP_REPLICATES = 10000


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_new(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def verify_freeze(cache, r18):
    freeze = json.loads((HERE / "FREEZE.json").read_text())
    if freeze["state"] != "FROZEN_BEFORE_FIRST_LIB1_FIT":
        raise ValueError("Evaluation was not frozen before fitting")
    if sha(cache) != CACHE_SHA256 or freeze["cache_sha256"] != CACHE_SHA256:
        raise ValueError("Lib1 cache identity changed")
    if sha(r18) != R18_SHA256 or freeze["r18_sha256"] != R18_SHA256:
        raise ValueError("R18 identity changed")
    for relative, expected in freeze["source_sha256"].items():
        if sha(ROOT / relative) != expected:
            raise ValueError("Frozen source changed: " + relative)
    if freeze["multipliers"] != list(MULTIPLIERS):
        raise ValueError("Multiplier order changed")
    if freeze["options"] != [list(option) for option in OPTIONS]:
        raise ValueError("Spectral option order changed")
    return freeze


def choose_pair(scores):
    """Return deterministic (multiplier-index, option-index)."""
    scores = np.asarray(scores, dtype=float)
    if scores.shape != (len(MULTIPLIERS), len(OPTIONS)) or not np.isfinite(scores).all():
        raise ValueError("All 3x10 inner scores must be finite")
    return min(
        ((mi, oi) for mi in range(len(MULTIPLIERS)) for oi in range(len(OPTIONS))),
        key=lambda pair: (scores[pair[0]][pair[1]], pair[0], pair[1]),
    )


def bootstrap_delta(candidate, reference, y, patients):
    delta = (patient_target_risk(candidate, y, patients).mean(1)
             - patient_target_risk(reference, y, patients).mean(1))
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    sampled = delta[rng.integers(0, len(delta),
                                size=(BOOTSTRAP_REPLICATES, len(delta)))].mean(1)
    return {
        "definition": "nested procedure minus fixed bandwidth-0.7 patient-balanced MSE",
        "point": float(delta.mean()),
        "lower_2_5pct": float(np.quantile(sampled, 0.025)),
        "upper_97_5pct": float(np.quantile(sampled, 0.975)),
        "replicates": BOOTSTRAP_REPLICATES,
        "seed": BOOTSTRAP_SEED,
        "independent_confirmation": False,
    }


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
    if sha(STUDY / "STUDY_LOCK.json") != LOCK_SHA256:
        raise ValueError("Historical study lock changed")
    lock = json.loads((STUDY / "STUDY_LOCK.json").read_text())
    for name, expected in lock["engine_files"].items():
        if sha(STUDY / "engine" / name) != expected:
            raise ValueError("Historical engine changed: " + name)
    for name, version in lock["deps"].items():
        if importlib.metadata.version(name) != version:
            raise ValueError("Pinned dependency required: " + name + "==" + version)

    arrays, catalog = load_cache(cache_path)
    x, y = arrays["x"], arrays["y"]
    patients = arrays["patient_ids"].astype(str)
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    source_names = ("PROTOCOL.md", "run_study.py", "verify_study.py", "test_selection.py", "FREEZE.json")
    write_new(output / "STARTED.json", {
        "schema": "dosepilot.nested_bandwidth_selection.started.v1",
        "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source_sha256": {name: sha(HERE / name) for name in source_names},
        "freeze_sha256": sha(HERE / "FREEZE.json"),
        "cache_sha256": sha(cache_path),
        "r18_expected_sha256": R18_SHA256,
        "multipliers": MULTIPLIERS,
        "options": OPTIONS,
        "automatic_retry": False,
        "private_lib1_train_used": True,
        "protected_response_access": False,
    })

    outer, _ = patient_folds(patients, 5, evaluate.SALT + "|outer")
    control_names = tuple(f"bandwidth{int(round(value * 10)):02d}" for value in MULTIPLIERS)
    predictions = {name: np.full((2, *y.shape), np.nan)
                   for name in ("nested", *control_names, "r13")}
    selections = []

    def build(indices):
        plan = plan_panel_fast(x[indices], y[indices], patients[indices], catalog)
        paid_a, paid_b = [acquire(x[indices], plan, orientation) for orientation in ("A", "B")]
        context = fit_prediction_context(paid_a, paid_b, y[indices], patients[indices],
                                         plan, catalog.target_ids)
        base = CoveragePredictor(context, plan, 0.01)
        z = (np.r_[paid_a, paid_b] - base.mean_x) / base.scale_x
        residual = np.r_[y[indices] - base.predict(paid_a),
                         y[indices] - base.predict(paid_b)]
        identities, inverse, counts = np.unique(
            patients[indices], return_inverse=True, return_counts=True
        )
        weights = np.tile(1.0 / (len(identities) * counts[inverse]), 2) / 2.0
        owner = np.asarray(plan["coordinate_target_indices"])
        models = []
        for multiplier in MULTIPLIERS:
            model = (AdditiveKernel(z, residual, weights, owner) if multiplier == 1.0
                     else BandwidthAdditive(z, residual, weights, owner, multiplier))
            coefficients = [np.zeros((len(z), 24))] + [
                model.coefficients(ridge, fraction)[0]
                for fraction, ridge in OPTIONS[1:]
            ]
            models.append((model, coefficients))
        return plan, base, models

    # Kept inline to ensure each inner fit is constructed exactly once.
    with threadpool_limits(limits=1):
        for fold in range(5):
            train = np.flatnonzero(outer != fold)
            test = np.flatnonzero(outer == fold)
            inner, _ = patient_folds(patients[train], 3, evaluate.SALT + f"|inner|{fold}")
            oof = np.full((len(MULTIPLIERS), len(OPTIONS), 2, len(train), 24), np.nan)
            for inner_fold in range(3):
                inner_train = train[inner != inner_fold]
                inner_valid = train[inner == inner_fold]
                if set(patients[inner_train]) & set(patients[inner_valid]):
                    raise ValueError("Patient leakage")
                plan_i, base_i, models_i = build(inner_train)
                for orientation_index, orientation in enumerate(("A", "B")):
                    paid = acquire(x[inner_valid], plan_i, orientation)
                    z_query = (paid - base_i.mean_x) / base_i.scale_x
                    base_prediction = base_i.predict(paid)
                    for multiplier_index, (model, coefficients) in enumerate(models_i):
                        cross = model.centered_cross(z_query)
                        for option_index, coefficient in enumerate(coefficients):
                            oof[multiplier_index, option_index, orientation_index,
                                inner == inner_fold] = base_prediction + cross @ coefficient
            scores = np.asarray([
                [patient_target_risk(oof[mi, oi], y[train], patients[train]).mean()
                 for oi in range(len(OPTIONS))]
                for mi in range(len(MULTIPLIERS))
            ])
            selected_pair = choose_pair(scores)
            fixed_options = [min(range(len(OPTIONS)), key=lambda oi: (scores[mi, oi], oi))
                             for mi in range(len(MULTIPLIERS))]
            plan, base, models = build(train)
            folder = output / f"outer_{fold:02d}"
            folder.mkdir()
            write_new(folder / "plan.json", plan)
            np.savez_compressed(folder / "inner_predictions_private.npz", predictions=oof,
                                y=y[train], patients=patients[train], folds=inner)
            native = np.asarray(plan["selected_native_indices"])
            for mi, (model, coefficients) in enumerate(models):
                np.savez_compressed(folder / f"bandwidth_{MULTIPLIERS[mi]:.1f}_model_private.npz",
                                    **base.arrays(), **model.arrays(coefficients[fixed_options[mi]]))
            for orientation_index, orientation in enumerate(("A", "B")):
                paid = acquire(x[test], plan, orientation)
                z_query = (paid - base.mean_x) / base.scale_x
                base_prediction = base.predict(paid)
                predictions["r13"][orientation_index, test] = base_prediction
                plates = np.asarray(plan[f"orientation_{orientation}_plate_indices"])
                wells = arrays["well_ids"][test][:, native, plates]
                if ((plates == 0).sum() != 32 or (plates == 1).sum() != 32
                        or not all(len(set(row)) == 64 for row in wells)):
                    raise ValueError("Physical 64-well budget changed")
                for mi, name in enumerate(control_names):
                    model, coefficients = models[mi]
                    predictions[name][orientation_index, test] = (
                        base_prediction + model.centered_cross(z_query) @ coefficients[fixed_options[mi]]
                    )
                mi, oi = selected_pair
                model, coefficients = models[mi]
                predictions["nested"][orientation_index, test] = (
                    base_prediction + model.centered_cross(z_query) @ coefficients[oi]
                )
            record = {
                "fold": fold,
                "nested_selected_multiplier": MULTIPLIERS[selected_pair[0]],
                "nested_selected_option": OPTIONS[selected_pair[1]],
                "fixed_selected_options": dict(zip(control_names,
                    [OPTIONS[index] for index in fixed_options])),
                "inner_scores": scores.tolist(),
                "wells": 64,
                "per_plate": 32,
                "all_bandwidths_share_plan": True,
            }
            selections.append(record)
            write_new(folder / "selection.json", record)
            print(json.dumps({"fold": fold, "multiplier": record["nested_selected_multiplier"],
                              "option": record["nested_selected_option"]}), flush=True)

        if not all(np.isfinite(value).all() for value in predictions.values()):
            raise ValueError("Incomplete predictions")
        prediction_path = output / "predictions_private.npz"
        np.savez_compressed(prediction_path, **predictions, y=y, patients=patients,
                            folds=outer, sample_ids=arrays["sample_ids"],
                            drug_ids=arrays["drug_ids"], library_ids=arrays["library_ids"])
        write_new(output / "PREDICTIONS_COMMITTED.json", {
            "prediction_sha256": sha(prediction_path),
            "created_before_r18_access": True,
            "protected_response_access": False,
        })

        with np.load(r18_path, allow_pickle=False) as source:
            for key, expected in (("y", y), ("sample_ids", arrays["sample_ids"]),
                                  ("patient_ids", patients), ("drug_ids", arrays["drug_ids"]),
                                  ("library_ids", arrays["library_ids"]), ("folds", outer)):
                if not np.array_equal(source[key], expected):
                    raise ValueError("R18 identity mismatch: " + key)
            predictions["r18"] = np.stack((source["candidate_A"], source["candidate_B"]))

        metric_values = {name: metrics(value, y, patients, outer, arrays["drug_ids"])
                         for name, value in predictions.items()}
        matches = {name: abs(metric_values[name]["mse"] - value) <= 1e-12
                   for name, value in EXPECTED.items()}
        if not all(matches.values()):
            raise ValueError("Historical control mismatch")
        comparisons = {name: compare(predictions["nested"], predictions[name],
                                     metric_values["nested"], metric_values[name], y, patients)
                       for name in ("bandwidth07", "bandwidth10", "bandwidth14", "r13", "r18")}
        nested_targets = metric_values["nested"]["target_mse"]
        incumbent_targets = metric_values["bandwidth07"]["target_mse"]
        regressing = [target for target in map(str, arrays["drug_ids"])
                      if nested_targets[target] > incumbent_targets[target]]
        result = {
            "schema": "dosepilot.nested_bandwidth_selection.result.v1",
            "status": "COMPLETE",
            "decision": "EVALUATION_ONLY_RETAIN_BANDWIDTH07",
            "metrics": metric_values,
            "expected_control_matches": matches,
            "comparisons": comparisons,
            "nested_selections": selections,
            "selection_counts": {str(multiplier): sum(
                item["nested_selected_multiplier"] == multiplier for item in selections)
                for multiplier in MULTIPLIERS},
            "regressing_targets_vs_bandwidth07": regressing,
            "regressing_target_count_vs_bandwidth07": len(regressing),
            "bootstrap_vs_bandwidth07": bootstrap_delta(
                predictions["nested"], predictions["bandwidth07"], y, patients),
            "prediction_sha256": sha(prediction_path),
            "cache_sha256": sha(cache_path),
            "r18_sha256": sha(r18_path),
            "source_sha256": {name: sha(HERE / name) for name in source_names},
            "seconds": time.monotonic() - started,
            "algorithmically_nested_bandwidth_choice": True,
            "same_task_repeated_adaptive_development": True,
            "independent_validation": False,
            "selection_corrected_for_wider_historical_campaign": False,
            "protected_response_access": False,
            "accepted_kaggle_entry_changed": False,
            "official_competition_score": None,
        }
        write_new(output / "RESULT.json", result)
        print(json.dumps({"status": result["status"], "mse": {
            name: value["mse"] for name, value in metric_values.items()},
            "selection_counts": result["selection_counts"]}, indent=2))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--r18", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
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
