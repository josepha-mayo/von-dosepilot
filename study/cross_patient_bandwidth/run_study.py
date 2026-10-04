#!/usr/bin/env python3
"""Run the single prefrozen cross-patient median-bandwidth Lib1 study."""
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
from median_bandwidth import CrossPatientMedianBandwidth


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
BOOTSTRAP_SEED = 20261004
BOOTSTRAP_REPLICATES = 10000
BASE_COMMIT = "b80ca4c6668adfa2a82173aed1dc6cd8119bdd3c"
EXPECTED_BANDWIDTH07 = {
    "p90_rmse": 0.0378942853087202,
    "orientation_mse": [0.0011047521616732161, 0.0010117979224870915],
}
EXPECTED_BANDWIDTH07_COMPARISONS = {
    "additive": {"patient_wins": 38, "patient_losses": 21, "fold_wins": 5},
    "r13": {"patient_wins": 49, "patient_losses": 10, "fold_wins": 5},
    "r18": {"patient_wins": 47, "patient_losses": 12, "fold_wins": 5},
}


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
    current_commit = subprocess.check_output(
        ["git", "-C", str(STUDY.parent), "rev-parse", "HEAD"], text=True
    ).strip()
    if current_commit != BASE_COMMIT:
        raise ValueError("Worktree moved after study freeze")
    if freeze["cache_sha256"] != sha(cache_path) or freeze["cache_sha256"] != CACHE_SHA256:
        raise ValueError("Frozen Lib1 cache identity changed")
    if freeze["r18_sha256"] != sha(r18_path) or freeze["r18_sha256"] != R18_SHA256:
        raise ValueError("Frozen R18 identity changed")
    for relative, expected in freeze["source_sha256"].items():
        if sha(STUDY.parent / relative) != expected:
            raise ValueError("Frozen study source changed: " + relative)
    for relative, expected in freeze["parent_source_sha256"].items():
        if sha(STUDY.parent / relative) != expected:
            raise ValueError("Frozen parent source changed: " + relative)
    if freeze["options"] != [[name, value] for name, value in OPTIONS]:
        raise ValueError("Frozen option order changed")
    if freeze["promotion_gate"] != {
        "bandwidth07": {"mse": "strictly_lower", "patient_wins": 30, "fold_wins": 5, "p90": "nonworse"},
        "r13_and_r18": {"relative_gain": 0.05, "patient_wins": 40, "fold_wins": 4, "p90": "nonworse", "both_orientations_below_reference_mse": True},
        "prediction_equivalence_atol": 1e-12,
    }:
        raise ValueError("Frozen promotion gate changed")
    return freeze


def load_cache(path):
    from compact_train import catalog_layout, read_catalog

    path = Path(path)
    if sha(path) != CACHE_SHA256:
        raise ValueError("Authenticated Lib1 TRAIN cache changed")
    required = {
        "y", "sample_ids", "patient_ids", "drug_ids", "library_ids", "x",
        "well_ids", "native_ids", "native_target_indices", "concentrations",
    }
    with np.load(path, allow_pickle=False) as source:
        if set(source.files) != required:
            raise ValueError("Lib1 TRAIN cache schema changed")
        arrays = {name: source[name].copy() for name in required}
    spec = read_catalog(STUDY / "TRAIN_CATALOG.json")
    layout, catalog = catalog_layout(spec)
    if arrays["y"].shape != (119, 24) or arrays["x"].shape != (119, 164, 2):
        raise ValueError("Lib1 TRAIN dimensions changed")
    if arrays["well_ids"].shape != arrays["x"].shape:
        raise ValueError("Physical well identities are misaligned")
    if len(set(arrays["patient_ids"].astype(str))) != 59:
        raise ValueError("Whole-patient denominator changed")
    if set(arrays["library_ids"].astype(str)) != {"lib1"}:
        raise ValueError("Only Lib1 TRAIN is authorized")
    if not np.isfinite(arrays["y"]).all() or not np.isfinite(arrays["x"]).all():
        raise ValueError("Lib1 TRAIN cache contains nonfinite numerical input")
    if not np.array_equal(arrays["drug_ids"].astype(str), catalog.target_ids.astype(str)):
        raise ValueError("Target identities changed")
    if not np.array_equal(arrays["native_ids"].astype(str), catalog.native_ids.astype(str)):
        raise ValueError("Native identities changed")
    if not np.array_equal(arrays["native_target_indices"], catalog.native_target_indices):
        raise ValueError("Native ownership changed")
    if tuple(arrays["concentrations"].astype(str)) != tuple(map(str, catalog.concentrations)):
        raise ValueError("Native concentrations changed")
    return arrays, catalog


