"""One TRAIN-only native coverage policy; no file or response source access.

Each deployment orientation purchases 64 individual physical wells at 64
distinct native concentrations. Complementary orientations are alternative
acquisitions, never a free 128-well prediction ensemble.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from itertools import combinations
import numpy as np

from sparse_methods import LAMBDAS, fit_sparse_context


ALLOCATION_ALPHA = 0.1
BUDGET = 64
TARGETS = 24
UPGRADES = 16
ORIENTATIONS = ("A", "B")
PAIRED_BUDGET = 32


@dataclass
class CoverageCatalog:
    native_ids: np.ndarray
    target_ids: np.ndarray
    native_target_indices: np.ndarray
    concentrations: tuple
    library_id: str = "lib1"


def catalog_from_features(features):
    layout = features["layout"]
    old_doses = {q["query_id"]: str(q["concentration_nM"]) for q in features["old"]["pool"]["queries"]}
    doses = tuple(old_doses.get(str(identity), layout.native_concentrations[i]) for i, identity in enumerate(layout.native_ids))
    catalog = CoverageCatalog(layout.native_ids.copy(), layout.target_ids.copy(), layout.native_target_indices.copy(), doses, layout.library_id)
    validate_catalog(catalog)
    return catalog


def validate_catalog(catalog):
    if catalog.library_id != "lib1" or len(catalog.target_ids) != TARGETS:
        raise ValueError("Coverage is restricted to the 24-target Lib1 TRAIN catalog")
    if len(catalog.native_ids) != len(catalog.native_target_indices) or len(catalog.native_ids) != len(catalog.concentrations):
        raise ValueError("Native catalog columns are misaligned")
    if len(set(catalog.native_ids)) != len(catalog.native_ids) or len(set(catalog.target_ids)) != TARGETS:
        raise ValueError("Duplicate native or target identities")
    for target in range(TARGETS):
        native = np.flatnonzero(catalog.native_target_indices == target)
        doses = [Decimal(catalog.concentrations[q]) for q in native]
        if len(native) < 3 or len(set(doses)) != len(doses) or any(not dose.is_finite() or dose <= 0 for dose in doses):
            raise ValueError("Each target needs three distinct positive finite native concentrations")
    if not np.isin(catalog.native_target_indices, np.arange(TARGETS)).all():
        raise ValueError("Native actions map outside the fixed targets")


def subset_orientations(replicates, subset):
    """The two complementary alternating plate layouts for one native subset."""
    values = np.asarray(replicates, dtype=float)
    chosen = values[:, np.asarray(subset, dtype=int), :]
    plates = np.arange(len(subset)) % 2
    return chosen[:, np.arange(len(subset)), plates], chosen[:, np.arange(len(subset)), 1 - plates]


def plan_panel(replicates, y, patients, catalog):
    """Fit best size-2/3 own-drug subsets, then exactly sixteen upgrades."""
    validate_catalog(catalog)
    values, y = np.asarray(replicates, dtype=float), np.asarray(y, dtype=float)
    patients = np.asarray(patients, dtype=str)
    if values.shape != (len(y), len(catalog.native_ids), 2) or y.shape != (len(patients), TARGETS) or not np.isfinite(values).all() or not np.isfinite(y).all():
        raise ValueError("Malformed fitting rows for the single-well allocation")
    doubled_patients = np.concatenate((patients, patients))
    all_scores, choices = [], []
    for target, target_id in enumerate(catalog.target_ids):
        native = sorted(np.flatnonzero(catalog.native_target_indices == target), key=lambda q: (Decimal(catalog.concentrations[q]), str(catalog.native_ids[q])))
        best = {}
        for size in (2, 3):
            options = []
            for subset in combinations(native, size):
                a, b = subset_orientations(values, subset)
                ids = [str(catalog.native_ids[q]) for q in subset]
                context = fit_sparse_context(np.concatenate((a, b)), np.concatenate((y[:, [target]], y[:, [target]])), doubled_patients, ids, [target_id])
                cross = context.cxy[:, 0]
                residual = float(context.cyy[0, 0] - cross @ np.linalg.solve(context.cxx + ALLOCATION_ALPHA * np.eye(size), cross))
                record = {"target_index": target, "target_id": str(target_id), "size": size, "native_indices": list(map(int, subset)), "native_ids": ids, "residual_proxy": residual}
                all_scores.append(record)
                options.append((residual, tuple(ids), tuple(map(int, subset))))
            best[size] = min(options)
        choices.append({"target_index": target, "target_id": str(target_id), "best2": list(best[2][2]), "best3": list(best[3][2]), "proxy2": best[2][0], "proxy3": best[3][0], "upgrade_gain": best[2][0] - best[3][0]})
    ranked = sorted(choices, key=lambda row: (-row["upgrade_gain"], row["target_id"]))
    upgraded = {row["target_index"] for row in ranked[:UPGRADES]}
    upgraded_order = sorted(upgraded, key=lambda target: str(catalog.target_ids[target]))
    upgrade_orientation = {target: position % 2 for position, target in enumerate(upgraded_order)}
    selected, ownership, plates_a = [], [], []
    for target in range(TARGETS):
        subset = choices[target]["best3" if target in upgraded else "best2"]
        start = upgrade_orientation.get(target, 0)
        selected.extend(subset)
        ownership.extend([target] * len(subset))
        plates_a.extend((start + offset) % 2 for offset in range(len(subset)))
    plan = {"library_id": catalog.library_id, "allocation_alpha": ALLOCATION_ALPHA, "selected_native_indices": selected, "selected_native_ids": [str(catalog.native_ids[q]) for q in selected], "coordinate_target_indices": ownership, "selected_concentrations_nM": [str(catalog.concentrations[q]) for q in selected], "orientation_A_plate_indices": plates_a, "orientation_B_plate_indices": [1 - plate for plate in plates_a], "choices": choices, "all_subset_scores": all_scores, "upgraded_target_ids": [str(catalog.target_ids[q]) for q in upgraded_order], "distinct_native_doses": BUDGET, "treatment_wells_per_orientation": BUDGET, "plate_wells_per_orientation": {"p1": 32, "p2": 32}, "exact_auc_count": 0, "prediction_semantics": "raw purchased single-well normalized viability", "primary_orientation_semantics": "equal average of two alternative orientation losses; never average predictions"}
    validate_plan(plan, catalog)
    return plan


def validate_plan(plan, catalog=None):
    selected = plan["selected_native_indices"]
    ownership = np.asarray(plan["coordinate_target_indices"], dtype=int)
    a, b = np.asarray(plan["orientation_A_plate_indices"]), np.asarray(plan["orientation_B_plate_indices"])
    counts = np.bincount(ownership, minlength=TARGETS)
    if len(selected) != BUDGET or len(set(selected)) != BUDGET or ownership.shape != (BUDGET,) or counts.shape != (TARGETS,) or (counts == 2).sum() != 8 or (counts == 3).sum() != 16:
        raise ValueError("Policy must purchase 64 distinct native doses, eight two-dose and sixteen three-dose heads")
    if a.shape != (BUDGET,) or b.shape != (BUDGET,) or not np.isin(a, (0, 1)).all() or not np.array_equal(b, 1 - a) or (a == 0).sum() != 32:
        raise ValueError("Complementary orientations must each buy 32 wells from each plate")
    if catalog is not None:
        if min(selected) < 0 or max(selected) >= len(catalog.native_ids) or not np.array_equal(ownership, catalog.native_target_indices[selected]):
            raise ValueError("Native ownership changed")
        if plan["selected_native_ids"] != list(map(str, catalog.native_ids[selected])):
            raise ValueError("Selected native identities changed")


def plan_paired_panel(replicates, y, patients, catalog):
    """Matched native-dose control: best 1/2 paired means and eight upgrades."""
    validate_catalog(catalog)
    replicates, y = np.asarray(replicates, dtype=float), np.asarray(y, dtype=float)
    if replicates.shape != (len(y), len(catalog.native_ids), 2) or y.shape != (len(patients), TARGETS) or not np.isfinite(replicates).all() or not np.isfinite(y).all():
        raise ValueError("Malformed fitting rows for the matched paired control")
    means = replicates.mean(axis=2)
    all_scores, choices = [], []
    for target, target_id in enumerate(catalog.target_ids):
        native = sorted(np.flatnonzero(catalog.native_target_indices == target), key=lambda q: (Decimal(catalog.concentrations[q]), str(catalog.native_ids[q])))
        best = {}
        for size in (1, 2):
            options = []
            for subset in combinations(native, size):
                ids = [str(catalog.native_ids[q]) for q in subset]
                context = fit_sparse_context(means[:, subset], y[:, [target]], patients, ids, [target_id])
                cross = context.cxy[:, 0]
                residual = float(context.cyy[0, 0] - cross @ np.linalg.solve(context.cxx + ALLOCATION_ALPHA * np.eye(size), cross))
                all_scores.append({"target_index": target, "target_id": str(target_id), "size": size, "native_indices": list(map(int, subset)), "native_ids": ids, "residual_proxy": residual})
                options.append((residual, tuple(ids), tuple(map(int, subset))))
            best[size] = min(options)
        choices.append({"target_index": target, "target_id": str(target_id), "best1": list(best[1][2]), "best2": list(best[2][2]), "proxy1": best[1][0], "proxy2": best[2][0], "upgrade_gain": best[1][0] - best[2][0]})
    upgraded = {row["target_index"] for row in sorted(choices, key=lambda row: (-row["upgrade_gain"], row["target_id"]))[:8]}
    selected, ownership = [], []
    for target in range(TARGETS):
        subset = choices[target]["best2" if target in upgraded else "best1"]
        selected.extend(subset)
        ownership.extend([target] * len(subset))
    plan = {"library_id": catalog.library_id, "allocation_alpha": ALLOCATION_ALPHA, "selected_native_indices": selected, "selected_native_ids": [str(catalog.native_ids[q]) for q in selected], "coordinate_target_indices": ownership, "selected_concentrations_nM": [str(catalog.concentrations[q]) for q in selected], "choices": choices, "all_subset_scores": all_scores, "upgraded_target_ids": sorted(str(catalog.target_ids[q]) for q in upgraded), "distinct_native_doses": 32, "treatment_wells": 64, "exact_auc_count": 0, "prediction_semantics": "each feature is the mean of two explicitly paid native wells"}
    validate_paired_plan(plan, catalog)
    return plan


def validate_paired_plan(plan, catalog=None):
    selected = plan["selected_native_indices"]
    ownership = np.asarray(plan["coordinate_target_indices"], dtype=int)
    counts = np.bincount(ownership, minlength=TARGETS)
    if len(selected) != PAIRED_BUDGET or len(set(selected)) != PAIRED_BUDGET or ownership.shape != (PAIRED_BUDGET,) or counts.shape != (TARGETS,) or (counts == 1).sum() != 16 or (counts == 2).sum() != 8:
        raise ValueError("Matched control requires 24 base pairs plus eight upgrades")
    if catalog is not None:
        if min(selected) < 0 or max(selected) >= len(catalog.native_ids) or not np.array_equal(ownership, catalog.native_target_indices[selected]) or plan["selected_native_ids"] != list(map(str, catalog.native_ids[selected])):
            raise ValueError("Matched paired native ownership or identity changed")


def acquire_paired(replicates, plan):
    validate_paired_plan(plan)
    values = np.asarray(replicates, dtype=float)
    if values.ndim != 3 or values.shape[2] != 2:
        raise ValueError("Paired acquisition requires two native wells per action")
    paid = values[:, plan["selected_native_indices"], :].copy()
    if paid.shape != (len(values), PAIRED_BUDGET, 2) or not np.isfinite(paid).all():
        raise ValueError("All 64 explicitly paid paired-control wells must be finite")
    return paid.mean(axis=2)


def fit_paired_prediction_context(paid, y, patients, plan, target_ids):
    validate_paired_plan(plan)
    return fit_sparse_context(paid, y, patients, plan["selected_native_ids"], target_ids)


def acquire(replicates, plan, orientation):
    """Read only one orientation's 64 paid cells; all other cells may be NaN."""
    if orientation not in ORIENTATIONS:
        raise ValueError("Unknown fixed orientation")
    validate_plan(plan)
    values = np.asarray(replicates, dtype=float)
    if values.ndim != 3 or values.shape[2] != 2:
        raise ValueError("Acquisition requires native-by-plate data")
    native = np.asarray(plan["selected_native_indices"], dtype=int)
    plates = np.asarray(plan[f"orientation_{orientation}_plate_indices"], dtype=int)
    paid = values[:, native, plates].copy()
    if paid.shape != (len(values), BUDGET) or not np.isfinite(paid).all():
        raise ValueError("All 64 paid single-well values must be finite")
    return paid


