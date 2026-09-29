#!/usr/bin/env python3
"""One frozen TRAIN-only 64-well lossless-bracketing procedure comparison."""
from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
import platform
import time
import traceback

for _name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_name] = "1"

import numpy as np
from threadpoolctl import threadpool_limits

import evaluate as first
import evaluate_sparse as sparse_eval
import evaluate_mechanism as mechanism_eval
from methods import patient_folds, per_patient_loss
from sparse_methods import LAMBDAS
from bracketing_methods import ALLOCATION_ALPHA, MISSING_DRUGS, PREDICTORS, BracketingPredictor, acquire, encode_paid, fit_prediction_context, layout_from_contract, plan_panel


CONTRACT_SHA256 = "25678678b1b8d43b47675ab2256bcc81df0b21ba19cc57a76844518a5dea32a0"
R8_MANIFEST_SHA256 = "8e0e5d407418f9e6d7aa0f41786b7c0d1ab1abca02a4b6095f1581501a849720"
R7_MANIFEST_SHA256 = mechanism_eval.SPARSE_REFERENCE_MANIFEST_SHA256
INPUT_HASHES = {"train": "c775264e3c612711281bbe88793e77b3edfee2e2dbc4180116dd296854a8787a", "metadata": "131c7de4eb16fafe08d07aaaad613377a6208db14bbd4396090b2ec674f9753e", "curves": "b192dc242362d74c4faa941752792336c7610d9bd403cccbf1cee7a8a1fc7c94", "preparation_audit": "33561a7ba7a3e27c3d79b677e89aceb43c9b0641d9b19ab4c62603d5886491a4", "query_pool": mechanism_eval.QUERY_POOL_SHA256, "contract": CONTRACT_SHA256}
FROZEN_CODE_HASHES = {**mechanism_eval.FROZEN_CODE_HASHES, "mechanism_methods.py": "d38452a8454df7ce7f85a257b9bb0aa81a874f909ef5f0c66ec2529212811a15", "evaluate_mechanism.py": "52f911dcaeb2942a45f9fd9c7585fb6f9e6506cd09787887cc03b959ceb8d45d"}
NEW_CODE = ("bracketing_methods.py", "evaluate_bracketing.py", "synthetic_bracketing_preflight.py")


def code_hashes():
    folder = Path(__file__).resolve().parent
    return {name: first.sha(folder / name) for name in (*FROZEN_CODE_HASHES, *NEW_CODE)}


def check_freeze(args):
    """Check authorization and every scientific input before reading responses."""
    freeze = json.loads(args.freeze.read_text())
    if freeze.get("authorization") != "exactly one TRAIN-only bracketing run":
        raise ValueError("Explicit one-attempt bracketing authorization missing")
    if freeze.get("protocol_sha256") != first.sha(args.protocol):
        raise ValueError("Bracketing protocol differs from root freeze")
    actual_code = code_hashes()
    for name, expected in FROZEN_CODE_HASHES.items():
        if actual_code[name] != expected:
            raise ValueError("Prior frozen code changed: " + name)
    for name in NEW_CODE:
        if freeze.get("code", {}).get(name) != actual_code[name]:
            raise ValueError("Bracketing code differs from root freeze: " + name)
    for name, expected in INPUT_HASHES.items():
        if first.sha(getattr(args, name)) != expected:
            raise ValueError("Scientific input changed before numerical access: " + name)
    project = Path(__file__).resolve().parents[2]
    if (project / freeze.get("attempt", "MISSING")).resolve() != args.output.resolve():
        raise ValueError("Output attempt is not the authorized frozen location")
    return freeze