def patient_target_risk(predictions, y, patients):
    error = ((predictions[0] - y) ** 2 + (predictions[1] - y) ** 2) / 2.0
    return np.stack([error[patients == value].mean(0) for value in np.unique(patients)])


def metrics(predictions, y, patients, folds, targets):
    patient_target = patient_target_risk(predictions, y, patients)
    patient_mean = patient_target.mean(1)
    patient_folds = np.asarray(
        [folds[np.flatnonzero(patients == value)[0]] for value in np.unique(patients)]
    )
    return {
        "mse": float(patient_mean.mean()),
        "p90_rmse": float(np.quantile(np.sqrt(patient_mean), 0.9)),
        "fold_mse": [float(patient_mean[patient_folds == fold].mean()) for fold in range(5)],
        "target_mse": dict(zip(map(str, targets), map(float, patient_target.mean(0)))),
        "orientation_mse": [
            float(np.mean([
                ((predictions[o, patients == value] - y[patients == value]) ** 2).mean()
                for value in np.unique(patients)
            ]))
            for o in (0, 1)
        ],
    }


def compare(candidate_predictions, reference_predictions, candidate, reference, y, patients):
    candidate_patient = patient_target_risk(candidate_predictions, y, patients).mean(1)
    reference_patient = patient_target_risk(reference_predictions, y, patients).mean(1)
    wins = int(np.sum(candidate_patient < reference_patient))
    losses = int(np.sum(candidate_patient > reference_patient))
    return {
        "relative_gain": float(1.0 - candidate["mse"] / reference["mse"]),
        "patient_wins": wins,
        "patient_losses": losses,
        "patient_ties": int(len(candidate_patient) - wins - losses),
        "fold_wins": int(sum(a < b for a, b in zip(candidate["fold_mse"], reference["fold_mse"]))),
        "p90_nonworse": bool(candidate["p90_rmse"] <= reference["p90_rmse"]),
        "orientation_below_reference_expected_mse": [
            bool(value < reference["mse"]) for value in candidate["orientation_mse"]
        ],
    }


def gate(comparisons, equivalent):
    immediate = comparisons["bandwidth07"]
    immediate_gate = {
        "strictly_lower_mse": immediate["relative_gain"] > 0.0,
        "patient_wins_at_least_30": immediate["patient_wins"] >= 30,
        "all_five_folds_favorable": immediate["fold_wins"] == 5,
        "p90_nonworse": immediate["p90_nonworse"],
        "not_prediction_equivalent": not equivalent,
    }
    historical = {}
    for name in ("r13", "r18"):
        comparison = comparisons[name]
        historical[name] = {
            "mse_reduction_at_least_5pct": comparison["relative_gain"] >= 0.05,
            "patient_wins_at_least_40": comparison["patient_wins"] >= 40,
            "fold_wins_at_least_4": comparison["fold_wins"] >= 4,
            "p90_nonworse": comparison["p90_nonworse"],
            "both_orientation_mse_below_reference_expected_mse": all(
                comparison["orientation_below_reference_expected_mse"]
            ),
        }
    passed = all(immediate_gate.values()) and all(
        all(value.values()) for value in historical.values()
    )
    return immediate_gate, historical, passed


