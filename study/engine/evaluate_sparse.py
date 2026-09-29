#!/usr/bin/env python3
"""Third TRAIN-only experiment: three allocation policies, 32 native pairs each."""
from __future__ import annotations

import argparse
import csv
from decimal import Decimal, localcontext
import json
import os
from pathlib import Path
import platform
import time

for _name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_name] = "1"

import numpy as np
import scipy
from threadpoolctl import threadpool_limits

import evaluate as first
import evaluate_curve_shape as curve
from methods import METHOD_CONFIGS, patient_folds, per_patient_loss
from sparse_methods import ALLOCATION_FAMILIES, LAMBDAS, SparseRidgePredictor, allocate, descriptor_from_manifest, fit_sparse_context


PROTOCOL_SHA256 = "5c555baa66ef9a1d71702efc4e6b36ac9c112ac42e93f712db44c585880ece49"
QUERY_POOL_SHA256 = "536ece2d552740671a5a44f16c948b8ddc4ca6330be1f9b3c4f11398491a3aab"
PRIOR_CODE_HASHES = {**curve.FIRST_CODE_HASHES, "curve_shape_methods.py": "82a5e4c2c338acb5b3c545724a8c9c2de58d3f6326f9b8be9f0403fa7096d70e", "evaluate_curve_shape.py": "dd0ca6065751d86cc280265d62e8ea3434309780e68f89b9f9654f1a4d02c1e7"}
REFERENCE_FAMILIES = tuple(METHOD_CONFIGS) + ("curve_ridge", "curve_boosting")


def code_hashes():
    folder = Path(__file__).resolve().parent
    return {name: first.sha(folder / name) for name in (*PRIOR_CODE_HASHES, "sparse_methods.py", "evaluate_sparse.py")}


def assert_frozen_sources():
    folder = Path(__file__).resolve().parent
    for name, expected in PRIOR_CODE_HASHES.items():
        if first.sha(folder / name) != expected:
            raise ValueError("Prior frozen implementation changed: " + name)
    protocol = folder.parents[1] / "research/round7_sparse_dose_protocol_review.md"
    if first.sha(protocol) != PROTOCOL_SHA256:
        raise ValueError("Frozen sparse allocation protocol changed")
    curve.assert_frozen_sources()


def dose_key(value):
    # Same inherited 12-significant-digit Decimal input identity convention.
    with localcontext() as context:
        context.prec = 12
        return str((+Decimal(str(value))).normalize())


def verify_manifest(directory, expected_sha256):
    directory = Path(directory)
    manifest_path = directory / "MANIFEST.json"
    if first.sha(manifest_path) != expected_sha256:
        raise ValueError("Immutable control manifest differs from its frozen hash")
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("committed") is not True:
        raise ValueError("Control attempt is not committed")
    root = directory.resolve()
    for relative, expected in manifest["files"].items():
        path = directory / relative
        if not path.resolve().is_relative_to(root) or first.sha(path) != expected:
            raise ValueError("Immutable control file changed: " + relative)
    return manifest


