"""Fixed within-drug monotone projection for purchased dose observations."""
from __future__ import annotations

from decimal import Decimal
import numpy as np


def decreasing_pava(values):
    """Equal-weight Euclidean projection onto x[0] >= ... >= x[n-1]."""
    values = np.asarray(values, dtype=float)
    if values.ndim != 1 or not len(values) or not np.isfinite(values).all():
        raise ValueError("PAVA requires one nonempty finite vector")
    levels, weights, starts = [], [], []
    for index, value in enumerate(values):
        levels.append(float(value)); weights.append(1); starts.append(index)
        while len(levels) >= 2 and levels[-2] < levels[-1]:
            weight = weights[-2] + weights[-1]
            level = (weights[-2] * levels[-2] + weights[-1] * levels[-1]) / weight
            levels[-2:] = [level]; weights[-2:] = [weight]; starts[-1:] = []
    result = np.empty_like(values)
    for block, (level, start) in enumerate(zip(levels, starts)):
        stop = starts[block + 1] if block + 1 < len(starts) else len(values)
        result[start:stop] = level
    return result


def project_paid(paid, plan):
    """Project each purchased within-drug dose sequence; never mix drug heads."""
    paid = np.asarray(paid, dtype=float)
    owners = np.asarray(plan.get("coordinate_target_indices"), dtype=int)
    doses = plan.get("selected_concentrations_nM")
    if paid.ndim != 2 or paid.shape[1] != 64 or owners.shape != (64,):
        raise ValueError("Expected rows of exactly 64 paid treatment values")
    if not np.isfinite(paid).all() or doses is None or len(doses) != 64:
        raise ValueError("Paid values and dose identities must be complete and finite")
    try:
        numeric_doses = np.asarray([float(Decimal(str(value))) for value in doses])
    except Exception as error:
        raise ValueError("Dose identities must be positive finite decimals") from error
    if not np.isfinite(numeric_doses).all() or np.any(numeric_doses <= 0):
        raise ValueError("Dose identities must be positive finite decimals")
    result = paid.copy()
    for owner in np.unique(owners):
        columns = np.flatnonzero(owners == owner)
        order = columns[np.argsort(numeric_doses[columns], kind="stable")]
        if len(order) not in (2, 3) or len(set(numeric_doses[order])) != len(order):
            raise ValueError("Every drug head must contain two or three distinct doses")
        for row in range(len(result)):
            result[row, order] = decreasing_pava(result[row, order])
    if not np.isfinite(result).all():
        raise ValueError("Projection produced nonfinite values")
    return result