def load_bracketing_features(data, metadata, train_path, curves_path, audit_path, pool_path, contract_path):
    """Reuse authorized Lib1 release and verify exact physical joins for new nodes."""
    contract_path = Path(contract_path)
    if first.sha(contract_path) != CONTRACT_SHA256:
        raise ValueError("The input-only lossless contract changed")
    contract = json.loads(contract_path.read_text())
    for name, record in contract["files"].items():
        path = contract_path.parent / name
        if not path.resolve().is_relative_to(contract_path.parent.resolve()) or first.sha(path) != record["sha256"]:
            raise ValueError("Lossless contract evidence changed: " + name)
    if set(map(str, data["library_ids"])) != {"lib1"} or metadata.get("split_role") != "TRAIN" or metadata.get("lib2_response_values_converted", 0) != 0:
        raise ValueError("Bracketing loader authorizes Lib1 TRAIN values only")
    old = sparse_eval.load_sparse_features(data, metadata, train_path, curves_path, audit_path, pool_path, mechanism_eval.QUERY_POOL_SHA256)
    return join_native_features(data, old, curves_path, contract_path, contract)


def join_native_features(data, old, curves_path, contract_path, contract):
    """Exact response-to-input-metadata join, separated for adversarial fixtures."""
    if set(map(str, data["library_ids"])) != {"lib1"}:
        raise ValueError("Native joins authorize only the Lib1 TRAIN partition")
    layout = layout_from_contract(old["descriptor"], contract)
    n, m = len(data["y"]), len(layout.native_ids)
    paired = np.full((n, m, 2), np.nan)
    paired[:, :150] = old["x_replicates"]
    wells = np.full((n, m, 2), "", dtype=object)
    wells[:, :150] = old["well_ids"]
    samples = {str(v): i for i, v in enumerate(data["sample_ids"])}
    targets = {str(v): i for i, v in enumerate(data["drug_ids"])}
    native_lookup = {str(v): i for i, v in enumerate(layout.native_ids)}
    selected_records = {r["sample_id"]: r for r in old["pool"]["selected_records"] if r["partition"] == "train"}
    raw_by_physical = {}
    with Path(curves_path).open(newline="") as handle:
        for row in csv.DictReader(handle):
            # Identity and release gate precede float conversion.
            sample = row["sample_id"]
            if sample not in samples or row["library_id"] != "lib1" or row["plate"] not in ("p1", "p2") or row["drug_id"] not in targets:
                raise ValueError("Unreleased or malformed raw response row")
            i = samples[sample]
            if row["patient_id"] != data["patient_ids"][i] or row["run_id"] != selected_records[sample]["run_id"]:
                raise ValueError("Native response patient/run mismatch")
            key = (row["library_id"], sample, row["run_id"], row["plate"], row["drow"], row["dcol"])
            if key in raw_by_physical:
                raise ValueError("Duplicate physical native response row")
            value = float(row["viability"])
            if not np.isfinite(value):
                raise ValueError("Nonfinite supplied viability")
            raw_by_physical[key] = (row, value)
    candidates = {c["feature_id"]: c for c in layout.candidates}
    mapping_rows = 0
    with (contract_path.parent / "candidate_native_wells.csv").open(newline="") as handle:
        for row in csv.DictReader(handle):
            if row["partition"] != "train":
                continue  # Reserved metadata do not cause any numerical access.
            if row["library_id"] != "lib1" or row["sample_id"] not in samples or row["plate"] not in ("p1", "p2") or row["feature_id"] not in candidates:
                raise ValueError("Unreleased or malformed candidate well mapping")
            i, candidate = samples[row["sample_id"]], candidates[row["feature_id"]]
            if row["native_action_id"] not in candidate["native_ids"]:
                raise ValueError("Candidate maps an unpurchased native action")
            q, r = native_lookup[row["native_action_id"]], int(row["plate"][-1]) - 1
            position = candidate["native_ids"].index(row["native_action_id"])
            if row["node_role"] != ("lower", "upper")[position] or row["drug_id"] != candidate["drug_id"] or float(row["q"]) != candidate["q"] or row["coordinate_ids"].split(";") != candidate["coordinate_ids"]:
                raise ValueError("Candidate coordinate identity mismatch")
            for coord, prefix in enumerate(("z", "m")):
                if not np.isclose(float(row[prefix + "_coefficient_on_this_well_decimal80"]), candidate["forward_matrix"][coord][position] / 2, rtol=0, atol=1e-14):
                    raise ValueError("Individual-well transform coefficient mismatch")
            key = (row["library_id"], row["sample_id"], row["run_id"], row["plate"], row["drow"], row["dcol"])
            found = raw_by_physical.get(key)
            if found is None:
                raise ValueError("Candidate well absent from authorized response release")
            raw, value = found
            if any(raw[field] != row[field] for field in ("patient_id", "drug_id", "assay_no")) or sparse_eval.dose_key(raw["dose_nM"]) != sparse_eval.dose_key(row["native_concentration_nM"]) or sparse_eval.dose_key(raw["dose_nM"]) != sparse_eval.dose_key(layout.native_concentrations[q]):
                raise ValueError("Candidate native concentration/drug/patient/assay mismatch")
            physical_id = "|".join((row["run_id"], row["plate"], row["drow"], row["dcol"]))
            if wells[i, q, r] and (wells[i, q, r] != physical_id or paired[i, q, r] != value):
                raise ValueError("Repeated candidate node conflicts with its physical identity")
            paired[i, q, r], wells[i, q, r] = value, physical_id
            mapping_rows += 1
    if mapping_rows != n * 10 * 4 or not np.isfinite(paired).all() or any(len(set(wells[i].ravel())) != 2 * m for i in range(n)):
        raise ValueError("Native universe has missing/overlapping pairs or incomplete mappings")
    return {"x": paired.mean(axis=2), "x_replicates": paired, "well_ids": wells.astype(str), "layout": layout, "old": old, "audit": {"n_pdo": n, "native_pair_universe": m, "old_native_pairs": 150, "new_native_pairs": m - 150, "candidate_mapping_rows": mapping_rows, "same_train_release": True, "lib2_response_values_converted": 0, "bridge_response_values_opened": 0, "genotype_values_opened": 0, "contract_sha256": CONTRACT_SHA256, "native_auc_endpoint_audit": old["audit"]}}


