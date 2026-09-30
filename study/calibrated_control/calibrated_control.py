"""Training-only, own-target affine calibration of a frozen interpolation readout.

The input to each head is one interpolation AUC. No additional measurement,
other-target feature, confirmation value, clipping or model averaging is used.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np

OPTIONS = ("identity", 0.0, 0.01, 0.1, 1.0, 10.0)
SCALE_FLOOR = 0.05


def validate(x, y=None, patients=None):
    x = np.asarray(x, dtype=float)
    if x.ndim != 2 or not len(x) or not np.isfinite(x).all():
        raise ValueError("Nonempty finite matrix required")
    if y is not None:
        y = np.asarray(y, dtype=float)
        if y.shape != x.shape or not np.isfinite(y).all():
            raise ValueError("Targets must match the finite input matrix")
    if patients is not None:
        p = np.asarray(patients, dtype=str)
        if p.shape != (len(x),) or any(not a for a in p):
            raise ValueError("Complete patient/group identities required")
    return x


def weights(patients):
    p = np.asarray(patients, dtype=str)
    if p.ndim != 1 or not len(p) or any(not s for s in p):
        raise ValueError("Nonempty group identities required")
    _, inv, count = np.unique(p, return_inverse=True, return_counts=True)
    return 1.0 / (len(count) * count[inv])


def group_target_risks(y, prediction, patients):
    y = validate(y, prediction, patients)
    p = np.asarray(patients, dtype=str)
    errors = (y - np.asarray(prediction)) ** 2
    return np.asarray([errors[p == g].mean(axis=0) for g in np.unique(p)])


@dataclass
class Calibration:
    option: object
    mean_x: np.ndarray
    scale_x: np.ndarray
    mean_y: np.ndarray
    beta: np.ndarray

    def predict(self, x):
        x = validate(x)
        if x.shape[1] != len(self.beta):
            raise ValueError("Target width changed")
        if self.option == "identity":
            return x.copy()
        result = self.mean_y + (x - self.mean_x) / self.scale_x * self.beta
        if not np.isfinite(result).all():
            raise ValueError("Nonfinite calibrated prediction")
        return result

    def arrays(self):
        return {"option": np.asarray(str(self.option)), "mean_x": self.mean_x,
                "scale_x": self.scale_x, "mean_y": self.mean_y, "beta": self.beta}


def fit(x, y, patients, option):
    x = validate(x, y, patients)
    y = np.asarray(y, dtype=float)
    if option not in OPTIONS:
        raise ValueError("Unregistered calibration option")
    q = weights(patients)
    mx, my = q @ x, q @ y
    sx = np.maximum(np.sqrt(q @ ((x - mx) ** 2)), SCALE_FLOOR)
    z = (x - mx) / sx
    var = q @ (z * z)
    cross = q @ (z * (y - my))
    if option == "identity":
        beta = np.zeros(x.shape[1])
    else:
        denom = var + float(option)
        beta = np.divide(cross, denom, out=np.zeros_like(cross), where=denom > 1e-24)
    return Calibration(option, mx, sx, my, beta)


def select_from_folds(blocks, y, patients):
    """Each block holds only interpolation outputs from its training-only plan.

    Every sample must appear once in validation, never in its fitting block.
    Plan selection itself belongs to the source backend and is re-executed by
    the runner for each training slice before these records are constructed.
    """
    y = validate(y, patients=patients)
    patients = np.asarray(patients, dtype=str)
    predictions = np.full((len(OPTIONS), *y.shape), np.nan)
    seen = np.zeros(len(y), dtype=int)
    for block in blocks:
        tr, va = np.asarray(block['train'], int), np.asarray(block['validation'], int)
        if len(set(tr)) != len(tr) or len(set(va)) != len(va) or set(tr) & set(va):
            raise ValueError("Invalid fold row identities")
        if set(patients[tr]) & set(patients[va]):
            raise ValueError("Patient/group crosses a fold")
        seen[va] += 1
        for i, option in enumerate(OPTIONS):
            m = fit(block['fit_interpolation'], y[tr], patients[tr], option)
            predictions[i, va] = m.predict(block['validation_interpolation'])
    if not np.all(seen == 1) or not np.isfinite(predictions).all():
        raise ValueError("Incomplete or repeated OOF predictions")
    scores = [float(group_target_risks(y, p, patients).mean()) for p in predictions]
    selected = min(range(len(OPTIONS)), key=lambda i: (scores[i], i))
    return OPTIONS[selected], scores, predictions
