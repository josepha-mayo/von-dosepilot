#!/usr/bin/env python3
"""Independent no-refit audit of a completed simplex-stacking attempt."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


CACHE_SHA256 = "2ccd4995699417db72316c8f403095b8ef560f94913b0c8a80fe7429a2d0cbef"
R18_SHA256 = "253998d20b9425c4ceade4269b94f4ed97cb7039ac5ec60838bb15794d47a6e2"
EXPECTED = {
    "bandwidth07": 0.0010582750420801538,
    "additive": 0.001060552730112811,
    "r13": 0.001144858681382854,
    "r18": 0.0011414048112341991,
}
OPTIONS = [("identity", 0.0)] + [
    (fraction, ridge) for fraction in (0.1, 0.3, 0.6) for ridge in (0.1, 1.0, 10.0)
]
BOOTSTRAP_SEED = 20261004
BOOTSTRAP_REPLICATES = 10000


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def patient_matrix(predictions, truth, patients):
    error = ((predictions[0] - truth) ** 2 + (predictions[1] - truth) ** 2) / 2.0
    return np.stack([error[patients == patient].mean(0) for patient in np.unique(patients)])


def summarize(predictions, truth, patients, folds):
    matrix = patient_matrix(predictions, truth, patients)
    per_patient = matrix.mean(1)
    patient_folds = np.asarray([
        folds[np.flatnonzero(patients == patient)[0]] for patient in np.unique(patients)
    ])
    return {
        "mse": float(per_patient.mean()),
        "p90": float(np.quantile(np.sqrt(per_patient), 0.9)),
        "folds": [float(per_patient[patient_folds == fold].mean()) for fold in range(5)],
        "orientations": [
            float(np.mean([
                ((predictions[o, patients == patient] - truth[patients == patient]) ** 2).mean()
                for patient in np.unique(patients)
            ]))
            for o in (0, 1)
        ],
        "patient": per_patient,
        "target": matrix.mean(0),
    }


def comparison(candidate, reference):
    wins = int(np.sum(candidate["patient"] < reference["patient"]))
    losses = int(np.sum(candidate["patient"] > reference["patient"]))
    return {
        "relative_gain": float(1.0 - candidate["mse"] / reference["mse"]),
        "patient_wins": wins,
        "patient_losses": losses,
        "patient_ties": int(59 - wins - losses),
        "fold_wins": int(sum(a < b for a, b in zip(candidate["folds"], reference["folds"]))),
        "p90_nonworse": bool(candidate["p90"] <= reference["p90"]),
        "orientations": [bool(value < reference["mse"]) for value in candidate["orientations"]],
    }


def inner_geometry(predictions, truth, patients):
    models, orientations, samples, targets = predictions.shape
    identities, inverse, counts = np.unique(patients, return_inverse=True, return_counts=True)
    sample_weight = 1.0 / (len(identities) * counts[inverse])
    weight = np.broadcast_to(
        sample_weight[None, :, None] / (orientations * targets),
        (orientations, samples, targets),
    ).reshape(-1)
    design = np.moveaxis(predictions, 0, -1).reshape(-1, models)
    response = np.broadcast_to(truth[None], (orientations, samples, targets)).reshape(-1)
    return design, response, weight


def audit_simplex(predictions, truth, patients, weights, recorded_loss):
    require(weights.shape == (10,), "STACK_WEIGHT_SHAPE")
    require(np.isfinite(weights).all(), "STACK_WEIGHT_FINITE")
    require(weights.min() >= -1e-11, "STACK_WEIGHT_NONNEGATIVE")
    require(abs(float(weights.sum()) - 1.0) <= 1e-11, "STACK_WEIGHT_SUM")
    design, response, observation_weight = inner_geometry(predictions, truth, patients)
    residual = design @ weights - response
    objective = float(np.sum(observation_weight * residual * residual))
    require(abs(objective - recorded_loss) <= 1e-14, "STACK_OBJECTIVE")
    gram = (design * observation_weight[:, None]).T @ design
    cross = (design * observation_weight[:, None]).T @ response
    gradient = 2.0 * (gram @ weights - cross)
    active = weights > 1e-9
    require(active.any(), "STACK_ACTIVE")
    level = float(np.mean(gradient[active]))
    require(float(np.max(np.abs(gradient[active] - level))) <= 2e-8, "STACK_KKT_ACTIVE")
    require(float(np.min(gradient[~active] - level, initial=0.0)) >= -2e-8, "STACK_KKT_INACTIVE")
    return objective


def raw_cross(query, model):
    training = model["z_training"]
    owner = model["kernel_owner"].astype(int)
    result = query @ training.T
    for target in range(24):
        group = np.flatnonzero(owner == target)
        first, second = query[:, group], training[:, group]
        distance = np.maximum(
            (first * first).sum(1)[:, None] + (second * second).sum(1)[None, :]
            - 2.0 * first @ second.T,
            0.0,
        )
        result += len(group) * np.exp(-distance / (2.0 * len(group) * 0.7 ** 2))
    return result


def reconstruct(paid, model):
    query = (paid - model["mean_x"]) / model["scale_x"]
    base = model["mean_y"] + query @ model["beta"]
    raw = raw_cross(query, model)
    centered = (
        raw - (raw @ model["weights"])[:, None]
        - model["train_kernel_mean"][None, :] + float(model["kernel_grand"])
    )
    return base + centered @ model["dual_coefficients"]


def verify(attempt, cache, r18):
    attempt, cache, r18 = Path(attempt), Path(cache), Path(r18)
    require(sha(cache) == CACHE_SHA256, "CACHE_HASH")
    require(sha(r18) == R18_SHA256, "R18_HASH")
    result = json.loads((attempt / "RESULT.json").read_text())
    commitment = json.loads((attempt / "PREDICTIONS_COMMITTED.json").read_text())
    prediction_path = attempt / "predictions_private.npz"
    require(commitment["created_before_r18_access"] is True, "COMMITMENT_ORDER")
    require(commitment["prediction_sha256"] == sha(prediction_path), "COMMITMENT_HASH")
    require(result["prediction_sha256"] == sha(prediction_path), "RESULT_HASH")
    with np.load(prediction_path, allow_pickle=False) as source:
        predictions = {name: source[name].copy() for name in (
            "simplex_stack", "bandwidth07", "additive", "r13"
        )}
        truth = source["y"].copy()
        patients = source["patients"].astype(str)
        folds = source["folds"].copy()
        sample_ids = source["sample_ids"].copy()
        drug_ids = source["drug_ids"].astype(str)
        library_ids = source["library_ids"].astype(str)
    require(truth.shape == (119, 24) and len(set(patients)) == 59, "DENOMINATOR")
    require(all(value.shape == (2, 119, 24) for value in predictions.values()), "PREDICTION_SHAPE")
    with np.load(cache, allow_pickle=False) as source:
        for key, expected in (
            ("y", truth), ("sample_ids", sample_ids), ("patient_ids", patients),
            ("drug_ids", drug_ids), ("library_ids", library_ids),
        ):
            actual = source[key].astype(str) if key in {"patient_ids", "drug_ids", "library_ids"} else source[key]
            require(np.array_equal(actual, expected), "CACHE_IDENTITY_" + key.upper())
        x = source["x"].copy()
        well_ids = source["well_ids"].astype(str)
    with np.load(r18, allow_pickle=False) as source:
        for key, expected in (
            ("y", truth), ("sample_ids", sample_ids), ("patient_ids", patients),
            ("drug_ids", drug_ids), ("library_ids", library_ids), ("folds", folds),
        ):
            actual = source[key].astype(str) if key in {"patient_ids", "drug_ids", "library_ids"} else source[key]
            require(np.array_equal(actual, expected), "R18_IDENTITY_" + key.upper())
        predictions["r18"] = np.stack((source["candidate_A"], source["candidate_B"]))

    summaries = {name: summarize(value, truth, patients, folds) for name, value in predictions.items()}
    for name, expected in EXPECTED.items():
        require(abs(summaries[name]["mse"] - expected) <= 1e-12, "CONTROL_" + name.upper())
    for name, summary in summaries.items():
        recorded = result["metrics"][name]
        require(abs(recorded["mse"] - summary["mse"]) <= 1e-15, "METRIC_MSE_" + name.upper())
        require(abs(recorded["p90_rmse"] - summary["p90"]) <= 1e-15, "METRIC_P90_" + name.upper())
        require(np.allclose(recorded["fold_mse"], summary["folds"], rtol=0, atol=1e-15), "METRIC_FOLD_" + name.upper())
        require(np.allclose(recorded["orientation_mse"], summary["orientations"], rtol=0, atol=1e-15), "METRIC_ORIENTATION_" + name.upper())
        target = np.asarray([recorded["target_mse"][name] for name in drug_ids])
        require(np.allclose(target, summary["target"], rtol=0, atol=1e-15), "METRIC_TARGET_" + name.upper())

    candidate = summaries["simplex_stack"]
    comparisons = {}
    for name in ("bandwidth07", "additive", "r13", "r18"):
        current = comparison(candidate, summaries[name])
        recorded = result["comparisons"][name]
        for key in ("relative_gain", "patient_wins", "patient_losses", "patient_ties", "fold_wins", "p90_nonworse"):
            if isinstance(current[key], float):
                require(abs(recorded[key] - current[key]) <= 1e-15, "COMPARISON_" + name.upper() + "_" + key.upper())
            else:
                require(recorded[key] == current[key], "COMPARISON_" + name.upper() + "_" + key.upper())
        require(recorded["orientation_below_reference_expected_mse"] == current["orientations"], "COMPARISON_ORIENTATION_" + name.upper())
        comparisons[name] = current
    maximum_difference = float(np.max(np.abs(predictions["simplex_stack"] - predictions["bandwidth07"])))
    equivalent = maximum_difference <= 1e-12
    immediate = comparisons["bandwidth07"]
    expected_immediate = {
        "strictly_lower_mse": immediate["relative_gain"] > 0,
        "patient_wins_at_least_30": immediate["patient_wins"] >= 30,
        "all_five_folds_favorable": immediate["fold_wins"] == 5,
        "p90_nonworse": immediate["p90_nonworse"],
        "not_prediction_equivalent": not equivalent,
    }
    require(result["immediate_gate"] == expected_immediate, "IMMEDIATE_GATE")
    expected_historical = {}
    for name in ("r13", "r18"):
        value = comparisons[name]
        expected_historical[name] = {
            "mse_reduction_at_least_5pct": value["relative_gain"] >= 0.05,
            "patient_wins_at_least_40": value["patient_wins"] >= 40,
            "fold_wins_at_least_4": value["fold_wins"] >= 4,
            "p90_nonworse": value["p90_nonworse"],
            "both_orientation_mse_below_reference_expected_mse": all(value["orientations"]),
        }
    require(result["historical_gate"] == expected_historical, "HISTORICAL_GATE")
    promoted = all(expected_immediate.values()) and all(all(value.values()) for value in expected_historical.values())
    require(result["all_gates_passed"] is promoted, "FINAL_GATE")
    require(result["decision"] == ("PROMOTE_PENDING_INDEPENDENT_REPRODUCTION" if promoted else "REJECT_RETAIN_BANDWIDTH07"), "DECISION")
    require(result["protected_response_access"] is False, "PROTECTED_BOUNDARY")

    delta = candidate["patient"] - summaries["bandwidth07"]["patient"]
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    sampled = delta[rng.integers(0, 59, size=(BOOTSTRAP_REPLICATES, 59))].mean(1)
    bootstrap = result["bootstrap_vs_bandwidth07"]
    for key, expected in (
        ("point", delta.mean()), ("lower_2_5pct", np.quantile(sampled, 0.025)),
        ("upper_97_5pct", np.quantile(sampled, 0.975)),
    ):
        require(abs(bootstrap[key] - expected) <= 1e-15, "BOOTSTRAP_" + key.upper())

    kkt_checks = 0
    reconstruction_checks = 0
    for fold in range(5):
        folder = attempt / f"outer_{fold:02}"
        selection = json.loads((folder / "selection.json").read_text())
        with np.load(folder / "inner_predictions_private.npz", allow_pickle=False) as inner:
            inner_bandwidth = inner["bandwidth07"].copy()
            inner_truth = inner["y"].copy()
            inner_patients = inner["patients"].astype(str)
            saved_weights = inner["stacking_weights"].copy()
            for name in ("bandwidth07", "additive"):
                scores = [float(patient_matrix(item, inner_truth, inner_patients).mean()) for item in inner[name]]
                require(np.allclose(scores, selection["inner_scores"][name], rtol=0, atol=1e-15), "INNER_SCORE_" + name.upper())
                selected = min(range(10), key=lambda index: (scores[index], index))
                require(list(OPTIONS[selected]) == selection["selected"][name], "INNER_SELECTION_" + name.upper())
        require(np.allclose(saved_weights, selection["stacking_weights"], rtol=0, atol=1e-15), "STACK_WEIGHT_RECORD")
        audit_simplex(inner_bandwidth, inner_truth, inner_patients, saved_weights, selection["stacking_inner_mse"])
        kkt_checks += 1

        plan = json.loads((folder / "plan.json").read_text())
        native = np.asarray(plan["selected_native_indices"], dtype=int)
        require(len(native) == 64 and len(set(native.tolist())) == 64, "PLAN_64")
        held = np.flatnonzero(folds == fold)
        with np.load(folder / "simplex_stack_model_private.npz", allow_pickle=False) as archive:
            model = {key: archive[key].copy() for key in archive.files}
        require(abs(float(model["kernel_bandwidth_multiplier"]) - 0.7) <= 1e-15, "MODEL_BANDWIDTH")
        require(np.allclose(model["stacking_weights"], saved_weights, rtol=0, atol=1e-15), "MODEL_STACK_WEIGHTS")
        combined = np.tensordot(saved_weights, model["stacking_component_coefficients"], axes=(0, 0))
        require(np.allclose(combined, model["dual_coefficients"], rtol=0, atol=1e-14), "MODEL_COMBINED_COEFFICIENT")
        for orientation_index, orientation in enumerate(("A", "B")):
            plates = np.asarray(plan[f"orientation_{orientation}_plate_indices"], dtype=int)
            require((plates == 0).sum() == 32 and (plates == 1).sum() == 32, "PLAN_PLATES")
            paid = x[held][:, native, plates]
            require(all(len(set(row)) == 64 for row in well_ids[held][:, native, plates]), "DISTINCT_WELLS")
            rebuilt = reconstruct(paid, model)
            expected = predictions["simplex_stack"][orientation_index, held]
            require(np.allclose(rebuilt, expected, rtol=0, atol=3e-14), "MODEL_RECONSTRUCTION")
            reconstruction_checks += len(held) * 24

    verification = {
        "schema": "dosepilot.simplex_stacking.verification.v1",
        "status": "PASS",
        "decision": result["decision"],
        "candidate_mse": candidate["mse"],
        "incumbent_mse": summaries["bandwidth07"]["mse"],
        "kkt_folds_verified": kkt_checks,
        "held_target_predictions_reconstructed": reconstruction_checks,
        "metric_and_gate_recomputed_without_refit": True,
        "private_arrays_read": True,
        "protected_response_access": False,
    }
    target = attempt / "VERIFICATION.json"
    with target.open("x") as stream:
        json.dump(verification, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps(verification, indent=2))
    return verification


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--r18", type=Path, required=True)
    args = parser.parse_args()
    verify(args.attempt, args.cache, args.r18)


if __name__ == "__main__":
    main()