def load_references(data, features, r8_path, r7_path):
    r7 = mechanism_eval.load_sparse_reference(data, features["old"], r7_path)
    manifest = sparse_eval.verify_manifest(r8_path, R8_MANIFEST_SHA256)
    summary = json.loads((Path(r8_path) / "SUMMARY.json").read_text())
    if summary.get("completed") is not True or summary.get("heldout_library_used") is not False or summary.get("treatment_wells") != 64:
        raise ValueError("R8 reference is not a completed 64-well TRAIN run")
    for name in ("mechanism_methods.py", "evaluate_mechanism.py"):
        if summary["code_hashes"][name] != FROZEN_CODE_HASHES[name]:
            raise ValueError("R8 reference implementation identity changed")
    with np.load(Path(r8_path) / "oof_predictions.npz", allow_pickle=False) as saved:
        for key in ("y", "sample_ids", "patient_ids", "drug_ids", "library_ids"):
            if not np.array_equal(saved[key], data[key]):
                raise ValueError("R8 reference identity mismatch: " + key)
        if not np.array_equal(saved["query_ids"], features["layout"].old_descriptor.query_ids) or not np.array_equal(saved["folds"], r7["folds"]) or not np.array_equal(saved["action_mask"], r7["action_mask"]):
            raise ValueError("R8 reference query/action/fold identity mismatch")
        r8_prediction = saved["hybrid_drugwise22"].copy()
    if r8_prediction.shape != data["y"].shape or not np.isfinite(r8_prediction).all():
        raise ValueError("R8 incumbent prediction is malformed")
    return {"predictions": {"reference_r8_own_hybrid": r8_prediction, "reference_r7_shared": r7["prediction"]}, "folds": r7["folds"], "old_action_mask": r7["action_mask"], "provenance": {"r8_manifest_sha256": R8_MANIFEST_SHA256, "r8_oof_sha256": manifest["files"]["oof_predictions.npz"], "r7_manifest_sha256": R7_MANIFEST_SHA256, "references_refit": False}}


def save_model(path, model, context):
    np.savez_compressed(path, **model.arrays(), cxx=context.cxx, cxy=context.cxy, cyy=context.cyy, weights=context.weights)


