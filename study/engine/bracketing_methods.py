"""Lossless two-node bracketing with 32 paid native pairs, and no data access.

Allocation sees only supplied fitting rows. Prediction accepts only the 32
purchased native paired means; the coordinate change retains all paid inputs.
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np

from sparse_methods import LAMBDAS, allocate, fit_sparse_context


ALLOCATION_ALPHA = 0.1
PREDICTORS = ("shared_all24", "own_drug_all24")
MISSING_DRUGS = ("Gedatolisib", "Palbociclib")
Q_VALUES = (0.0, 0.25, 0.5, 0.75, 1.0)


@dataclass
class BracketingLayout:
    old_descriptor: object
    native_ids: np.ndarray
    native_target_indices: np.ndarray
    native_concentrations: tuple
    candidates: tuple

    @property
    def target_ids(self):
        return self.old_descriptor.target_ids

    @property
    def library_id(self):
        return self.old_descriptor.library_id


def layout_from_contract(descriptor, contract):
    """Build a numeric-value-free native catalog from the frozen input contract."""
    if tuple(map(float, contract["fixed_q_values"])) != Q_VALUES:
        raise ValueError("The fixed five-position grid changed")
    if tuple(contract["missing_drugs"]) != MISSING_DRUGS:
        raise ValueError("The missing-drug identity/order changed")
    if len(descriptor.query_ids) != 150 or len(descriptor.target_ids) != 24:
        raise ValueError("Original 150-action/24-target contract changed")
    queryable = set(map(int, descriptor.query_target_indices))
    if len(queryable) != 22:
        raise ValueError("Exactly 22 original targets must be queryable")
    native_ids = list(map(str, descriptor.query_ids))
    native_targets = list(map(int, descriptor.query_target_indices))
    concentrations = [None] * 150
    native_lookup = {value: i for i, value in enumerate(native_ids)}
    candidates = []
    for drug in MISSING_DRUGS:
        matches = [i for i, value in enumerate(descriptor.target_ids) if value == drug]
        if len(matches) != 1 or matches[0] in queryable:
            raise ValueError("Missing drug overlaps original queryable targets")
        target = matches[0]
        features = sorted((f for f in contract["features"] if f["drug_id"] == drug), key=lambda f: float(f["q"]))
        if tuple(float(f["q"]) for f in features) != Q_VALUES:
            raise ValueError("A missing drug lacks its exact five positions")
        for feature in features:
            details = feature["by_library"][descriptor.library_id]
            if feature["target_index"] != target or details["native_pair_count"] != 2 or details["treatment_well_count"] != 4:
                raise ValueError("Incorrect candidate target or physical budget")
            nodes = details["nodes"]
            if [n["role"] for n in nodes] != ["lower", "upper"]:
                raise ValueError("Native nodes are not lower/upper ordered")
            if [n["native_action_id"] for n in nodes] != details["native_action_ids"]:
                raise ValueError("Candidate native identities disagree")
            indices = []
            for node in nodes:
                identity = str(node["native_action_id"])
                concentration = str(node["concentration_nM"])
                if identity not in native_lookup:
                    native_lookup[identity] = len(native_ids)
                    native_ids.append(identity)
                    native_targets.append(target)
                    concentrations.append(concentration)
                index = native_lookup[identity]
                if index < 150 or native_targets[index] != target or concentrations[index] != concentration:
                    raise ValueError("Native node has conflicting identities")
                indices.append(index)
            forward = np.asarray(details["forward_matrix_rows_z_then_m_decimal80"], dtype=float)
            inverse = np.asarray(details["inverse_matrix_rows_v_lower_then_v_upper_decimal80"], dtype=float)
            if len(set(indices)) != 2 or forward.shape != (2, 2) or inverse.shape != (2, 2) or not np.allclose(forward @ inverse, np.eye(2), rtol=0, atol=2e-14):
                raise ValueError("The paid two-coordinate map is not invertible")
            candidates.append({"feature_id": feature["feature_id"], "drug_id": drug, "target_index": target, "q": float(feature["q"]), "native_indices": indices, "native_ids": list(details["native_action_ids"]), "coordinate_ids": list(feature["coordinate_order"]), "forward_matrix": forward.tolist(), "inverse_matrix": inverse.tolist()})
    return BracketingLayout(descriptor, np.asarray(native_ids, dtype=str), np.asarray(native_targets, dtype=int), tuple(concentrations), tuple(candidates))


def plan_panel(native_x, y, patients, layout):
    """Select the 28 original pairs and two two-node segments using fitting rows."""
    native_x = np.asarray(native_x, dtype=float)
    y = np.asarray(y, dtype=float)
    if native_x.ndim != 2 or native_x.shape[1] != len(layout.native_ids) or y.shape != (len(native_x), 24):
        raise ValueError("Allocation rows or native/target columns are misaligned")
    old_context = fit_sparse_context(native_x[:, :150], y, patients, layout.old_descriptor.query_ids, layout.target_ids)
    old_selected, old_plan = allocate(old_context, layout.old_descriptor, "broad_drugwise", ALLOCATION_ALPHA, budget=28)
    if layout.old_descriptor.exact_targets(old_selected).any():
        raise ValueError("Unexpected exact AUC in the original 28 native pairs")
    target_counts = np.bincount(layout.old_descriptor.query_target_indices[list(old_selected)], minlength=24)
    if np.sum(target_counts == 1) != 16 or np.sum(target_counts == 2) != 6:
        raise ValueError("Original plan must buy 22 singles and exactly six upgrades")
    selected_candidates, candidate_scores = [], []
    for drug in MISSING_DRUGS:
        options = []
        for candidate in [c for c in layout.candidates if c["drug_id"] == drug]:
            pair = native_x[:, candidate["native_indices"]]
            coordinates = pair @ np.asarray(candidate["forward_matrix"]).T
            target = candidate["target_index"]
            context = fit_sparse_context(coordinates, y[:, [target]], patients, candidate["coordinate_ids"], [drug])
            cross = context.cxy[:, 0]
            score = float(context.cyy[0, 0] - cross @ np.linalg.solve(context.cxx + ALLOCATION_ALPHA * np.eye(2), cross))
            candidate_scores.append({"feature_id": candidate["feature_id"], "drug_id": drug, "q": candidate["q"], "residual_proxy": score, "planning_statistics": {"mean_x": context.mean_x.tolist(), "scale_x": context.scale_x.tolist(), "mean_y": context.mean_y.tolist(), "cxx": context.cxx.tolist(), "cxy": context.cxy.tolist(), "cyy": context.cyy.tolist(), "patient_row_weights": context.weights.tolist()}})
            options.append((score, candidate["q"], candidate))
        selected_candidates.append(min(options, key=lambda item: (item[0], item[1]))[2])
    selected = list(map(int, old_selected))
    coordinate_ids = [str(layout.native_ids[i]) for i in selected]
    coordinate_targets = [int(layout.native_target_indices[i]) for i in selected]
    transform = np.eye(32)
    inverse = np.eye(32)
    for offset, candidate in zip((28, 30), selected_candidates):
        selected.extend(candidate["native_indices"])
        coordinate_ids.extend(candidate["coordinate_ids"])
        coordinate_targets.extend([candidate["target_index"]] * 2)
        transform[offset:offset + 2, offset:offset + 2] = candidate["forward_matrix"]
        inverse[offset:offset + 2, offset:offset + 2] = candidate["inverse_matrix"]
    if len(selected) != 32 or len(set(selected)) != 32 or len(coordinate_ids) != 32 or len(set(coordinate_ids)) != 32:
        raise ValueError("Lossless bracketing plan does not buy 32 distinct pairs")
    if not np.all(np.isin(np.bincount(coordinate_targets, minlength=24), (1, 2))):
        raise ValueError("Every target needs one or two own coordinates")
    return {"library_id": layout.library_id, "allocation_alpha": ALLOCATION_ALPHA, "selected_native_indices": selected, "selected_native_ids": [str(layout.native_ids[i]) for i in selected], "coordinate_ids": coordinate_ids, "coordinate_target_indices": coordinate_targets, "forward_matrix": transform.tolist(), "inverse_matrix": inverse.tolist(), "missing_drug_candidates": selected_candidates, "candidate_scores": candidate_scores, "original_plan": old_plan, "native_pairs": 32, "treatment_wells": 64, "original_upgrade_count": 6, "exact_auc_count": 0}


def acquire(native_x, plan):
    """Select only paid measurements; unpurchased entries need not be finite."""
    values = np.asarray(native_x, dtype=float)
    if values.ndim != 2:
        raise ValueError("Acquisition input must be a native-action matrix")
    paid = values[:, plan["selected_native_indices"]].copy()
    if paid.shape[1] != 32 or not np.isfinite(paid).all():
        raise ValueError("The 32 purchased native paired means must be finite")
    return paid


def encode_paid(paid_native, plan):
    paid = np.asarray(paid_native, dtype=float)
    if paid.ndim != 2 or paid.shape[1] != 32 or not np.isfinite(paid).all():
        raise ValueError("Encoding accepts only 32 finite paid native paired means")
    encoded = paid @ np.asarray(plan["forward_matrix"], dtype=float).T
    if not np.isfinite(encoded).all():
        raise ValueError("Encoded purchased observations are nonfinite")
    return encoded


def fit_prediction_context(paid_native, y, patients, plan, target_ids):
    return fit_sparse_context(encode_paid(paid_native, plan), y, patients, plan["coordinate_ids"], target_ids)


class BracketingPredictor:
    """Fixed shared or own-drug ridge with no hidden truth or exact-AUC copy."""
    def __init__(self, context, plan, lam, family):
        if family not in PREDICTORS or lam not in LAMBDAS or len(context.query_ids) != 32 or len(context.target_ids) != 24:
            raise ValueError("Predictor is outside the two-by-four frozen family")
        if list(context.query_ids) != plan["coordinate_ids"]:
            raise ValueError("Prediction context and paid plan disagree")
        self.plan, self.family, self.lam = plan, family, float(lam)
        self.mean_x, self.scale_x, self.mean_y = context.mean_x.copy(), context.scale_x.copy(), context.mean_y.copy()
        ownership = np.asarray(plan["coordinate_target_indices"], dtype=int)
        self.feature_mask = np.equal(np.arange(24)[:, None], ownership[None, :]) if family == "own_drug_all24" else np.ones((24, 32), dtype=bool)
        self.beta = np.zeros((32, 24))
        if family == "shared_all24":
            self.beta = np.linalg.solve(context.cxx + self.lam * np.eye(32), context.cxy)
        else:
            for target in range(24):
                columns = np.flatnonzero(self.feature_mask[target])
                if len(columns) not in (1, 2):
                    raise ValueError("Own-drug head must use one or two own coordinates")
                self.beta[columns, target] = np.linalg.solve(context.cxx[np.ix_(columns, columns)] + self.lam * np.eye(len(columns)), context.cxy[columns, target])

    def predict(self, paid_native):
        encoded = encode_paid(paid_native, self.plan)
        result = self.mean_y + ((encoded - self.mean_x) / self.scale_x) @ self.beta
        if not np.isfinite(result).all():
            raise ValueError("Nonfinite bracketing prediction")
        return result

    def arrays(self):
        return {"mean_x": self.mean_x, "scale_x": self.scale_x, "mean_y": self.mean_y, "beta": self.beta, "feature_mask": self.feature_mask, "forward_matrix": np.asarray(self.plan["forward_matrix"]), "inverse_matrix": np.asarray(self.plan["inverse_matrix"]), "lambda": np.asarray(self.lam)}
