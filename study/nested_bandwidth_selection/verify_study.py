#!/usr/bin/env python3
"""Independent no-refit arithmetic audit of the nested-bandwidth replay."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

MULTIPLIERS = (0.7, 1.0, 1.4)
OPTIONS = [("identity", 0.0)] + [
    (fraction, ridge) for fraction in (0.1, 0.3, 0.6) for ridge in (0.1, 1.0, 10.0)
]
EXPECTED = {
    "bandwidth07": 0.0010582750420801538,
    "bandwidth10": 0.001060552730112811,
    "bandwidth14": 0.00106370935859072,
    "r13": 0.001144858681382854,
    "r18": 0.0011414048112341991,
}
BOOTSTRAP_SEED = 20261004
BOOTSTRAP_REPLICATES = 10000


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def require(condition, label):
    if not condition:
        raise ValueError(label)


def patient_target(predictions, y, patients):
    error = ((predictions[0] - y) ** 2 + (predictions[1] - y) ** 2) / 2.0
    return np.stack([error[patients == patient].mean(0)
                     for patient in np.unique(patients)])


def summarize(predictions, y, patients, folds):
    matrix = patient_target(predictions, y, patients)
    per_patient = matrix.mean(1)
    patient_folds = np.asarray([
        folds[np.flatnonzero(patients == patient)[0]] for patient in np.unique(patients)
    ])
    return {
        "mse": float(per_patient.mean()),
        "p90_rmse": float(np.quantile(np.sqrt(per_patient), 0.9)),
        "fold_mse": [float(per_patient[patient_folds == fold].mean()) for fold in range(5)],
        "orientation_mse": [float(np.mean([
            ((predictions[o, patients == patient] - y[patients == patient]) ** 2).mean()
            for patient in np.unique(patients)
        ])) for o in (0, 1)],
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
        "fold_wins": int(sum(a < b for a, b in zip(candidate["fold_mse"], reference["fold_mse"]))),
        "p90_nonworse": bool(candidate["p90_rmse"] <= reference["p90_rmse"]),
        "orientation_below_reference_expected_mse": [
            bool(value < reference["mse"]) for value in candidate["orientation_mse"]
        ],
    }


def choose(scores):
    return min(((mi, oi) for mi in range(3) for oi in range(10)),
               key=lambda pair: (scores[pair[0], pair[1]], pair[0], pair[1]))


def verify(attempt, cache, r18):
    attempt = Path(attempt)
    result = json.loads((attempt / "RESULT.json").read_text())
    prediction_path = attempt / "predictions_private.npz"
    require(result["prediction_sha256"] == sha(prediction_path), "PREDICTION_HASH")
    with np.load(prediction_path, allow_pickle=False) as source:
        arrays = {name: source[name].copy() for name in source.files}
    names = ("nested", "bandwidth07", "bandwidth10", "bandwidth14", "r13")
    predictions = {name: arrays[name] for name in names}
    y = arrays["y"]
    patients = arrays["patients"].astype(str)
    folds = arrays["folds"]
    drug_ids = arrays["drug_ids"].astype(str)
    require(y.shape == (119, 24) and len(np.unique(patients)) == 59, "DENOMINATOR")
    require(all(predictions[name].shape == (2, 119, 24) for name in names), "PREDICTION_SHAPE")
    with np.load(cache, allow_pickle=False) as source:
        require(np.array_equal(source["y"], y), "CACHE_Y")
        require(np.array_equal(source["patient_ids"].astype(str), patients), "CACHE_PATIENTS")
        require(np.array_equal(source["drug_ids"].astype(str), drug_ids), "CACHE_DRUGS")
    with np.load(r18, allow_pickle=False) as source:
        require(np.array_equal(source["y"], y), "R18_Y")
        require(np.array_equal(source["patient_ids"].astype(str), patients), "R18_PATIENTS")
        require(np.array_equal(source["folds"], folds), "R18_FOLDS")
        predictions["r18"] = np.stack((source["candidate_A"], source["candidate_B"]))

    summaries = {name: summarize(value, y, patients, folds)
                 for name, value in predictions.items()}
    for name, expected in EXPECTED.items():
        require(abs(summaries[name]["mse"] - expected) <= 1e-12,
                "CONTROL_" + name.upper())
    for name, summary in summaries.items():
        recorded = result["metrics"][name]
        require(abs(recorded["mse"] - summary["mse"]) <= 1e-15,
                "MSE_" + name.upper())
        require(abs(recorded["p90_rmse"] - summary["p90_rmse"]) <= 1e-15,
                "P90_" + name.upper())
        require(np.allclose(recorded["fold_mse"], summary["fold_mse"], rtol=0, atol=1e-15),
                "FOLDS_" + name.upper())
        require(np.allclose(recorded["orientation_mse"], summary["orientation_mse"],
                            rtol=0, atol=1e-15), "ORIENTATIONS_" + name.upper())
        recorded_targets = np.asarray([recorded["target_mse"][target] for target in drug_ids])
        require(np.allclose(recorded_targets, summary["target"], rtol=0, atol=1e-15),
                "TARGETS_" + name.upper())

    candidate = summaries["nested"]
    for name in ("bandwidth07", "bandwidth10", "bandwidth14", "r13", "r18"):
        actual = compare(candidate, summaries[name])
        recorded = result["comparisons"][name]
        require(abs(actual["relative_gain"] - recorded["relative_gain"]) <= 1e-15,
                "GAIN_" + name.upper())
        for key in ("patient_wins", "patient_losses", "patient_ties", "fold_wins",
                    "p90_nonworse", "orientation_below_reference_expected_mse"):
            require(actual[key] == recorded[key], "COMPARE_" + name.upper() + "_" + key)

    counts = {str(multiplier): 0 for multiplier in MULTIPLIERS}
    for fold in range(5):
        folder = attempt / f"outer_{fold:02d}"
        selection = json.loads((folder / "selection.json").read_text())
        with np.load(folder / "inner_predictions_private.npz", allow_pickle=False) as source:
            inner_predictions = source["predictions"]
            inner_y = source["y"]
            inner_patients = source["patients"].astype(str)
        scores = np.asarray([[patient_target(inner_predictions[mi, oi], inner_y,
                                             inner_patients).mean()
                              for oi in range(10)] for mi in range(3)])
        require(np.allclose(scores, selection["inner_scores"], rtol=0, atol=1e-15),
                "INNER_SCORES_" + str(fold))
        selected = choose(scores)
        require(selection["nested_selected_multiplier"] == MULTIPLIERS[selected[0]],
                "MULTIPLIER_" + str(fold))
        require(selection["nested_selected_option"] == list(OPTIONS[selected[1]]),
                "OPTION_" + str(fold))
        for mi, name in enumerate(("bandwidth07", "bandwidth10", "bandwidth14")):
            fixed = min(range(10), key=lambda oi: (scores[mi, oi], oi))
            require(selection["fixed_selected_options"][name] == list(OPTIONS[fixed]),
                    "FIXED_OPTION_" + name + "_" + str(fold))
        plan = json.loads((folder / "plan.json").read_text())
        native = plan["selected_native_indices"]
        require(len(native) == 64 and len(set(native)) == 64, "PLAN_64_" + str(fold))
        for orientation in ("A", "B"):
            plates = np.asarray(plan[f"orientation_{orientation}_plate_indices"])
            require((plates == 0).sum() == 32 and (plates == 1).sum() == 32,
                    "PLATES_" + str(fold) + orientation)
        counts[str(MULTIPLIERS[selected[0]])] += 1
    require(result["selection_counts"] == counts, "SELECTION_COUNTS")

    delta = candidate["patient"] - summaries["bandwidth07"]["patient"]
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    sampled = delta[rng.integers(0, len(delta),
                                size=(BOOTSTRAP_REPLICATES, len(delta)))].mean(1)
    bootstrap = result["bootstrap_vs_bandwidth07"]
    require(abs(bootstrap["point"] - delta.mean()) <= 1e-15, "BOOTSTRAP_POINT")
    require(abs(bootstrap["lower_2_5pct"] - np.quantile(sampled, 0.025)) <= 1e-15,
            "BOOTSTRAP_LOWER")
    require(abs(bootstrap["upper_97_5pct"] - np.quantile(sampled, 0.975)) <= 1e-15,
            "BOOTSTRAP_UPPER")
    require(result["decision"] == "EVALUATION_ONLY_RETAIN_BANDWIDTH07", "DECISION")
    require(result["protected_response_access"] is False, "PROTECTED_BOUNDARY")
    return {
        "status": "PASS",
        "nested_mse": candidate["mse"],
        "bandwidth07_mse": summaries["bandwidth07"]["mse"],
        "selection_counts": counts,
        "patient_wins_vs_bandwidth07": result["comparisons"]["bandwidth07"]["patient_wins"],
        "fold_wins_vs_bandwidth07": result["comparisons"]["bandwidth07"]["fold_wins"],
        "prediction_sha256": sha(prediction_path),
        "fit_routine_called": False,
        "private_arrays_read": True,
        "protected_response_access": False,
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
