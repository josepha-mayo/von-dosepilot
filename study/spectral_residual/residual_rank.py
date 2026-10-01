"""Reduced-rank correction of a fixed own-drug ridge predictor.

All fitting rows must belong to the current training fold. Both inputs are paid
64-well deployment alternatives. Prediction consumes only one alternative.
This is a research estimator, not a biological noise model or clinical tool.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from scipy.linalg import solve_triangular


def reduced_ridge(gram: np.ndarray, cross: np.ndarray, penalty: float,
                  rank: int) -> tuple[np.ndarray, np.ndarray]:
    gram, cross = np.asarray(gram, float), np.asarray(cross, float)
    if (gram.ndim != 2 or gram.shape[0] != gram.shape[1] or
            cross.ndim != 2 or cross.shape[0] != len(gram) or
            not np.isfinite(gram).all() or not np.isfinite(cross).all() or
            penalty <= 0 or not np.isfinite(penalty) or
            not isinstance(rank, (int, np.integer)) or not 1 <= rank <= cross.shape[1]):
        raise ValueError('Malformed reduced-ridge system')
    if not np.allclose(gram, gram.T, atol=1e-12, rtol=0):
        raise ValueError('Gram matrix must be symmetric')
    h = gram + penalty * np.eye(len(gram))
    lower = np.linalg.cholesky(h)
    transformed = solve_triangular(lower, cross, lower=True)
    _, singular, vt = np.linalg.svd(transformed, full_matrices=False)
    projector = vt[:rank].T @ vt[:rank]
    coefficients = np.linalg.solve(h, cross) @ projector
    return coefficients, singular


@dataclass
class ResidualRank:
    base: object
    correction: np.ndarray
    eigenvalues: np.ndarray
    rank: int
    penalty: float

    def predict(self, paid: np.ndarray) -> np.ndarray:
        paid = np.asarray(paid, float)
        if paid.ndim != 2 or paid.shape[1] != 64 or not np.isfinite(paid).all():
            raise ValueError('Exactly 64 finite purchased values required')
        original = self.base.predict(paid)
        z = (paid - self.base.mean_x) / self.base.scale_x
        return original + z @ self.correction

    def arrays(self) -> dict:
        return dict(self.base.arrays(), correction=self.correction,
                    singular_values=self.eigenvalues, residual_rank=self.rank,
                    residual_penalty=self.penalty)


def fit(context, base, penalty: float, rank: int) -> ResidualRank:
    # Own-drug coefficients remain frozen; the low-rank correction is fitted
    # jointly on all 24 residuals. No held-patient residual is an input.
    residual_cross = context.cxy - context.cxx @ base.beta
    correction, singular = reduced_ridge(context.cxx, residual_cross, penalty, rank)
    return ResidualRank(base, correction, singular, rank, penalty)
