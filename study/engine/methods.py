"""Bounded response-panel methods. No data are read by this module.

Prediction interfaces receive only the observed four-column panel, never a
complete held-out response vector. Training weights give each patient mass one.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math

import numpy as np
from scipy.linalg import solve_triangular
from scipy.special import logsumexp
from sklearn.ensemble import GradientBoostingRegressor


METHOD_CONFIGS = {
    "drug_mean": [{}],
    "patient_offset": [{"alpha": x} for x in (0.0, 0.5, 1.0)],
    "patient_knn": [{"k": x} for x in (3, 7, 15)],
    "ridge": [{"lambda": x} for x in (0.01, 0.1, 1.0, 10.0)],
    "gaussian": [{"rank": x} for x in (2, 4, 8, "full")],
    "mixture": [{"rank": r, "eta": e} for r in (2, 4) for e in (0.75, 0.95)],
    "drp_boosting": [{"trees": 100, "depth": 2, "learning_rate": 0.1}],
}


def config_key(config):
    return json.dumps(config, sort_keys=True, separators=(",", ":"))


def patient_weights(patient_ids):
    _, inverse, counts = np.unique(patient_ids, return_inverse=True, return_counts=True)
    return 1.0 / counts[inverse]


def patient_folds(patient_ids, n_splits, salt):
    patients = sorted(set(map(str, patient_ids)), key=lambda p: (hashlib.sha256((salt + "|" + p).encode()).hexdigest(), p))
    if len(patients) < n_splits:
        raise ValueError("Fewer patients than required folds")
    assignment = {p: i % n_splits for i, p in enumerate(patients)}
    fold = np.asarray([assignment[str(p)] for p in patient_ids], dtype=np.int64)
    return fold, assignment


def per_patient_loss(y, prediction, patient_ids, mask=None, absolute=False):
    error = np.abs(prediction - y) if absolute else (prediction - y) ** 2
    if mask is None:
        row_loss = error.mean(axis=1)
    else:
        counts = mask.sum(axis=1)
        if np.any(counts == 0):
            raise ValueError("No target columns remain")
        row_loss = np.where(mask, error, 0.0).sum(axis=1) / counts
    patients = np.asarray(sorted(set(map(str, patient_ids))))
    losses = np.asarray([row_loss[patient_ids == p].mean() for p in patients])
    return patients, losses


def regularized_covariance(covariance, rank):
    d = len(covariance)
    if rank == "full":
        return covariance + np.eye(d) * 0.1
    eigenvalues, vectors = np.linalg.eigh(covariance)
    order = np.argsort(eigenvalues)[::-1][:min(int(rank), d)]
    selected = vectors[:, order]
    low = (selected * np.maximum(eigenvalues[order], 0.0)) @ selected.T
    diagonal = np.maximum(np.diag(covariance - low), 0.1)
    result = low + np.diag(diagonal)
    return (result + result.T) / 2


def normal_log_density(x, mean, covariance):
    lower = np.linalg.cholesky(covariance)
    centered = solve_triangular(lower, (x - mean).T, lower=True, check_finite=False)
    logdet = 2.0 * np.log(np.diag(lower)).sum()
    return -0.5 * (len(mean) * math.log(2.0 * math.pi) + logdet + (centered ** 2).sum(axis=0))


@dataclass
class Context:
    mean: np.ndarray
    scale: np.ndarray
    z: np.ndarray
    patient_ids: np.ndarray
    weights: np.ndarray
    raw_variance: np.ndarray
    covariance: np.ndarray
    drug_ids: np.ndarray
    gaussian_covariances: dict
    mixtures: dict


def fit_context(y, patient_ids, drug_ids, fit_mixtures=True):
    y = np.asarray(y, dtype=np.float64)
    patient_ids = np.asarray(patient_ids, dtype=str)
    drug_ids = np.asarray(drug_ids, dtype=str)
    if not np.isfinite(y).all():
        raise ValueError("Training matrix must be finite")
    weights = patient_weights(patient_ids)
    normalized = weights / weights.sum()
    mean = normalized @ y
    variance = normalized @ (y - mean) ** 2
    scale = np.maximum(np.sqrt(variance), 0.05)
    z = (y - mean) / scale
    covariance = (z.T * normalized) @ z
    context = Context(mean, scale, z, patient_ids, weights, variance, covariance, drug_ids, {}, {})
    for rank in (2, 4, 8, "full"):
        context.gaussian_covariances[str(rank)] = regularized_covariance(covariance, rank)
    if fit_mixtures:
        for config in METHOD_CONFIGS["mixture"]:
            context.mixtures[config_key(config)] = fit_mixture(context, config)
    return context


def fit_mixture(context, config):
    z, weights = context.z, context.weights
    n, d = z.shape
    shared = context.gaussian_covariances[str(config["rank"])]
    eigenvalues, vectors = np.linalg.eigh(context.covariance)
    vector = vectors[:, -1]
    if vector[np.argmax(np.abs(vector))] < 0:
        vector = -vector
    scores = z @ vector
    order = np.argsort(scores, kind="stable")
    position = np.searchsorted(np.cumsum(weights[order]), weights.sum() / 2, side="left")
    median = scores[order[min(position, n - 1)]]
    memberships = np.column_stack((scores <= median, scores > median)).astype(float)
    effective = (memberships.T * weights).sum(axis=1)
    if np.any(effective <= 1e-12):
        return {"means": np.zeros((2, d)), "covariances": np.stack((shared, shared)), "probabilities": np.array([0.5, 0.5]), "iterations": 0, "converged": True, "fallback": "identical_shared_gaussian_empty_initial_component"}
    means = np.asarray([(weights * memberships[:, k]) @ z / effective[k] for k in range(2)])
    covariances = np.stack((shared.copy(), shared.copy()))
    probabilities = (effective + 2.0) / (weights.sum() + 4.0)
    converged = False
    for iteration in range(1, 101):
        logp = np.column_stack([np.log(probabilities[k]) + normal_log_density(z, means[k], covariances[k]) for k in range(2)])
        responsibilities = np.exp(logp - logsumexp(logp, axis=1, keepdims=True))
        weighted = responsibilities * weights[:, None]
        effective = weighted.sum(axis=0)
        new_means = np.asarray([weighted[:, k] @ z / (effective[k] + 5.0) for k in range(2)])
        new_covariances = []
        for k in range(2):
            centered = z - new_means[k]
            local = (centered.T * weighted[:, k]) @ centered / max(effective[k], 1e-12)
            updated = config["eta"] * shared + (1.0 - config["eta"]) * (local + np.eye(d) * 0.1)
            new_covariances.append((updated + updated.T) / 2)
        new_covariances = np.asarray(new_covariances)
        new_probabilities = (effective + 2.0) / (weights.sum() + 4.0)
        change = max(np.max(np.abs(new_means - means)), np.max(np.abs(new_covariances - covariances)), np.max(np.abs(new_probabilities - probabilities)))
        means, covariances, probabilities = new_means, new_covariances, new_probabilities
        if change < 1e-6:
            converged = True
            break
    return {"means": means, "covariances": covariances, "probabilities": probabilities, "iterations": iteration, "converged": converged, "fallback": None}


def panel_rules(context, budget=4):
    d = len(context.drug_ids)
    if d < budget:
        raise ValueError("Panel larger than drug universe")
    # Raw AUC units align the trace objective with the primary MSE.
    raw = context.gaussian_covariances["4"] * np.outer(context.scale, context.scale)
    lexical = sorted(range(d), key=lambda j: str(context.drug_ids[j]))

    def greedy(seed=None):
        remaining_covariance = raw.copy()
        selected = []
        for step in range(budget):
            if step == 0 and seed is not None:
                best = seed
            else:
                values = {j: float(np.dot(remaining_covariance[:, j], remaining_covariance[:, j]) / max(remaining_covariance[j, j], 1e-15)) for j in lexical if j not in selected}
                best_value = max(values.values())
                best = next(j for j in lexical if j in values and values[j] >= best_value - 1e-12)
            selected.append(best)
            column = remaining_covariance[:, best].copy()
            remaining_covariance -= np.outer(column, column) / max(remaining_covariance[best, best], 1e-15)
            remaining_covariance[best, :] = 0.0
            remaining_covariance[:, best] = 0.0
            remaining_covariance = (remaining_covariance + remaining_covariance.T) / 2
        return tuple(sorted(selected))

    rules = {"gaussian_empty": greedy()}
    for j in lexical:
        rules["gaussian_seed:" + str(context.drug_ids[j])] = greedy(j)
    ranked = sorted(lexical, key=lambda j: (-context.raw_variance[j], str(context.drug_ids[j])))
    rules["high_variance"] = tuple(sorted(ranked[:budget]))
    eligible = ranked[:max(budget, math.ceil(d / 2))]
    sd = np.sqrt(np.maximum(np.diag(context.covariance), 0.0))
    denominator = np.outer(sd, sd)
    correlation = np.divide(context.covariance, denominator, out=np.zeros_like(context.covariance), where=denominator > 1e-15)
    correlation = np.clip(correlation, -1.0, 1.0)
    scores = {j: float(np.median([abs(correlation[j, q]) for q in eligible if q != j])) for j in eligible}
    first = min(eligible, key=lambda j: (scores[j], str(context.drug_ids[j])))
    selected = [first]
    while len(selected) < budget:
        candidates = [j for j in eligible if j not in selected]
        distances = {j: min(1.0 - abs(correlation[j, q]) for q in selected) for j in candidates}
        best = min(candidates, key=lambda j: (-distances[j], str(context.drug_ids[j])))
        selected.append(best)
    rules["functional_diversity"] = tuple(sorted(selected))
    return rules


class PanelPredictor:
    """A fitted method for one literal panel; observed data must have only b columns."""

    def __init__(self, context, family, config, panel):
        self.context = context
        self.family = family
        self.config = dict(config)
        self.panel = tuple(panel)
        self.targets = [j for j in range(len(context.drug_ids)) if j not in self.panel]
        self.models = None
        self.beta = None
        if family == "ridge":
            xp = context.z[:, self.panel]
            normalized = context.weights / context.weights.sum()
            self.beta = np.linalg.solve((xp.T * normalized) @ xp + np.eye(len(panel)) * config["lambda"], (xp.T * normalized) @ context.z)
        if family == "drp_boosting":
            self.models = {}
            for j in self.targets:
                model = GradientBoostingRegressor(n_estimators=config["trees"], max_depth=config["depth"], learning_rate=config["learning_rate"], min_samples_leaf=1, subsample=1.0, random_state=0)
                model.fit(context.z[:, self.panel], context.z[:, j], sample_weight=context.weights)
                self.models[j] = model

    def predict(self, observed):
        context, panel = self.context, self.panel
        observed = np.asarray(observed, dtype=np.float64)
        if observed.ndim != 2 or observed.shape[1] != len(panel) or not np.isfinite(observed).all():
            raise ValueError("Prediction accepts only finite observed-panel columns")
        xp = (observed - context.mean[list(panel)]) / context.scale[list(panel)]
        n, d = len(observed), len(context.drug_ids)
        if self.family == "drug_mean":
            zprediction = np.zeros((n, d))
        elif self.family == "patient_offset":
            zprediction = np.repeat((self.config["alpha"] * xp.mean(axis=1))[:, None], d, axis=1)
        elif self.family == "ridge":
            zprediction = xp @ self.beta
        elif self.family == "patient_knn":
            squared = ((xp[:, None, :] - context.z[None, :, panel]) ** 2).sum(axis=2)
            patient_list = sorted(set(context.patient_ids))
            groups = [np.flatnonzero(context.patient_ids == p) for p in patient_list]
            zprediction = np.zeros((n, d))
            for i in range(n):
                representatives = [group[np.argmin(squared[i, group])] for group in groups]
                representatives.sort(key=lambda j: (squared[i, j], str(context.patient_ids[j]), j))
                selected = representatives[:min(self.config["k"], len(representatives))]
                weights = 1.0 / (np.sqrt(squared[i, selected]) + 1e-6)
                zprediction[i] = weights @ context.z[selected] / weights.sum()
        elif self.family == "gaussian":
            covariance = context.gaussian_covariances[str(self.config["rank"])]
            coefficient = np.linalg.solve(covariance[np.ix_(panel, panel)], covariance[list(panel), :])
            zprediction = xp @ coefficient
        elif self.family == "mixture":
            mixture = context.mixtures[config_key(self.config)]
            predictions, logp = [], []
            for mean, covariance, probability in zip(mixture["means"], mixture["covariances"], mixture["probabilities"]):
                observed_covariance = covariance[np.ix_(panel, panel)]
                coefficient = np.linalg.solve(observed_covariance, covariance[list(panel), :])
                predictions.append(mean + (xp - mean[list(panel)]) @ coefficient)
                logp.append(np.log(probability) + normal_log_density(xp, mean[list(panel)], observed_covariance))
            logp = np.column_stack(logp)
            responsibilities = np.exp(logp - logsumexp(logp, axis=1, keepdims=True))
            zprediction = np.sum(np.stack(predictions, axis=1) * responsibilities[:, :, None], axis=1)
        elif self.family == "drp_boosting":
            zprediction = np.zeros((n, d))
            for j, model in self.models.items():
                zprediction[:, j] = model.predict(xp)
        else:
            raise ValueError("Unknown family: " + self.family)
        result = context.mean + context.scale * zprediction
        result[:, list(panel)] = observed
        if not np.isfinite(result).all():
            raise ValueError("Nonfinite prediction")
        return result


def context_diagnostics(context):
    return {key: {k: value[k] for k in ("iterations", "converged", "fallback")} for key, value in context.mixtures.items()}
