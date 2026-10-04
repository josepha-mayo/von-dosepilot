"""Frozen own-drug interpolation and affine-calibration control.

This module reads no files.  It exhaustively evaluates native two/three-dose
subsets inside supplied patient folds, buys exactly sixteen third-dose
upgrades, and selects one shared affine-calibration option.  Complementary A/B
layouts are separately costed alternatives; only their losses are averaged.
"""
from __future__ import annotations

from decimal import Decimal
from itertools import combinations
import numpy as np

from calibrated_control import OPTIONS, fit, weights
from coverage_methods import subset_orientations, validate_catalog, validate_plan
from interpolation_policy import integration_weights


def _subsets(catalog, target, size):
    native = sorted(
        np.flatnonzero(catalog.native_target_indices == target),
        key=lambda q: (Decimal(catalog.concentrations[q]), str(catalog.native_ids[q])),
    )
    return list(combinations(map(int, native), size))


def subset_raw(replicates, subset, catalog, bounds):
    readout = integration_weights(
        [catalog.concentrations[q] for q in subset], bounds
    )
    a, b = subset_orientations(replicates, subset)
    return np.stack((a @ readout, b @ readout))


def _target_risk(y, predictions, patients):
    error = ((predictions[0] - y) ** 2 + (predictions[1] - y) ** 2) / 2.0
    return float(weights(patients) @ error)


def select_joint(replicates, y, patients, catalog, bounds, folds):
    """Select subset, sixteen upgrades and one shared option using OOF losses."""
    validate_catalog(catalog)
    x = np.asarray(replicates, float)
    y = np.asarray(y, float)
    patients = np.asarray(patients, str)
    folds = np.asarray(folds, int)
    bounds = np.asarray(bounds, float)
    if x.shape != (len(y), len(catalog.native_ids), 2) or y.shape != (len(y), 24):
        raise ValueError("Malformed fitting arrays")
    if folds.shape != (len(y),) or set(folds) != {0, 1, 2}:
        raise ValueError("Exactly three complete inner folds required")
    if bounds.shape != (24, 2) or not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ValueError("Invalid finite data or target bounds")

    option_rows = []
    for option_index, option in enumerate(OPTIONS):
        target_choices = []
        for target in range(24):
            best = {}
            for size in (2, 3):
                candidates = []
                for subset in _subsets(catalog, target, size):
                    oof = np.full((2, len(y)), np.nan)
                    for fold in range(3):
                        tr, va = folds != fold, folds == fold
                        if set(patients[tr]) & set(patients[va]):
                            raise ValueError("Patient leakage")
                        raw_tr = subset_raw(x[tr], subset, catalog, bounds[target])
                        raw_va = subset_raw(x[va], subset, catalog, bounds[target])
                        model = fit(
                            raw_tr.reshape(-1, 1),
                            np.tile(y[tr, target], 2)[:, None],
                            np.tile(patients[tr], 2),
                            option,
                        )
                        for orientation in (0, 1):
                            oof[orientation, va] = model.predict(raw_va[orientation, :, None])[:, 0]
                    risk = _target_risk(y[:, target], oof, patients)
                    ids = tuple(str(catalog.native_ids[q]) for q in subset)
                    candidates.append((risk, ids, tuple(subset)))
                best[size] = min(candidates)
            target_choices.append({
                "target_index": target,
                "target_id": str(catalog.target_ids[target]),
                "best2": list(best[2][2]), "risk2": best[2][0],
                "best3": list(best[3][2]), "risk3": best[3][0],
                "upgrade_gain": best[2][0] - best[3][0],
            })
        ranked = sorted(target_choices, key=lambda r: (-r["upgrade_gain"], r["target_id"]))
        upgraded = {r["target_index"] for r in ranked[:16]}
        score = float(sum(r["risk3"] if r["target_index"] in upgraded else r["risk2"] for r in target_choices) / 24)
        option_rows.append((score, option_index, option, target_choices, upgraded))
    score, _, option, choices, upgraded = min(option_rows, key=lambda r: (r[0], r[1]))
    return build_plan(catalog, bounds, choices, upgraded, option, score), [float(r[0]) for r in option_rows]


def build_plan(catalog, bounds, choices, upgraded, option, score):
    upgraded_order = sorted(upgraded, key=lambda j: str(catalog.target_ids[j]))
    starts = {j: k % 2 for k, j in enumerate(upgraded_order)}
    selected, owners, plates, decoder = [], [], [], np.zeros((64, 24))
    for target, choice in enumerate(choices):
        subset = choice["best3" if target in upgraded else "best2"]
        offset = len(selected)
        decoder[offset:offset + len(subset), target] = integration_weights(
            [catalog.concentrations[q] for q in subset], bounds[target]
        )
        selected.extend(subset)
        owners.extend([target] * len(subset))
        plates.extend((starts.get(target, 0) + k) % 2 for k in range(len(subset)))
    plan = {
        "policy": "cooptimized_calibrated_interpolation_64_v1",
        "library_id": "lib1",
        "selected_native_indices": selected,
        "selected_native_ids": [str(catalog.native_ids[q]) for q in selected],
        "selected_concentrations_nM": [str(catalog.concentrations[q]) for q in selected],
        "coordinate_target_indices": owners,
        "orientation_A_plate_indices": plates,
        "orientation_B_plate_indices": [1 - p for p in plates],
        "upgraded_target_ids": [str(catalog.target_ids[j]) for j in upgraded_order],
        "choices": choices,
        "readout_weights": decoder.tolist(),
        "calibration_option": option,
        "inner_expected_mse": score,
        "treatment_wells_per_orientation": 64,
        "plate_wells_per_orientation": {"p1": 32, "p2": 32},
        "primary_orientation_semantics": "mean losses only; never mean predictions",
    }
    validate_plan(plan, catalog)
    return plan


def raw_from_plan(replicates, plan):
    x = np.asarray(replicates, float)
    decoder = np.asarray(plan["readout_weights"], float)
    result = []
    for name in ("A", "B"):
        native = np.asarray(plan["selected_native_indices"], int)
        plates = np.asarray(plan[f"orientation_{name}_plate_indices"], int)
        result.append(x[:, native, plates] @ decoder)
    return np.stack(result)


def fit_plan(replicates, y, patients, plan):
    raw = raw_from_plan(replicates, plan)
    return fit(
        raw.reshape(-1, 24), np.tile(np.asarray(y, float), (2, 1)),
        np.tile(np.asarray(patients, str), 2), plan["calibration_option"],
    )


def predict_plan(replicates, plan, model):
    raw = raw_from_plan(replicates, plan)
    return np.stack([model.predict(raw[o]) for o in (0, 1)])