def fit_prediction_context(paid_a, paid_b, y, patients, plan, target_ids):
    """Symmetric augmentation gives each original patient total mass one."""
    if np.shape(paid_a) != np.shape(paid_b) or np.shape(paid_a) != (len(y), BUDGET):
        raise ValueError("Complementary fitting layouts are misaligned")
    return fit_sparse_context(np.concatenate((paid_a, paid_b)), np.concatenate((y, y)), np.concatenate((patients, patients)), plan["selected_native_ids"], target_ids)


class CoveragePredictor:
    """One shared ridge penalty across 24 strictly own-drug heads."""
    def __init__(self, context, plan, lam):
        validate_plan(plan)
        if lam not in LAMBDAS or list(context.query_ids) != plan["selected_native_ids"] or len(context.target_ids) != TARGETS:
            raise ValueError("Predictor differs from the frozen four-penalty own-drug family")
        self.plan, self.lam = plan, float(lam)
        self.mean_x, self.scale_x, self.mean_y = context.mean_x.copy(), context.scale_x.copy(), context.mean_y.copy()
        self.feature_mask = np.equal(np.arange(TARGETS)[:, None], np.asarray(plan["coordinate_target_indices"])[None, :])
        self.beta = np.zeros((BUDGET, TARGETS))
        for target in range(TARGETS):
            columns = np.flatnonzero(self.feature_mask[target])
            self.beta[columns, target] = np.linalg.solve(context.cxx[np.ix_(columns, columns)] + self.lam * np.eye(len(columns)), context.cxy[columns, target])

    def predict(self, paid):
        paid = np.asarray(paid, dtype=float)
        if paid.ndim != 2 or paid.shape[1] != BUDGET or not np.isfinite(paid).all():
            raise ValueError("Prediction accepts only 64 finite paid values")
        result = self.mean_y + ((paid - self.mean_x) / self.scale_x) @ self.beta
        if not np.isfinite(result).all():
            raise ValueError("Nonfinite own-drug predictions")
        return result

    def arrays(self):
        return {"mean_x": self.mean_x, "scale_x": self.scale_x, "mean_y": self.mean_y, "beta": self.beta, "feature_mask": self.feature_mask, "lambda": np.asarray(self.lam)}


