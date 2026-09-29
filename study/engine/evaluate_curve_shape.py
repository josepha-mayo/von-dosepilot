#!/usr/bin/env python3
"""Sealed second TRAIN experiment; first-protocol files and results stay immutable."""
from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
import platform
import time

for _name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_name] = "1"

import numpy as np
import scipy
import sklearn
from threadpoolctl import threadpool_limits

import evaluate as first
from curve_shape_methods import CURVE_CONFIGS, KNOT_FRACTIONS, CurvePanelPredictor, interpolate_curve
from methods import METHOD_CONFIGS, fit_context, panel_rules, patient_folds, per_patient_loss


MEMO_SHA256 = "2bf519a837b54dc48a7fddeedc797ddc873d479a08d48bf480baf11a51f250b3"
FIRST_CODE_HASHES = {
    "methods.py": "6fc6909ab92057aa8715383f0001f4bcaa14df85d0e897ed8900f88efb1aaf5f",
    "evaluate.py": "24593a7d8608fd3ce98c367e1760af596b3b33554c1ef7a3f8ac645b046b700b",
}


def code_hashes():
    folder = Path(__file__).resolve().parent
    return {name: first.sha(folder / name) for name in (*FIRST_CODE_HASHES, "curve_shape_methods.py", "evaluate_curve_shape.py")}


def assert_frozen_sources():
    folder = Path(__file__).resolve().parent
    for name, expected in FIRST_CODE_HASHES.items():
        if first.sha(folder / name) != expected:
            raise ValueError("Frozen first-protocol code has changed: " + name)
    memo = folder.parents[1] / "research" / "round7_curve_shape_followup.md"
    if first.sha(memo) != MEMO_SHA256:
        raise ValueError("Sealed curve-shape protocol has changed")


