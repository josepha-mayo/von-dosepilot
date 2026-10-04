"""Response-free per-group bandwidth normalization for one frozen challenger."""
from __future__ import annotations

import numpy as np

from additive_kernel import AdditiveKernel


ANCHOR = 0.7
REFERENCE_MEDIAN = {2: 2.772588722239781, 3: 4.731947768750675}
MIN_MEDIAN = 1e-12


def _groups(owner):
    owner = np.asarray(owner)
    if owner.shape != (64,) or owner.dtype.kind not in "iu" or set(owner) != set(range(24)):
        raise ValueError("Exactly 24 integer owner groups over 64 coordinates required")
    groups = [np.flatnonzero(owner == j) for j in range(24)]
    if sorted(map(len, groups)) != [2] * 8 + [3] * 16:
        raise ValueError("Original 64-well two/three-coordinate ownership required")
    return owner.astype(int, copy=True), groups


def weighted_median(values, weights, first_index=None, second_index=None):
    """First deterministic value reaching half of positive total weight."""
    values = np.asarray(values, dtype=float)
    weights = np.asarray(weights, dtype=float)
    if values.ndim != 1 or weights.shape != values.shape or not len(values):
        raise ValueError("Nonempty aligned one-dimensional values and weights required")
    if not np.isfinite(values).all() or not np.isfinite(weights).all() or (weights <= 0).any():
        raise ValueError("Weighted median inputs must be finite with positive weights")
    if first_index is None:
        first_index = np.arange(len(values), dtype=int)
    if second_index is None:
        second_index = np.zeros(len(values), dtype=int)
    first_index = np.asarray(first_index)
    second_index = np.asarray(second_index)
    if first_index.shape != values.shape or second_index.shape != values.shape:
        raise ValueError("Tie-break indices are misaligned")
    order = np.lexsort((second_index, first_index, values))
    cumulative = np.cumsum(weights[order])
    position = int(np.searchsorted(cumulative, weights.sum() / 2.0, side="left"))
    return float(values[order[position]])


def estimate_group_bandwidths(z, weights, owner, patient_ids):
    """Estimate fitting-only bandwidths without accepting any outcome argument."""
    z = np.asarray(z, dtype=float)
    weights = np.asarray(weights, dtype=float)
    patient_ids = np.asarray(patient_ids, dtype=str)
    owner, groups = _groups(owner)
    if z.ndim != 2 or z.shape[1] != 64 or not np.isfinite(z).all():
        raise ValueError("Finite fitting features with 64 coordinates required")
    if weights.shape != (len(z),) or not np.isfinite(weights).all() or (weights <= 0).any():
        raise ValueError("Positive finite fitting-row weights required")
    if not np.isclose(weights.sum(), 1.0, rtol=0.0, atol=1e-12):
        raise ValueError("Fitting-row weights must sum to one")
    if patient_ids.shape != (len(z),) or any(not value for value in patient_ids):
        raise ValueError("One nonempty whole-patient identity per fitting row required")
    if len(np.unique(patient_ids)) < 2:
        raise ValueError("At least two whole patients are required")

    first, second = np.triu_indices(len(z), 1)
    cross = patient_ids[first] != patient_ids[second]
    first, second = first[cross], second[cross]
    if not len(first):
        raise ValueError("No cross-patient fitting-row pairs")
    pair_weights = weights[first] * weights[second]
    medians = np.empty(24, dtype=float)
    bandwidths = np.empty(24, dtype=float)
    for target, group in enumerate(groups):
        differences = z[first][:, group] - z[second][:, group]
        distances = np.einsum("ij,ij->i", differences, differences)
        median = weighted_median(distances, pair_weights, first, second)
        if not np.isfinite(median) or median <= MIN_MEDIAN:
            raise ValueError("Degenerate cross-patient group distance")
        bandwidth = ANCHOR * np.sqrt(median / REFERENCE_MEDIAN[len(group)])
        if not np.isfinite(bandwidth) or bandwidth <= 0:
            raise ValueError("Invalid derived group bandwidth")
        medians[target] = median
        bandwidths[target] = bandwidth
    return medians, bandwidths


class CrossPatientMedianBandwidth(AdditiveKernel):
    """Additive kernel with fixed response-free fitting-slice group bandwidths."""

    def __init__(self, z, residual, weights, owner, patient_ids):
        self.fitting_patient_ids = np.asarray(patient_ids, dtype=str).copy()
        self.group_medians, self.group_bandwidths = estimate_group_bandwidths(
            z, weights, owner, self.fitting_patient_ids
        )
        super().__init__(z, residual, weights, owner)

    def raw_cross(self, z):
        z = np.asarray(z, dtype=float)
        if z.ndim != 2 or z.shape[1] != 64 or not np.isfinite(z).all():
            raise ValueError("64 finite query coordinates required")
        result = z @ self.z.T
        for target, group in enumerate(self.groups):
            a, b = z[:, group], self.z[:, group]
            distance = np.maximum(
                (a * a).sum(1)[:, None] + (b * b).sum(1)[None, :] - 2 * a @ b.T,
                0.0,
            )
            scale = self.group_bandwidths[target] ** 2
            result += len(group) * np.exp(-distance / (2 * len(group) * scale))
        return result

    def arrays(self, coefficients):
        return dict(
            super().arrays(coefficients),
            kernel_group_distance_medians=self.group_medians,
            kernel_group_bandwidth_multipliers=self.group_bandwidths,
            kernel_fitting_patient_ids=self.fitting_patient_ids,
            kernel_bandwidth_anchor=np.asarray(ANCHOR),
        )