def select_lambdas(x, y, patients, sample_ids, layout, directory, n_splits, salt):
    directory = Path(directory)
    directory.mkdir()
    folds, assignment = patient_folds(patients, n_splits, salt)
    first.dump(directory / "patient_folds.json", assignment)
    predictions = {(family, lam): np.full_like(y, np.nan) for family in PREDICTORS for lam in LAMBDAS}
    for fold in range(n_splits):
        training, validation = folds != fold, folds == fold
        plan = plan_panel(x[training], y[training], patients[training], layout)
        context = fit_prediction_context(acquire(x[training], plan), y[training], patients[training], plan, layout.target_ids)
        paid = acquire(x[validation], plan)
        inner = directory / f"inner_{fold:02d}"
        inner.mkdir()
        first.dump(inner / "plan.json", plan)
        record = {"training_sample_ids": list(map(str, sample_ids[training])), "validation_sample_ids": list(map(str, sample_ids[validation])), "training_patient_ids": sorted(set(map(str, patients[training]))), "validation_patient_ids": sorted(set(map(str, patients[validation]))), "results": []}
        np.savez_compressed(inner / "paid_validation.npz", sample_ids=sample_ids[validation], patient_ids=patients[validation], paid_native=paid, encoded=encode_paid(paid, plan), y=y[validation])
        for family in PREDICTORS:
            for index, lam in enumerate(LAMBDAS):
                model = BracketingPredictor(context, plan, lam, family)
                prediction = model.predict(paid)
                predictions[family, lam][validation] = prediction
                pids, losses = per_patient_loss(y[validation], prediction, patients[validation])
                record["results"].append({"family": family, "lambda_index": index, "lambda": lam, "patient_ids": list(map(str, pids)), "patient_losses": list(map(float, losses)), "patient_loss_sum": float(losses.sum()), "patient_count": len(losses)})
                save_model(inner / f"model__{family}__lambda_{index}.npz", model, context)
        first.dump(inner / "scores.json", record)
    selections = {}
    scores = []
    for family in PREDICTORS:
        options = []
        for index, lam in enumerate(LAMBDAS):
            if not np.isfinite(predictions[family, lam]).all():
                raise AssertionError("Inner predictions do not cover all patients")
            pids, losses = per_patient_loss(y, predictions[family, lam], patients)
            score = float(losses.mean())
            options.append((score, index, lam))
            scores.append({"family": family, "lambda": lam, "lambda_index": index, "patient_ids": list(map(str, pids)), "patient_losses": list(map(float, losses)), "patient_mse": score})
        score, index, lam = min(options)
        selections[family] = {"lambda": lam, "lambda_index": index, "inner_patient_mse": score}
    np.savez_compressed(directory / "inner_oof_predictions.npz", y=y, sample_ids=sample_ids, patient_ids=patients, drug_ids=layout.target_ids, folds=folds, **{f"{family}__lambda_{i}": predictions[family, lam] for family in PREDICTORS for i, lam in enumerate(LAMBDAS)})
    first.dump(directory / "selection.json", {"selections": selections, "all_scores": scores, "selector_count": 2, "lambdas_per_selector": 4, "selection_target_count": 24, "allocation_regenerated_per_inner_training_fold": True, "joint_lambda_cross_product_searched": False})
    return selections


def scopes(layout):
    missing = np.asarray([list(layout.target_ids).index(drug) for drug in MISSING_DRUGS], dtype=int)
    return {"all24": np.arange(24), "original22": np.setdiff1d(np.arange(24), missing), "missing2": missing}