def load_curve_features(data, metadata, train_path, curves_path, audit_path):
    """Join released TRAIN curves by identities; never read raw or Lib2 tables."""
    train_path, curves_path, audit_path = map(Path, (train_path, curves_path, audit_path))
    if metadata.get("split_role") != "TRAIN" or metadata.get("lib2_response_values_converted", 0) != 0:
        raise ValueError("Only the explicit TRAIN curve release is permitted")
    if first.sha(train_path) != metadata.get("npz_sha256") or first.sha(audit_path) != metadata.get("preparation_audit_sha256"):
        raise ValueError("TRAIN artifact or preparation audit hash mismatch")
    preparation = json.loads(audit_path.read_text())
    if preparation.get("status") != "complete" or preparation.get("authorized_partition") != "train" or preparation.get("lib2_response_values_converted", 0) != 0:
        raise ValueError("Curve release is not a completed TRAIN-only preparation")
    for path in (train_path, curves_path):
        if preparation.get("files", {}).get(path.name) != first.sha(path):
            raise ValueError("Curve release file differs from its preparation audit: " + path.name)
    with np.load(train_path, allow_pickle=False) as source:
        sample_ids = np.asarray(source["sample_ids"], dtype=str)
        drug_ids = np.asarray(source["drug_ids"], dtype=str)
        sample_order = {value: index for index, value in enumerate(sample_ids)}
        drug_order = {value: index for index, value in enumerate(drug_ids)}
        rows = np.asarray([sample_order[value] for value in data["sample_ids"]])
        columns = np.asarray([drug_order[value] for value in data["drug_ids"]])
        runs = np.asarray(source["run_ids"], dtype=str)[rows]
        intervals = np.asarray(source["common_intervals_nM"], dtype=float)[columns]
        old_replicates = np.asarray(source["y_replicates"], dtype=float)[np.ix_(rows, columns)]
        well_counts = np.asarray(source["well_counts"])[np.ix_(rows, columns)]
    n, d = data["y"].shape
    if intervals.shape != (d, 2) or old_replicates.shape != (n, d, 2) or well_counts.shape != (n, d) or runs.shape != (n,):
        raise ValueError("Canonical TRAIN replicate, interval or run dimensions disagree")
    declared_intervals = np.asarray([metadata["common_intervals_nM"][drug] for drug in data["drug_ids"]], dtype=float)
    if not np.array_equal(intervals, declared_intervals) or not np.array_equal(old_replicates.mean(axis=2), data["y"]):
        raise ValueError("Original endpoint or declared concentration intervals disagree")
    sample_index = {str(sample): index for index, sample in enumerate(data["sample_ids"])}
    drug_index = {str(drug): index for index, drug in enumerate(data["drug_ids"])}
    curves = {}
    wells = set()
    required = {"sample_id", "patient_id", "library_id", "run_id", "drug_id", "plate", "dose_nM", "viability", "drow", "dcol", "assay_no"}
    with curves_path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        if not required.issubset(reader.fieldnames or []):
            raise ValueError("Released TRAIN curve CSV has missing fields")
        for row in reader:
            if row["sample_id"] not in sample_index or row["drug_id"] not in drug_index or row["plate"] not in ("p1", "p2"):
                raise ValueError("Curve CSV contains an unknown sample/item/technical plate")
            i, j = sample_index[row["sample_id"]], drug_index[row["drug_id"]]
            if (row["patient_id"], row["library_id"], row["run_id"]) != (data["patient_ids"][i], data["library_ids"][i], runs[i]):
                raise ValueError("Curve CSV patient/library/run identity mismatch")
            physical_well = (row["run_id"], row["plate"], row["drow"], row["dcol"])
            if physical_well in wells:
                raise ValueError("Duplicate physical well in the standalone TRAIN release")
            wells.add(physical_well)
            key = i, j, int(row["plate"][-1]) - 1
            curves.setdefault(key, []).append((float(row["dose_nM"]), float(row["viability"])))
    if len(curves) != n * d * 2:
        raise ValueError("At least one required technical curve is absent")
    knots = np.empty((n, d, 2, 5), dtype=np.float64)
    recovered_auc = np.empty((n, d, 2), dtype=np.float64)
    recovered_counts = np.zeros((n, d), dtype=np.int64)
    for (i, j, replicate), points in curves.items():
        dose, viability = np.asarray(points, dtype=np.float64).T
        knots[i, j, replicate], recovered_auc[i, j, replicate] = interpolate_curve(dose, viability, intervals[j])
        recovered_counts[i, j] += len(points)
    if not np.array_equal(recovered_counts, well_counts):
        raise ValueError("Curve row counts disagree with the frozen treatment-well budget")
    if not np.allclose(recovered_auc, old_replicates, rtol=0, atol=1e-12):
        raise ValueError("Released curves do not reproduce the original per-replicate AUC")
    locations = np.exp(np.log(intervals[:, :1]) + KNOT_FRACTIONS[None, :] * np.log(intervals[:, 1:2] / intervals[:, :1]))
    audit = {
        "source": "authorized TRAIN-only full-curve CSV", "csv_sha256": first.sha(curves_path),
        "train_npz_sha256": first.sha(train_path), "preparation_audit_sha256": first.sha(audit_path),
        "pdo_count": n, "drug_count": d, "technical_curve_count": len(curves), "treatment_well_count": len(wells),
        "maximum_auc_reconstruction_difference": float(np.max(np.abs(recovered_auc - old_replicates))),
        "original_y_preserved": True, "heldout_library_used": False,
        "knot_fractions": KNOT_FRACTIONS.tolist(), "feature_encoding": "per item: exact old AUC followed by five knot-minus-AUC values",
    }
    return {"curve_knots": knots.mean(axis=2), "curve_knots_replicates": knots, "knot_concentrations_nM": locations, "common_intervals_nM": intervals, "well_counts": well_counts, "audit": audit}


