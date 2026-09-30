"""A separately optimized, constant-tail log-linear 64-well comparator.

No files or response sources are read here. Acquisition uses fitting patients
only; the fixed readout has no learned coefficients or tuned hyperparameters.
The search class is the R13 class: 2/3 native doses per drug, exactly 16 upgrades.
A and B are alternate physical acquisitions; average losses, never predictions.
"""
from __future__ import annotations
from decimal import Decimal
from itertools import combinations
import numpy as np
from coverage_methods import validate_catalog, validate_plan, subset_orientations


def patient_weights(patients):
    patients = np.asarray(patients, dtype=str)
    if patients.ndim != 1 or not len(patients):
        raise ValueError('Nonempty patient vector required')
    _, inverse, counts = np.unique(patients, return_inverse=True, return_counts=True)
    return 1.0 / (len(counts) * counts[inverse])


def integration_weights(doses, bounds):
    """Exact normalized integral weights for log-linear, constant-tail readout."""
    doses = np.asarray(doses, dtype=float)
    bounds = np.asarray(bounds, dtype=float)
    if doses.ndim != 1 or len(doses) < 2 or bounds.shape != (2,):
        raise ValueError('Need an ordered dose vector and two bounds')
    if (not np.isfinite(doses).all() or not np.isfinite(bounds).all()
            or np.any(doses <= 0) or np.any(bounds <= 0)
            or np.any(np.diff(doses) <= 0) or bounds[0] >= bounds[1]):
        raise ValueError('Dose and interval identities must be positive, finite, ordered')
    x = np.log(doses)
    lo, hi = np.log(bounds)
    knots = np.r_[lo, x[(x > lo) & (x < hi)], hi]
    basis = np.eye(len(x))
    values = np.column_stack([np.interp(knots, x, col) for col in basis])
    weights = np.sum(np.diff(knots)[:, None] * (values[:-1] + values[1:]) / 2, axis=0) / (hi - lo)
    if np.any(weights < -1e-14) or not np.isclose(weights.sum(), 1, rtol=0, atol=1e-12):
        raise AssertionError('Nonconvex or unnormalized integral')
    return weights


def plan_panel(replicates, targets, patients, catalog, bounds):
    """Globally minimize fitting loss within the declared separable 2/3 class.

    Exactly enumerate size-2 and size-3 subsets for each drug, then take the
    sixteen largest loss reductions. Complementary plate-flip symmetry makes
    each target's expected loss independent of its global orientation start.
    This is a fitting optimum in this finite class, not a population optimum.
    """
    validate_catalog(catalog)
    x, y = np.asarray(replicates, dtype=float), np.asarray(targets, dtype=float)
    bounds = np.asarray(bounds, dtype=float)
    weights = patient_weights(patients)
    if (x.shape != (len(weights), len(catalog.native_ids), 2)
            or y.shape != (len(weights), 24) or bounds.shape != (24, 2)
            or not np.isfinite(x).all() or not np.isfinite(y).all()):
        raise ValueError('Malformed fitting data')
    choices, scores = [], []
    for j, target_id in enumerate(catalog.target_ids):
        native = sorted(np.flatnonzero(catalog.native_target_indices == j),
                        key=lambda q: (Decimal(catalog.concentrations[q]), str(catalog.native_ids[q])))
        best = {}
        for size in (2, 3):
            options = []
            for subset in combinations(native, size):
                readout = integration_weights([catalog.concentrations[q] for q in subset], bounds[j])
                a, b = subset_orientations(x, subset)
                loss = ((a @ readout - y[:, j]) ** 2 + (b @ readout - y[:, j]) ** 2) / 2
                risk = float(weights @ loss)
                ids = tuple(str(catalog.native_ids[q]) for q in subset)
                options.append((risk, ids, tuple(map(int, subset))))
                scores.append({'target_index': j, 'size': size, 'native_ids': list(ids), 'fitting_expected_mse': risk})
            best[size] = min(options)
        choices.append({'target_index': j, 'target_id': str(target_id),
                        'best2': list(best[2][2]), 'best3': list(best[3][2]),
                        'risk2': best[2][0], 'risk3': best[3][0],
                        'upgrade_gain': best[2][0] - best[3][0]})
    ranked = sorted(choices, key=lambda row: (-row['upgrade_gain'], row['target_id']))
    upgraded = {row['target_index'] for row in ranked[:16]}
    upgraded_order = sorted(upgraded, key=lambda j: str(catalog.target_ids[j]))
    starts = {j: k % 2 for k, j in enumerate(upgraded_order)}
    selected, ownership, plates, decoder = [], [], [], np.zeros((64, 24))
    for j, choice in enumerate(choices):
        subset = choice['best3' if j in upgraded else 'best2']
        offset = len(selected)
        decoder[offset:offset + len(subset), j] = integration_weights(
            [catalog.concentrations[q] for q in subset], bounds[j])
        selected.extend(subset)
        ownership.extend([j] * len(subset))
        plates.extend((starts.get(j, 0) + k) % 2 for k in range(len(subset)))
    plan = {'policy': 'interpolation_optimized_64_v1', 'library_id': 'lib1',
            'selected_native_indices': selected,
            'selected_native_ids': [str(catalog.native_ids[q]) for q in selected],
            'selected_concentrations_nM': [str(catalog.concentrations[q]) for q in selected],
            'coordinate_target_indices': ownership,
            'orientation_A_plate_indices': plates,
            'orientation_B_plate_indices': [1 - p for p in plates],
            'upgraded_target_ids': [str(catalog.target_ids[j]) for j in upgraded_order],
            'choices': choices, 'all_subset_scores': scores,
            'readout_weights': decoder.tolist(), 'treatment_wells_per_orientation': 64,
            'plate_wells_per_orientation': {'p1': 32, 'p2': 32},
            'primary_orientation_semantics': 'mean losses only; never mean predictions'}
    validate_plan(plan, catalog)
    return plan


def predict_paid(paid, plan):
    validate_plan(plan)
    x = np.asarray(paid, dtype=float)
    decoder = np.asarray(plan['readout_weights'], dtype=float)
    if x.ndim != 2 or x.shape[1] != 64 or not np.isfinite(x).all():
        raise ValueError('Exactly 64 finite purchased values are required')
    ownership = np.asarray(plan['coordinate_target_indices'])
    if (decoder.shape != (64, 24) or not np.isfinite(decoder).all()
            or np.any(decoder < 0)
            or not np.allclose(decoder.sum(axis=0), 1, rtol=0, atol=1e-12)
            or np.any(decoder[ownership[:, None] != np.arange(24)[None, :]] != 0)):
        raise ValueError('Readout must be convex and drug-specific')
    return x @ decoder
