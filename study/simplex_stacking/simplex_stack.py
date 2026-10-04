"""Deterministic patient-balanced simplex stacking for complete predictors."""
from __future__ import annotations

import itertools
import numpy as np


def _validated(predictions, truth, patients):
    predictions = np.asarray(predictions, dtype=float)
    truth = np.asarray(truth, dtype=float)
    patients = np.asarray(patients)
    if predictions.ndim != 4:
        raise ValueError("Predictions must have model, orientation, sample and target axes")
    models, orientations, samples, targets = predictions.shape
    if models < 2 or models > 16 or orientations != 2:
        raise ValueError("Expected 2-16 models and exactly two deployment orientations")
    if truth.shape != (samples, targets) or patients.shape != (samples,):
        raise ValueError("Truth or patient shape does not match predictions")
    if targets < 1 or not np.isfinite(predictions).all() or not np.isfinite(truth).all():
        raise ValueError("Predictions and truth must be finite and nonempty")
    identities, inverse, counts = np.unique(patients.astype(str), return_inverse=True, return_counts=True)
    if len(identities) < 2:
        raise ValueError("At least two whole patients are required")
    sample_weight = 1.0 / (len(identities) * counts[inverse])
    observation_weight = np.broadcast_to(
        sample_weight[None, :, None] / (orientations * targets),
        (orientations, samples, targets),
    ).reshape(-1)
    design = np.moveaxis(predictions, 0, -1).reshape(-1, models)
    response = np.broadcast_to(truth[None, :, :], (orientations, samples, targets)).reshape(-1)
    return design, response, observation_weight


def patient_balanced_loss(prediction, truth, patients):
    """Equal-patient, equal-target, equal-orientation squared loss."""
    prediction = np.asarray(prediction, dtype=float)
    if prediction.ndim != 3:
        raise ValueError("Prediction must have orientation, sample and target axes")
    design, response, weight = _validated(
        np.stack((prediction, prediction)), truth, patients
    )
    # _validated duplicated the same complete predictor as two model candidates;
    # use its first design column solely to share the exact weighting contract.
    return float(np.sum(weight * (design[:, 0] - response) ** 2))


def fit_simplex(predictions, truth, patients, tolerance=1e-11):
    """Fit the exact global nonnegative simplex least-squares combination.

    All nonempty faces of the at-most-16-model simplex are enumerated.  Each
    face is solved by its equality-constrained KKT system.  Enumeration avoids
    optimizer tolerances or random starts and is practical for the frozen ten
    candidates (1023 faces).
    """
    if not np.isfinite(tolerance) or tolerance <= 0:
        raise ValueError("Tolerance must be positive and finite")
    design, response, weight = _validated(predictions, truth, patients)
    root_weight = np.sqrt(weight)
    weighted_design = design * root_weight[:, None]
    weighted_response = response * root_weight
    gram = weighted_design.T @ weighted_design
    cross = weighted_design.T @ weighted_response
    models = design.shape[1]
    best = None
    scale = max(1.0, float(weighted_response @ weighted_response))
    for size in range(1, models + 1):
        for active_tuple in itertools.combinations(range(models), size):
            active = np.asarray(active_tuple, dtype=int)
            subgram = gram[np.ix_(active, active)]
            kkt = np.block([
                [subgram, np.ones((size, 1))],
                [np.ones((1, size)), np.zeros((1, 1))],
            ])
            rhs = np.r_[cross[active], 1.0]
            solution = np.linalg.lstsq(kkt, rhs, rcond=None)[0][:-1]
            if solution.min(initial=0.0) < -tolerance:
                continue
            solution = np.maximum(solution, 0.0)
            total = float(solution.sum())
            if total <= 0:
                continue
            solution /= total
            candidate = np.zeros(models, dtype=float)
            candidate[active] = solution
            residual = design @ candidate - response
            objective = float(np.sum(weight * residual * residual))
            key = (objective, float(candidate @ candidate), tuple(np.round(candidate, 15)))
            if best is None or key[0] < best[0][0] - tolerance * scale or (
                abs(key[0] - best[0][0]) <= tolerance * scale and key[1:] < best[0][1:]
            ):
                best = (key, candidate)
    if best is None:
        raise ValueError("No feasible simplex solution")
    weights = best[1]
    if (weights < -tolerance).any() or abs(float(weights.sum()) - 1.0) > tolerance:
        raise ValueError("Internal simplex constraint failure")
    prediction = np.tensordot(weights, np.asarray(predictions, dtype=float), axes=(0, 0))
    return weights, patient_balanced_loss(prediction, truth, patients)


def combine_coefficients(coefficients, weights):
    """Collapse complete spectral models into one deployable coefficient matrix."""
    coefficients = np.asarray(coefficients, dtype=float)
    weights = np.asarray(weights, dtype=float)
    if coefficients.ndim != 3 or weights.shape != (len(coefficients),):
        raise ValueError("Coefficient or weight shape mismatch")
    if not np.isfinite(coefficients).all() or not np.isfinite(weights).all():
        raise ValueError("Coefficients and weights must be finite")
    if (weights < -1e-12).any() or abs(float(weights.sum()) - 1.0) > 1e-10:
        raise ValueError("Weights are not on the simplex")
    return np.tensordot(weights, coefficients, axes=(0, 0))