def load_controls(data, directory, input_manifest, expected_manifest_sha256, outer_splits=5, inner_splits=3):
    """Strict immutable reuse of a completed first-protocol OOF evaluation."""
    directory = Path(directory)
    manifest_path = directory / "MANIFEST.json"
    if first.sha(manifest_path) != expected_manifest_sha256:
        raise ValueError("First control manifest hash does not match its frozen value")
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("committed") is not True:
        raise ValueError("First controls are not a committed attempt")
    listed = manifest.get("files", {})
    required_files = {"STARTED.json", "SUMMARY.json", "oof_predictions.npz", "outer_patient_folds.json"}
    required_files.update(f"outer_{fold:02d}/selection/inner_{inner:02d}.json" for fold in range(outer_splits) for inner in range(inner_splits))
    required_files.update(f"outer_{fold:02d}/selection/patient_folds.json" for fold in range(outer_splits))
    if not required_files.issubset(listed):
        raise ValueError("First control manifest lacks required immutable evidence")
    root = directory.resolve()
    for relative, expected in listed.items():
        path = directory / relative
        if not path.resolve().is_relative_to(root) or first.sha(path) != expected:
            raise ValueError("First control artifact changed: " + relative)
    started = json.loads((directory / "STARTED.json").read_text())
    summary = json.loads((directory / "SUMMARY.json").read_text())
    if not summary.get("completed") or summary.get("heldout_library_used") is not False:
        raise ValueError("First attempt is incomplete or used held-out data")
    if started.get("code_hashes") != FIRST_CODE_HASHES or summary.get("code_hashes") != FIRST_CODE_HASHES:
        raise ValueError("First control implementation does not match frozen hashes")
    if started.get("method_configs") != METHOD_CONFIGS or started.get("budget") != 4 or started.get("fold_salt") != first.SALT:
        raise ValueError("First controls have a different model/measurement/fold contract")
    if started.get("outer_splits") != outer_splits or started.get("inner_splits") != inner_splits:
        raise ValueError("First controls have different fold counts")
    for key in ("npz_sha256", "metadata_sha256"):
        if not input_manifest.get(key) or started.get("input", {}).get(key) != input_manifest[key]:
            raise ValueError("First controls refer to different TRAIN input: " + key)
    folds, assignment = patient_folds(data["patient_ids"], outer_splits, first.SALT + "|outer")
    if json.loads((directory / "outer_patient_folds.json").read_text()) != assignment:
        raise ValueError("First outer patient assignments disagree")
    predictions, masks = {}, {}
    with np.load(directory / "oof_predictions.npz", allow_pickle=False) as saved:
        for key in ("y", "sample_ids", "patient_ids", "drug_ids", "library_ids"):
            if not np.array_equal(saved[key], data[key]):
                raise ValueError("First OOF data are not exactly aligned: " + key)
        if not np.array_equal(saved["folds"], folds):
            raise ValueError("First OOF row folds disagree")
        for variant in ("primary", "shared"):
            for family in METHOD_CONFIGS:
                name = variant + "__" + family
                prediction, mask = np.array(saved[name]), np.array(saved[name + "__observed_mask"])
                if prediction.shape != data["y"].shape or not np.isfinite(prediction).all() or mask.shape != prediction.shape or mask.dtype != bool:
                    raise ValueError("Malformed first control predictions/mask: " + name)
                if not np.all(mask.sum(axis=1) == 4) or not np.array_equal(prediction[mask], data["y"][mask]):
                    raise ValueError("First controls violate the exact four-curve measurement contract")
                predictions[name], masks[name] = prediction, mask
    if any(not np.array_equal(masks["shared__" + family], masks["shared__ridge"]) for family in METHOD_CONFIGS):
        raise ValueError("Original shared-panel controls do not use the same measured items")
    for fold in range(outer_splits):
        train = folds != fold
        _, inner_assignment = patient_folds(data["patient_ids"][train], inner_splits, first.SALT + f"|inner|{fold}")
        path = directory / f"outer_{fold:02d}/selection/patient_folds.json"
        if json.loads(path.read_text()) != inner_assignment:
            raise ValueError("First inner patient assignments disagree")
    return {"predictions": predictions, "masks": masks, "directory": str(directory.resolve()), "provenance": {"first_manifest_sha256": expected_manifest_sha256, "first_oof_sha256": listed["oof_predictions.npz"], "first_code_hashes": FIRST_CODE_HASHES, "exact_identity_target_and_fold_alignment": True}}


