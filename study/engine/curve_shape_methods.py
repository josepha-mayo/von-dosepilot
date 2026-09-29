"""Fixed curve-shape representation and two bounded predictors; no data I/O."""
from __future__ import annotations

import numpy as np
from sklearn.ensemble import GradientBoostingRegressor


KNOT_FRACTIONS = np.asarray([0.0, 0.25, 0.5, 0.75, 1.0])
CURVE_CONFIGS = {
    "curve_ridge": [{"lambda": value} for value in (0.01, 0.1, 1.0, 10.0)],
    "curve_boosting": [{"trees": 100, "depth": 2, "learning_rate": 0.1}],
}


def interpolate_curve(dose, viability, interval):
    """Five fixed log-dose knots and exact piecewise-linear common-window AUC."""
    dose = np.asarray(dose, dtype=np.float64)
    viability = np.asarray(viability, dtype=np.float64)
    interval = np.asarray(interval, dtype=np.float64)
    if dose.ndim != 1 or viability.shape != dose.shape or len(dose) < 2:
        raise ValueError("A curve requires matching dose/viability vectors")
    if not np.isfinite(dose).all() or not np.isfinite(viability).all() or np.any(dose <= 0):
        raise ValueError("Curve doses must be positive and all values finite")
    if interval.shape != (2,) or not np.isfinite(interval).all() or not 0 < interval[0] < interval[1]:
        raise ValueError("Invalid common concentration interval")
    order = np.argsort(dose, kind="stable")
    dose, viability = dose[order], viability[order]
    if np.any(np.diff(dose) <= 0):
        raise ValueError("Duplicate source concentration in one technical curve")
    if dose[0] > interval[0] or dose[-1] < interval[1]:
        raise ValueError("Common-window boundary is not bracketed; extrapolation forbidden")
    log_dose = np.log(dose)
    lower, upper = np.log(interval)
    knot_locations = lower + KNOT_FRACTIONS * (upper - lower)
    knots = np.interp(knot_locations, log_dose, viability)
    inside = log_dose[(log_dose > lower) & (log_dose < upper)]
    axis = np.concatenate(([lower], inside, [upper]))
    values = np.interp(axis, log_dose, viability)
    auc = np.sum(np.diff(axis) * (values[1:] + values[:-1]) / 2) / (upper - lower)
    return knots, float(auc)


def curve_features(observed_auc, observed_knots, budget=4):
    auc = np.asarray(observed_auc, dtype=np.float64)
    knots = np.asarray(observed_knots, dtype=np.float64)
    if auc.ndim != 2 or auc.shape[1] != budget:
        raise ValueError("Prediction accepts exactly four observed AUC columns")
    if knots.shape != (len(auc), budget, len(KNOT_FRACTIONS)):
        raise ValueError("Prediction accepts only five knots for each of four observed curves")
    if not np.isfinite(auc).all() or not np.isfinite(knots).all():
        raise ValueError("Observed curve inputs must be finite")
    blocks = np.concatenate((auc[:, :, None], knots - auc[:, :, None]), axis=2)
    return blocks.reshape(len(auc), budget * (1 + len(KNOT_FRACTIONS)))


class CurvePanelPredictor:
    """Learns from full TRAIN targets; prediction sees only four measured curves."""

    def __init__(self, context, training_auc, training_knots, family, config, panel):
        training_auc = np.asarray(training_auc, dtype=np.float64)
        training_knots = np.asarray(training_knots, dtype=np.float64)
        if training_auc.shape != context.z.shape or training_knots.shape != (*context.z.shape, 5):
            raise ValueError("Training curve arrays are not aligned with the AUC context")
        if not np.isfinite(training_auc).all() or not np.isfinite(training_knots).all():
            raise ValueError("Training curve inputs must be finite")
        if len(panel) != 4 or len(set(panel)) != 4 or any(j < 0 or j >= training_auc.shape[1] for j in panel):
            raise ValueError("A panel requires four distinct target item indices")
        if family not in CURVE_CONFIGS or config not in CURVE_CONFIGS[family]:
            raise ValueError("Configuration is outside the frozen curve family")
        self.family, self.config, self.panel = family, dict(config), tuple(panel)
        self.drug_ids = context.drug_ids.copy()
        self.target_mean, self.target_scale = context.mean.copy(), context.scale.copy()
        self.targets = [j for j in range(training_auc.shape[1]) if j not in self.panel]
        features = curve_features(training_auc[:, self.panel], training_knots[:, self.panel, :])
        normalized = context.weights / context.weights.sum()
        self.feature_mean = normalized @ features
        self.feature_scale = np.maximum(np.sqrt(normalized @ (features - self.feature_mean) ** 2), 0.05)
        x = (features - self.feature_mean) / self.feature_scale
        self.beta, self.models = None, None
        if family == "curve_ridge":
            self.beta = np.linalg.solve((x.T * normalized) @ x + config["lambda"] * np.eye(x.shape[1]), (x.T * normalized) @ context.z)
        else:
            self.models = {}
            for j in self.targets:
                model = GradientBoostingRegressor(n_estimators=config["trees"], max_depth=config["depth"], learning_rate=config["learning_rate"], min_samples_leaf=1, subsample=1.0, random_state=0)
                model.fit(x, context.z[:, j], sample_weight=context.weights)
                self.models[j] = model

    def predict(self, observed_auc, observed_knots):
        features = curve_features(observed_auc, observed_knots)
        x = (features - self.feature_mean) / self.feature_scale
        if self.family == "curve_ridge":
            standardized = x @ self.beta
        else:
            standardized = np.zeros((len(x), len(self.drug_ids)))
            for j, model in self.models.items():
                standardized[:, j] = model.predict(x)
        prediction = self.target_mean + self.target_scale * standardized
        prediction[:, self.panel] = observed_auc
        if not np.isfinite(prediction).all():
            raise ValueError("Nonfinite prediction")
        return prediction
