#!/usr/bin/env python3
"""Frozen-family, grouped nested development for a TRAIN-only PDO response panel.

No source download or raw-data parsing. A new output directory is required.
Only a root-authorized canonical TRAIN NPZ is accepted for a scientific run.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import time

# Small matrices perform poorly with many BLAS threads; set before NumPy import.
for _name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_name] = "1"

import joblib
import numpy as np
import scipy
import sklearn
from threadpoolctl import threadpool_limits

from methods import (
    METHOD_CONFIGS, PanelPredictor, config_key, context_diagnostics,
    fit_context, panel_rules, patient_folds, per_patient_loss,
)


SALT = "von-organoid-sentinel-v1"
BUDGET = 4


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_train(path, metadata_path):
    metadata = json.loads(metadata_path.read_text())
    with np.load(path, allow_pickle=False) as source:
        required = ("y", "sample_ids", "patient_ids", "drug_ids", "library_ids")
        missing = [k for k in required if k not in source]
        if missing:
            raise ValueError("Missing canonical TRAIN keys: " + ", ".join(missing))
        data = {k: np.array(source[k]) for k in required}
    y = data["y"]
    if y.ndim != 2 or not np.issubdtype(y.dtype, np.floating) or not np.isfinite(y).all():
        raise ValueError("Canonical y must be a finite floating matrix")
    for key in ("sample_ids", "patient_ids", "library_ids"):
        if data[key].shape != (len(y),) or data[key].dtype.kind not in "US":
            raise ValueError("Invalid string identity column: " + key)
    if data["drug_ids"].shape != (y.shape[1],) or data["drug_ids"].dtype.kind not in "US":
        raise ValueError("Invalid drug identities")
    for key in ("sample_ids", "patient_ids", "library_ids", "drug_ids"):
        data[key] = data[key].astype(str)
        if any(not value.strip() for value in data[key]):
            raise ValueError("Blank identifier: " + key)
    if len(set(data["sample_ids"])) != len(y) or len(set(data["drug_ids"])) != y.shape[1]:
        raise ValueError("Duplicate canonical sample/drug identifier")
    if y.shape[1] <= BUDGET or len(set(data["patient_ids"])) < 10:
        raise ValueError("Insufficient patients/drugs for this frozen protocol")
    allowed_libraries = metadata.get("training_library_ids", ["lib1"])
    allowed = set(str(x).lower() for x in allowed_libraries)
    if not set(x.lower() for x in data["library_ids"]).issubset(allowed):
        raise ValueError("Canonical input contains an unauthorized library")
    if metadata.get("split_role", "TRAIN") != "TRAIN":
        raise ValueError("This entrypoint accepts TRAIN data only")
    expected = metadata.get("npz_sha256")
    if expected is not None and expected != sha(path):
        raise ValueError("Canonical input does not match declared NPZ hash")
    row_order = np.argsort(data["sample_ids"], kind="stable")
    col_order = np.argsort(data["drug_ids"], kind="stable")
    data["y"] = y[np.ix_(row_order, col_order)].astype(np.float64)
    data["drug_ids"] = data["drug_ids"][col_order]
    for key in ("sample_ids", "patient_ids", "library_ids"):
        data[key] = data[key][row_order]
    return data, metadata


def options():
    for family, configs in METHOD_CONFIGS.items():
        for index, config in enumerate(configs):
            yield family, index, config


def select_rules(y, patients, drugs, n_splits, salt, directory):
    directory.mkdir()
    folds, assignment = patient_folds(patients, n_splits, salt)
    dump(directory / "patient_folds.json", assignment)
    total = {}
    fold_records = []
    rule_ids = None
    started = time.perf_counter()
    for fold in range(n_splits):
        train, validation = folds != fold, folds == fold
        context = fit_context(y[train], patients[train], drugs)
        rules = panel_rules(context, BUDGET)
        if rule_ids is None:
            rule_ids = sorted(rules)
        elif sorted(rules) != rule_ids:
            raise AssertionError("Rule identities changed across folds")
        literal_to_rules = {}
        for rule in rule_ids:
            literal_to_rules.setdefault(rules[rule], []).append(rule)
        record = {
            "fold": fold,
            "training_patients": len(set(patients[train])),
            "validation_patients": len(set(patients[validation])),
            "rule_panels": {r: [str(drugs[j]) for j in p] for r, p in rules.items()},
            "distinct_panels": len(literal_to_rules),
            "mixture_fit": context_diagnostics(context),
            "scores": [],
        }
        for panel, equivalent_rules in sorted(literal_to_rules.items()):
            observed = y[validation][:, panel]
            for family, index, config in options():
                predictor = PanelPredictor(context, family, config, panel)
                prediction = predictor.predict(observed)
                pids, losses = per_patient_loss(y[validation], prediction, patients[validation])
                risk_sum, count = float(losses.sum()), len(losses)
                for rule in equivalent_rules:
                    key = (family, index, rule)
                    old_sum, old_count = total.get(key, (0.0, 0))
                    total[key] = old_sum + risk_sum, old_count + count
                    record["scores"].append({"family": family, "config_index": index, "rule": rule, "patient_risk_sum": risk_sum, "patient_count": count, "mse": risk_sum / count})
        fold_records.append(record)
        dump(directory / f"inner_{fold:02d}.json", record)
        print(json.dumps({"event": "inner_fold_complete", "location": str(directory), "fold": fold, "distinct_panels": len(literal_to_rules), "seconds": time.perf_counter() - started}), flush=True)
    scores = {key: risk_sum / count for key, (risk_sum, count) in total.items()}
    selected, shared = {}, {}
    for family, configs in METHOD_CONFIGS.items():
        choices = [(scores[(family, i, r)], i, r) for i in range(len(configs)) for r in rule_ids]
        score, index, rule = min(choices)
        selected[family] = {"config_index": index, "config": configs[index], "rule": rule, "inner_mse": score}
        score, index, rule = min((scores[(family, i, "gaussian_empty")], i, "gaussian_empty") for i in range(len(configs)))
        shared[family] = {"config_index": index, "config": configs[index], "rule": rule, "inner_mse": score}
    dump(directory / "selection.json", {"primary": selected, "shared_panel": shared, "inner_patients": len(set(patients)), "seconds": time.perf_counter() - started})
    return selected, shared


def bootstrap_difference(candidate, reference, seed=20260928):
    difference = candidate - reference
    generator = np.random.default_rng(seed)
    indices = generator.integers(0, len(difference), size=(10000, len(difference)))
    means = difference[indices].mean(axis=1)
    return {"mean_mse_difference_candidate_minus_reference": float(difference.mean()), "bootstrap_95_interval": [float(x) for x in np.quantile(means, [0.025, 0.975])], "patients": len(difference), "bootstrap_resamples": 10000, "seed": seed}


def summarize(y, patients, predictions, masks):
    report = {}
    patient_table = []
    patient_losses = {}
    for name, prediction in predictions.items():
        pids, losses = per_patient_loss(y, prediction, patients)
        _, maes = per_patient_loss(y, prediction, patients, absolute=True)
        _, unobserved = per_patient_loss(y, prediction, patients, mask=~masks[name])
        _, unobserved_mae = per_patient_loss(y, prediction, patients, mask=~masks[name], absolute=True)
        report[name] = {"mse": float(losses.mean()), "rmse": float(np.sqrt(losses.mean())), "mae": float(maes.mean()), "unmeasured_rmse": float(np.sqrt(unobserved.mean())), "unmeasured_mae": float(unobserved_mae.mean()), "patient_count": len(pids)}
        patient_losses[name] = losses
        for p, risk, mae in zip(pids, losses, maes):
            patient_table.append({"method": name, "patient_id": str(p), "mse": float(risk), "mae": float(mae)})
    contrasts = {}
    for variant in ("primary", "shared"):
        candidate = f"{variant}__mixture"
        for family in METHOD_CONFIGS:
            reference = f"{variant}__{family}"
            if reference != candidate:
                contrasts[candidate + "__versus__" + reference] = bootstrap_difference(patient_losses[candidate], patient_losses[reference])
    return report, patient_table, contrasts


def code_hashes():
    folder = Path(__file__).resolve().parent
    return {p.name: sha(p) for p in (folder / "methods.py", folder / "evaluate.py")}


def fit_final(data, output):
    y, patients, drugs = data["y"], data["patient_ids"], data["drug_ids"]
    selected, shared = select_rules(y, patients, drugs, 5, SALT + "|final", output / "final_selection")
    context = fit_context(y, patients, drugs)
    rules = panel_rules(context, BUDGET)
    bundle = {"schema": "von-organoid-sentinel-model-v2", "code_hashes": code_hashes(), "drug_ids": drugs, "training_patient_ids": np.asarray(sorted(set(patients))), "models": {"primary": {}, "shared_panel": {}}, "selections": {"primary": {}, "shared_panel": {}}}
    for variant, selections in (("primary", selected), ("shared_panel", shared)):
        for family, selection in selections.items():
            panel = rules[selection["rule"]]
            predictor = PanelPredictor(context, family, selection["config"], panel)
            bundle["models"][variant][family] = predictor
            bundle["selections"][variant][family] = {**selection, "panel_indices": list(panel), "panel_drug_ids": [str(drugs[j]) for j in panel]}
    model_path = output / "frozen_models.joblib"
    joblib.dump(bundle, model_path, compress=3)
    dump(output / "frozen_models.json", {"schema": bundle["schema"], "model_file": model_path.name, "model_sha256": sha(model_path), "code_hashes": bundle["code_hashes"], "drug_ids": list(map(str, drugs)), "training_patient_ids": sorted(set(map(str, patients))), "model_variants": list(bundle["models"]), "selections": bundle["selections"], "warning": "Trusted locally generated model only; joblib deserialization executes Python objects."})


def run(data, output, metadata, input_manifest, finalize=False, outer_splits=5, inner_splits=3):
    output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    dump(output / "STARTED.json", {"unix_time": time.time(), "input": input_manifest, "metadata": metadata, "code_hashes": code_hashes(), "versions": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__, "sklearn": sklearn.__version__}, "budget": BUDGET, "method_configs": METHOD_CONFIGS, "fold_salt": SALT, "outer_splits": outer_splits, "inner_splits": inner_splits, "finalize": finalize})
    y, patients, drugs = data["y"], data["patient_ids"], data["drug_ids"]
    folds, assignment = patient_folds(patients, outer_splits, SALT + "|outer")
    dump(output / "outer_patient_folds.json", assignment)
    predictions = {f"{variant}__{family}": np.full_like(y, np.nan) for variant in ("primary", "shared") for family in METHOD_CONFIGS}
    masks = {key: np.zeros_like(y, dtype=bool) for key in predictions}
    outer_records = []
    for fold in range(outer_splits):
        train, test = folds != fold, folds == fold
        directory = output / f"outer_{fold:02d}"
        directory.mkdir()
        selected, shared = select_rules(y[train], patients[train], drugs, inner_splits, SALT + f"|inner|{fold}", directory / "selection")
        context = fit_context(y[train], patients[train], drugs)
        rules = panel_rules(context, BUDGET)
        record = {"fold": fold, "training_patients": len(set(patients[train])), "validation_patients": len(set(patients[test])), "mixture_fit": context_diagnostics(context), "results": {}}
        cache = {}
        for variant, selections in (("primary", selected), ("shared", shared)):
            for family, selection in selections.items():
                panel = rules[selection["rule"]]
                key = family, selection["config_index"], panel
                if key not in cache:
                    predictor = PanelPredictor(context, family, selection["config"], panel)
                    cache[key] = predictor.predict(y[test][:, panel])
                name = f"{variant}__{family}"
                predictions[name][test] = cache[key]
                masks[name][np.ix_(np.flatnonzero(test), panel)] = True
                record["results"][name] = {**selection, "panel_drug_ids": [str(drugs[j]) for j in panel], "panel_indices": list(panel)}
        outer_records.append(record)
        dump(directory / "outer_result.json", record)
        print(json.dumps({"event": "outer_fold_complete", "fold": fold, "seconds": time.perf_counter() - started}), flush=True)
    if not all(np.isfinite(value).all() for value in predictions.values()):
        raise AssertionError("Incomplete outer predictions")
    for key in masks:
        if not np.all(masks[key].sum(axis=1) == BUDGET):
            raise AssertionError("Wrong observed budget")
    metrics, patient_table, contrasts = summarize(y, patients, predictions, masks)
    np.savez_compressed(output / "oof_predictions.npz", y=y, sample_ids=data["sample_ids"], patient_ids=patients, drug_ids=drugs, library_ids=data["library_ids"], folds=folds, **predictions, **{k + "__observed_mask": v for k, v in masks.items()})
    with (output / "per_patient_losses.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=("method", "patient_id", "mse", "mae"))
        writer.writeheader()
        writer.writerows(patient_table)
    dump(output / "metrics.json", metrics)
    dump(output / "paired_patient_contrasts.json", {"interpretation": "Exploratory nested-CV comparisons; descriptive patient bootstrap because training folds overlap. Negative differences favor the mixture. These intervals do not correct selection of a family from outer results.", "contrasts": contrasts})
    if finalize:
        fit_final(data, output)
    summary = {"completed": True, "n_pdo": len(y), "n_patients": len(set(patients)), "n_drugs": y.shape[1], "budget_curves": BUDGET, "all_libraries": sorted(set(map(str, data["library_ids"]))), "heldout_library_used": False, "scientific_role": "TRAIN-only exploratory grouped development", "metrics": metrics, "seconds": time.perf_counter() - started, "code_hashes": code_hashes(), "input": input_manifest, "final_models_frozen": finalize}
    dump(output / "SUMMARY.json", summary)
    files = {str(p.relative_to(output)): sha(p) for p in sorted(output.rglob("*")) if p.is_file()}
    dump(output / "MANIFEST.json", {"committed": True, "files": files})
    print(json.dumps({"event": "complete", "output": str(output), "seconds": summary["seconds"], "metrics": metrics}), flush=True)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--finalize", action="store_true", help="Also select final models/panels on all TRAIN and save trusted model objects")
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Output already exists; preserve the first attempt")
    data, metadata = load_train(args.train, args.metadata)
    input_manifest = {"npz_path": str(args.train.resolve()), "npz_sha256": sha(args.train), "metadata_path": str(args.metadata.resolve()), "metadata_sha256": sha(args.metadata)}
    with threadpool_limits(limits=1):
        run(data, args.output, metadata, input_manifest, finalize=args.finalize)


if __name__ == "__main__":
    main()