def select_rules(y, knots, patients, drugs, n_splits, salt, directory, first_selection_directory):
    directory.mkdir()
    folds, assignment = patient_folds(patients, n_splits, salt)
    first.dump(directory / "patient_folds.json", assignment)
    total, rule_ids = {}, None
    started = time.perf_counter()
    for fold in range(n_splits):
        train, validation = folds != fold, folds == fold
        context = fit_context(y[train], patients[train], drugs, fit_mixtures=False)
        rules = panel_rules(context, 4)
        if rule_ids is None:
            rule_ids = sorted(rules)
        elif sorted(rules) != rule_ids:
            raise AssertionError("Rule identities changed across folds")
        named_panels = {rule: [str(drugs[j]) for j in panel] for rule, panel in rules.items()}
        previous = json.loads((Path(first_selection_directory) / f"inner_{fold:02d}.json").read_text())
        if previous["rule_panels"] != named_panels:
            raise ValueError("Regenerated curve-experiment panel rules differ from first controls")
        literals = {}
        for rule in rule_ids:
            literals.setdefault(rules[rule], []).append(rule)
        record = {"fold": fold, "training_patients": len(set(patients[train])), "validation_patients": len(set(patients[validation])), "rule_panels": named_panels, "distinct_panels": len(literals), "first_rule_panels_exact_match": True, "scores": []}
        for panel, equivalent_rules in sorted(literals.items()):
            auc_query, knot_query = y[validation][:, panel], knots[validation][:, panel, :]
            for family, configs in CURVE_CONFIGS.items():
                for index, config in enumerate(configs):
                    model = CurvePanelPredictor(context, y[train], knots[train], family, config, panel)
                    prediction = model.predict(auc_query, knot_query)
                    _, losses = per_patient_loss(y[validation], prediction, patients[validation])
                    risk_sum, count = float(losses.sum()), len(losses)
                    for rule in equivalent_rules:
                        key = family, index, rule
                        old_sum, old_count = total.get(key, (0.0, 0))
                        total[key] = old_sum + risk_sum, old_count + count
                        record["scores"].append({"family": family, "config_index": index, "rule": rule, "patient_risk_sum": risk_sum, "patient_count": count, "mse": risk_sum / count})
        first.dump(directory / f"inner_{fold:02d}.json", record)
        print(json.dumps({"event": "curve_inner_fold_complete", "location": str(directory), "fold": fold, "distinct_panels": len(literals), "seconds": time.perf_counter() - started}), flush=True)
    scores = {key: total_loss / count for key, (total_loss, count) in total.items()}
    selected, shared = {}, {}
    for family, configs in CURVE_CONFIGS.items():
        score, index, rule = min((scores[(family, i, r)], i, r) for i in range(len(configs)) for r in rule_ids)
        selected[family] = {"config_index": index, "config": configs[index], "rule": rule, "inner_mse": score}
        score, index, rule = min((scores[(family, i, "gaussian_empty")], i, "gaussian_empty") for i in range(len(configs)))
        shared[family] = {"config_index": index, "config": configs[index], "rule": rule, "inner_mse": score}
    first.dump(directory / "selection.json", {"primary": selected, "shared_panel": shared, "inner_patients": len(set(patients)), "seconds": time.perf_counter() - started})
    return selected, shared


