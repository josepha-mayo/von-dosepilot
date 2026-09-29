#!/usr/bin/env python3
"""TRAIN-only matched-observation mechanism comparison.

The broad allocation is regenerated with planning alpha 0.1 inside every
inner-training and outer-training split.  Shared and own-drug predictors see
the identical 32 paid native-action means and tune four prediction penalties
independently.  This file does not authorize a scientific run: the caller must
provide and hash-check a separately frozen protocol.
"""
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
from threadpoolctl import threadpool_limits

import evaluate as first
import evaluate_sparse as sparse_eval
from mechanism_methods import (
    ALLOCATION_ALPHA,
    PREDICTION_LAMBDAS,
    OwnDrugRidgePredictor,
    SharedRidgePredictor,
    broad_panel,
    fit_context,
    hybrid_prediction,
)
from methods import patient_folds, per_patient_loss


QUERY_POOL_SHA256 = "536ece2d552740671a5a44f16c948b8ddc4ca6330be1f9b3c4f11398491a3aab"
SPARSE_REFERENCE_MANIFEST_SHA256 = "48e3401d780064fdf3b14e34b3da0feaf5e853dceecb411832a39119285985e5"
FROZEN_CODE_HASHES = {
    "methods.py": "6fc6909ab92057aa8715383f0001f4bcaa14df85d0e897ed8900f88efb1aaf5f",
    "evaluate.py": "24593a7d8608fd3ce98c367e1760af596b3b33554c1ef7a3f8ac645b046b700b",
    "sparse_methods.py": "511ea1665a7f245cd3a2923fd8a6be6f5c2e45ba901da1620f7298a4125ec64c",
    "evaluate_sparse.py": "f07954779744fc8fdcaddac1f2413ef8ceb7e5e9d27c407bc1f425e96e599ada",
}
SELECTORS = ("shared_all24", "shared_22", "own_drug_22")


def code_hashes():
    folder = Path(__file__).resolve().parent
    names = (*FROZEN_CODE_HASHES, "mechanism_methods.py", "evaluate_mechanism.py")
    return {name: first.sha(folder / name) for name in names}


def assert_frozen_sources(protocol_path, protocol_sha256):
    folder = Path(__file__).resolve().parent
    for name, expected in FROZEN_CODE_HASHES.items():
        if first.sha(folder / name) != expected:
            raise ValueError("Prior frozen implementation changed: " + name)
    if first.sha(protocol_path) != protocol_sha256:
        raise ValueError("Mechanism protocol does not match its issued freeze hash")


def load_sparse_reference(data, features, directory):
    directory = Path(directory)
    manifest = sparse_eval.verify_manifest(
        directory, SPARSE_REFERENCE_MANIFEST_SHA256
    )
    summary = json.loads((directory / "SUMMARY.json").read_text())
    started = json.loads((directory / "STARTED.json").read_text())
    if (
        not summary.get("completed")
        or summary.get("heldout_library_used") is not False
        or summary.get("code_hashes", {}).get("sparse_methods.py")
        != FROZEN_CODE_HASHES["sparse_methods.py"]
        or summary.get("code_hashes", {}).get("evaluate_sparse.py")
        != FROZEN_CODE_HASHES["evaluate_sparse.py"]
        or started.get("families") != list(sparse_eval.ALLOCATION_FAMILIES)
        or float(started.get("treatment_wells", -1)) != 64
    ):
        raise ValueError("Round-seven sparse reference is not the frozen completed run")
    with np.load(directory / "oof_predictions.npz", allow_pickle=False) as saved:
        for key in ("y", "sample_ids", "patient_ids", "drug_ids", "library_ids"):
            if not np.array_equal(saved[key], data[key]):
                raise ValueError("Sparse reference identity differs: " + key)
        if not np.array_equal(saved["query_ids"], features["descriptor"].query_ids):
            raise ValueError("Sparse reference query identity differs")
        prediction = np.asarray(saved["sparse__broad_drugwise"], dtype=float)
        action_mask = np.asarray(
            saved["sparse__broad_drugwise__action_mask"], dtype=bool
        )
        folds = np.asarray(saved["folds"], dtype=int)
    if (
        prediction.shape != data["y"].shape
        or action_mask.shape != features["x"].shape
        or not np.isfinite(prediction).all()
        or not np.all(action_mask.sum(axis=1) == 32)
    ):
        raise ValueError("Sparse reference prediction or action mask is malformed")
    for fold in range(5):
        outer = json.loads(
            (directory / f"outer_{fold:02d}" / "outer_result.json").read_text()
        )
        result = outer["results"]["sparse__broad_drugwise"]
        if float(result["lambda"]) != ALLOCATION_ALPHA:
            raise ValueError("Round-seven broad panel did not select alpha 0.1")
    return {
        "prediction": prediction,
        "action_mask": action_mask,
        "folds": folds,
        "provenance": {
            "manifest_sha256": SPARSE_REFERENCE_MANIFEST_SHA256,
            "oof_predictions_sha256": manifest["files"]["oof_predictions.npz"],
            "role": "immutable_round7_broad_reference",
        },
    }


