"""Three fixed 64-well allocation policies and one weighted ridge predictor."""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
import numpy as np

from methods import patient_weights


LAMBDAS = (0.01, 0.1, 1.0, 10.0)
ALLOCATION_FAMILIES = ("broad_drugwise", "complete_support_then_fill", "joint_native_greedy")


@dataclass
class LibraryDescriptor:
    library_id: str
    query_ids: np.ndarray
    target_ids: np.ndarray
    query_target_indices: np.ndarray
    weights: np.ndarray
    recoverable: np.ndarray
    supports: tuple

    def exact_targets(self, selected):
        selected = set(selected)
        return np.asarray([bool(self.recoverable[j]) and support is not None and len(support) > 0 and set(support).issubset(selected) for j, support in enumerate(self.supports)], dtype=bool)


def descriptor_from_manifest(pool, library_id):
    queries = sorted(pool["queries"], key=lambda item: item["query_index"])
    targets = sorted(pool["targets"], key=lambda item: item["target_index"])
    if [item["query_index"] for item in queries] != list(range(len(queries))) or [item["target_index"] for item in targets] != list(range(len(targets))):
        raise ValueError("Noncanonical action or target indices")
    query_ids = np.asarray([item["query_id"] for item in queries], dtype=str)
    target_ids = np.asarray([item["drug_id"] for item in targets], dtype=str)
    if len(set(query_ids)) != len(queries) or len(set(target_ids)) != len(targets):
        raise ValueError("Duplicate query or target identity")
    lookup = {query_id: index for index, query_id in enumerate(query_ids)}
    query_targets = np.asarray([item["target_index"] for item in queries], dtype=int)
    if any(item["treatment_well_cost"] != 2 or not 0 <= item["target_index"] < len(targets) or item["drug_id"] != target_ids[item["target_index"]] for item in queries):
        raise ValueError("Invalid paired-well cost or target mapping")
    weights = np.zeros((len(targets), len(queries)))
    supports, recoverable = [], []
    for target in targets:
        j = target["target_index"]
        details = target["by_library"][library_id]
        nodes = details.get("support_nodes", [])
        native_weights = np.asarray([node["auc_weight"] for node in nodes], dtype=float)
        valid = len(nodes) > 0 and np.isfinite(native_weights).all() and np.all(native_weights > 0) and abs(native_weights.sum() - 1.0) <= 1e-12
        available = valid and all(node.get("query_id") in lookup for node in nodes)
        declared = bool(details.get("fully_computable_from_common_pool", False))
        if declared != available:
            raise ValueError("Native support availability declaration is inconsistent")
        seen = set()
        for node in nodes:
            query_id = node.get("query_id")
            if query_id is None:
                continue
            if query_id not in lookup or query_id in seen:
                raise ValueError("Unknown or repeated query in native support")
            index = lookup[query_id]
            if query_targets[index] != j:
                raise ValueError("Native support belongs to another target")
            seen.add(query_id)
            weights[j, index] = float(node["auc_weight"])
        supports.append(tuple(sorted(lookup[node["query_id"]] for node in nodes)) if available else None)
        recoverable.append(available)
    return LibraryDescriptor(library_id, query_ids, target_ids, query_targets, weights, np.asarray(recoverable, dtype=bool), tuple(supports))


@dataclass
class SparseContext:
    mean_x: np.ndarray
    scale_x: np.ndarray
    mean_y: np.ndarray
    cxx: np.ndarray
    cxy: np.ndarray
    cyy: np.ndarray
    weights: np.ndarray
    query_ids: np.ndarray
    target_ids: np.ndarray


def fit_sparse_context(x, y, patients, query_ids, target_ids):
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    if x.ndim != 2 or y.ndim != 2 or len(x) != len(y) or len(patients) != len(x) or not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ValueError("Malformed or nonfinite aligned TRAIN matrices")
    if x.shape[1] != len(query_ids) or y.shape[1] != len(target_ids):
        raise ValueError("TRAIN feature/target identities disagree")
    weights = patient_weights(np.asarray(patients, dtype=str))
    normalized = weights / weights.sum()
    mean_x, mean_y = normalized @ x, normalized @ y
    scale = np.maximum(np.sqrt(normalized @ (x - mean_x) ** 2), 0.05)
    z, centered = (x - mean_x) / scale, y - mean_y
    return SparseContext(mean_x, scale, mean_y, (z.T * normalized) @ z, (z.T * normalized) @ centered, (centered.T * normalized) @ centered, weights, np.asarray(query_ids, dtype=str), np.asarray(target_ids, dtype=str))


