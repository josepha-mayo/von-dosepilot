#!/usr/bin/env python3
"""Execute the single frozen co-optimized calibrated-interpolation control."""
from __future__ import annotations

import argparse, datetime, hashlib, json, os, platform, sys, time, traceback
from pathlib import Path
for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[name] = "1"
import numpy as np

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
sys.path[:0] = [str(HERE), str(STUDY), str(STUDY / "engine"),
                str(STUDY / "audits"), str(STUDY / "calibrated_control")]

from calibrated_control import OPTIONS, fit, weights
from cooptimized_control import fit_plan, predict_plan, raw_from_plan, select_joint
from interpolation_policy import plan_panel
from methods import patient_folds
import evaluate

CACHE_SHA256 = "2ccd4995699417db72316c8f403095b8ef560f94913b0c8a80fe7429a2d0cbef"
REFERENCE_SHA256 = "0d007814fa04d02ec2f0233880c7790ffbaa45b5c3be176edee7567c8a68e150"
R18_SHA256 = "253998d20b9425c4ceade4269b94f4ed97cb7039ac5ec60838bb15794d47a6e2"
EXPECTED = {"bandwidth07": 0.0010582750420801538, "r13": 0.001144858681382854,
            "r18": 0.0011414048112341991}
BOOTSTRAP_SEED = 20261004


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_new(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def load_cache(path):
    from compact_train import catalog_layout, read_catalog
    if sha(path) != CACHE_SHA256:
        raise ValueError("Authenticated Lib1 TRAIN cache changed")
    required = {"y", "sample_ids", "patient_ids", "drug_ids", "library_ids", "x",
                "well_ids", "native_ids", "native_target_indices", "concentrations"}
    with np.load(path, allow_pickle=False) as source:
        if set(source.files) != required:
            raise ValueError("Lib1 TRAIN cache schema changed")
        arrays = {name: source[name].copy() for name in required}
    spec = read_catalog(STUDY / "TRAIN_CATALOG.json")
    _, catalog = catalog_layout(spec)
    bounds = np.asarray([spec["target_bounds_nM"][str(d)] for d in arrays["drug_ids"]], float)
    if arrays["x"].shape != (119, 164, 2) or arrays["y"].shape != (119, 24):
        raise ValueError("Fixed TRAIN dimensions changed")
    if len(set(arrays["patient_ids"].astype(str))) != 59 or set(arrays["library_ids"].astype(str)) != {"lib1"}:
        raise ValueError("Patient or library denominator changed")
    if not np.isfinite(arrays["x"]).all() or not np.isfinite(arrays["y"]).all():
        raise ValueError("Nonfinite TRAIN input")
    return arrays, catalog, bounds


def patient_target_risk(prediction, y, patients):
    error = ((prediction[0] - y) ** 2 + (prediction[1] - y) ** 2) / 2
    return np.stack([error[patients == p].mean(0) for p in np.unique(patients)])


def metrics(prediction, y, patients, folds, targets):
    risk = patient_target_risk(prediction, y, patients)
    patient = risk.mean(1)
    patient_folds = np.asarray([folds[np.flatnonzero(patients == p)[0]] for p in np.unique(patients)])
    return {"mse": float(patient.mean()), "p90_rmse": float(np.quantile(np.sqrt(patient), .9)),
            "fold_mse": [float(patient[patient_folds == f].mean()) for f in range(5)],
            "target_mse": dict(zip(map(str, targets), map(float, risk.mean(0)))),
            "orientation_mse": [float(np.mean([((prediction[o, patients == p] - y[patients == p]) ** 2).mean()
                                                  for p in np.unique(patients)])) for o in (0, 1)]}


def compare(candidate_prediction, reference_prediction, candidate, reference, y, patients):
    a = patient_target_risk(candidate_prediction, y, patients).mean(1)
    b = patient_target_risk(reference_prediction, y, patients).mean(1)
    return {"relative_gain": float(1 - candidate["mse"] / reference["mse"]),
            "patient_wins": int((a < b).sum()), "patient_losses": int((a > b).sum()),
            "patient_ties": int((a == b).sum()),
            "fold_wins": int(sum(x < z for x, z in zip(candidate["fold_mse"], reference["fold_mse"]))),
            "p90_nonworse": bool(candidate["p90_rmse"] <= reference["p90_rmse"]),
            "orientation_below_reference_expected_mse": [bool(x < reference["mse"]) for x in candidate["orientation_mse"]]}


def choose_calibrated_original(x, y, patients, catalog, bounds, inner):
    oof = np.full((len(OPTIONS), 2, len(y), 24), np.nan)
    for fold in range(3):
        tr, va = inner != fold, inner == fold
        plan = plan_panel(x[tr], y[tr], patients[tr], catalog, bounds)
        raw_tr, raw_va = raw_from_plan(x[tr], plan), raw_from_plan(x[va], plan)
        for oi, option in enumerate(OPTIONS):
            model = fit(raw_tr.reshape(-1, 24), np.tile(y[tr], (2, 1)), np.tile(patients[tr], 2), option)
            for orientation in (0, 1):
                oof[oi, orientation, va] = model.predict(raw_va[orientation])
    scores = [float(patient_target_risk(pred, y, patients).mean()) for pred in oof]
    selected = min(range(len(OPTIONS)), key=lambda i: (scores[i], i))
    return OPTIONS[selected], scores


def check_physical(arrays, rows, plan):
    native = np.asarray(plan["selected_native_indices"], int)
    for orientation in ("A", "B"):
        plates = np.asarray(plan[f"orientation_{orientation}_plate_indices"], int)
        wells = arrays["well_ids"][rows][:, native, plates]
        if (plates == 0).sum() != 32 or (plates == 1).sum() != 32 or not all(len(set(row)) == 64 for row in wells):
            raise ValueError("Physical 64-well budget changed")


def gate(comparisons):
    immediate = comparisons["bandwidth07"]
    parts = {"strictly_lower_mse": immediate["relative_gain"] > 0,
             "patient_wins_at_least_30": immediate["patient_wins"] >= 30,
             "all_five_folds_favorable": immediate["fold_wins"] == 5,
             "p90_nonworse": immediate["p90_nonworse"]}
    history = {}
    for name in ("r13", "r18"):
        c = comparisons[name]
        history[name] = {"mse_reduction_at_least_5pct": c["relative_gain"] >= .05,
                         "patient_wins_at_least_40": c["patient_wins"] >= 40,
                         "fold_wins_at_least_4": c["fold_wins"] >= 4,
                         "p90_nonworse": c["p90_nonworse"],
                         "both_orientation_mse_below_reference_expected_mse": all(c["orientation_below_reference_expected_mse"])}
    return parts, history, all(parts.values()) and all(all(v.values()) for v in history.values())


def execute(cache, reference, r18, output):
    freeze = json.loads((HERE / "FREEZE.json").read_text())
    if freeze["state"] != "FROZEN_BEFORE_FIRST_LIB1_FIT":
        raise ValueError("Study is not frozen")
    for relative, expected in freeze["source_sha256"].items():
        if sha(STUDY.parent / relative) != expected:
            raise ValueError("Frozen source changed: " + relative)
    if sha(cache) != CACHE_SHA256 or sha(reference) != REFERENCE_SHA256 or sha(r18) != R18_SHA256:
        raise ValueError("Frozen input identity changed")
    arrays, catalog, bounds = load_cache(cache)
    x, y, patients = arrays["x"], arrays["y"], arrays["patient_ids"].astype(str)
    output.mkdir(parents=True, exist_ok=False)
    t0 = time.monotonic()
    write_new(output / "STARTED.json", {"schema": "dosepilot.cooptimized_control.started.v1",
              "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "protocol_sha256": sha(HERE / "PROTOCOL.json"), "freeze_sha256": sha(HERE / "FREEZE.json"),
              "cache_sha256": sha(cache), "reference_sha256": sha(reference), "automatic_retry": False,
              "protected_response_access": False, "python": platform.python_version()})
    outer, _ = patient_folds(patients, 5, evaluate.SALT + "|outer")
    names = ("cooptimized", "raw_optimized", "calibrated_original")
    predictions = {name: np.full((2, *y.shape), np.nan) for name in names}
    records = []
    for fold in range(5):
        train, test = np.flatnonzero(outer != fold), np.flatnonzero(outer == fold)
        inner, _ = patient_folds(patients[train], 3, evaluate.SALT + f"|inner|{fold}")
        candidate_plan, candidate_scores = select_joint(x[train], y[train], patients[train], catalog, bounds, inner)
        candidate_model = fit_plan(x[train], y[train], patients[train], candidate_plan)
        predictions["cooptimized"][:, test] = predict_plan(x[test], candidate_plan, candidate_model)
        raw_plan = plan_panel(x[train], y[train], patients[train], catalog, bounds)
        predictions["raw_optimized"][:, test] = raw_from_plan(x[test], raw_plan)
        option, calibration_scores = choose_calibrated_original(x[train], y[train], patients[train], catalog, bounds, inner)
        raw_train = raw_from_plan(x[train], raw_plan)
        calibration = fit(raw_train.reshape(-1, 24), np.tile(y[train], (2, 1)), np.tile(patients[train], 2), option)
        raw_test = raw_from_plan(x[test], raw_plan)
        predictions["calibrated_original"][:, test] = np.stack([calibration.predict(raw_test[o]) for o in (0, 1)])
        check_physical(arrays, test, candidate_plan); check_physical(arrays, test, raw_plan)
        record = {"fold": fold, "candidate_calibration_option": candidate_plan["calibration_option"],
                  "candidate_inner_scores": candidate_scores, "original_calibration_option": option,
                  "original_calibration_scores": calibration_scores,
                  "candidate_upgraded_target_ids": candidate_plan["upgraded_target_ids"], "wells": 64, "per_plate": 32}
        records.append(record)
        folder = output / f"outer_{fold:02d}"; folder.mkdir()
        write_new(folder / "selection.json", record)
        write_new(folder / "candidate_plan.json", candidate_plan)
        print(json.dumps({"fold": fold, "candidate_option": candidate_plan["calibration_option"], "control_option": option}), flush=True)
    if not all(np.isfinite(p).all() for p in predictions.values()):
        raise ValueError("Incomplete predictions")
    private = output / "predictions_private.npz"
    np.savez_compressed(private, **predictions, y=y, patients=patients, folds=outer,
                        sample_ids=arrays["sample_ids"], drug_ids=arrays["drug_ids"], library_ids=arrays["library_ids"])
    write_new(output / "PREDICTIONS_COMMITTED.json", {"prediction_sha256": sha(private),
              "created_before_reference_access": True, "protected_response_access": False})
    with np.load(reference, allow_pickle=False) as source:
        for key, expected in (("y", y), ("patients", patients), ("folds", outer),
                              ("sample_ids", arrays["sample_ids"]), ("drug_ids", arrays["drug_ids"]),
                              ("library_ids", arrays["library_ids"])):
            if not np.array_equal(source[key], expected): raise ValueError("Incumbent identity mismatch: " + key)
        predictions["bandwidth07"] = source["bandwidth07"].copy()
        predictions["r13"] = source["r13"].copy()
    with np.load(r18, allow_pickle=False) as source:
        for key, expected in (("y", y), ("patient_ids", patients), ("folds", outer)):
            if not np.array_equal(source[key], expected): raise ValueError("R18 identity mismatch: " + key)
        predictions["r18"] = np.stack((source["candidate_A"], source["candidate_B"]))
    values = {name: metrics(p, y, patients, outer, arrays["drug_ids"]) for name, p in predictions.items()}
    matches = {name: abs(values[name]["mse"] - expected) <= 1e-12 for name, expected in EXPECTED.items()}
    if not all(matches.values()): raise ValueError("Historical reference mismatch")
    comparisons = {name: compare(predictions["cooptimized"], predictions[name], values["cooptimized"], values[name], y, patients)
                   for name in ("bandwidth07", "r13", "r18", "raw_optimized", "calibrated_original")}
    immediate, historical, promoted = gate(comparisons)
    candidate_patient = patient_target_risk(predictions["cooptimized"], y, patients).mean(1)
    incumbent_patient = patient_target_risk(predictions["bandwidth07"], y, patients).mean(1)
    delta = candidate_patient - incumbent_patient
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    boot = delta[rng.integers(0, 59, (10000, 59))].mean(1)
    regressing = [d for d in map(str, arrays["drug_ids"]) if values["cooptimized"]["target_mse"][d] > values["bandwidth07"]["target_mse"][d]]
    result = {"schema": "dosepilot.cooptimized_control.result.v1", "status": "COMPLETE",
              "decision": "REQUIRES_INDEPENDENT_REPRODUCTION" if promoted else "REJECT_RETAIN_BANDWIDTH07",
              "metrics": values, "expected_control_matches": matches, "comparisons": comparisons,
              "immediate_gate": immediate, "historical_gate": historical, "all_gates_passed": promoted,
              "regressing_targets_vs_bandwidth07": regressing, "regressing_target_count_vs_bandwidth07": len(regressing),
              "bootstrap_vs_bandwidth07": {"definition": "candidate minus incumbent patient-balanced MSE",
                 "point": float(delta.mean()), "lower_2_5pct": float(np.quantile(boot, .025)),
                 "upper_97_5pct": float(np.quantile(boot, .975)), "replicates": 10000, "seed": BOOTSTRAP_SEED,
                 "selection_corrected": False},
              "selections": records, "prediction_sha256": sha(private), "seconds": time.monotonic() - t0,
              "same_task_repeated_adaptive_development": True, "independent_validation": False,
              "protected_response_access": False, "accepted_kaggle_entry_changed": False,
              "official_competition_score": None}
    write_new(output / "RESULT.json", result)
    print(json.dumps({"status": result["status"], "decision": result["decision"],
                      "mse": {k: v["mse"] for k, v in values.items()}, "gate": promoted}, indent=2))
    return result


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True); parser.add_argument("--r18", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True); args = parser.parse_args()
    try: execute(args.cache, args.reference, args.r18, args.output)
    except BaseException as error:
        if args.output.exists():
            write_new(args.output / "FAILURE.json", {"error": str(error), "traceback": traceback.format_exc(),
                      "automatic_retry": False, "protected_response_access": False})
        raise


if __name__ == "__main__": main()