def summarize(y, patients, predictions, masks):
    metrics, patient_table, risks = {}, [], {}
    for name, prediction in predictions.items():
        ids, losses = per_patient_loss(y, prediction, patients)
        _, maes = per_patient_loss(y, prediction, patients, absolute=True)
        _, unmeasured = per_patient_loss(y, prediction, patients, mask=~masks[name])
        _, unmeasured_maes = per_patient_loss(y, prediction, patients, mask=~masks[name], absolute=True)
        metrics[name] = {"mse": float(losses.mean()), "rmse": float(np.sqrt(losses.mean())), "mae": float(maes.mean()), "unmeasured_rmse": float(np.sqrt(unmeasured.mean())), "unmeasured_mae": float(unmeasured_maes.mean()), "patient_count": len(ids)}
        risks[name] = losses
        patient_table.extend({"method": name, "patient_id": str(pid), "mse": float(loss), "mae": float(mae)} for pid, loss, mae in zip(ids, losses, maes))
    contrasts = {}
    for variant in ("primary", "shared"):
        for family in CURVE_CONFIGS:
            candidate = variant + "__" + family
            for reference_family in METHOD_CONFIGS:
                reference = variant + "__" + reference_family
                contrasts[candidate + "__versus__" + reference] = first.bootstrap_difference(risks[candidate], risks[reference])
    return metrics, patient_table, contrasts