def _patient_loss(y, prediction, patients, targets=None):
    if targets is not None:
        y = y[:, targets]
        prediction = prediction[:, targets]
    return per_patient_loss(y, prediction, patients)[1]


def select_prediction_lambdas(
    x,
    y,
    patients,
    descriptor,
    n_splits,
    salt,
    directory,
):
    directory = Path(directory)
    directory.mkdir()
    folds, assignment = patient_folds(patients, n_splits, salt)
    first.dump(directory / "patient_folds.json", assignment)
    queryable = np.flatnonzero(
        np.bincount(
            descriptor.query_target_indices,
            minlength=len(descriptor.target_ids),
        )
    )
    totals = {
        (selector, lam): [0.0, 0]
        for selector in SELECTORS
        for lam in PREDICTION_LAMBDAS
    }
    for fold in range(n_splits):
        training, validation = folds != fold, folds == fold
        context = fit_context(x[training], y[training], patients[training], descriptor)
        selected, plan = broad_panel(context, descriptor)
        observed = x[validation][:, selected]
        record = {
            "fold": fold,
            "training_patients": len(set(patients[training])),
            "validation_patients": len(set(patients[validation])),
            "allocation_alpha": ALLOCATION_ALPHA,
            "plan": plan,
            "results": [],
        }
        for lam in PREDICTION_LAMBDAS:
            shared = SharedRidgePredictor(context, selected, lam, descriptor).predict(
                observed
            )
            own_model = OwnDrugRidgePredictor(context, selected, lam, descriptor)
            own = own_model.predict(observed)
            shared_all24_loss = _patient_loss(
                y[validation], shared, patients[validation]
            )
            shared_22_loss = _patient_loss(
                y[validation], shared, patients[validation], queryable
            )
            own_loss = per_patient_loss(
                y[validation][:, queryable], own, patients[validation]
            )[1]
            validation_patient_ids = per_patient_loss(
                y[validation], shared, patients[validation]
            )[0]
            for selector, losses in (
                ("shared_all24", shared_all24_loss),
                ("shared_22", shared_22_loss),
                ("own_drug_22", own_loss),
            ):
                totals[selector, lam][0] += float(losses.sum())
                totals[selector, lam][1] += len(losses)
            record["results"].append(
                {
                    "prediction_lambda": lam,
                    "shared_all24_patient_loss_sum": float(shared_all24_loss.sum()),
                    "shared_22_target_patient_loss_sum": float(shared_22_loss.sum()),
                    "shared_patient_count": len(shared_all24_loss),
                    "own_drug_22_target_patient_loss_sum": float(own_loss.sum()),
                    "own_drug_patient_count": len(own_loss),
                    "validation_patient_ids": list(map(str, validation_patient_ids)),
                    "shared_all24_patient_losses": list(map(float, shared_all24_loss)),
                    "shared_22_target_patient_losses": list(map(float, shared_22_loss)),
                    "own_drug_22_target_patient_losses": list(map(float, own_loss)),
                }
            )
        first.dump(directory / f"inner_{fold:02d}.json", record)

    selections = {}
    for selector in SELECTORS:
        score, index, lam = min(
            (
                totals[selector, lam][0] / totals[selector, lam][1],
                index,
                lam,
            )
            for index, lam in enumerate(PREDICTION_LAMBDAS)
        )
        selections[selector] = {
            "prediction_lambda": lam,
            "lambda_index": index,
            "inner_patient_mse": score,
            "selection_scope": "all24"
            if selector == "shared_all24"
            else "queryable22",
        }
    first.dump(
        directory / "selection.json",
        {
            "selections": selections,
            "allocation_alpha": ALLOCATION_ALPHA,
            "allocation_regenerated_per_inner_training_fold": True,
            "pooled_patient_count": len(set(patients)),
            "selectors": SELECTORS,
            "prediction_configurations_per_selector": len(PREDICTION_LAMBDAS),
            "total_selector_lambda_scores": len(SELECTORS)
            * len(PREDICTION_LAMBDAS),
            "joint_lambda_cross_product_searched": False,
        },
    )
    return selections