class PairedNativePredictor:
    """Matched own-drug ridge on 32 paid paired means; no exact-target copying."""
    def __init__(self, context, plan, lam):
        validate_paired_plan(plan)
        if lam not in LAMBDAS or list(context.query_ids) != plan["selected_native_ids"] or len(context.target_ids) != TARGETS:
            raise ValueError("Matched predictor differs from the frozen four-penalty family")
        self.plan, self.lam = plan, float(lam)
        self.mean_x, self.scale_x, self.mean_y = context.mean_x.copy(), context.scale_x.copy(), context.mean_y.copy()
        self.feature_mask = np.equal(np.arange(TARGETS)[:, None], np.asarray(plan["coordinate_target_indices"])[None, :])
        self.beta = np.zeros((PAIRED_BUDGET, TARGETS))
        for target in range(TARGETS):
            columns = np.flatnonzero(self.feature_mask[target])
            self.beta[columns, target] = np.linalg.solve(context.cxx[np.ix_(columns, columns)] + self.lam * np.eye(len(columns)), context.cxy[columns, target])

    def predict(self, paid):
        paid = np.asarray(paid, dtype=float)
        if paid.ndim != 2 or paid.shape[1] != PAIRED_BUDGET or not np.isfinite(paid).all():
            raise ValueError("Matched prediction accepts only 32 finite paid paired means")
        result = self.mean_y + ((paid - self.mean_x) / self.scale_x) @ self.beta
        if not np.isfinite(result).all():
            raise ValueError("Nonfinite matched paired prediction")
        return result

    def arrays(self):
        return {"mean_x": self.mean_x, "scale_x": self.scale_x, "mean_y": self.mean_y, "beta": self.beta, "feature_mask": self.feature_mask, "lambda": np.asarray(self.lam)}


def orientation_errors(y, prediction_a, prediction_b, absolute=False):
    """Loss of randomized 64-well deployment; never constructs an ensemble."""
    a, b = np.asarray(prediction_a) - y, np.asarray(prediction_b) - y
    return (np.abs(a) + np.abs(b)) / 2 if absolute else (a ** 2 + b ** 2) / 2
