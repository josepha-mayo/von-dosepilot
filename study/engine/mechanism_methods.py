"""Matched-observation predictors for the sparse-dose mechanism experiment.

This module reads no data.  Allocation is deliberately separated from
prediction: the broad 32-action policy always uses planning alpha 0.1, while
the two predictors independently tune one of four ridge penalties.
"""
from __future__ import annotations

import numpy as np

from sparse_methods import (
    LAMBDAS,
    SparseRidgePredictor,
    allocate,
    fit_sparse_context,
)


ALLOCATION_ALPHA = 0.1
PREDICTION_LAMBDAS = LAMBDAS
ALLOCATION_FAMILY = "broad_drugwise"


def broad_panel(context, descriptor):
    """Return the fixed-alpha broad panel; prediction lambda is not accepted."""
    selected, plan = allocate(
        context, descriptor, ALLOCATION_FAMILY, ALLOCATION_ALPHA
    )
    counts = np.bincount(
        descriptor.query_target_indices[list(selected)],
        minlength=len(descriptor.target_ids),
    )
    queryable = np.flatnonzero(
        np.bincount(
            descriptor.query_target_indices,
            minlength=len(descriptor.target_ids),
        )
    )
    if len(selected) != 32 or not np.all(np.isin(counts[queryable], (1, 2))):
        raise AssertionError("Fixed broad policy violated its one-or-two action contract")
    if not np.all(counts[np.setdiff1d(np.arange(len(counts)), queryable)] == 0):
        raise AssertionError("Broad policy selected an action for an unqueryable target")
    if int(np.sum(counts[queryable] == 2)) != 10:
        raise AssertionError("Broad policy did not buy exactly ten second actions")
    return selected, plan


class SharedRidgePredictor:
    """All 32 purchased actions jointly predict all 24 AUC targets."""

    def __init__(self, context, selected, lam, descriptor):
        if lam not in PREDICTION_LAMBDAS:
            raise ValueError("Shared prediction penalty is outside the frozen grid")
        self._model = SparseRidgePredictor(context, selected, lam, descriptor)
        self.selected = tuple(selected)
        self.lam = float(lam)
        self.exact_target_mask = self._model.exact_target_mask.copy()

    def predict(self, observed_actions):
        return self._model.predict(observed_actions)


class OwnDrugRidgePredictor:
    """Twenty-two independent heads, each using only its own paid actions.

    All heads share one penalty.  Means, scales and covariance moments come
    from the same equal-patient-weighted training context as the shared model.
    The prediction interface receives only the 32 paid action values.
    """

    def __init__(self, context, selected, lam, descriptor):
        selected = tuple(map(int, selected))
        if len(selected) != 32 or len(set(selected)) != 32:
            raise ValueError("Own-drug prediction requires 32 distinct actions")
        if lam not in PREDICTION_LAMBDAS:
            raise ValueError("Own-drug prediction penalty is outside the frozen grid")
        if not np.array_equal(context.query_ids, descriptor.query_ids) or not np.array_equal(
            context.target_ids, descriptor.target_ids
        ):
            raise ValueError("Context and descriptor identities disagree")

        selected_array = np.asarray(selected, dtype=int)
        if np.any(selected_array < 0) or np.any(selected_array >= len(context.query_ids)):
            raise ValueError("Selected action index is outside the query universe")
        selected_targets = descriptor.query_target_indices[selected_array]
        all_counts = np.bincount(
            descriptor.query_target_indices, minlength=len(descriptor.target_ids)
        )
        self.target_indices = np.flatnonzero(all_counts)
        if len(self.target_indices) != 22:
            raise ValueError("Mechanism control requires exactly 22 queryable targets")

        self.selected = selected
        self.lam = float(lam)
        self.local_columns = []
        self.means_x = []
        self.scales_x = []
        self.means_y = []
        self.betas = []
        for target in self.target_indices:
            local = np.flatnonzero(selected_targets == target)
            if len(local) not in (1, 2):
                raise ValueError("Each queried target must have one or two purchased actions")
            global_actions = selected_array[local]
            covariance = context.cxx[np.ix_(global_actions, global_actions)]
            cross = context.cxy[global_actions, target]
            beta = np.linalg.solve(covariance + float(lam) * np.eye(len(local)), cross)
            self.local_columns.append(local)
            self.means_x.append(context.mean_x[global_actions].copy())
            self.scales_x.append(context.scale_x[global_actions].copy())
            self.means_y.append(float(context.mean_y[target]))
            self.betas.append(beta)

    def predict(self, observed_actions):
        observed = np.asarray(observed_actions, dtype=float)
        if observed.ndim != 2 or observed.shape[1] != 32:
            raise ValueError("Prediction accepts only the 32 purchased action means")
        if not np.isfinite(observed).all():
            raise ValueError("Purchased observations must be finite")
        result = np.empty((len(observed), len(self.target_indices)), dtype=float)
        for column, (local, mean_x, scale_x, mean_y, beta) in enumerate(
            zip(
                self.local_columns,
                self.means_x,
                self.scales_x,
                self.means_y,
                self.betas,
            )
        ):
            result[:, column] = mean_y + ((observed[:, local] - mean_x) / scale_x) @ beta
        if not np.isfinite(result).all():
            raise ValueError("Own-drug prediction is nonfinite")
        return result


def hybrid_prediction(shared_prediction, own_prediction, target_indices):
    """Replace only the 22 queried shared outputs with own-drug outputs."""
    shared = np.asarray(shared_prediction, dtype=float)
    own = np.asarray(own_prediction, dtype=float)
    targets = np.asarray(target_indices, dtype=int)
    if shared.ndim != 2 or own.shape != (len(shared), len(targets)):
        raise ValueError("Shared and own-drug predictions are not aligned")
    if len(set(map(int, targets))) != len(targets) or np.any(targets < 0) or np.any(
        targets >= shared.shape[1]
    ):
        raise ValueError("Invalid queried-target mapping")
    if not np.isfinite(shared).all() or not np.isfinite(own).all():
        raise ValueError("Hybrid inputs must be finite")
    result = shared.copy()
    result[:, targets] = own
    return result


def fit_context(x, y, patients, descriptor):
    """Identity-preserving alias used by the evaluator and synthetic tests."""
    return fit_sparse_context(
        x, y, patients, descriptor.query_ids, descriptor.target_ids
    )