def _metrics(y, prediction, patients, targets=None):
    losses = _patient_loss(y, prediction, patients, targets)
    if targets is None:
        absolute = per_patient_loss(y, prediction, patients, absolute=True)[1]
    else:
        absolute = per_patient_loss(
            y[:, targets], prediction[:, targets], patients, absolute=True
        )[1]
    return {
        "mse": float(losses.mean()),
        "rmse": float(np.sqrt(losses.mean())),
        "mae": float(absolute.mean()),
        "patient_count": len(losses),
        "target_count": y.shape[1] if targets is None else len(targets),
        "treatment_wells_per_pdo": 64,
    }


def _per_target_metrics(y, prediction, patients, target_ids):
    records = []
    patient_order = sorted(set(map(str, patients)))
    for target, target_id in enumerate(target_ids):
        squared = (prediction[:, target] - y[:, target]) ** 2
        absolute = np.abs(prediction[:, target] - y[:, target])
        patient_mse = np.asarray(
            [squared[patients == patient].mean() for patient in patient_order]
        )
        patient_mae = np.asarray(
            [absolute[patients == patient].mean() for patient in patient_order]
        )
        records.append(
            {
                "target_index": target,
                "target_id": str(target_id),
                "patient_balanced_mse": float(patient_mse.mean()),
                "patient_balanced_rmse": float(np.sqrt(patient_mse.mean())),
                "patient_balanced_mae": float(patient_mae.mean()),
            }
        )
    return records


def _contrast_summary(candidate_losses, reference_losses, patient_ids, folds):
    patient_ids = np.asarray(patient_ids, dtype=str)
    delta = np.asarray(candidate_losses) - np.asarray(reference_losses)
    fold_by_patient = {
        patient: int(np.unique(folds[patient_ids == patient])[0])
        for patient in sorted(set(patient_ids))
    }
    ordered = np.asarray(sorted(fold_by_patient), dtype=str)
    if len(delta) != len(ordered):
        raise ValueError("Patient contrast and identity count differ")

    def summarize(values):
        tolerance = 1e-15
        return {
            "patient_count": len(values),
            "mean_delta": float(np.mean(values)),
            "median_delta": float(np.median(values)),
            "candidate_wins": int(np.sum(values < -tolerance)),
            "reference_wins": int(np.sum(values > tolerance)),
            "ties": int(np.sum(np.abs(values) <= tolerance)),
        }

    fold_records = []
    for fold in sorted(set(fold_by_patient.values())):
        mask = np.asarray([fold_by_patient[patient] == fold for patient in ordered])
        fold_records.append({"fold": fold, **summarize(delta[mask])})
    return {
        "overall": summarize(delta),
        "folds": fold_records,
        "patient_ids": list(map(str, ordered)),
        "patient_deltas": list(map(float, delta)),
    }


