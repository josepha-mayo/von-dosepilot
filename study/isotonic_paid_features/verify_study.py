#!/usr/bin/env python3
"""Independent no-refit arithmetic audit of an isotonic-feature attempt."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / "cross_patient_bandwidth")]
from run_study import compare, metrics


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("attempt", type=Path)
    args = parser.parse_args()
    result = json.loads((args.attempt / "RESULT.json").read_text())
    committed = json.loads((args.attempt / "PREDICTIONS_COMMITTED.json").read_text())
    prediction_path = args.attempt / "predictions_private.npz"
    if sha(prediction_path) != committed["prediction_sha256"] != result["prediction_sha256"]:
        raise ValueError("Prediction commitment mismatch")
    with np.load(prediction_path, allow_pickle=False) as source:
        required = {"isotonic", "bandwidth07", "r13", "y", "patients", "folds",
                    "sample_ids", "drug_ids", "library_ids"}
        if set(source.files) != required:
            raise ValueError("Private prediction schema changed")
        arrays = {name: source[name] for name in source.files}
    audited = {name: metrics(arrays[name], arrays["y"], arrays["patients"],
                             arrays["folds"], arrays["drug_ids"])
               for name in ("isotonic", "bandwidth07", "r13")}
    for name in audited:
        if abs(audited[name]["mse"] - result["metrics"][name]["mse"]) > 1e-15:
            raise ValueError("MSE mismatch: " + name)
    comparison = compare(arrays["isotonic"], arrays["bandwidth07"],
                         audited["isotonic"], audited["bandwidth07"],
                         arrays["y"], arrays["patients"])
    if comparison != result["comparisons"]["bandwidth07"]:
        raise ValueError("Comparison arithmetic mismatch")
    for fold in range(5):
        plan = json.loads((args.attempt / f"outer_{fold:02}" / "plan.json").read_text())
        if (plan["treatment_wells_per_orientation"] != 64
                or plan["plate_wells_per_orientation"] != {"p1": 32, "p2": 32}):
            raise ValueError("Physical budget mismatch")
    print(json.dumps({"status": "PASS", "prediction_sha256": sha(prediction_path),
                      "candidate_mse": audited["isotonic"]["mse"],
                      "incumbent_mse": audited["bandwidth07"]["mse"],
                      "patient_wins": comparison["patient_wins"],
                      "fold_wins": comparison["fold_wins"]}, indent=2))


if __name__ == "__main__":
    main()
