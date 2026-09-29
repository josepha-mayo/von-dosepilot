"""Prospectively fixed R13 patient-balanced expected-loss scoring; no model I/O."""
from __future__ import annotations

import numpy as np


ARITHMETIC_TOLERANCE = 1e-15
BOOTSTRAP_SEED = 20260928
BOOTSTRAP_RESAMPLES = 10000
METHODS = (
    "single64_A", "single64_B", "single64_expected_loss",
    "matched_paired_native", "reference_r9_own24",
)
PRIMARY_REFERENCES = ("reference_r9_own24", "matched_paired_native")
PROMOTION_GATE = {
    "minimum_full24_relative_mse_reduction": 0.05,
    "minimum_strict_patient_wins": 40,
    "minimum_strict_fold_wins": 4,
    "p90_patient_rmse_must_not_increase": True,
    "each_orientation_full24_mse_strictly_below_each_reference": True,
    "primary_references": list(PRIMARY_REFERENCES),
    "secondary_paired_reference": "reference_r9_own24",
    "strict_win_absolute_mse_tolerance": 0.0,
    "p90_absolute_rmse_tolerance": 0.0,
    "reference_r9_mse": 0.0017214230057830812,
    "quantile_method": "linear",
    "primary_risk": "mean of complementary orientation losses; never mean predictions",
    "decision_order": ["single64_expected_loss", "matched_paired_native", "reference_r9_own24"],
}


def _patient_tables(cell_errors, patients, patient_ids):
    return np.asarray([cell_errors[patients == pid].mean(axis=0) for pid in patient_ids])


def _counts(delta):
    return {
        "patient_wins": int(np.sum(delta < 0)),
        "patient_ties": int(np.sum(delta == 0)),
        "patient_losses": int(np.sum(delta > 0)),
    }


def _bootstrap(delta, indices):
    means = delta[indices].mean(axis=1)
    return {
        "mean_mse_difference_candidate_minus_reference": float(delta.mean()),
        "bootstrap_95_interval": [float(x) for x in np.quantile(means, [0.025, 0.975], method="linear")],
        "patients": len(delta),
        "bootstrap_resamples": BOOTSTRAP_RESAMPLES,
        "seed": BOOTSTRAP_SEED,
        "generator": "PCG64",
        "quantile_method": "linear",
        "bootstrap_role": "descriptive paired whole-patient repeated-development evidence",
    }


def _gate_checks(candidate_loss, reference_loss, patient_folds, orientation_losses=None):
    """Pure decision arithmetic, also used by synthetic boundary checks."""
    candidate_loss = np.asarray(candidate_loss, dtype=float)
    reference_loss = np.asarray(reference_loss, dtype=float)
    patient_folds = np.asarray(patient_folds)
    delta = candidate_loss - reference_loss
    fold_deltas = [float(delta[patient_folds == fold].mean()) for fold in range(5)]
    candidate_p90 = float(np.quantile(np.sqrt(candidate_loss), 0.9, method="linear"))
    reference_p90 = float(np.quantile(np.sqrt(reference_loss), 0.9, method="linear"))
    checks = {
        "at_least_five_percent_full24_reduction": bool(candidate_loss.mean() <= 0.95 * reference_loss.mean()),
        "at_least_40_strict_patient_wins": bool(np.sum(delta < 0) >= 40),
        "at_least_four_strict_fold_wins": bool(sum(x < 0 for x in fold_deltas) >= 4),
        "p90_patient_rmse_not_increased": bool(candidate_p90 <= reference_p90),
    }
    if orientation_losses is not None:
        for orientation in ("A", "B"):
            checks[f"orientation_{orientation}_strictly_better_full24"] = bool(
                np.mean(orientation_losses[orientation]) - reference_loss.mean() < 0)
    return checks


