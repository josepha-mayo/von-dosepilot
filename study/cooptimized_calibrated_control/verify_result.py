#!/usr/bin/env python3
"""Independent no-refit arithmetic and budget audit of one completed result."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import numpy as np


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def risks(prediction, y, patients):
    error = ((prediction[0] - y) ** 2 + (prediction[1] - y) ** 2) / 2
    return np.stack([error[patients == p].mean(0) for p in np.unique(patients)])


def metric(prediction, y, patients, folds):
    r = risks(prediction, y, patients); p = r.mean(1)
    pf = np.array([folds[np.flatnonzero(patients == q)[0]] for q in np.unique(patients)])
    return {"mse": float(p.mean()), "p90_rmse": float(np.quantile(np.sqrt(p), .9)),
            "fold_mse": [float(p[pf == f].mean()) for f in range(5)],
            "orientation_mse": [float(np.mean([((prediction[o, patients == q] - y[patients == q]) ** 2).mean()
                                                  for q in np.unique(patients)])) for o in (0, 1)],
            "target_mse": r.mean(0)}


def close(a, b, atol=1e-15):
    if not np.allclose(np.asarray(a, float), np.asarray(b, float), rtol=0, atol=atol):
        raise ValueError(f"Arithmetic mismatch: {a!r} != {b!r}")


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--attempt", type=Path, required=True)
    args = parser.parse_args(); root = args.attempt
    result = json.loads((root / "RESULT.json").read_text())
    committed = json.loads((root / "PREDICTIONS_COMMITTED.json").read_text())
    if committed["prediction_sha256"] != sha(root / "predictions_private.npz"):
        raise ValueError("Committed prediction hash mismatch")
    with np.load(root / "predictions_private.npz", allow_pickle=False) as z:
        prediction = {k: z[k].copy() for k in ("cooptimized", "raw_optimized", "calibrated_original")}
        y, patients, folds, targets = z["y"].copy(), z["patients"].astype(str), z["folds"].copy(), z["drug_ids"].astype(str)
    if y.shape != (119, 24) or len(np.unique(patients)) != 59 or set(folds) != set(range(5)):
        raise ValueError("Task denominator changed")
    for name, pred in prediction.items():
        if pred.shape != (2, 119, 24) or not np.isfinite(pred).all():
            raise ValueError("Incomplete prediction: " + name)
        m = metric(pred, y, patients, folds); recorded = result["metrics"][name]
        close(m["mse"], recorded["mse"]); close(m["p90_rmse"], recorded["p90_rmse"])
        close(m["fold_mse"], recorded["fold_mse"]); close(m["orientation_mse"], recorded["orientation_mse"])
        close(m["target_mse"], [recorded["target_mse"][t] for t in targets])
    for fold in range(5):
        plan = json.loads((root / f"outer_{fold:02d}" / "candidate_plan.json").read_text())
        selected, owners = plan["selected_native_indices"], np.asarray(plan["coordinate_target_indices"])
        a, b = np.asarray(plan["orientation_A_plate_indices"]), np.asarray(plan["orientation_B_plate_indices"])
        counts = np.bincount(owners, minlength=24)
        if len(selected) != 64 or len(set(selected)) != 64 or (counts == 2).sum() != 8 or (counts == 3).sum() != 16:
            raise ValueError("64-well ownership failure")
        if (a == 0).sum() != 32 or not np.array_equal(b, 1-a):
            raise ValueError("32/32 complementary layout failure")
    incumbent = result["metrics"]["bandwidth07"]
    candidate = result["metrics"]["cooptimized"]
    if not candidate["mse"] > incumbent["mse"] or result["decision"] != "REJECT_RETAIN_BANDWIDTH07":
        raise ValueError("Decision is inconsistent with primary MSE")
    comparison = result["comparisons"]["bandwidth07"]
    if comparison["patient_wins"] != 3 or comparison["patient_losses"] != 56 or comparison["fold_wins"] != 0:
        raise ValueError("Incumbent comparison mismatch")
    if result["regressing_target_count_vs_bandwidth07"] != 22 or result["all_gates_passed"]:
        raise ValueError("Adverse slice or gate mismatch")
    print(json.dumps({"status": "PASS", "no_refit": True, "prediction_sha256": committed["prediction_sha256"],
                      "candidate_mse": candidate["mse"], "incumbent_mse": incumbent["mse"],
                      "patient_wins": 3, "fold_wins": 0, "regressing_targets": 22,
                      "physical_plans_checked": 5, "protected_response_access": False}, indent=2))


if __name__ == "__main__": main()