def bootstrap_delta(candidate_predictions, incumbent_predictions, y, patients):
    candidate = patient_target_risk(candidate_predictions, y, patients).mean(1)
    incumbent = patient_target_risk(incumbent_predictions, y, patients).mean(1)
    delta = candidate - incumbent
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    sampled = delta[rng.integers(0, len(delta), size=(BOOTSTRAP_REPLICATES, len(delta)))].mean(1)
    return {
        "definition": "candidate minus bandwidth-0.7 patient-balanced MSE; negative favors candidate",
        "point": float(delta.mean()),
        "lower_2_5pct": float(np.quantile(sampled, 0.025)),
        "upper_97_5pct": float(np.quantile(sampled, 0.975)),
        "replicates": BOOTSTRAP_REPLICATES,
        "seed": BOOTSTRAP_SEED,
        "selection_corrected": False,
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
    x = arrays["x"]
    y = arrays["y"]
    patients = arrays["patient_ids"].astype(str)
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    source_names = ["median_bandwidth.py", "run_study.py", "verify_study.py", "PROTOCOL.md", "FREEZE.json"]
    write_new(output / "STARTED.json", {
        "schema": "dosepilot.cross_patient_bandwidth.started.v1",
        "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "cache_sha256": sha(cache_path),
        "r18_expected_sha256": R18_SHA256,
        "source_sha256": {name: sha(HERE / name) for name in source_names},
        "freeze_sha256": sha(HERE / "FREEZE.json"),
        "base_public_commit": freeze["base_public_commit"],
        "options": OPTIONS,
        "automatic_retry": False,
        "private_train_kit_used": True,
        "protected_response_access": False,
    })

    outer, _ = patient_folds(patients, 5, evaluate.SALT + "|outer")
    names = ("cross_patient_median", "bandwidth07", "additive")
    predictions = {name: np.full((2, *y.shape), np.nan) for name in (*names, "r13")}
    records = []
    final_bandwidths = []

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
        stacked_patients = np.tile(patients[indices], 2)
        owner = np.asarray(plan["coordinate_target_indices"])
        models = {
            "cross_patient_median": CrossPatientMedianBandwidth(
                z, residual, weights, owner, stacked_patients
            ),
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
        oof = {name: np.full((10, 2, len(indices), 24), np.nan) for name in names}
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
        scores = {
            name: [float(patient_target_risk(item, y[indices], patients[indices]).mean()) for item in oof[name]]
            for name in names
        }
        selected = {name: min(range(10), key=lambda i: (scores[name][i], i)) for name in names}
        return selected, scores, oof, inner

    with threadpool_limits(limits=1):
        for fold in range(5):
            train = np.flatnonzero(outer != fold)
            test = np.flatnonzero(outer == fold)
            selected, scores, oof, inner = choose(train, evaluate.SALT + f"|inner|{fold}")
            plan, base, models = build(train)
            folder = output / f"outer_{fold:02}"
            folder.mkdir()
            write_new(folder / "plan.json", plan)
            np.savez_compressed(
                folder / "inner_predictions_private.npz",
                **oof,
                y=y[train],
                patients=patients[train],
                folds=inner,
            )
            candidate_model = models["cross_patient_median"][0]
            final_bandwidths.append(candidate_model.group_bandwidths.copy())
            for name, (model, coefficients) in models.items():
                np.savez_compressed(
                    folder / (name + "_model_private.npz"),
                    **base.arrays(),
                    **model.arrays(coefficients[selected[name]]),
                )
            native = np.asarray(plan["selected_native_indices"])
            for orientation_index, orientation in enumerate(("A", "B")):
                paid = acquire(x[test], plan, orientation)
                z_query = (paid - base.mean_x) / base.scale_x
                base_prediction = base.predict(paid)
                predictions["r13"][orientation_index, test] = base_prediction
                plates = np.asarray(plan[f"orientation_{orientation}_plate_indices"])
                wells = arrays["well_ids"][test][:, native, plates]
                if ((plates == 0).sum() != 32 or (plates == 1).sum() != 32 or
                        not all(len(set(row)) == 64 for row in wells)):
                    raise ValueError("Physical 64-well budget changed")
                masked = np.full_like(x[test], np.nan)
                masked[:, native, plates] = paid
                if not np.array_equal(acquire(masked, plan, orientation), paid):
                    raise ValueError("Unpaid values affected acquired inputs")
                for name, (model, coefficients) in models.items():
                    predictions[name][orientation_index, test] = (
                        base_prediction + model.centered_cross(z_query) @ coefficients[selected[name]]
                    )
            record = {
                "fold": fold,
                "selected": {name: OPTIONS[selected[name]] for name in names},
                "inner_scores": scores,
                "candidate_bandwidth_summary": {
                    "minimum": float(candidate_model.group_bandwidths.min()),
                    "median": float(np.median(candidate_model.group_bandwidths)),
                    "maximum": float(candidate_model.group_bandwidths.max()),
                },
                "wells": 64,
                "per_plate": 32,
                "candidate_and_incumbent_plan_identical": True,
            }
            records.append(record)
            write_new(folder / "selection.json", record)
            print(json.dumps({"fold": fold, "selected": record["selected"]}), flush=True)

        if not all(np.isfinite(value).all() for value in predictions.values()):
            raise ValueError("Incomplete held-patient predictions")
        prediction_path = output / "predictions_private.npz"
        np.savez_compressed(
            prediction_path,
            **predictions,
            y=y,
            patients=patients,
            folds=outer,
            sample_ids=arrays["sample_ids"],
            drug_ids=arrays["drug_ids"],
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
        with np.load(r18_path, allow_pickle=False) as r18_source:
            required = {
                "y", "sample_ids", "patient_ids", "drug_ids", "library_ids", "folds",
                "candidate_A", "candidate_B", "r13_A", "r13_B", "r9",
            }
            if set(r18_source.files) != required:
                raise ValueError("Archived R18 schema changed")
            for key, expected in (
                ("y", y), ("sample_ids", arrays["sample_ids"]),
                ("patient_ids", patients), ("drug_ids", arrays["drug_ids"]),
                ("library_ids", arrays["library_ids"]), ("folds", outer),
            ):
                if not np.array_equal(r18_source[key], expected):
                    raise ValueError("Archived R18 identity mismatch: " + key)
            predictions["r18"] = np.stack((r18_source["candidate_A"], r18_source["candidate_B"]))

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
                predictions["cross_patient_median"], predictions[name],
                metric_values["cross_patient_median"], metric_values[name], y, patients,
            )
            for name in ("bandwidth07", "additive", "r13", "r18")
        }
        bandwidth_control_comparisons = {
            name: compare(
                predictions["bandwidth07"], predictions[name],
                metric_values["bandwidth07"], metric_values[name], y, patients,
            )
            for name in ("additive", "r13", "r18")
        }
        if abs(metric_values["bandwidth07"]["p90_rmse"] - EXPECTED_BANDWIDTH07["p90_rmse"]) > 1e-12:
            raise ValueError("Bandwidth-0.7 p90 control mismatch")
        if not np.allclose(
            metric_values["bandwidth07"]["orientation_mse"],
            EXPECTED_BANDWIDTH07["orientation_mse"], rtol=0.0, atol=1e-12,
        ):
            raise ValueError("Bandwidth-0.7 orientation control mismatch")
        for name, expected in EXPECTED_BANDWIDTH07_COMPARISONS.items():
            actual = bandwidth_control_comparisons[name]
            if any(actual[key] != value for key, value in expected.items()):
                raise ValueError("Bandwidth-0.7 comparison control mismatch: " + name)
        maximum_difference = float(np.max(np.abs(
            predictions["cross_patient_median"] - predictions["bandwidth07"]
        )))
        equivalent = maximum_difference <= 1e-12
        immediate_gate, historical_gate, promoted = gate(comparisons, equivalent)
        candidate_targets = metric_values["cross_patient_median"]["target_mse"]
        incumbent_targets = metric_values["bandwidth07"]["target_mse"]
        regressing_targets = [
            target for target in map(str, arrays["drug_ids"])
            if candidate_targets[target] > incumbent_targets[target]
        ]
        bandwidth_matrix = np.stack(final_bandwidths)
        result = {
            "schema": "dosepilot.cross_patient_bandwidth.result.v1",
            "status": "COMPLETE",
            "decision": "PROMOTE" if promoted else "REJECT_RETAIN_BANDWIDTH07",
            "metrics": metric_values,
            "expected_control_matches": expected_matches,
            "comparisons": comparisons,
            "bandwidth07_control_comparisons": bandwidth_control_comparisons,
            "immediate_gate": immediate_gate,
            "historical_gate": historical_gate,
            "all_gates_passed": promoted,
            "maximum_absolute_prediction_difference_vs_bandwidth07": maximum_difference,
            "prediction_equivalent_to_bandwidth07": equivalent,
            "regressing_targets_vs_bandwidth07": regressing_targets,
            "regressing_target_count_vs_bandwidth07": len(regressing_targets),
            "bootstrap_vs_bandwidth07": bootstrap_delta(
                predictions["cross_patient_median"], predictions["bandwidth07"], y, patients
            ),
            "candidate_outer_bandwidth_summary": {
                "minimum": float(bandwidth_matrix.min()),
                "median": float(np.median(bandwidth_matrix)),
                "maximum": float(bandwidth_matrix.max()),
            },
            "selections": records,
            "prediction_sha256": prediction_sha,
            "cache_sha256": sha(cache_path),
            "r18_sha256": sha(r18_path),
            "source_sha256": {name: sha(HERE / name) for name in source_names},
            "seconds": time.monotonic() - started,
            "same_task_repeated_adaptive_development": True,
            "independent_validation": False,
            "protected_response_access": False,
            "accepted_kaggle_entry_changed": False,
            "official_competition_score": None,
        }
        write_new(output / "RESULT.json", result)
        print(json.dumps({
            "status": result["status"],
            "decision": result["decision"],
            "mse": {name: metric["mse"] for name, metric in metric_values.items()},
            "immediate_gate": immediate_gate,
            "historical_gate": historical_gate,
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
                "error": str(error),
                "traceback": traceback.format_exc(),
                "automatic_retry": False,
                "protected_response_access": False,
            })
        raise


if __name__ == "__main__":
    main()