def _gate_margins(candidate_loss, reference_loss, patient_folds, orientation_losses=None):
    delta = candidate_loss - reference_loss
    fold_deltas = [float(delta[patient_folds == fold].mean()) for fold in range(5)]
    candidate_p90 = float(np.quantile(np.sqrt(candidate_loss), 0.9, method="linear"))
    reference_p90 = float(np.quantile(np.sqrt(reference_loss), 0.9, method="linear"))
    values = {
        "candidate_mse": float(candidate_loss.mean()), "reference_mse": float(reference_loss.mean()),
        "candidate_minus_95_percent_reference_mse": float(candidate_loss.mean() - 0.95 * reference_loss.mean()),
        "strict_patient_wins": int(np.sum(delta < 0)),
        "patient_wins_minus_40": int(np.sum(delta < 0)) - 40,
        "strict_fold_wins": int(sum(x < 0 for x in fold_deltas)),
        "fold_wins_minus_4": int(sum(x < 0 for x in fold_deltas)) - 4,
        "fold_delta_mse": fold_deltas,
        "candidate_p90_patient_rmse": candidate_p90,
        "reference_p90_patient_rmse": reference_p90,
        "candidate_minus_reference_p90_rmse": candidate_p90 - reference_p90,
    }
    if orientation_losses is not None:
        for orientation in ("A", "B"):
            values[f"orientation_{orientation}_minus_reference_mse"] = float(
                np.mean(orientation_losses[orientation]) - reference_loss.mean())
    return values


def _validate(data, predictions, reference, folds, catalog):
    if set(predictions) != {"A", "B", "matched_paired_native"}:
        raise ValueError("Scoring requires exactly A, B and matched_paired_native predictions")
    y = np.asarray(data["y"], dtype=float)
    patients = np.asarray(data["patient_ids"], dtype=str)
    samples = np.asarray(data["sample_ids"], dtype=str)
    drugs = np.asarray(data["drug_ids"], dtype=str)
    libraries = np.asarray(data["library_ids"], dtype=str)
    folds = np.asarray(folds)
    target_ids = np.asarray(catalog.target_ids, dtype=str)
    if (y.shape != (119, 24) or patients.shape != (119,) or samples.shape != (119,)
            or folds.shape != (119,) or libraries.shape != (119,)
            or len(set(patients)) != 59 or len(set(samples)) != 119
            or drugs.shape != (24,) or len(set(drugs)) != 24
            or not np.array_equal(drugs, target_ids)
            or set(libraries) != {"lib1"}):
        raise ValueError("Canonical Lib1 119-PDO / 59-patient / 24-target scoring identities changed")
    if not np.issubdtype(folds.dtype, np.integer) or set(folds) != set(range(5)):
        raise ValueError("Scoring requires the five integer outer folds")
    patient_ids = np.asarray(sorted(set(patients)), dtype=str)
    patient_folds = []
    for pid in patient_ids:
        unique = np.unique(folds[patients == pid])
        if len(unique) != 1:
            raise ValueError("A whole patient crosses outer folds in scoring")
        patient_folds.append(int(unique[0]))
    arrays = {key: np.asarray(value, dtype=float) for key, value in predictions.items()}
    reference = np.asarray(reference, dtype=float)
    if not np.isfinite(y).all() or reference.shape != y.shape or not np.isfinite(reference).all():
        raise ValueError("Scoring truth or R9 reference is incomplete/nonfinite")
    if any(value.shape != y.shape or not np.isfinite(value).all() for value in arrays.values()):
        raise ValueError("A frozen procedure's OOF predictions are incomplete/nonfinite")
    if sum(drug in ("Gedatolisib", "Palbociclib") for drug in drugs) != 2:
        raise ValueError("The fixed missing2 target identity changed")
    return y, patients, samples, drugs, patient_ids, np.asarray(patient_folds), arrays, reference