def summarize(data, predictions, folds, layout):
    y, patients = data["y"], data["patient_ids"]
    metrics, losses, patient_rows, target_rows, fold_rows = {}, {}, [], [], []
    for name, prediction in predictions.items():
        metrics[name], losses[name] = {}, {}
        for scope, targets in scopes(layout).items():
            pids, risk = per_patient_loss(y[:, targets], prediction[:, targets], patients)
            _, absolute = per_patient_loss(y[:, targets], prediction[:, targets], patients, absolute=True)
            losses[name][scope] = risk
            metrics[name][scope] = {"mse": float(risk.mean()), "rmse": float(np.sqrt(risk.mean())), "mae": float(absolute.mean()), "patients": len(pids), "targets": len(targets), "treatment_wells": 64}
            patient_rows.extend({"method": name, "scope": scope, "patient_id": str(pid), "mse": float(mse), "mae": float(mae)} for pid, mse, mae in zip(pids, risk, absolute))
            for fold in sorted(set(folds)):
                mask = folds == fold
                fr = per_patient_loss(y[mask][:, targets], prediction[mask][:, targets], patients[mask])[1]
                fold_rows.append({"method": name, "scope": scope, "fold": int(fold), "mse": float(fr.mean()), "patient_count": len(fr)})
        for target, identity in enumerate(layout.target_ids):
            risk = per_patient_loss(y[:, [target]], prediction[:, [target]], patients)[1]
            target_rows.append({"method": name, "target_index": target, "target_id": str(identity), "mse": float(risk.mean()), "rmse": float(np.sqrt(risk.mean()))})
    contrasts = {}
    for candidate, reference, role in (("own_drug_all24", "reference_r8_own_hybrid", "primary_total_procedure"), ("shared_all24", "reference_r7_shared", "secondary_acquisition_and_representation"), ("own_drug_all24", "shared_all24", "same_observation_prediction_mechanism")):
        entry = {"candidate": candidate, "reference": reference, "role": role, "scopes": {}}
        for scope in scopes(layout):
            c, r = losses[candidate][scope], losses[reference][scope]
            entry["scopes"][scope] = {**first.bootstrap_difference(c, r), **mechanism_eval._contrast_summary(c, r, patients, folds)}
        entry["decomposition_max_patient_residual"] = float(np.max(np.abs((losses[candidate]["all24"] - losses[reference]["all24"]) - (22 / 24) * (losses[candidate]["original22"] - losses[reference]["original22"]) - (2 / 24) * (losses[candidate]["missing2"] - losses[reference]["missing2"]))))
        contrasts[role] = entry
    primary = contrasts["primary_total_procedure"]["scopes"]["all24"]
    improved_folds = sum(row["mean_delta"] < 0 for row in primary["folds"])
    decision = {"primary_candidate": "own_drug_all24", "incumbent": "reference_r8_own_hybrid", "lower_full24_mse": metrics["own_drug_all24"]["all24"]["mse"] < metrics["reference_r8_own_hybrid"]["all24"]["mse"], "improving_outer_folds": improved_folds, "minimum_improving_folds": 2}
    decision["carry_forward"] = decision["lower_full24_mse"] and improved_folds >= 2
    return metrics, contrasts, decision, patient_rows, target_rows, fold_rows


