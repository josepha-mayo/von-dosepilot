#!/usr/bin/env python3
"""Independent no-refit verification of a completed CPM-BW attempt."""
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
REFERENCE_MEDIAN = {2: 2.772588722239781, 3: 4.731947768750675}
BOOTSTRAP_SEED = 20261004
BOOTSTRAP_REPLICATES = 10000
OPTIONS = [("identity", 0.0)] + [
    (fraction, ridge) for fraction in (0.1, 0.3, 0.6) for ridge in (0.1, 1.0, 10.0)
]


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def patient_risk(predictions, y, patients):
    error = ((predictions[0] - y) ** 2 + (predictions[1] - y) ** 2) / 2.0
    return np.stack([error[patients == patient].mean(0) for patient in np.unique(patients)])


def summarize(predictions, y, patients, folds):
    matrix = patient_risk(predictions, y, patients)
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
                ((predictions[o, patients == patient] - y[patients == patient]) ** 2).mean()
                for patient in np.unique(patients)
            ]))
            for o in (0, 1)
        ],
        "patient": per_patient,
        "target": matrix.mean(0),
    }


def compare(candidate, reference):
    wins = int(np.sum(candidate["patient"] < reference["patient"]))
    losses = int(np.sum(candidate["patient"] > reference["patient"]))
    return {
        "relative_gain": float(1 - candidate["mse"] / reference["mse"]),
        "patient_wins": wins,
        "patient_losses": losses,
        "patient_ties": int(59 - wins - losses),
        "fold_wins": int(sum(a < b for a, b in zip(candidate["folds"], reference["folds"]))),
        "p90_nonworse": bool(candidate["p90"] <= reference["p90"]),
        "orientations": [bool(value < reference["mse"]) for value in candidate["orientations"]],
    }


def require_close(actual, expected, message, tolerance=1e-15):
    require(abs(float(actual) - float(expected)) <= tolerance, message)


def weighted_median_direct(values, weights, first, second):
    rows = sorted(zip(values, first, second, weights), key=lambda row: (row[0], row[1], row[2]))
    halfway = sum(row[3] for row in rows) / 2.0
    cumulative = 0.0
    for value, _, _, weight in rows:
        cumulative += weight
        if cumulative >= halfway:
            return float(value)
    raise ValueError("WEIGHTED_MEDIAN")


def recompute_bandwidths(model):
    z = model["z_training"]
    weights = model["weights"]
    owner = model["kernel_owner"]
    patients = model["kernel_fitting_patient_ids"].astype(str)
    medians, bandwidths = [], []
    for target in range(24):
        group = np.flatnonzero(owner == target)
        values, pair_weights, first, second = [], [], [], []
        for i in range(len(z)):
            for k in range(i + 1, len(z)):
                if patients[i] == patients[k]:
                    continue
                difference = z[i, group] - z[k, group]
                values.append(float(difference @ difference))
                pair_weights.append(float(weights[i] * weights[k]))
                first.append(i)
                second.append(k)
        median = weighted_median_direct(values, pair_weights, first, second)
        medians.append(median)
        bandwidths.append(0.7 * np.sqrt(median / REFERENCE_MEDIAN[len(group)]))
    return np.asarray(medians), np.asarray(bandwidths)


def raw_cross(query, model, bandwidths):
    training = model["z_training"]
    owner = model["kernel_owner"]
    result = query @ training.T
    for target in range(24):
        group = np.flatnonzero(owner == target)
        a, b = query[:, group], training[:, group]
        distance = np.maximum(
            (a * a).sum(1)[:, None] + (b * b).sum(1)[None, :] - 2 * a @ b.T,
            0.0,
        )
        result += len(group) * np.exp(
            -distance / (2 * len(group) * bandwidths[target] ** 2)
        )
    return result