def run(
    data,
    features,
    reference,
    output,
    metadata,
    input_manifest,
    protocol_path,
    protocol_sha256,
    outer_splits=5,
    inner_splits=3,
):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    began = time.perf_counter()
    descriptor = features["descriptor"]
    x, y, patients = features["x"], data["y"], data["patient_ids"]
    queryable = np.flatnonzero(
        np.bincount(
            descriptor.query_target_indices,
            minlength=len(descriptor.target_ids),
        )
    )
    unqueryable = np.setdiff1d(np.arange(y.shape[1]), queryable)
    if len(queryable) != 22 or len(unqueryable) != 2:
        raise ValueError("Mechanism comparison requires the frozen 22/2 target split")

    first.dump(
        output / "STARTED.json",
        {
            "unix_time": time.time(),
            "input": input_manifest,
            "metadata": metadata,
            "protocol_path": str(Path(protocol_path).resolve()),
            "protocol_sha256": protocol_sha256,
            "code_hashes": code_hashes(),
            "sparse_reference": reference["provenance"],
            "allocation_family": "broad_drugwise",
            "allocation_alpha": ALLOCATION_ALPHA,
            "prediction_lambdas": PREDICTION_LAMBDAS,
            "selectors": SELECTORS,
            "outer_splits": outer_splits,
            "inner_splits": inner_splits,
            "fold_salt": first.SALT,
            "paired_actions": 32,
            "treatment_wells": 64,
            "versions": {
                "python": platform.python_version(),
                "numpy": np.__version__,
                "scipy": scipy.__version__,
            },
        },
    )
    folds, assignment = patient_folds(patients, outer_splits, first.SALT + "|outer")
    if not np.array_equal(folds, reference["folds"]):
        raise ValueError("Round-seven reference used different outer patient folds")
    first.dump(output / "outer_patient_folds.json", assignment)

    shared_all24_oof = np.full_like(y, np.nan)
    shared22_hybrid_oof = np.full_like(y, np.nan)
    own_hybrid_oof = np.full_like(y, np.nan)
    shared22_oof = np.full((len(y), len(queryable)), np.nan)
    own_oof = np.full((len(y), len(queryable)), np.nan)
    action_mask = np.zeros_like(x, dtype=bool)
    outer_action_mask = np.zeros((outer_splits, x.shape[1]), dtype=bool)
    own_feature_mask = np.zeros(
        (outer_splits, len(queryable), x.shape[1]), dtype=bool
    )
    rows_table = []
    for fold in range(outer_splits):
        training, test = folds != fold, folds == fold
        directory = output / f"outer_{fold:02d}"
        directory.mkdir()
        selections = select_prediction_lambdas(
            x[training],
            y[training],
            patients[training],
            descriptor,
            inner_splits,
            first.SALT + f"|inner|{fold}",
            directory / "selection",
        )
        context = fit_context(x[training], y[training], patients[training], descriptor)
        selected, plan = broad_panel(context, descriptor)
        test_rows = np.flatnonzero(test)
        action_mask[np.ix_(test_rows, selected)] = True
        outer_action_mask[fold, list(selected)] = True
        for own_column, target in enumerate(queryable):
            own_actions = [
                query
                for query in selected
                if descriptor.query_target_indices[query] == target
            ]
            if len(own_actions) not in (1, 2):
                raise AssertionError("Own-feature mask must contain one or two actions")
            own_feature_mask[fold, own_column, own_actions] = True
        if not np.array_equal(
            own_feature_mask[fold].any(axis=0), outer_action_mask[fold]
        ):
            raise AssertionError("Own-feature masks do not union to the paid panel")
        if not np.array_equal(
            action_mask[test], reference["action_mask"][test]
        ):
            raise AssertionError(
                "Fixed-alpha panel does not reproduce the immutable round-seven broad panel"
            )
        if any(
            len(set(features["well_ids"][row, selected].ravel())) != 64
            for row in test_rows
        ):
            raise AssertionError("A mechanism test panel does not buy 64 distinct wells")

        observed = x[test][:, selected]
        shared_all24_model = SharedRidgePredictor(
            context,
            selected,
            selections["shared_all24"]["prediction_lambda"],
            descriptor,
        )
        shared22_model = SharedRidgePredictor(
            context,
            selected,
            selections["shared_22"]["prediction_lambda"],
            descriptor,
        )
        own_model = OwnDrugRidgePredictor(
            context,
            selected,
            selections["own_drug_22"]["prediction_lambda"],
            descriptor,
        )
        if (
            shared_all24_model.exact_target_mask.any()
            or shared22_model.exact_target_mask.any()
        ):
            raise AssertionError("Broad mechanism panel unexpectedly reconstructs an exact AUC")
        shared_all24 = shared_all24_model.predict(observed)
        shared22_full = shared22_model.predict(observed)
        shared22 = shared22_full[:, queryable]
        own = own_model.predict(observed)
        if not np.array_equal(own_model.target_indices, queryable):
            raise AssertionError("Own-drug target order changed")
        shared22_hybrid = hybrid_prediction(shared_all24, shared22, queryable)
        own_hybrid = hybrid_prediction(shared_all24, own, queryable)
        shared_all24_oof[test] = shared_all24
        shared22_oof[test] = shared22
        own_oof[test] = own
        shared22_hybrid_oof[test] = shared22_hybrid
        own_hybrid_oof[test] = own_hybrid
        first.dump(
            directory / "outer_result.json",
            {
                "fold": fold,
                "selections": selections,
                "plan": plan,
                "reference_action_mask_exact_match": True,
                "distinct_physical_treatment_wells_per_pdo": 64,
                "shared_all24_exact_target_count": int(
                    shared_all24_model.exact_target_mask.sum()
                ),
                "shared22_exact_target_count": int(
                    shared22_model.exact_target_mask.sum()
                ),
            },
        )

    if (
        not np.isfinite(shared_all24_oof).all()
        or not np.isfinite(shared22_oof).all()
        or not np.isfinite(own_oof).all()
        or not np.isfinite(shared22_hybrid_oof).all()
        or not np.isfinite(own_hybrid_oof).all()
        or not np.all(action_mask.sum(axis=1) == 32)
    ):
        raise AssertionError("Mechanism OOF result is incomplete")
    if not np.all(np.isin(own_feature_mask.sum(axis=2), (1, 2))):
        raise AssertionError("Saved own-feature masks violate one/two-action support")
    if not np.all(outer_action_mask.sum(axis=1) == 32):
        raise AssertionError("Saved outer panels do not contain 32 actions")
    if not np.array_equal(own_feature_mask.any(axis=1), outer_action_mask):
        raise AssertionError("Saved own-feature masks do not reconstruct outer panels")
    if not np.array_equal(
        shared22_hybrid_oof[:, unqueryable],
        shared_all24_oof[:, unqueryable],
    ) or not np.array_equal(
        own_hybrid_oof[:, unqueryable], shared_all24_oof[:, unqueryable]
    ):
        raise AssertionError("Clean hybrids do not share identical unqueryable outputs")
    if not np.array_equal(shared22_hybrid_oof[:, queryable], shared22_oof):
        raise AssertionError("Shared-22 hybrid queried columns changed")
    if not np.array_equal(own_hybrid_oof[:, queryable], own_oof):
        raise AssertionError("Own-drug hybrid queried columns changed")

    clean_shared22 = _patient_loss(y, shared22_hybrid_oof, patients, queryable)
    clean_own22 = _patient_loss(y, own_hybrid_oof, patients, queryable)
    clean_shared24 = _patient_loss(y, shared22_hybrid_oof, patients)
    clean_own24 = _patient_loss(y, own_hybrid_oof, patients)
    if not np.allclose(
        clean_own24 - clean_shared24,
        (22.0 / 24.0) * (clean_own22 - clean_shared22),
        rtol=0,
        atol=2e-16,
    ):
        raise AssertionError("Full-24 and queried-22 paired differences disagree")

    names = {
        "shared_all24": shared_all24_oof,
        "hybrid_shared22": shared22_hybrid_oof,
        "hybrid_drugwise22": own_hybrid_oof,
        "reference_round7_broad": reference["prediction"],
    }
    metrics = {
        name: {
            "full24": _metrics(y, prediction, patients),
            "queryable22": _metrics(y, prediction, patients, queryable),
        }
        for name, prediction in names.items()
    }
    patient_ids = per_patient_loss(y, shared_all24_oof, patients)[0]
    losses = {
        name: _patient_loss(y, prediction, patients) for name, prediction in names.items()
    }
    losses22 = {
        name: _patient_loss(y, prediction, patients, queryable)
        for name, prediction in names.items()
    }
    for name in names:
        rows_table.extend(
            {
                "method": name,
                "patient_id": str(patient),
                "full24_mse": float(loss24),
                "queryable22_mse": float(loss22),
            }
            for patient, loss24, loss22 in zip(
                patient_ids, losses[name], losses22[name]
            )
        )
    contrasts = {
        "own_drug_hybrid_minus_shared22_hybrid_full24": first.bootstrap_difference(
            losses["hybrid_drugwise22"],
            losses["hybrid_shared22"],
        ),
        "own_drug_minus_shared22_queryable22": first.bootstrap_difference(
            losses22["hybrid_drugwise22"],
            losses22["hybrid_shared22"],
        ),
        "shared_all24_minus_round7_broad_full24": first.bootstrap_difference(
            losses["shared_all24"],
            losses["reference_round7_broad"],
        ),
        "own_drug_hybrid_minus_shared_all24_full24": first.bootstrap_difference(
            losses["hybrid_drugwise22"],
            losses["shared_all24"],
        ),
    }
    contrast_summaries = {
        "own_drug_hybrid_minus_shared22_hybrid_full24": _contrast_summary(
            losses["hybrid_drugwise22"],
            losses["hybrid_shared22"],
            patients,
            folds,
        ),
        "own_drug_minus_shared22_queryable22": _contrast_summary(
            losses22["hybrid_drugwise22"],
            losses22["hybrid_shared22"],
            patients,
            folds,
        ),
        "own_drug_hybrid_minus_shared_all24_full24": _contrast_summary(
            losses["hybrid_drugwise22"],
            losses["shared_all24"],
            patients,
            folds,
        ),
        "shared_all24_minus_round7_broad_full24": _contrast_summary(
            losses["shared_all24"],
            losses["reference_round7_broad"],
            patients,
            folds,
        ),
    }
    identity_residual = (clean_own24 - clean_shared24) - (
        22.0 / 24.0
    ) * (clean_own22 - clean_shared22)
    contrast_summaries["clean_contrast_scale_identity"] = {
        "maximum_absolute_patient_residual": float(np.max(np.abs(identity_residual))),
        "all_patients_within_2e_minus_16": bool(
            np.all(np.abs(identity_residual) <= 2e-16)
        ),
    }
    np.savez_compressed(
        output / "oof_predictions.npz",
        y=y,
        sample_ids=data["sample_ids"],
        patient_ids=patients,
        drug_ids=data["drug_ids"],
        library_ids=data["library_ids"],
        query_ids=descriptor.query_ids,
        queryable_target_indices=queryable,
        unqueryable_target_indices=unqueryable,
        folds=folds,
        action_mask=action_mask,
        outer_action_mask=outer_action_mask,
        own_feature_mask=own_feature_mask,
        shared_all24=shared_all24_oof,
        shared22_queryable=shared22_oof,
        hybrid_shared22=shared22_hybrid_oof,
        drugwise22_queryable=own_oof,
        hybrid_drugwise22=own_hybrid_oof,
        reference_round7_broad=reference["prediction"],
    )
    with (output / "per_patient_losses.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("method", "patient_id", "full24_mse", "queryable22_mse"),
        )
        writer.writeheader()
        writer.writerows(rows_table)
    first.dump(output / "metrics.json", metrics)
    first.dump(
        output / "per_target_metrics.json",
        {
            name: _per_target_metrics(y, prediction, patients, data["drug_ids"])
            for name, prediction in names.items()
        },
    )
    first.dump(output / "contrast_summaries.json", contrast_summaries)
    first.dump(
        output / "paired_patient_contrasts.json",
        {
            "contrasts": contrasts,
            "full24_delta_equals_22_over_24_times_queryable22_delta": True,
            "bootstrap_role": "descriptive TRAIN-only repeated-development interval",
        },
    )
    summary = {
        "completed": True,
        "scientific_role": "TRAIN-only identical-observation cross-drug mechanism comparison",
        "n_pdo": len(y),
        "n_patients": len(set(patients)),
        "n_targets": y.shape[1],
        "queryable_targets": len(queryable),
        "paired_actions": 32,
        "treatment_wells": 64,
        "heldout_library_used": False,
        "allocation_alpha": ALLOCATION_ALPHA,
        "selectors": SELECTORS,
        "metrics": metrics,
        "contrasts": contrasts,
        "seconds": time.perf_counter() - began,
        "code_hashes": code_hashes(),
        "protocol_sha256": protocol_sha256,
        "input": input_manifest,
    }
    first.dump(output / "SUMMARY.json", summary)
    first.dump(
        output / "MANIFEST.json",
        {
            "committed": True,
            "files": {
                str(path.relative_to(output)): first.sha(path)
                for path in sorted(output.rglob("*"))
                if path.is_file()
            },
        },
    )
    print(
        json.dumps(
            {
                "event": "mechanism_complete",
                "output": str(output),
                "seconds": summary["seconds"],
                "metrics": metrics,
            }
        ),
        flush=True,
    )
    return summary


