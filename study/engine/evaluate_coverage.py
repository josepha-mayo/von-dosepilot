#!/usr/bin/env python3
"""One frozen TRAIN-only 64-single-well comparison against immutable R9 OOF."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import signal
import time
import traceback

for _name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_name] = "1"

import numpy as np
from threadpoolctl import threadpool_limits

import evaluate as first
import evaluate_sparse as sparse_eval
import evaluate_bracketing as bracket_eval
from methods import patient_folds, patient_weights
from sparse_methods import LAMBDAS
from coverage_scoring import PROMOTION_GATE, summarize
from coverage_methods import ALLOCATION_ALPHA, ORIENTATIONS, CoveragePredictor, PairedNativePredictor, acquire, acquire_paired, catalog_from_features, fit_prediction_context, fit_paired_prediction_context, orientation_errors, plan_panel, plan_paired_panel


R9_MANIFEST_SHA256 = "def3fe8a0c87fc32aac0b5ae3585678daa28688651a14914149d7747ebb2d9c7"
R9_MSE = 0.0017214230057830812
INPUT_HASHES = dict(bracket_eval.INPUT_HASHES)
FROZEN_CODE_HASHES = {**sparse_eval.PRIOR_CODE_HASHES, **bracket_eval.FROZEN_CODE_HASHES, "bracketing_methods.py": "1b58f1c8af86117876bd08c900b6f73ae951506aad06cae6c5834168dd7e4eae", "evaluate_bracketing.py": "e47374a29c8af9d47b1880d308dd08959386a8b07a25030499f49a09379ea582"}
NEW_CODE = ("coverage_methods.py", "coverage_scoring.py", "evaluate_coverage.py", "synthetic_coverage_preflight.py", "synthetic_coverage_scoring.py")



def code_hashes():
    folder = Path(__file__).resolve().parent
    return {name: first.sha(folder / name) for name in (*FROZEN_CODE_HASHES, *NEW_CODE)}


def check_freeze(args):
    freeze = json.loads(args.freeze.read_text())
    if freeze.get("authorization") != "exactly one TRAIN-only single-well coverage run":
        raise ValueError("Root authorization for exactly one coverage attempt is missing")
    if freeze.get("protocol_sha256") != first.sha(args.protocol) or freeze.get("promotion_gate") != PROMOTION_GATE:
        raise ValueError("Protocol or promotion gate differs from root freeze")
    actual = code_hashes()
    for name, expected in FROZEN_CODE_HASHES.items():
        if actual[name] != expected:
            raise ValueError("Prior frozen implementation changed: " + name)
    for name in NEW_CODE:
        if freeze.get("code", {}).get(name) != actual[name]:
            raise ValueError("Coverage implementation changed after root freeze: " + name)
    for name, expected in INPUT_HASHES.items():
        if first.sha(getattr(args, name)) != expected or freeze.get("input_sha256", {}).get(name) != expected:
            raise ValueError("Scientific input differs from the fixed TRAIN release: " + name)
    if freeze.get("r9_reference_manifest_sha256") != R9_MANIFEST_SHA256:
        raise ValueError("Incumbent identity changed")
    project = Path(__file__).resolve().parents[2]
    if (project / freeze.get("attempt", "MISSING")).resolve() != args.output.resolve():
        raise ValueError("Output differs from the one authorized attempt")
    return freeze


def patient_errors(cell_errors, patients):
    patients = np.asarray(patients, dtype=str)
    ids = np.asarray(sorted(set(patients)), dtype=str)
    return ids, np.asarray([cell_errors[patients == pid].mean(axis=0) for pid in ids])


def load_reference(data, features, directory):
    manifest = sparse_eval.verify_manifest(directory, R9_MANIFEST_SHA256)
    directory = Path(directory)
    summary = json.loads((directory / "SUMMARY.json").read_text())
    if summary.get("completed") is not True or summary.get("heldout_library_used") is not False or summary.get("treatment_wells") != 64:
        raise ValueError("Incumbent is not the completed TRAIN-only 64-well R9 run")
    with np.load(directory / "oof_predictions.npz", allow_pickle=False) as source:
        for key in ("y", "sample_ids", "patient_ids", "drug_ids", "library_ids"):
            if not np.array_equal(source[key], data[key]):
                raise ValueError("R9 reference identity mismatch: " + key)
        if not np.array_equal(source["native_ids"], features["layout"].native_ids):
            raise ValueError("Candidate native universe differs from R9")
        prediction, folds = source["own_drug_all24"].copy(), source["folds"].copy()
        wells = source["paid_source_well_ids"].copy()
        action_mask = source["action_mask"].copy()
    if prediction.shape != data["y"].shape or not np.isfinite(prediction).all() or not np.all(action_mask.sum(axis=1) == 32) or wells.shape != (119, 32, 2) or any(len(set(row.ravel())) != 64 for row in wells):
        raise ValueError("R9 prediction or paid-well ledger changed")
    mse = patient_errors((prediction - data["y"]) ** 2, data["patient_ids"])[1].mean()
    if not np.isclose(mse, R9_MSE, rtol=0, atol=2e-18):
        raise ValueError("R9 reference MSE does not reproduce")
    return {"prediction": prediction, "folds": folds, "well_ids": wells, "action_mask": action_mask, "provenance": {"manifest_sha256": R9_MANIFEST_SHA256, "oof_sha256": manifest["files"]["oof_predictions.npz"], "reference_refit": False, "reference_mse": float(mse)}}


def save_model(path, model, context):
    np.savez_compressed(path, **model.arrays(), cxx=context.cxx, cxy=context.cxy, cyy=context.cyy, training_row_weights=context.weights)


def select_lambda(x, y, patients, samples, catalog, directory, salt, splits=3):
    directory = Path(directory)
    directory.mkdir()
    folds, assignments = patient_folds(patients, splits, salt)
    first.dump(directory / "patient_folds.json", assignments)
    oof = {(orientation, index): np.full_like(y, np.nan) for orientation in ORIENTATIONS for index in range(len(LAMBDAS))}
    paired_oof = {index: np.full_like(y, np.nan) for index in range(len(LAMBDAS))}
    for fold in range(splits):
        training, validation = folds != fold, folds == fold
        if set(patients[training]) & set(patients[validation]):
            raise AssertionError("An inner whole patient crosses its split")
        plan = plan_panel(x[training], y[training], patients[training], catalog)
        fit_a, fit_b = (acquire(x[training], plan, orientation) for orientation in ORIENTATIONS)
        context = fit_prediction_context(fit_a, fit_b, y[training], patients[training], plan, catalog.target_ids)
        paid = {orientation: acquire(x[validation], plan, orientation) for orientation in ORIENTATIONS}
        paired_plan = plan_paired_panel(x[training], y[training], patients[training], catalog)
        paired_context = fit_paired_prediction_context(acquire_paired(x[training], paired_plan), y[training], patients[training], paired_plan, catalog.target_ids)
        paired_paid = acquire_paired(x[validation], paired_plan)
        inner = directory / f"inner_{fold:02d}"
        inner.mkdir()
        first.dump(inner / "plan.json", plan)
        first.dump(inner / "paired_plan.json", paired_plan)
        np.savez_compressed(inner / "paid_validation.npz", sample_ids=samples[validation], patient_ids=patients[validation], paid_A=paid["A"], paid_B=paid["B"], paid_matched_paired=paired_paid, y=y[validation])
        scores = []
        for index, lam in enumerate(LAMBDAS):
            model = CoveragePredictor(context, plan, lam)
            a, b = (model.predict(paid[orientation]) for orientation in ORIENTATIONS)
            oof["A", index][validation], oof["B", index][validation] = a, b
            ids, per_target = patient_errors(orientation_errors(y[validation], a, b), patients[validation])
            losses = per_target.mean(axis=1)
            scores.append({"family": "single64", "lambda_index": index, "lambda": lam, "patient_ids": list(ids), "patient_expected_losses": losses.tolist(), "mean_expected_mse": float(losses.mean())})
            save_model(inner / f"model__lambda_{index}.npz", model, context)
            paired_model = PairedNativePredictor(paired_context, paired_plan, lam)
            paired_prediction = paired_model.predict(paired_paid)
            paired_oof[index][validation] = paired_prediction
            paired_ids, paired_target_losses = patient_errors((paired_prediction - y[validation]) ** 2, patients[validation])
            paired_losses = paired_target_losses.mean(axis=1)
            scores.append({"family": "matched_paired_native", "lambda_index": index, "lambda": lam, "patient_ids": list(paired_ids), "patient_expected_losses": paired_losses.tolist(), "mean_expected_mse": float(paired_losses.mean())})
            save_model(inner / f"paired_model__lambda_{index}.npz", paired_model, paired_context)
        first.dump(inner / "scores.json", {"training_sample_ids": list(samples[training]), "validation_sample_ids": list(samples[validation]), "training_patient_ids": sorted(set(patients[training])), "validation_patient_ids": sorted(set(patients[validation])), "results": scores})
    all_scores, options = [], []
    for index, lam in enumerate(LAMBDAS):
        a, b = oof["A", index], oof["B", index]
        if not np.isfinite(a).all() or not np.isfinite(b).all():
            raise AssertionError("Inner orientations do not cover all training rows")
        ids, per_target = patient_errors(orientation_errors(y, a, b), patients)
        losses = per_target.mean(axis=1)
        score = float(losses.mean())
        all_scores.append({"lambda_index": index, "lambda": lam, "mean_expected_mse": score, "patient_ids": list(ids), "patient_expected_losses": losses.tolist()})
        options.append((score, index, lam))
    score, index, lam = min(options)
    paired_scores, paired_options = [], []
    for paired_index, paired_lam in enumerate(LAMBDAS):
        if not np.isfinite(paired_oof[paired_index]).all():
            raise AssertionError("Matched paired inner predictions are incomplete")
        paired_ids, paired_losses = patient_errors((paired_oof[paired_index] - y) ** 2, patients)
        paired_losses = paired_losses.mean(axis=1)
        paired_score = float(paired_losses.mean())
        paired_scores.append({"lambda_index": paired_index, "lambda": paired_lam, "mean_expected_mse": paired_score, "patient_ids": list(paired_ids), "patient_expected_losses": paired_losses.tolist()})
        paired_options.append((paired_score, paired_index, paired_lam))
    paired_score, paired_index, paired_lam = min(paired_options)
    selection = {"single64": {"lambda": lam, "lambda_index": index, "inner_expected_mse": score, "all_scores": all_scores}, "matched_paired_native": {"lambda": paired_lam, "lambda_index": paired_index, "inner_expected_mse": paired_score, "all_scores": paired_scores}, "selectors": 2, "penalties_per_independent_selector": list(LAMBDAS), "target_count": 24, "orientation_selection": False, "prediction_averaging": False, "joint_lambda_cross_product_searched": False, "allocation_regenerated_inside_each_inner_training_fold": True}
    first.dump(directory / "selection.json", selection)
    np.savez_compressed(directory / "inner_oof_predictions.npz", y=y, sample_ids=samples, patient_ids=patients, drug_ids=catalog.target_ids, folds=folds, **{f"orientation_{orientation}__lambda_{index}": values for (orientation, index), values in oof.items()}, **{f"matched_paired__lambda_{index}": values for index, values in paired_oof.items()})
    return selection


def run(data, features, reference, output, provenance, attempt_reserved=False):
    output = Path(output)
    if attempt_reserved:
        if not output.is_dir() or {path.name for path in output.iterdir()} != {"ATTEMPT_STARTED.json"}:
            raise ValueError("Reserved attempt is not pristine")
    else:
        output.mkdir(parents=True, exist_ok=False)
    began = time.perf_counter()
    x, y, patients, samples = features["x_replicates"], data["y"], data["patient_ids"], data["sample_ids"]
    catalog = catalog_from_features(features)
    folds, assignments = patient_folds(patients, 5, first.SALT + "|outer")
    if not np.array_equal(folds, reference["folds"]):
        raise ValueError("Outer patient folds differ from the frozen R9 comparator")
    first.dump(output / "STARTED.json", {"provenance": provenance, "reference": reference["provenance"], "code_hashes": code_hashes(), "unix_time": time.time(), "outer_splits": 5, "inner_splits": 3, "fold_salt": first.SALT, "allocation_alpha": ALLOCATION_ALPHA, "prediction_penalties": list(LAMBDAS), "predictor_family": "own_drug", "acquisition_procedures": ["single64", "matched_paired_native"], "independent_penalty_selectors": 2, "primary": "average of A/B losses versus both references", "deployment_wells": 64, "heldout_library_used": False, "python_version": platform.python_version(), "numpy_version": np.__version__})
    first.dump(output / "outer_patient_folds.json", assignments)
    first.dump(output / "feature_audit.json", {**features["audit"], "native_ids": list(catalog.native_ids), "native_target_indices": catalog.native_target_indices.tolist(), "native_concentrations_nM": list(catalog.concentrations), "response_unit": "supplied unclipped normalized viability per one physical well", "no_source_reparse": True})
    predictions = {orientation: np.full_like(y, np.nan) for orientation in ORIENTATIONS}
    predictions["matched_paired_native"] = np.full_like(y, np.nan)
    paid_values = {orientation: np.full((len(y), 64), np.nan) for orientation in ORIENTATIONS}
    paid_wells = {orientation: np.full((len(y), 64), "", dtype=object) for orientation in ORIENTATIONS}
    paid_native = np.full((len(y), 64), -1, dtype=int)
    paid_plates = {orientation: np.full((len(y), 64), -1, dtype=int) for orientation in ORIENTATIONS}
    paired_values = np.full((len(y), 32), np.nan)
    paired_native = np.full((len(y), 32), -1, dtype=int)
    paired_wells = np.full((len(y), 32, 2), "", dtype=object)
    physical_rows, paired_physical_rows = [], []
    for fold in range(5):
        training, test = folds != fold, folds == fold
        if set(patients[training]) & set(patients[test]):
            raise AssertionError("Whole-patient leakage in outer split")
        directory = output / f"outer_{fold:02d}"
        directory.mkdir()
        selection = select_lambda(x[training], y[training], patients[training], samples[training], catalog, directory / "selection", first.SALT + f"|inner|{fold}")
        plan = plan_panel(x[training], y[training], patients[training], catalog)
        context = fit_prediction_context(acquire(x[training], plan, "A"), acquire(x[training], plan, "B"), y[training], patients[training], plan, catalog.target_ids)
        model = CoveragePredictor(context, plan, selection["single64"]["lambda"])
        paired_plan = plan_paired_panel(x[training], y[training], patients[training], catalog)
        paired_context = fit_paired_prediction_context(acquire_paired(x[training], paired_plan), y[training], patients[training], paired_plan, catalog.target_ids)
        paired_model = PairedNativePredictor(paired_context, paired_plan, selection["matched_paired_native"]["lambda"])
        first.dump(directory / "plan.json", plan)
        first.dump(directory / "paired_plan.json", paired_plan)
        save_model(directory / "model__own_drug.npz", model, context)
        save_model(directory / "model__matched_paired_native.npz", paired_model, paired_context)
        test_rows, native = np.flatnonzero(test), np.asarray(plan["selected_native_indices"])
        paid_native[test] = native
        for orientation in ORIENTATIONS:
            plates = np.asarray(plan[f"orientation_{orientation}_plate_indices"])
            paid = acquire(x[test], plan, orientation)
            wells = features["well_ids"][test][:, native, plates]
            predictions[orientation][test] = model.predict(paid)
            paid_values[orientation][test], paid_wells[orientation][test], paid_plates[orientation][test] = paid, wells, plates
            for row, physical in zip(test_rows, wells):
                if len(set(physical)) != 64:
                    raise AssertionError("Candidate acquisition repeats a physical treatment well")
                for position, (q, plate, well_id) in enumerate(zip(native, plates, physical)):
                    physical_rows.append({"orientation": orientation, "sample_id": str(samples[row]), "patient_id": str(patients[row]), "fold": fold, "library_id": "lib1", "paid_position": position, "native_index": int(q), "native_id": str(catalog.native_ids[q]), "target_id": str(catalog.target_ids[catalog.native_target_indices[q]]), "concentration_nM": str(catalog.concentrations[q]), "plate": f"p{plate + 1}", "physical_well_id": str(well_id)})
        paired_selected = paired_plan["selected_native_indices"]
        paired_native[test] = paired_selected
        paired_values[test] = acquire_paired(x[test], paired_plan)
        paired_wells[test] = features["well_ids"][test][:, paired_selected, :]
        predictions["matched_paired_native"][test] = paired_model.predict(paired_values[test])
        for row in test_rows:
            if len(set(paired_wells[row].ravel())) != 64:
                raise AssertionError("Matched paired acquisition repeats a physical treatment well")
            for position, q in enumerate(paired_selected):
                for plate in range(2):
                    paired_physical_rows.append({"sample_id": str(samples[row]), "patient_id": str(patients[row]), "fold": fold, "library_id": "lib1", "paid_position": position, "native_index": int(q), "native_id": str(catalog.native_ids[q]), "target_id": str(catalog.target_ids[catalog.native_target_indices[q]]), "concentration_nM": str(catalog.concentrations[q]), "plate": f"p{plate + 1}", "physical_well_id": str(paired_wells[row, position, plate])})
        np.savez_compressed(directory / "paid_test.npz", sample_ids=samples[test], patient_ids=patients[test], native_indices=paid_native[test], paid_A=paid_values["A"][test], paid_B=paid_values["B"][test], well_ids_A=paid_wells["A"][test].astype(str), well_ids_B=paid_wells["B"][test].astype(str), matched_paired_native_indices=paired_native[test], paid_matched_paired=paired_values[test], matched_paired_well_ids=paired_wells[test].astype(str), y=y[test])
        original_weights = patient_weights(patients[training])
        if not np.array_equal(context.weights[:training.sum()], original_weights / 2) or not np.array_equal(context.weights[training.sum():], original_weights / 2):
            raise AssertionError("Symmetric augmentation altered patient mass")
        if not np.array_equal(paired_context.weights, original_weights):
            raise AssertionError("Matched paired fitting changed patient mass")
        first.dump(directory / "outer_result.json", {"fold": fold, "selection": selection, "training_sample_ids": list(samples[training]), "test_sample_ids": list(samples[test]), "training_patient_ids": sorted(set(patients[training])), "test_patient_ids": sorted(set(patients[test])), "unique_native_doses_per_deployment": 64, "distinct_treatment_wells_per_deployment": 64, "alternative_orientation_union_wells": 128, "alternative_orientation_predictions_averaged": False, "augmented_patient_mass_preserved": True})
        print(json.dumps({"event": "coverage_outer_complete", "fold": fold, "single_lambda": selection["single64"]["lambda"], "matched_paired_lambda": selection["matched_paired_native"]["lambda"]}), flush=True)
    if any(not np.isfinite(value).all() for value in predictions.values()) or (paid_native < 0).any():
        raise AssertionError("OOF predictions or acquisitions are incomplete")
    metrics, contrasts, decision, patient_rows, target_rows, fold_rows = summarize(data, predictions, reference["prediction"], folds, catalog)
    np.savez_compressed(output / "oof_predictions.npz", **data, folds=folds, native_ids=catalog.native_ids, native_target_indices=catalog.native_target_indices, selected_native_indices=paid_native, prediction_A=predictions["A"], prediction_B=predictions["B"], matched_paired_native=predictions["matched_paired_native"], reference_r9_own24=reference["prediction"], paid_A=paid_values["A"], paid_B=paid_values["B"], paid_plate_indices_A=paid_plates["A"], paid_plate_indices_B=paid_plates["B"], paid_well_ids_A=paid_wells["A"].astype(str), paid_well_ids_B=paid_wells["B"].astype(str), matched_paired_native_indices=paired_native, paid_matched_paired=paired_values, matched_paired_well_ids=paired_wells.astype(str))
    for filename, rows in (("per_patient_losses.csv", patient_rows), ("per_target_metrics.csv", target_rows), ("per_fold_metrics.csv", fold_rows), ("paid_physical_wells.csv", physical_rows), ("matched_paired_physical_wells.csv", paired_physical_rows)):
        bracket_eval.write_csv(output / filename, rows)
    first.dump(output / "metrics.json", metrics)
    first.dump(output / "paired_patient_contrasts.json", {"contrasts": contrasts, "bootstrap_role": "descriptive repeated TRAIN-development evidence; not independent confirmation"})
    first.dump(output / "decision.json", decision)
    summary = {"completed": True, "scientific_role": "TRAIN-only repeated-development randomized-orientation single-well coverage procedure", "n_pdo": len(y), "n_patients": len(set(patients)), "deployment_treatment_wells": 64, "unique_native_doses": 64, "heldout_library_used": False, "prediction_averaging": False, "metrics": metrics, "decision": decision, "seconds": time.perf_counter() - began, "code_hashes": code_hashes(), "provenance": provenance}
    first.dump(output / "SUMMARY.json", summary)
    first.dump(output / "MANIFEST.json", {"committed": True, "files": {str(path.relative_to(output)): first.sha(path) for path in sorted(output.rglob("*")) if path.is_file()}})
    print(json.dumps({"event": "coverage_complete", "output": str(output), "metrics": metrics, "decision": decision}), flush=True)
    return summary


def main():
    parser = argparse.ArgumentParser()
    for name in ("train", "metadata", "curves", "preparation-audit", "query-pool", "contract", "r9-controls", "protocol", "freeze", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Preserve the first scientific attempt; no overwrite or retry")
    check_freeze(args)
    args.output.mkdir(parents=True, exist_ok=False)
    first.dump(args.output / "ATTEMPT_STARTED.json", {"unix_time": time.time(), "freeze_sha256": first.sha(args.freeze), "protocol_sha256": first.sha(args.protocol), "code_hashes": code_hashes(), "status": "reserved_before_train_numerical_loading", "input_sha256": INPUT_HASHES})
    def timeout_handler(_signal, _frame):
        raise TimeoutError("Frozen 900-second total execution limit exceeded; preserve this first attempt")
    previous_handler = signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(900)
    try:
        data, metadata = first.load_train(args.train, args.metadata)
        if data["y"].shape != (119, 24) or len(set(data["patient_ids"])) != 59:
            raise ValueError("Canonical TRAIN cohort changed")
        features = bracket_eval.load_bracketing_features(data, metadata, args.train, args.curves, args.preparation_audit, args.query_pool, args.contract)
        reference = load_reference(data, features, args.r9_controls)
        provenance = {"input_sha256": INPUT_HASHES, "protocol_sha256": first.sha(args.protocol), "freeze_sha256": first.sha(args.freeze), "protocol_path": str(args.protocol.resolve()), "freeze_path": str(args.freeze.resolve())}
        with threadpool_limits(limits=1):
            run(data, features, reference, args.output, provenance, attempt_reserved=True)
    except Exception as exc:
        first.dump(args.output / "FAILURE.json", {"failed": True, "exception_type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc(), "preserve_attempt": True, "code_hashes": code_hashes()})
        raise
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous_handler)


if __name__ == "__main__":
    main()