class PlanningState:
    """Incremental Schur calculations for the declared raw-AUC trace surrogate."""

    def __init__(self, context, descriptor, lam):
        self.descriptor = descriptor
        self.xx = context.cxx.copy() + float(lam) * np.eye(len(context.query_ids))
        self.xy = context.cxy.copy()
        self.diag_y = np.diag(context.cyy).copy()
        self.selected = set()

    def phi(self):
        exact = self.descriptor.exact_targets(self.selected)
        return float(np.where(exact, 0.0, np.maximum(self.diag_y, 0.0)).mean())

    def value_after(self, added):
        added = tuple(sorted(set(added) - self.selected))
        if not added:
            return self.phi()
        block = self.xx[np.ix_(added, added)]
        cross = self.xy[list(added)]
        updated = self.diag_y - np.sum(cross * np.linalg.solve(block, cross), axis=0)
        exact = self.descriptor.exact_targets(self.selected.union(added))
        return float(np.where(exact, 0.0, np.maximum(updated, 0.0)).mean())

    def candidate_point_values(self):
        variance = np.maximum(np.diag(self.xx), 1e-15)
        residuals = np.maximum(self.diag_y[None, :] - self.xy ** 2 / variance[:, None], 0.0)
        residuals[:, self.descriptor.exact_targets(self.selected)] = 0.0
        for j, support in enumerate(self.descriptor.supports):
            if self.descriptor.recoverable[j] and support:
                missing = set(support) - self.selected
                if len(missing) == 1:
                    residuals[next(iter(missing)), j] = 0.0
        values = residuals.mean(axis=1)
        if self.selected:
            values[list(self.selected)] = np.inf
        return values

    def add(self, added):
        added = tuple(sorted(set(added) - self.selected))
        if not added:
            raise ValueError("Allocation step adds no new action")
        block = self.xx[np.ix_(added, added)]
        columns = self.xx[:, added].copy()
        cross = self.xy[list(added)].copy()
        solved_x = np.linalg.solve(block, self.xx[list(added), :])
        solved_y = np.linalg.solve(block, cross)
        self.diag_y -= np.sum(cross * solved_y, axis=0)
        self.xy -= columns @ solved_y
        self.xx -= columns @ solved_x
        self.xx = (self.xx + self.xx.T) / 2
        self.xx[list(added), :] = 0.0
        self.xx[:, list(added)] = 0.0
        self.xy[list(added), :] = 0.0
        self.selected.update(added)