def load_sparse_features(data, metadata, train_path, curves_path, audit_path, pool_path, expected_pool_sha256):
    train_path, curves_path, audit_path, pool_path = map(Path, (train_path, curves_path, audit_path, pool_path))
    if first.sha(pool_path) != expected_pool_sha256:
        raise ValueError("Native-query input manifest hash mismatch")
    pool = json.loads(pool_path.read_text())
    if pool.get("input_manifest_sha256") != metadata.get("input_manifest_sha256"):
        raise ValueError("Query pool and TRAIN release use different input eligibility")
    for name, record in pool["files"].items():
        path = pool_path.parent / name
        if not path.resolve().is_relative_to(pool_path.parent.resolve()) or first.sha(path) != record["sha256"]:
            raise ValueError("Query-pool evidence hash mismatch: " + name)
    if metadata.get("split_role") != "TRAIN" or metadata.get("lib2_response_values_converted", 0) != 0:
        raise ValueError("Only explicit TRAIN responses are allowed")
    if first.sha(train_path) != metadata.get("npz_sha256") or first.sha(audit_path) != metadata.get("preparation_audit_sha256"):
        raise ValueError("TRAIN release/preparation hash mismatch")
    audit = json.loads(audit_path.read_text())
    if audit.get("status") != "complete" or audit.get("authorized_partition") != "train" or audit.get("lib2_response_values_converted", 0) != 0:
        raise ValueError("Preparation is not a completed TRAIN-only release")
    if any(audit.get("files", {}).get(path.name) != first.sha(path) for path in (train_path, curves_path)):
        raise ValueError("Original curve release changed")
    libraries = set(map(str, data["library_ids"]))
    if len(libraries) != 1:
        raise ValueError("Development requires one known measurement library")
    library = next(iter(libraries))
    descriptor = descriptor_from_manifest(pool, library)
    if not np.array_equal(descriptor.target_ids, data["drug_ids"]):
        raise ValueError("Query-pool target order does not match original AUCs")
    n, d = data["y"].shape
    m = len(descriptor.query_ids)
    sample_index = {str(sample): i for i, sample in enumerate(data["sample_ids"])}
    drug_index = {str(drug): j for j, drug in enumerate(data["drug_ids"])}
    with np.load(train_path, allow_pickle=False) as source:
        row_lookup = {str(sample): i for i, sample in enumerate(source["sample_ids"])}
        column_lookup = {str(drug): j for j, drug in enumerate(source["drug_ids"])}
        rows = np.asarray([row_lookup[sample] for sample in data["sample_ids"]])
        columns = np.asarray([column_lookup[drug] for drug in data["drug_ids"]])
        runs = np.asarray(source["run_ids"], dtype=str)[rows]
        old_replicates = np.asarray(source["y_replicates"], dtype=float)[np.ix_(rows, columns)]
        full_curve_counts = np.asarray(source["well_counts"], dtype=int)[np.ix_(rows, columns)]
    if old_replicates.shape != (n, d, 2) or full_curve_counts.shape != (n, d) or not np.array_equal(old_replicates.mean(axis=2), data["y"]):
        raise ValueError("Canonical source replicates or full-curve budgets disagree")
    selected = {row["sample_id"]: row for row in pool["selected_records"] if row["partition"] == "train"}
    if set(selected) != set(sample_index):
        raise ValueError("Physical query pool and TRAIN sample identities disagree")
    for sample, i in sample_index.items():
        record = selected[sample]
        if (record["patient_id"], record["library_id"], record["run_id"]) != (data["patient_ids"][i], library, runs[i]):
            raise ValueError("Physical query pool patient/library/run mapping disagrees")
    native_values, physical_rows = {}, {}
    actual_counts = np.zeros((n, d), dtype=int)
    with curves_path.open(newline="") as handle:
        for row in csv.DictReader(handle):
            if row["sample_id"] not in sample_index or row["drug_id"] not in drug_index or row["plate"] not in ("p1", "p2"):
                raise ValueError("Unexpected native TRAIN sample/item/replicate")
            i, j = sample_index[row["sample_id"]], drug_index[row["drug_id"]]
            if (row["patient_id"], row["library_id"], row["run_id"]) != (data["patient_ids"][i], library, runs[i]):
                raise ValueError("Native TRAIN curve identity mismatch")
            r = int(row["plate"][-1]) - 1
            concentration = dose_key(row["dose_nM"])
            value = float(row["viability"])
            key = i, j, r, concentration
            physical = row["run_id"], row["plate"], row["drow"], row["dcol"]
            if key in native_values or physical in physical_rows or not np.isfinite(value):
                raise ValueError("Duplicate or invalid native source measurement")
            native_values[key] = value
            physical_rows[physical] = (i, j, r, concentration, row["assay_no"], value)
            actual_counts[i, j] += 1
    if not np.array_equal(actual_counts, full_curve_counts):
        raise ValueError("Full source curve counts changed")
    paired = np.full((n, m, 2), np.nan)
    well_ids = np.empty((n, m, 2), dtype=object)
    query_lookup = {query_id: q for q, query_id in enumerate(descriptor.query_ids)}
    queries = sorted(pool["queries"], key=lambda row: row["query_index"])
    with (pool_path.parent / "query_wells.csv").open(newline="") as handle:
        for row in csv.DictReader(handle):
            if row["partition"] != "train":
                continue  # Input-only rows; no reserved response value is opened.
            if row["sample_id"] not in sample_index or row["query_id"] not in query_lookup or row["plate"] not in ("p1", "p2"):
                raise ValueError("Unknown physical query mapping")
            i, q, r = sample_index[row["sample_id"]], query_lookup[row["query_id"]], int(row["plate"][-1]) - 1
            query = queries[q]
            if (row["library_id"], row["patient_id"], row["run_id"], row["drug_id"]) != (library, data["patient_ids"][i], runs[i], query["drug_id"]):
                raise ValueError("Physical query identity mismatch")
            physical = row["run_id"], row["plate"], row["drow"], row["dcol"]
            observed = physical_rows.get(physical)
            expected = (i, query["target_index"], r, dose_key(query["concentration_nM"]), row["assay_no"])
            if observed is None or observed[:5] != expected or dose_key(row["concentration_nM"]) != expected[3] or np.isfinite(paired[i, q, r]):
                raise ValueError("Query is not its exact declared native source well")
            paired[i, q, r] = observed[5]
            well_ids[i, q, r] = "|".join(physical)
    if not np.isfinite(paired).all():
        raise ValueError("At least one declared native action lacks a technical replicate")
    well_ids = well_ids.astype(str)
    if any(len(set(well_ids[i].ravel())) != 2 * m for i in range(n)):
        raise ValueError("Different query actions reuse the same physical well")
    recovered = np.zeros((n, d, 2))
    for target in pool["targets"]:
        j, details = target["target_index"], target["by_library"][library]
        for node in details["support_nodes"]:
            for i in range(n):
                for r in range(2):
                    recovered[i, j, r] += float(node["auc_weight"]) * native_values[(i, j, r, dose_key(node["concentration_nM"]))]
    if not np.allclose(recovered, old_replicates, rtol=0, atol=1e-12):
        raise ValueError("Native quadrature does not reproduce the unchanged AUC endpoint")
    x = paired.mean(axis=2)
    exact = descriptor.recoverable
    if not np.allclose((x @ descriptor.weights.T)[:, exact], data["y"][:, exact], rtol=0, atol=1e-12):
        raise ValueError("Available complete supports do not reconstruct original targets")
    return {"x": x, "x_replicates": paired, "query_ids": descriptor.query_ids, "descriptor": descriptor, "pool": pool, "well_ids": well_ids, "full_curve_well_counts": full_curve_counts, "audit": {"query_pool_sha256": expected_pool_sha256, "curve_csv_sha256": first.sha(curves_path), "pdo_count": n, "query_count": m, "queryable_drug_count": len(set(descriptor.query_target_indices)), "native_bundle_count": int(exact.sum()), "library_id": library, "maximum_native_auc_difference": float(np.max(np.abs(recovered - old_replicates))), "original_auc_targets_unchanged": True, "all_query_actions_have_two_distinct_source_wells": True, "heldout_library_response_used": False}}