def write_csv(path, rows):
    if not rows:
        raise ValueError("Empty required evidence table")
    with Path(path).open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def run(data, features, references, output, provenance, outer_splits=5, inner_splits=3, attempt_reserved=False):
    output = Path(output)
    if attempt_reserved:
        if not output.is_dir() or set(path.name for path in output.iterdir()) != {"ATTEMPT_STARTED.json"}:
            raise ValueError("Reserved attempt is not pristine; preserve existing evidence")
    else:
        output.mkdir(parents=True, exist_ok=False)
    began = time.perf_counter()
    x, y, patients, layout = features["x"], data["y"], data["patient_ids"], features["layout"]
    first.dump(output / "STARTED.json", {"provenance": provenance, "reference": references["provenance"], "code_hashes": code_hashes(), "unix_time": time.time(), "outer_splits": outer_splits, "inner_splits": inner_splits, "fold_salt": first.SALT, "predictors": PREDICTORS, "prediction_lambdas": LAMBDAS, "allocation_alpha": ALLOCATION_ALPHA, "native_pairs": 32, "treatment_wells": 64, "heldout_library_used": False, "python_version": platform.python_version(), "numpy_version": np.__version__})
    folds, assignment = patient_folds(patients, outer_splits, first.SALT + "|outer")
    if not np.array_equal(folds, references["folds"]):
        raise ValueError("Frozen comparator patient folds differ")
    first.dump(output / "outer_patient_folds.json", assignment)
    first.dump(output / "feature_audit.json", features["audit"])
    predictions = {name: np.full_like(y, np.nan) for name in PREDICTORS}
    action_mask = np.zeros_like(x, dtype=bool)
    original_mask = np.zeros((len(y), 150), dtype=bool)
    own_mask = np.zeros((outer_splits, 24, 32), dtype=bool)
    paid_values = np.full((len(y), 32), np.nan)
    paid_wells = np.full((len(y), 32, 2), "", dtype=object)
    physical_rows, overlap_rows, plan_rows = [], [], []
    for fold in range(outer_splits):
        training, test = folds != fold, folds == fold
        directory = output / f"outer_{fold:02d}"
        directory.mkdir()
        selections = select_lambdas(x[training], y[training], patients[training], data["sample_ids"][training], layout, directory / "selection", inner_splits, first.SALT + f"|inner|{fold}")
        plan = plan_panel(x[training], y[training], patients[training], layout)
        selected = plan["selected_native_indices"]
        context = fit_prediction_context(acquire(x[training], plan), y[training], patients[training], plan, layout.target_ids)
        paid = acquire(x[test], plan)
        paid_values[test] = paid
        test_rows = np.flatnonzero(test)
        action_mask[np.ix_(test_rows, selected)] = True
        original_mask[np.ix_(test_rows, selected[:28])] = True
        paid_wells[test] = features["well_ids"][test][:, selected]
        own_mask[fold] = np.equal(np.arange(24)[:, None], np.asarray(plan["coordinate_target_indices"])[None, :])
        if not np.all(np.isin(own_mask[fold].sum(axis=1), (1, 2))) or not np.all(own_mask[fold].sum(axis=0) == 1):
            raise AssertionError("Own-drug feature ownership is not exclusive and complete")
        first.dump(directory / "plan.json", plan)
        for family in PREDICTORS:
            model = BracketingPredictor(context, plan, selections[family]["lambda"], family)
            predictions[family][test] = model.predict(paid)
            save_model(directory / f"model__{family}.npz", model, context)
        np.savez_compressed(directory / "paid_test.npz", sample_ids=data["sample_ids"][test], patient_ids=patients[test], paid_native=paid, encoded=encode_paid(paid, plan), paid_source_well_ids=paid_wells[test].astype(str), y=y[test])
        for row in test_rows:
            if len(set(paid_wells[row].ravel())) != 64:
                raise AssertionError("A paid OOF plan reuses physical treatment wells")
            old = set(np.flatnonzero(references["old_action_mask"][row]))
            new = set(selected[:28])
            overlap_rows.append({"sample_id": str(data["sample_ids"][row]), "fold": fold, "old_original_pairs": len(old), "new_original_pairs": len(new), "retained_original_pairs": len(old & new), "removed_original_pairs": len(old - new), "added_original_pairs": len(new - old), "added_missing_pairs": 4, "removed_treatment_wells": 2 * len(old - new), "added_treatment_wells": 2 * (len(new - old) + 4)})
            for local, native in enumerate(selected):
                for plate in range(2):
                    physical_rows.append({"sample_id": str(data["sample_ids"][row]), "patient_id": str(patients[row]), "fold": fold, "library_id": str(data["library_ids"][row]), "paid_native_position": local, "native_index": native, "native_id": str(layout.native_ids[native]), "drug_id": str(layout.target_ids[layout.native_target_indices[native]]), "plate": f"p{plate + 1}", "physical_well_id": str(paid_wells[row, local, plate])})
        for candidate in plan["missing_drug_candidates"]:
            plan_rows.append({"fold": fold, "drug_id": candidate["drug_id"], "q": candidate["q"], "feature_id": candidate["feature_id"], "native_ids": ";".join(candidate["native_ids"])})
        first.dump(directory / "outer_result.json", {"fold": fold, "selections": selections, "training_sample_ids": list(map(str, data["sample_ids"][training])), "test_sample_ids": list(map(str, data["sample_ids"][test])), "training_patient_ids": sorted(set(map(str, patients[training]))), "test_patient_ids": sorted(set(map(str, patients[test]))), "native_pairs": 32, "distinct_treatment_wells_per_pdo": 64, "exact_auc_count": 0})
        print(json.dumps({"event": "bracketing_outer_complete", "fold": fold}), flush=True)
    if any(not np.isfinite(p).all() for p in predictions.values()) or not np.all(action_mask.sum(axis=1) == 32) or not np.all(original_mask.sum(axis=1) == 28):
        raise AssertionError("Final predictions/acquisition mask are incomplete")
    predictions.update(references["predictions"])
    metrics, contrasts, decision, patient_rows, target_rows, fold_rows = summarize(data, predictions, folds, layout)
    np.savez_compressed(output / "oof_predictions.npz", **data, folds=folds, native_ids=layout.native_ids, native_target_indices=layout.native_target_indices, original_query_ids=layout.old_descriptor.query_ids, action_mask=action_mask, original_action_mask=original_mask, own_feature_mask=own_mask, paid_native_values=paid_values, paid_source_well_ids=paid_wells.astype(str), reference_original_action_mask=references["old_action_mask"], **predictions)
    write_csv(output / "per_patient_losses.csv", patient_rows)
    write_csv(output / "per_target_metrics.csv", target_rows)
    write_csv(output / "per_fold_metrics.csv", fold_rows)
    write_csv(output / "paid_physical_wells.csv", physical_rows)
    write_csv(output / "acquisition_overlap.csv", overlap_rows)
    write_csv(output / "selected_positions.csv", plan_rows)
    first.dump(output / "metrics.json", metrics)
    first.dump(output / "paired_patient_contrasts.json", {"contrasts": contrasts, "bootstrap_role": "descriptive repeated TRAIN-development evidence"})
    first.dump(output / "decision.json", decision)
    summary = {"completed": True, "scientific_role": "TRAIN-only repeated-development lossless bracketing procedure comparison", "n_pdo": len(y), "n_patients": len(set(patients)), "native_pairs": 32, "treatment_wells": 64, "heldout_library_used": False, "metrics": metrics, "decision": decision, "seconds": time.perf_counter() - began, "code_hashes": code_hashes(), "provenance": provenance}
    first.dump(output / "SUMMARY.json", summary)
    first.dump(output / "MANIFEST.json", {"committed": True, "files": {str(path.relative_to(output)): first.sha(path) for path in sorted(output.rglob("*")) if path.is_file()}})
    print(json.dumps({"event": "bracketing_complete", "output": str(output), "metrics": metrics, "decision": decision}), flush=True)
    return summary