def summarize(data, predictions, reference, folds, catalog):
    """Return metrics, contrasts, decision, patient rows, target rows, fold rows.

    `predictions` has exactly A/B/matched_paired_native; `reference` is the
    immutable R9 own24 OOF array. Expected-risk output averages losses only.
    No source, model or file is opened by this pure scoring function.
    """
    y, patients, samples, target_ids, ids, patient_fold, predictions, reference = _validate(
        data, predictions, reference, folds, catalog)
    missing = np.flatnonzero(np.isin(target_ids, ["Gedatolisib", "Palbociclib"]))
    scopes = {"all24": np.arange(24), "original22": np.setdiff1d(np.arange(24), missing), "missing2": missing}
    with np.errstate(over="raise", invalid="raise"):
        err_a, err_b = predictions["A"] - y, predictions["B"] - y
        err_paired, err_r9 = predictions["matched_paired_native"] - y, reference - y
        squared = {
            "single64_A": err_a ** 2, "single64_B": err_b ** 2,
            "single64_expected_loss": (err_a ** 2 + err_b ** 2) / 2,
            "matched_paired_native": err_paired ** 2, "reference_r9_own24": err_r9 ** 2,
        }
        absolute = {
            "single64_A": np.abs(err_a), "single64_B": np.abs(err_b),
            "single64_expected_loss": (np.abs(err_a) + np.abs(err_b)) / 2,
            "matched_paired_native": np.abs(err_paired), "reference_r9_own24": np.abs(err_r9),
        }
    metrics, risk_tables, patient_rows, target_rows, fold_rows = {}, {}, [], [], []
    for method in METHODS:
        per_target = _patient_tables(squared[method], patients, ids)
        per_target_absolute = _patient_tables(absolute[method], patients, ids)
        metrics[method], risk_tables[method] = {}, {}
        for scope, columns in scopes.items():
            risk = per_target[:, columns].mean(axis=1)
            mae = per_target_absolute[:, columns].mean(axis=1)
            patient_rmse = np.sqrt(risk)
            risk_tables[method][scope] = risk
            metrics[method][scope] = {
                "mse": float(risk.mean()), "rmse": float(np.sqrt(risk.mean())),
                "mae": float(mae.mean()), "mean_patient_rmse": float(patient_rmse.mean()),
                "median_patient_rmse": float(np.quantile(patient_rmse, 0.5, method="linear")),
                "p90_patient_rmse": float(np.quantile(patient_rmse, 0.9, method="linear")),
                "worst_patient_rmse": float(patient_rmse.max()),
                "patients": len(ids), "targets": len(columns),
                "treatment_wells_per_deployment": 64,
                "risk_semantics": "mean orientation losses" if method == "single64_expected_loss" else "fixed procedure loss",
            }
            for pid, fold, loss, absolute_loss in zip(ids, patient_fold, risk, mae):
                patient_rows.append({"method": method, "scope": scope, "patient_id": str(pid),
                    "fold": int(fold), "pdo_count": int(np.sum(patients == pid)),
                    "mse": float(loss), "rmse": float(np.sqrt(loss)), "mae": float(absolute_loss)})
            for fold in range(5):
                keep = patient_fold == fold
                fold_rows.append({"method": method, "scope": scope, "fold": fold,
                    "mse": float(risk[keep].mean()), "rmse": float(np.sqrt(risk[keep].mean())),
                    "mae": float(mae[keep].mean()), "patient_count": int(keep.sum())})
        decomposition = (22 / 24 * risk_tables[method]["original22"]
                       + 2 / 24 * risk_tables[method]["missing2"])
        if not np.allclose(risk_tables[method]["all24"], decomposition, rtol=0, atol=ARITHMETIC_TOLERANCE):
            raise AssertionError("Fixed target-set patient risk decomposition failed")
        for target, target_id in enumerate(target_ids):
            target_rows.append({"method": method, "target_index": target, "target_id": str(target_id),
                "fixed_scope": "missing2" if target in missing else "original22",
                "mse": float(per_target[:, target].mean()),
                "rmse": float(np.sqrt(per_target[:, target].mean())),
                "mae": float(per_target_absolute[:, target].mean())})
    expected_check = (risk_tables["single64_A"]["all24"] + risk_tables["single64_B"]["all24"]) / 2
    if not np.allclose(risk_tables["single64_expected_loss"]["all24"], expected_check, rtol=0, atol=ARITHMETIC_TOLERANCE):
        raise AssertionError("Expected policy risk is not the average of orientation losses")
    generator = np.random.Generator(np.random.PCG64(BOOTSTRAP_SEED))
    indices = generator.integers(0, len(ids), size=(BOOTSTRAP_RESAMPLES, len(ids)))
    contrast_roles = {
        "primary_single_vs_r9": ("single64_expected_loss", "reference_r9_own24"),
        "primary_single_vs_matched": ("single64_expected_loss", "matched_paired_native"),
        "secondary_matched_vs_r9": ("matched_paired_native", "reference_r9_own24"),
    }
    contrasts = {}
    for role, (candidate, ref) in contrast_roles.items():
        item = {"candidate": candidate, "reference": ref, "scopes": {}}
        for scope in scopes:
            c, r = risk_tables[candidate][scope], risk_tables[ref][scope]
            delta = c - r
            fold_deltas = [{"fold": fold, "mean_delta": float(delta[patient_fold == fold].mean()),
                            "patients": int(np.sum(patient_fold == fold))} for fold in range(5)]
            item["scopes"][scope] = {
                **_bootstrap(delta, indices), **_counts(delta),
                "relative_mse_reduction": float(1 - c.mean() / r.mean()) if r.mean() > 0 else None,
                "improving_folds": int(sum(f["mean_delta"] < 0 for f in fold_deltas)),
                "tied_folds": int(sum(f["mean_delta"] == 0 for f in fold_deltas)),
                "worsening_folds": int(sum(f["mean_delta"] > 0 for f in fold_deltas)),
                "fold_deltas": fold_deltas,
                "patient_ids": list(ids), "patient_delta_mse": [float(x) for x in delta],
                "patient_delta_min": float(delta.min()), "patient_delta_max": float(delta.max()),
            }
        residual = ((risk_tables[candidate]["all24"] - risk_tables[ref]["all24"])
                    - 22 / 24 * (risk_tables[candidate]["original22"] - risk_tables[ref]["original22"])
                    - 2 / 24 * (risk_tables[candidate]["missing2"] - risk_tables[ref]["missing2"]))
        item["decomposition_max_patient_residual"] = float(np.max(np.abs(residual)))
        if not np.allclose(residual, 0, rtol=0, atol=ARITHMETIC_TOLERANCE):
            raise AssertionError("Fixed target-set paired contrast decomposition failed")
        contrasts[role] = item
    orientation_losses = {key: risk_tables[f"single64_{key}"]["all24"] for key in ("A", "B")}
    primary_checks = {
        ref: _gate_checks(risk_tables["single64_expected_loss"]["all24"], risk_tables[ref]["all24"],
                          patient_fold, orientation_losses)
        for ref in PRIMARY_REFERENCES
    }
    primary_pass = all(value for checks in primary_checks.values() for value in checks.values())
    secondary_checks = _gate_checks(risk_tables["matched_paired_native"]["all24"],
                                   risk_tables["reference_r9_own24"]["all24"], patient_fold)
    secondary_pass = all(secondary_checks.values())
    primary_margins = {
        ref: _gate_margins(risk_tables["single64_expected_loss"]["all24"], risk_tables[ref]["all24"],
                          patient_fold, orientation_losses)
        for ref in PRIMARY_REFERENCES
    }
    secondary_margins = _gate_margins(risk_tables["matched_paired_native"]["all24"],
                                     risk_tables["reference_r9_own24"]["all24"], patient_fold)
    leading = ("single64_expected_loss" if primary_pass else
               "matched_paired_native" if secondary_pass else "reference_r9_own24")
    decision = {
        "primary": "single64_expected_loss", "primary_references": list(PRIMARY_REFERENCES),
        "secondary": "matched_paired_native", "secondary_reference": "reference_r9_own24",
        "gate": PROMOTION_GATE,
        "primary_checks_by_reference": primary_checks,
        "secondary_paired_checks": secondary_checks,
        "primary_margins_by_reference": primary_margins,
        "secondary_paired_margins": secondary_margins,
        "carry_forward": bool(primary_pass),
        "matched_paired_carry_forward": bool(secondary_pass),
        "leading_development_procedure": leading,
        "paired_control_won_when_primary_failed": bool(not primary_pass and secondary_pass),
        "decision_role": "prospective practical TRAIN-development gate; not significance or probability of winning",
        "prediction_averaging": False,
        "lib2_access_authorized": False, "r10_models_changed": False,
    }
    return metrics, contrasts, decision, patient_rows, target_rows, fold_rows