def load_shared_controls(data, features, directory, expected_manifest_sha256, input_manifest, outer_splits=5, inner_splits=3):
    directory = Path(directory)
    manifest = verify_manifest(directory, expected_manifest_sha256)
    required = {"STARTED.json", "SUMMARY.json", "oof_predictions.npz", "outer_patient_folds.json"}
    if not required.issubset(manifest["files"]):
        raise ValueError("Reference manifest lacks required evidence")
    started, summary = [json.loads((directory / name).read_text()) for name in ("STARTED.json", "SUMMARY.json")]
    if not summary.get("completed") or summary.get("heldout_library_used") is not False or started.get("code_hashes") != PRIOR_CODE_HASHES or summary.get("code_hashes") != PRIOR_CODE_HASHES:
        raise ValueError("Reference attempt is incomplete or not the frozen curve comparison")
    if started.get("outer_splits") != outer_splits or started.get("inner_splits") != inner_splits or started.get("fold_salt") != first.SALT or started.get("budget") != 4:
        raise ValueError("Reference fold or measurement contract differs")
    for key in ("npz_sha256", "metadata_sha256", "curve_csv_sha256"):
        if not input_manifest.get(key) or started.get("input", {}).get(key) != input_manifest[key]:
            raise ValueError("References used different TRAIN input: " + key)
    folds, assignment = patient_folds(data["patient_ids"], outer_splits, first.SALT + "|outer")
    if json.loads((directory / "outer_patient_folds.json").read_text()) != assignment:
        raise ValueError("Reference patient folds differ")
    predictions, masks = {}, {}
    with np.load(directory / "oof_predictions.npz", allow_pickle=False) as saved:
        for key in ("y", "sample_ids", "patient_ids", "drug_ids", "library_ids"):
            if not np.array_equal(saved[key], data[key]):
                raise ValueError("Reference target or identity alignment differs: " + key)
        if not np.array_equal(saved["folds"], folds):
            raise ValueError("Reference row folds differ")
        for family in REFERENCE_FAMILIES:
            name = "shared__" + family
            prediction, mask = np.asarray(saved[name]), np.asarray(saved[name + "__observed_mask"])
            if prediction.shape != data["y"].shape or mask.shape != prediction.shape or mask.dtype != bool or not np.isfinite(prediction).all():
                raise ValueError("Malformed reference prediction/mask")
            if not np.all(mask.sum(axis=1) == 4) or not np.array_equal(prediction[mask], data["y"][mask]):
                raise ValueError("Reference measured targets are not its four real curves")
            if not np.all((features["full_curve_well_counts"] * mask).sum(axis=1) == 64):
                raise ValueError("A reference consumes a different treatment-well budget")
            predictions[name], masks[name] = prediction.copy(), mask.copy()
    if any(not np.array_equal(mask, masks["shared__ridge"]) for mask in masks.values()):
        raise ValueError("Reference shared panels disagree")
    return {"predictions": predictions, "masks": masks, "provenance": {"curve_manifest_sha256": expected_manifest_sha256, "curve_oof_sha256": manifest["files"]["oof_predictions.npz"], "reference_count": len(predictions), "each_reference_treatment_wells": 64, "identities_targets_and_folds_exactly_aligned": True}}