def reconstruct(query_paid, model, bandwidths):
    query = (query_paid - model["mean_x"]) / model["scale_x"]
    base = model["mean_y"] + query @ model["beta"]
    raw = raw_cross(query, model, bandwidths)
    centered = (
        raw - (raw @ model["weights"])[:, None]
        - model["train_kernel_mean"][None, :] + float(model["kernel_grand"])
    )
    return base + centered @ model["dual_coefficients"]


def verify(attempt, cache, r18):
    attempt, cache, r18 = Path(attempt), Path(cache), Path(r18)
    require(sha(cache) == CACHE_SHA256, "TRAIN_CACHE_HASH")
    require(sha(r18) == R18_SHA256, "R18_HASH")
    result = json.loads((attempt / "RESULT.json").read_text())
    commitment = json.loads((attempt / "PREDICTIONS_COMMITTED.json").read_text())
    prediction_path = attempt / "predictions_private.npz"
    require(commitment["created_before_r18_access"] is True, "COMMITMENT_ORDER")
    require(commitment["prediction_sha256"] == sha(prediction_path), "PREDICTION_HASH")
    require(result["prediction_sha256"] == sha(prediction_path), "RESULT_PREDICTION_HASH")
    with np.load(prediction_path, allow_pickle=False) as source:
        predictions = {
            name: source[name].copy()
            for name in ("cross_patient_median", "bandwidth07", "additive", "r13")
        }
        y = source["y"].copy()
        patients = source["patients"].astype(str)
        folds = source["folds"].copy()
        sample_ids = source["sample_ids"].copy()
        drug_ids = source["drug_ids"].astype(str)
        library_ids = source["library_ids"].astype(str)
    require(y.shape == (119, 24) and len(set(patients)) == 59, "DENOMINATOR")
    require(all(value.shape == (2, 119, 24) for value in predictions.values()), "PREDICTION_SHAPE")
    require(all(np.isfinite(value).all() for value in predictions.values()), "PREDICTION_FINITE")
    with np.load(cache, allow_pickle=False) as source:
        require(np.array_equal(source["y"], y), "CACHE_Y")
        require(np.array_equal(source["sample_ids"], sample_ids), "CACHE_SAMPLES")
        require(np.array_equal(source["patient_ids"].astype(str), patients), "CACHE_PATIENTS")
        require(np.array_equal(source["drug_ids"].astype(str), drug_ids), "CACHE_DRUGS")
        require(np.array_equal(source["library_ids"].astype(str), library_ids), "CACHE_LIBRARY")
        x = source["x"].copy()
        well_ids = source["well_ids"].astype(str)
    with np.load(r18, allow_pickle=False) as source:
        for key, expected in (
            ("y", y), ("sample_ids", sample_ids), ("patient_ids", patients),
            ("drug_ids", drug_ids), ("library_ids", library_ids), ("folds", folds),
        ):
            require(np.array_equal(source[key], expected), "R18_IDENTITY_" + key.upper())
        predictions["r18"] = np.stack((source["candidate_A"], source["candidate_B"]))

    summaries = {name: summarize(value, y, patients, folds) for name, value in predictions.items()}
    for name, expected in EXPECTED.items():
        require(abs(summaries[name]["mse"] - expected) <= 1e-12, "CONTROL_" + name.upper())
        require(abs(result["metrics"][name]["mse"] - summaries[name]["mse"]) <= 1e-15,
                "RESULT_METRIC_" + name.upper())
    for name, summary in summaries.items():
        recorded = result["metrics"][name]
        require_close(recorded["mse"], summary["mse"], "METRIC_MSE_" + name.upper())
        require_close(recorded["p90_rmse"], summary["p90"], "METRIC_P90_" + name.upper())
        require(np.allclose(recorded["fold_mse"], summary["folds"], rtol=0.0, atol=1e-15),
                "METRIC_FOLDS_" + name.upper())
        require(np.allclose(recorded["orientation_mse"], summary["orientations"], rtol=0.0, atol=1e-15),
                "METRIC_ORIENTATIONS_" + name.upper())
        target = np.asarray([recorded["target_mse"][key] for key in drug_ids])
        require(np.allclose(target, summary["target"], rtol=0.0, atol=1e-15),
                "METRIC_TARGETS_" + name.upper())
    candidate = summaries["cross_patient_median"]
    require(abs(result["metrics"]["cross_patient_median"]["mse"] - candidate["mse"]) <= 1e-15,
            "CANDIDATE_MSE")
    comparisons = {}
    for name in ("bandwidth07", "additive", "r13", "r18"):
        reference = summaries[name]
        comparison = compare(candidate, reference)
        recorded = result["comparisons"][name]
        require(abs(recorded["relative_gain"] - comparison["relative_gain"]) <= 1e-15,
                "GAIN_" + name.upper())
        for key in ("patient_wins", "patient_losses", "patient_ties", "fold_wins", "p90_nonworse"):
            require(recorded[key] == comparison[key], "COMPARISON_" + name.upper() + "_" + key.upper())
        require(recorded["orientation_below_reference_expected_mse"] == comparison["orientations"],
                "ORIENTATION_" + name.upper())
        comparisons[name] = comparison
    for name in ("additive", "r13", "r18"):
        comparison = compare(summaries["bandwidth07"], summaries[name])
        recorded = result["bandwidth07_control_comparisons"][name]
        require_close(recorded["relative_gain"], comparison["relative_gain"],
                      "BW_CONTROL_GAIN_" + name.upper())
        for key in ("patient_wins", "patient_losses", "patient_ties", "fold_wins", "p90_nonworse"):
            require(recorded[key] == comparison[key], "BW_CONTROL_" + name.upper() + "_" + key.upper())
    maximum_difference = float(np.max(np.abs(
        predictions["cross_patient_median"] - predictions["bandwidth07"]
    )))
    equivalent = maximum_difference <= 1e-12
    immediate = comparisons["bandwidth07"]
    immediate_pass = (
        immediate["relative_gain"] > 0 and immediate["patient_wins"] >= 30
        and immediate["fold_wins"] == 5 and immediate["p90_nonworse"] and not equivalent
    )
    historical_pass = all(
        comparisons[name]["relative_gain"] >= 0.05
        and comparisons[name]["patient_wins"] >= 40
        and comparisons[name]["fold_wins"] >= 4
        and comparisons[name]["p90_nonworse"]
        and all(comparisons[name]["orientations"])
        for name in ("r13", "r18")
    )
    promoted = immediate_pass and historical_pass
    expected_immediate = {
        "strictly_lower_mse": immediate["relative_gain"] > 0,
        "patient_wins_at_least_30": immediate["patient_wins"] >= 30,
        "all_five_folds_favorable": immediate["fold_wins"] == 5,
        "p90_nonworse": immediate["p90_nonworse"],
        "not_prediction_equivalent": not equivalent,
    }
    require(result["immediate_gate"] == expected_immediate, "IMMEDIATE_GATE_FIELDS")
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
    require(result["historical_gate"] == expected_historical, "HISTORICAL_GATE_FIELDS")
    require(result["all_gates_passed"] is promoted, "FINAL_GATE")
    require(result["decision"] == ("PROMOTE" if promoted else "REJECT_RETAIN_BANDWIDTH07"),
            "DECISION")
    require(result["protected_response_access"] is False, "PROTECTED_BOUNDARY")
    delta = candidate["patient"] - summaries["bandwidth07"]["patient"]
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    sampled = delta[rng.integers(0, len(delta), size=(BOOTSTRAP_REPLICATES, len(delta)))].mean(1)
    bootstrap = result["bootstrap_vs_bandwidth07"]
    require_close(bootstrap["point"], delta.mean(), "BOOTSTRAP_POINT")
    require_close(bootstrap["lower_2_5pct"], np.quantile(sampled, 0.025), "BOOTSTRAP_LOWER")
    require_close(bootstrap["upper_97_5pct"], np.quantile(sampled, 0.975), "BOOTSTRAP_UPPER")

    # Reload every outer model and reconstruct held-patient predictions without fitting.
    for fold in range(5):
        folder = attempt / f"outer_{fold:02}"
        plan = json.loads((folder / "plan.json").read_text())
        native = np.asarray(plan["selected_native_indices"], dtype=int)
        require(len(native) == 64 and len(set(native.tolist())) == 64, "PLAN_64_" + str(fold))
        held = np.flatnonzero(folds == fold)
        selection = json.loads((folder / "selection.json").read_text())
        with np.load(folder / "inner_predictions_private.npz", allow_pickle=False) as inner:
            for name in ("cross_patient_median", "bandwidth07", "additive"):
                score = [float(patient_risk(item, inner["y"], inner["patients"].astype(str)).mean())
                         for item in inner[name]]
                require(np.allclose(score, selection["inner_scores"][name], rtol=0.0, atol=1e-15),
                        "INNER_SCORE_" + name.upper() + "_" + str(fold))
                selected = min(range(10), key=lambda index: (score[index], index))
                require(list(OPTIONS[selected]) == selection["selected"][name],
                        "INNER_SELECTION_" + name.upper() + "_" + str(fold))
        for name in ("cross_patient_median", "bandwidth07"):
            with np.load(folder / (name + "_model_private.npz"), allow_pickle=False) as archive:
                model = {key: archive[key].copy() for key in archive.files}
            if name == "cross_patient_median":
                medians, bandwidths = recompute_bandwidths(model)
                require(np.allclose(medians, model["kernel_group_distance_medians"], rtol=0.0, atol=1e-14),
                        "BANDWIDTH_MEDIANS_" + str(fold))
                require(np.allclose(bandwidths, model["kernel_group_bandwidth_multipliers"], rtol=0.0, atol=1e-14),
                        "BANDWIDTH_VALUES_" + str(fold))
            else:
                bandwidths = np.full(24, 0.7)
            for orientation_index, orientation in enumerate(("A", "B")):
                plates = np.asarray(plan[f"orientation_{orientation}_plate_indices"], dtype=int)
                require((plates == 0).sum() == 32 and (plates == 1).sum() == 32,
                        "PLATE_BALANCE_" + str(fold) + orientation)
                paid = x[held][:, native, plates]
                wells = well_ids[held][:, native, plates]
                require(all(len(set(row)) == 64 for row in wells), "PHYSICAL_WELLS_" + str(fold))
                rebuilt = reconstruct(paid, model, bandwidths)
                require(np.allclose(rebuilt, predictions[name][orientation_index, held], rtol=0.0, atol=1e-12),
                        "RECONSTRUCT_" + name.upper() + "_" + str(fold) + orientation)
    return {
        "status": "PASS",
        "decision": result["decision"],
        "candidate_mse": candidate["mse"],
        "bandwidth07_mse": summaries["bandwidth07"]["mse"],
        "patient_wins_vs_bandwidth07": comparisons["bandwidth07"]["patient_wins"],
        "fold_wins_vs_bandwidth07": comparisons["bandwidth07"]["fold_wins"],
        "p90_nonworse_vs_bandwidth07": comparisons["bandwidth07"]["p90_nonworse"],
        "prediction_sha256": sha(prediction_path),
        "private_arrays_read": True,
        "protected_response_access": False,
        "fit_routine_called": False,
        "outer_models_reconstructed": 10,
        "inner_selections_recomputed": 15,
        "group_bandwidth_vectors_recomputed": 5,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--r18", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    result = verify(arguments.attempt, arguments.cache, arguments.r18)
    text = json.dumps(result, indent=2, allow_nan=False) + "\n"
    if arguments.output:
        with arguments.output.open("x") as stream:
            stream.write(text)
    print(text, end="")


if __name__ == "__main__":
    main()