def main():
    parser = argparse.ArgumentParser()
    for name in (
        "train",
        "metadata",
        "curves",
        "preparation-audit",
        "query-pool",
        "sparse-controls",
        "protocol",
        "output",
    ):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--protocol-sha256", required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Preserve the existing scientific attempt")
    assert_frozen_sources(args.protocol, args.protocol_sha256)
    data, metadata = first.load_train(args.train, args.metadata)
    features = sparse_eval.load_sparse_features(
        data,
        metadata,
        args.train,
        args.curves,
        args.preparation_audit,
        args.query_pool,
        QUERY_POOL_SHA256,
    )
    if (
        data["y"].shape[1] != 24
        or features["x"].shape[1] != 150
        or len(set(features["descriptor"].query_target_indices)) != 22
        or set(data["library_ids"]) != {"lib1"}
    ):
        raise ValueError("Scientific data differ from the frozen 24/150/22 Lib1 contract")
    input_manifest = {
        "npz_path": str(args.train.resolve()),
        "npz_sha256": first.sha(args.train),
        "metadata_path": str(args.metadata.resolve()),
        "metadata_sha256": first.sha(args.metadata),
        "curve_csv_path": str(args.curves.resolve()),
        "curve_csv_sha256": first.sha(args.curves),
        "query_pool_path": str(args.query_pool.resolve()),
        "query_pool_sha256": QUERY_POOL_SHA256,
        "preparation_audit_sha256": first.sha(args.preparation_audit),
    }
    reference = load_sparse_reference(data, features, args.sparse_controls)
    with threadpool_limits(limits=1):
        run(
            data,
            features,
            reference,
            args.output,
            metadata,
            input_manifest,
            args.protocol,
            args.protocol_sha256,
        )


if __name__ == "__main__":
    main()
