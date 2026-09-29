#!/usr/bin/env python3
"""Small structural and algebraic checks on invented data only; no TRAIN load."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time
import traceback

import numpy as np

import evaluate as first
from methods import patient_folds, patient_weights
from coverage_methods import CoverageCatalog, CoveragePredictor, PairedNativePredictor, acquire, acquire_paired, fit_prediction_context, fit_paired_prediction_context, orientation_errors, plan_panel, plan_paired_panel


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    source = Path(__file__).resolve().parent
    pins = {name: first.sha(source / name) for name in ("coverage_methods.py", "coverage_scoring.py", "evaluate_coverage.py", "synthetic_coverage_preflight.py", "synthetic_coverage_scoring.py")}
    first.dump(args.output / "STARTED.json", {"synthetic_only": True, "train_or_lib2_access": False, "code": pins, "unix_time": time.time()})
    checks = []

    def require(condition, name):
        if not bool(condition):
            raise AssertionError(name)
        checks.append(name)

    def rejects(action, name):
        try:
            action()
        except ValueError:
            checks.append(name)
            return
        raise AssertionError(name)

    try:
        rng = np.random.default_rng(130028)
        patients = np.asarray([f"synthetic_patient_{p:02d}" for p in range(12) for _ in range(1 + p % 3)])
        n = len(patients)
        targets = np.asarray([f"synthetic_drug_{j:02d}" for j in range(24)])
        native = np.asarray([f"synthetic_native_{j:03d}" for j in range(96)])
        owner = np.repeat(np.arange(24), 4)
        catalog = CoverageCatalog(native, targets, owner, tuple(str(value) for _ in range(24) for value in (1, 3, 10, 30)))
        y = rng.normal(0.5, 0.14, (n, 24))
        x = np.repeat(y[:, owner, None], 2, axis=2) + rng.normal(0, 0.06, (n, 96, 2))
        x[:, :, 1] += 0.07  # Known plate difference makes a hidden mean observable.
        plan, paired_plan = plan_panel(x, y, patients, catalog), plan_paired_panel(x, y, patients, catalog)
        a, b = acquire(x, plan, "A"), acquire(x, plan, "B")
        chosen = plan["selected_native_indices"]
        plate_a, plate_b = plan["orientation_A_plate_indices"], plan["orientation_B_plate_indices"]
        physical_a = [(q, p) for q, p in zip(chosen, plate_a)]
        physical_b = [(q, p) for q, p in zip(chosen, plate_b)]
        require(len(set(chosen)) == len(physical_a) == len(set(physical_a)) == 64, "single orientation buys exactly 64 distinct native wells")
        require(len(set(physical_b)) == 64 and len(set(physical_a) | set(physical_b)) == 128 and not set(physical_a) & set(physical_b), "complementary layouts are disjoint alternatives totaling 128 recorded wells")
        require(plate_a.count(0) == plate_a.count(1) == plate_b.count(0) == plate_b.count(1) == 32, "each alternative is exactly 32 p1 and 32 p2")
        require(np.array_equal(np.asarray(plate_b), 1 - np.asarray(plate_a)), "orientation B is the exact plate flip")
        scalar_a = np.asarray([[x[i, q, p] for q, p in physical_a] for i in range(n)])
        scalar_b = np.asarray([[x[i, q, p] for q, p in physical_b] for i in range(n)])
        require(np.array_equal(a, scalar_a) and np.array_equal(b, scalar_b), "paid feature is exactly one native cell, not a paired mean")
        require(not np.allclose(a, x[:, chosen].mean(axis=2)), "synthetic fixture exposes illicit paired-mean replacement")
        hidden = np.full_like(x, np.nan)
        for q, plate in physical_a:
            hidden[:, q, plate] = x[:, q, plate]
        require(np.array_equal(acquire(hidden, plan, "A"), a), "candidate acquisition ignores every unpaid cell")
        rejects(lambda: acquire(hidden, plan, "B"), "unpaid alternate orientation cannot be predicted for free")
        context = fit_prediction_context(a, b, y, patients, plan, targets)
        original_weights = patient_weights(patients)
        require(np.array_equal(context.weights[:n], original_weights / 2) and np.array_equal(context.weights[n:], original_weights / 2), "augmentation halves each row mass in each orientation")
        doubled = np.concatenate((patients, patients))
        require(all(abs(context.weights[doubled == pid].sum() - 1) < 3e-16 for pid in set(patients)), "every original patient retains unit total mass")
        normalized = context.weights / context.weights.sum()
        require(np.allclose(context.mean_x, normalized @ np.concatenate((a, b)), atol=1e-15, rtol=0), "centering uses pooled single-cell orientations")
        row_weights = original_weights / original_weights.sum()
        midpoint, half_difference = (a + b) / 2, (a - b) / 2
        centered_midpoint = midpoint - row_weights @ midpoint
        cov_midpoint = (centered_midpoint.T * row_weights) @ centered_midpoint
        second_difference = (half_difference.T * row_weights) @ half_difference
        unscaled_pooled_cov = context.cxx * context.scale_x[:, None] * context.scale_x[None, :]
        require(np.allclose(unscaled_pooled_cov, cov_midpoint + second_difference, atol=2e-16, rtol=0), "pooled single-well covariance equals Cov(midpoint) plus E[half-difference outer product]")
        own_columns = np.flatnonzero(np.asarray(plan["coordinate_target_indices"]) == 0)
        reversed_a, reversed_b = a.copy(), b.copy()
        reversed_a[:, own_columns], reversed_b[:, own_columns] = b[:, own_columns], a[:, own_columns]
        pooled_own = np.concatenate((a[:, own_columns], b[:, own_columns]))
        reversed_own = np.concatenate((reversed_a[:, own_columns], reversed_b[:, own_columns]))
        own_mean, reversed_mean = normalized @ pooled_own, normalized @ reversed_own
        own_cov = ((pooled_own - own_mean).T * normalized) @ (pooled_own - own_mean)
        reversed_cov = ((reversed_own - reversed_mean).T * normalized) @ (reversed_own - reversed_mean)
        require(np.allclose(own_mean, reversed_mean, atol=2e-16, rtol=0) and np.allclose(own_cov, reversed_cov, atol=2e-16, rtol=0), "local orientation reversal preserves own-head pooled moments without extra fits")
        model = CoveragePredictor(context, plan, 0.1)
        prediction = model.predict(a)
        changed = a.copy()
        columns = np.flatnonzero(np.asarray(plan["coordinate_target_indices"]) == 0)
        changed[:, columns] += 2.0
        require(np.array_equal(model.predict(changed)[:, 1:], prediction[:, 1:]), "own-drug prediction has no cross-drug path")
        require(np.all(model.beta[~model.feature_mask.T] == 0), "every off-drug coefficient is exactly zero")
        require(np.array_equal(orientation_errors(np.zeros((1, 24)), np.ones((1, 24)), -np.ones((1, 24))), np.ones((1, 24))), "primary averages alternative losses rather than predictions")
        paired_paid = acquire_paired(x, paired_plan)
        paired_selected = paired_plan["selected_native_indices"]
        require(len(set((q, plate) for q in paired_selected for plate in range(2))) == 64, "matched control buys 64 explicit wells at 32 native doses")
        require(np.array_equal(paired_paid, x[:, paired_selected, :].mean(axis=2)), "paired feature pays for and averages both native wells")
        paired_hidden = np.full_like(x, np.nan)
        paired_hidden[:, paired_selected, :] = x[:, paired_selected, :]
        require(np.array_equal(acquire_paired(paired_hidden, paired_plan), paired_paid), "matched control ignores unpaid wells")
        paired_hidden[0, paired_selected[0], 1] = np.nan
        rejects(lambda: acquire_paired(paired_hidden, paired_plan), "paired control rejects a missing paid replicate")
        paired_context = fit_paired_prediction_context(paired_paid, y, patients, paired_plan, targets)
        require(np.array_equal(paired_context.weights, original_weights), "paired control retains identical patient mass")
        paired_model = PairedNativePredictor(paired_context, paired_plan, 0.1)
        require(np.isfinite(paired_model.predict(paired_paid)).all() and np.all(paired_model.beta[~paired_model.feature_mask.T] == 0), "matched paired predictor is finite and strictly own-drug")
        folds, _ = patient_folds(patients, 5, first.SALT + "|outer")
        require(all(len(set(folds[patients == pid])) == 1 for pid in set(patients)), "whole patients stay in one outer fold")
        for fold in range(5):
            training = folds != fold
            inner, _ = patient_folds(patients[training], 3, first.SALT + f"|inner|{fold}")
            require(all(len(set(inner[patients[training] == pid])) == 1 for pid in set(patients[training])), f"whole patients stay in one inner fold for outer {fold}")
        first.dump(args.output / "CHECKS.json", {"passed": True, "checks": checks, "check_count": len(checks), "synthetic_only": True, "train_or_lib2_access": False, "invented_patients": 12, "invented_pdo": n})
        first.dump(args.output / "MANIFEST.json", {"committed": True, "code": pins, "files": {str(p.relative_to(args.output)): first.sha(p) for p in sorted(args.output.iterdir()) if p.is_file()}})
        print(json.dumps({"passed": True, "checks": len(checks), "output": str(args.output)}))
    except Exception as exc:
        first.dump(args.output / "FAILURE.json", {"failed": True, "message": str(exc), "traceback": traceback.format_exc(), "checks_before_failure": checks, "preserve_first_attempt": True})
        raise


if __name__ == "__main__":
    main()