def select_lambdas(x, y, patients, descriptor, n_splits, salt, directory):
    directory.mkdir()
    folds, assignment = patient_folds(patients, n_splits, salt)
    first.dump(directory / "patient_folds.json", assignment)
    totals = {(family, lam): (0.0, 0) for family in ALLOCATION_FAMILIES for lam in LAMBDAS}
    for fold in range(n_splits):
        train, validation = folds != fold, folds == fold
        context = fit_sparse_context(x[train], y[train], patients[train], descriptor.query_ids, descriptor.target_ids)
        record = {"fold": fold, "training_patients": len(set(patients[train])), "validation_patients": len(set(patients[validation])), "results": []}
        for family in ALLOCATION_FAMILIES:
            for lam in LAMBDAS:
                began = time.perf_counter()
                selected, plan = allocate(context, descriptor, family, lam)
                predictor = SparseRidgePredictor(context, selected, lam, descriptor)
                prediction = predictor.predict(x[validation][:, selected])
                _, losses = per_patient_loss(y[validation], prediction, patients[validation])
                old_sum, old_count = totals[family, lam]
                totals[family, lam] = old_sum + float(losses.sum()), old_count + len(losses)
                record["results"].append({"family": family, "lambda": lam, "plan": plan, "patient_loss_sum": float(losses.sum()), "patient_count": len(losses), "seconds": time.perf_counter() - began})
        first.dump(directory / f"inner_{fold:02d}.json", record)
        print(json.dumps({"event": "sparse_inner_fold_complete", "location": str(directory), "fold": fold}), flush=True)
    selected = {}
    for family in ALLOCATION_FAMILIES:
        score, index, lam = min((totals[family, lam][0] / totals[family, lam][1], i, lam) for i, lam in enumerate(LAMBDAS))
        selected[family] = {"lambda": lam, "lambda_index": index, "inner_mse": score}
    first.dump(directory / "selection.json", {"selections": selected, "pooled_patient_count": len(set(patients)), "configurations": 12})
    return selected