def allocate(context, descriptor, family, lam, budget=32):
    if family not in ALLOCATION_FAMILIES or lam not in LAMBDAS:
        raise ValueError("Allocation is outside the frozen three-by-four family")
    if not np.array_equal(context.query_ids, descriptor.query_ids) or not np.array_equal(context.target_ids, descriptor.target_ids):
        raise ValueError("Context and native library descriptor are not aligned")
    if not 0 < budget <= len(context.query_ids):
        raise ValueError("Invalid paired-action budget")
    state, history = PlanningState(context, descriptor, lam), []
    if family == "broad_drugwise":
        choices = []
        for j in range(len(descriptor.target_ids)):
            actions = list(np.flatnonzero(descriptor.query_target_indices == j))
            if not actions:
                continue
            if len(actions) < 2:
                raise ValueError("Broad comparison needs at least two native actions per queryable item")
            best = {}
            for cardinality in (1, 2):
                options = []
                for subset in combinations(actions, cardinality):
                    cross = context.cxy[list(subset), j]
                    residual = float(context.cyy[j, j] - cross @ np.linalg.solve(context.cxx[np.ix_(subset, subset)] + lam * np.eye(cardinality), cross))
                    options.append((residual, tuple(str(descriptor.query_ids[q]) for q in subset), subset))
                best[cardinality] = min(options)
            choices.append({"target_index": j, "single": best[1][2], "pair": best[2][2], "gain": best[1][0] - best[2][0]})
        upgrades = budget - len(choices)
        if not 0 <= upgrades <= len(choices):
            raise ValueError("Broad budget cannot be represented by one or two actions per item")
        ranked = sorted(choices, key=lambda item: (-item["gain"], str(descriptor.target_ids[item["target_index"]])))
        upgraded = {item["target_index"] for item in ranked[:upgrades]}
        for item in choices:
            chosen = item["pair"] if item["target_index"] in upgraded else item["single"]
            state.add(chosen)
            history.append({"stage": "broad_pair" if len(chosen) == 2 else "broad_single", "target_id": str(descriptor.target_ids[item["target_index"]]), "best_single_indices": list(map(int, item["single"])), "best_pair_indices": list(map(int, item["pair"])), "selected_indices": list(map(int, chosen)), "own_target_pair_gain": float(item["gain"])})
    elif family == "complete_support_then_fill":
        while True:
            options = []
            before = state.phi()
            for j, support in enumerate(descriptor.supports):
                if not descriptor.recoverable[j] or not support:
                    continue
                added = tuple(sorted(set(support) - state.selected))
                if not added or len(state.selected) + len(added) > budget:
                    continue
                after = state.value_after(added)
                options.append((-(before - after) / len(added), str(descriptor.target_ids[j]), j, added, after))
            if not options:
                break
            _, _, j, added, after = min(options)
            state.add(added)
            history.append({"stage": "complete_support", "target_id": str(descriptor.target_ids[j]), "added_indices": list(map(int, added)), "surrogate_before": before, "surrogate_after": after})
    while len(state.selected) < budget:
        values = state.candidate_point_values()
        q = min((q for q in range(len(values)) if q not in state.selected), key=lambda q: (values[q], str(descriptor.query_ids[q])))
        before, after = state.phi(), float(values[q])
        state.add((q,))
        history.append({"stage": "joint_point", "added_indices": [int(q)], "surrogate_before": before, "surrogate_after": after})
    selected = tuple(sorted(state.selected))
    if len(selected) != budget:
        raise AssertionError("Allocation failed exact pair accounting")
    exact = descriptor.exact_targets(selected)
    return selected, {"family": family, "lambda": lam, "library_id": descriptor.library_id, "selected_indices": list(map(int, selected)), "query_ids": [str(descriptor.query_ids[q]) for q in selected], "native_exact_target_ids": [str(descriptor.target_ids[j]) for j in np.flatnonzero(exact)], "paired_actions": budget, "treatment_wells": 2 * budget, "final_surrogate_raw_auc_mse": state.phi(), "history": history}


class SparseRidgePredictor:
    def __init__(self, context, selected, lam, descriptor):
        self.selected = tuple(selected)
        if len(self.selected) != 32 or len(set(self.selected)) != 32 or lam not in LAMBDAS:
            raise ValueError("Prediction requires a frozen 32-pair selection and penalty")
        self.mean_x = context.mean_x[list(selected)].copy()
        self.scale_x = context.scale_x[list(selected)].copy()
        self.mean_y = context.mean_y.copy()
        self.beta = np.linalg.solve(context.cxx[np.ix_(selected, selected)] + lam * np.eye(len(selected)), context.cxy[list(selected)])
        self.exact_target_mask = descriptor.exact_targets(selected)
        self.copy_weights = descriptor.weights[:, list(selected)].copy()
        self.library_id, self.lam = descriptor.library_id, lam

    def predict(self, observed_actions):
        observed = np.asarray(observed_actions, dtype=float)
        if observed.ndim != 2 or observed.shape[1] != 32 or not np.isfinite(observed).all():
            raise ValueError("Prediction accepts only 32 finite queried native paired means")
        result = self.mean_y + ((observed - self.mean_x) / self.scale_x) @ self.beta
        exact = self.exact_target_mask
        result[:, exact] = observed @ self.copy_weights[exact].T
        if not np.isfinite(result).all():
            raise ValueError("Nonfinite sparse prediction")
        return result