def run(data, features, controls, output, metadata, input_manifest, outer_splits=5, inner_splits=3):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    first.dump(output / "STARTED.json", {"unix_time": time.time(), "input": input_manifest, "metadata": metadata, "code_hashes": code_hashes(), "protocol_memo_sha256": MEMO_SHA256, "controls": controls["provenance"], "feature_audit": features["audit"], "versions": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__, "sklearn": sklearn.__version__}, "budget": 4, "curve_configs": CURVE_CONFIGS, "fold_salt": first.SALT, "outer_splits": outer_splits, "inner_splits": inner_splits})
    y, patients, drugs, knots = data["y"], data["patient_ids"], data["drug_ids"], features["curve_knots"]
    if knots.shape != (*y.shape, 5) or not np.isfinite(knots).all():
        raise ValueError("Fixed curve features are not aligned with TRAIN AUCs")
    folds, assignment = patient_folds(patients, outer_splits, first.SALT + "|outer")
    first.dump(output / "outer_patient_folds.json", assignment)
    predictions = {name: values.copy() for name, values in controls["predictions"].items()}
    masks = {name: values.copy() for name, values in controls["masks"].items()}
    for variant in ("primary", "shared"):
        for family in CURVE_CONFIGS:
            name = variant + "__" + family
            predictions[name], masks[name] = np.full_like(y, np.nan), np.zeros_like(y, dtype=bool)
    for fold in range(outer_splits):
        train, test = folds != fold, folds == fold
        directory = output / f"outer_{fold:02d}"
        directory.mkdir()
        selected, shared = select_rules(y[train], knots[train], patients[train], drugs, inner_splits, first.SALT + f"|inner|{fold}", directory / "selection", Path(controls["directory"]) / f"outer_{fold:02d}/selection")
        context = fit_context(y[train], patients[train], drugs, fit_mixtures=False)
        rules, cache = panel_rules(context, 4), {}
        record = {"fold": fold, "training_patients": len(set(patients[train])), "validation_patients": len(set(patients[test])), "results": {}}
        for variant, selections in (("primary", selected), ("shared", shared)):
            for family, selection in selections.items():
                panel = rules[selection["rule"]]
                key = family, selection["config_index"], panel
                if key not in cache:
                    model = CurvePanelPredictor(context, y[train], knots[train], family, selection["config"], panel)
                    cache[key] = model.predict(y[test][:, panel], knots[test][:, panel, :])
                name = variant + "__" + family
                predictions[name][test] = cache[key]
                masks[name][np.ix_(np.flatnonzero(test), panel)] = True
                if variant == "shared" and not np.array_equal(masks[name][test], masks["shared__ridge"][test]):
                    raise ValueError("Curve and original shared panels do not match")
                counts = features["well_counts"][test][:, panel].sum(axis=1)
                record["results"][name] = {**selection, "panel_indices": list(panel), "panel_drug_ids": [str(drugs[j]) for j in panel], "test_panel_treatment_wells": sorted(set(map(int, counts)))}
        first.dump(directory / "outer_result.json", record)
        print(json.dumps({"event": "curve_outer_fold_complete", "fold": fold, "seconds": time.perf_counter() - started}), flush=True)
    for name, prediction in predictions.items():
        if not np.isfinite(prediction).all() or not np.all(masks[name].sum(axis=1) == 4) or not np.array_equal(prediction[masks[name]], y[masks[name]]):
            raise AssertionError("Incomplete predictions or observed-budget violation: " + name)
    metrics, patient_table, contrasts = summarize(y, patients, predictions, masks)
    np.savez_compressed(output / "curve_features.npz", sample_ids=data["sample_ids"], patient_ids=patients, drug_ids=drugs, library_ids=data["library_ids"], y=y, knot_fractions=KNOT_FRACTIONS, **{key: value for key, value in features.items() if key != "audit"})
    first.dump(output / "feature_audit.json", features["audit"])
    np.savez_compressed(output / "oof_predictions.npz", y=y, sample_ids=data["sample_ids"], patient_ids=patients, drug_ids=drugs, library_ids=data["library_ids"], folds=folds, **predictions, **{name + "__observed_mask": value for name, value in masks.items()})
    with (output / "per_patient_losses.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=("method", "patient_id", "mse", "mae"))
        writer.writeheader()
        writer.writerows(patient_table)
    first.dump(output / "metrics.json", metrics)
    first.dump(output / "paired_patient_contrasts.json", {"principal_contrast": "shared__curve_ridge__versus__shared__ridge", "matched_nonlinear_contrast": "shared__curve_boosting__versus__shared__drp_boosting", "interpretation": "Exploratory second TRAIN experiment; descriptive patient bootstrap with overlapping training folds. Negative differences favor curve features. Family selection and repeated development use are not corrected by these intervals.", "contrasts": contrasts})
    summary = {"completed": True, "n_pdo": len(y), "n_patients": len(set(patients)), "n_drugs": y.shape[1], "budget_curves": 4, "query_features": 24, "all_libraries": sorted(set(map(str, data["library_ids"]))), "heldout_library_used": False, "scientific_role": "Second TRAIN-only exploratory grouped development; frozen curve representation", "metrics": metrics, "seconds": time.perf_counter() - started, "code_hashes": code_hashes(), "input": input_manifest, "controls": controls["provenance"]}
    first.dump(output / "SUMMARY.json", summary)
    files = {str(path.relative_to(output)): first.sha(path) for path in sorted(output.rglob("*")) if path.is_file()}
    first.dump(output / "MANIFEST.json", {"committed": True, "files": files})
    print(json.dumps({"event": "curve_complete", "output": str(output), "seconds": summary["seconds"], "new_metrics": {name: value for name, value in metrics.items() if "__curve_" in name}}), flush=True)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--curves", type=Path, required=True)
    parser.add_argument("--preparation-audit", type=Path, required=True)
    parser.add_argument("--controls", type=Path, required=True)
    parser.add_argument("--controls-manifest-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Output already exists; preserve the previous attempt")
    assert_frozen_sources()
    data, metadata = first.load_train(args.train, args.metadata)
    if data["y"].shape[1] != 24:
        raise ValueError("The frozen scientific experiment requires the same 24 target items")
    input_manifest = {"npz_path": str(args.train.resolve()), "npz_sha256": first.sha(args.train), "metadata_path": str(args.metadata.resolve()), "metadata_sha256": first.sha(args.metadata), "curve_csv_path": str(args.curves.resolve()), "curve_csv_sha256": first.sha(args.curves), "preparation_audit_path": str(args.preparation_audit.resolve()), "preparation_audit_sha256": first.sha(args.preparation_audit)}
    controls = load_controls(data, args.controls, input_manifest, args.controls_manifest_sha256)
    features = load_curve_features(data, metadata, args.train, args.curves, args.preparation_audit)
    with threadpool_limits(limits=1):
        run(data, features, controls, args.output, metadata, input_manifest)


if __name__ == "__main__":
    main()