def summarize(y, patients, predictions, exact_masks):
    metrics, table, risks = {}, [], {}
    for name, prediction in predictions.items():
        ids, losses = per_patient_loss(y, prediction, patients)
        _, maes = per_patient_loss(y, prediction, patients, absolute=True)
        _, remaining = per_patient_loss(y, prediction, patients, mask=~exact_masks[name])
        metrics[name] = {"mse": float(losses.mean()), "rmse": float(np.sqrt(losses.mean())), "mae": float(maes.mean()), "not_exactly_reconstructed_rmse": float(np.sqrt(remaining.mean())), "patient_count": len(ids), "treatment_wells_per_pdo": 64}
        risks[name] = losses
        table.extend({"method": name, "patient_id": str(pid), "mse": float(loss), "mae": float(mae)} for pid, loss, mae in zip(ids, losses, maes))
    contrasts = {}
    for family in ALLOCATION_FAMILIES:
        candidate = "sparse__" + family
        for reference in predictions:
            if reference != candidate and (reference.startswith("shared__") or family == "joint_native_greedy"):
                contrasts[candidate + "__versus__" + reference] = first.bootstrap_difference(risks[candidate], risks[reference])
    return metrics, table, contrasts


def run(data, features, controls, output, metadata, input_manifest, outer_splits=5, inner_splits=3):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    descriptor = features["descriptor"]
    first.dump(output / "STARTED.json", {"unix_time": time.time(), "input": input_manifest, "metadata": metadata, "code_hashes": code_hashes(), "protocol_sha256": PROTOCOL_SHA256, "query_audit": features["audit"], "controls": controls["provenance"], "families": ALLOCATION_FAMILIES, "lambdas": LAMBDAS, "outer_splits": outer_splits, "inner_splits": inner_splits, "fold_salt": first.SALT, "paired_actions": 32, "treatment_wells": 64, "versions": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__}})
    x, y, patients = features["x"], data["y"], data["patient_ids"]
    folds, assignment = patient_folds(patients, outer_splits, first.SALT + "|outer")
    first.dump(output / "outer_patient_folds.json", assignment)
    predictions = {key: value.copy() for key, value in controls["predictions"].items()}
    exact_masks = {key: value.copy() for key, value in controls["masks"].items()}
    action_masks = {}
    for family in ALLOCATION_FAMILIES:
        name = "sparse__" + family
        predictions[name], exact_masks[name], action_masks[name] = np.full_like(y, np.nan), np.zeros_like(y, dtype=bool), np.zeros_like(x, dtype=bool)
    for fold in range(outer_splits):
        train, test = folds != fold, folds == fold
        directory = output / f"outer_{fold:02d}"
        directory.mkdir()
        selections = select_lambdas(x[train], y[train], patients[train], descriptor, inner_splits, first.SALT + f"|inner|{fold}", directory / "selection")
        context = fit_sparse_context(x[train], y[train], patients[train], descriptor.query_ids, descriptor.target_ids)
        record = {"fold": fold, "results": {}}
        for family, selection in selections.items():
            chosen, plan = allocate(context, descriptor, family, selection["lambda"])
            model = SparseRidgePredictor(context, chosen, selection["lambda"], descriptor)
            observed = x[test][:, chosen]
            prediction = model.predict(observed)
            exact = model.exact_target_mask
            if not np.allclose(prediction[:, exact], observed @ model.copy_weights[exact].T, rtol=0, atol=1e-12):
                raise AssertionError("An exact target was not derived from its queried measurements")
            if any(len(set(features["well_ids"][i, chosen].ravel())) != 64 for i in np.flatnonzero(test)):
                raise AssertionError("A test plan does not purchase 64 distinct physical wells")
            name = "sparse__" + family
            predictions[name][test] = prediction
            exact_masks[name][test] = exact
            action_masks[name][np.ix_(np.flatnonzero(test), chosen)] = True
            record["results"][name] = {**selection, "plan": plan}
        first.dump(directory / "outer_result.json", record)
        print(json.dumps({"event": "sparse_outer_fold_complete", "fold": fold, "seconds": time.perf_counter() - started}), flush=True)
    if any(not np.isfinite(value).all() for value in predictions.values()) or any(not np.all(mask.sum(axis=1) == 32) for mask in action_masks.values()):
        raise AssertionError("Incomplete sparse predictions or action budgets")
    metrics, patient_table, contrasts = summarize(y, patients, predictions, exact_masks)
    np.savez_compressed(output / "oof_predictions.npz", y=y, sample_ids=data["sample_ids"], patient_ids=patients, drug_ids=data["drug_ids"], library_ids=data["library_ids"], query_ids=descriptor.query_ids, folds=folds, **predictions, **{key + "__exact_target_mask": value for key, value in exact_masks.items()}, **{key + "__action_mask": value for key, value in action_masks.items()})
    np.savez_compressed(output / "native_query_features.npz", x=x, x_replicates=features["x_replicates"], well_ids=features["well_ids"], sample_ids=data["sample_ids"], patient_ids=patients, drug_ids=data["drug_ids"], query_ids=descriptor.query_ids, native_weights=descriptor.weights, native_recoverable=descriptor.recoverable, library_id=descriptor.library_id)
    first.dump(output / "query_audit.json", features["audit"])
    with (output / "per_patient_losses.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=("method", "patient_id", "mse", "mae"))
        writer.writeheader(); writer.writerows(patient_table)
    first.dump(output / "metrics.json", metrics)
    first.dump(output / "paired_patient_contrasts.json", {"interpretation": "Exploratory TRAIN-only allocation comparison. Every reported method consumes 64 treatment wells. Native exact targets come from queried weighted sums, never copied hidden y. Descriptive patient bootstrap does not correct overlapping training folds or campaign model selection.", "contrasts": contrasts})
    summary = {"completed": True, "n_pdo": len(y), "n_patients": len(set(patients)), "n_drugs": y.shape[1], "paired_actions": 32, "treatment_wells": 64, "heldout_library_used": False, "scientific_role": "Third TRAIN-only exploratory native-dose allocation experiment", "metrics": metrics, "seconds": time.perf_counter() - started, "code_hashes": code_hashes(), "input": input_manifest, "library_specific_native_bundle_count": int(descriptor.recoverable.sum())}
    first.dump(output / "SUMMARY.json", summary)
    first.dump(output / "MANIFEST.json", {"committed": True, "files": {str(path.relative_to(output)): first.sha(path) for path in sorted(output.rglob("*")) if path.is_file()}})
    print(json.dumps({"event": "sparse_complete", "output": str(output), "seconds": summary["seconds"], "new_metrics": {name: value for name, value in metrics.items() if name.startswith("sparse__")}}), flush=True)
    return summary


def main():
    parser = argparse.ArgumentParser()
    for name in ("train", "metadata", "curves", "preparation-audit", "query-pool", "curve-controls", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--curve-controls-manifest-sha256", required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Preserve the existing scientific attempt")
    assert_frozen_sources()
    data, metadata = first.load_train(args.train, args.metadata)
    features = load_sparse_features(data, metadata, args.train, args.curves, args.preparation_audit, args.query_pool, QUERY_POOL_SHA256)
    if data["y"].shape[1] != 24 or features["x"].shape[1] != 150 or len(set(features["descriptor"].query_target_indices)) != 22 or set(data["library_ids"]) != {"lib1"}:
        raise ValueError("Scientific run differs from the frozen 24-target/150-action Lib1 contract")
    input_manifest = {"npz_path": str(args.train.resolve()), "npz_sha256": first.sha(args.train), "metadata_path": str(args.metadata.resolve()), "metadata_sha256": first.sha(args.metadata), "curve_csv_path": str(args.curves.resolve()), "curve_csv_sha256": first.sha(args.curves), "query_pool_path": str(args.query_pool.resolve()), "query_pool_sha256": QUERY_POOL_SHA256, "preparation_audit_sha256": first.sha(args.preparation_audit)}
    controls = load_shared_controls(data, features, args.curve_controls, args.curve_controls_manifest_sha256, input_manifest)
    with threadpool_limits(limits=1):
        run(data, features, controls, args.output, metadata, input_manifest)


if __name__ == "__main__":
    main()