def main():
    parser = argparse.ArgumentParser()
    for name in ("train", "metadata", "curves", "preparation-audit", "query-pool", "contract", "r8-controls", "r7-controls", "protocol", "freeze", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Preserve the existing scientific attempt; no overwrite")
    check_freeze(args)
    args.output.mkdir(parents=True, exist_ok=False)
    first.dump(args.output / "ATTEMPT_STARTED.json", {"unix_time": time.time(), "freeze_sha256": first.sha(args.freeze), "protocol_sha256": first.sha(args.protocol), "code_hashes": code_hashes(), "status": "reserved_before_numerical_loading", "input_sha256": INPUT_HASHES})
    try:
        data, metadata = first.load_train(args.train, args.metadata)
        if data["y"].shape != (119, 24) or len(set(data["patient_ids"])) != 59:
            raise ValueError("Scientific cohort differs from the frozen 119-PDO/59-patient contract")
        features = load_bracketing_features(data, metadata, args.train, args.curves, args.preparation_audit, args.query_pool, args.contract)
        references = load_references(data, features, args.r8_controls, args.r7_controls)
        provenance = {"input_sha256": INPUT_HASHES, "protocol_sha256": first.sha(args.protocol), "freeze_sha256": first.sha(args.freeze), "protocol_path": str(args.protocol.resolve()), "freeze_path": str(args.freeze.resolve())}
        with threadpool_limits(limits=1):
            run(data, features, references, args.output, provenance, attempt_reserved=True)
    except Exception as exc:
        first.dump(args.output / "FAILURE.json", {"failed": True, "exception_type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc(), "preserve_attempt": True, "code_hashes": code_hashes()})
        raise


if __name__ == "__main__":
    main()
