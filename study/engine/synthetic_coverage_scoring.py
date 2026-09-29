#!/usr/bin/env python3
"""Generated-only focused checks for the frozen R13 scoring semantics."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import time
import traceback
from types import SimpleNamespace

import numpy as np

import coverage_scoring as score


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    with Path(path).open("x") as f:
        json.dump(value, f, indent=2, sort_keys=True, allow_nan=False)
        f.write("\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    project = Path(__file__).resolve().parents[2]
    pins = {"scoring_sha256": sha(Path(score.__file__)),
            "synthetic_script_sha256": sha(Path(__file__)),
            "protocol_sha256": sha(project / "research/round13_coverage_scoring/PROTOCOL.md")}
    dump(args.output / "STARTED.json", {"unix_time": time.time(), "pins": pins,
        "source": "generated arrays only; no TRAIN or Lib2 numerical input"})
    checks = []

    def check(name, condition, detail=None):
        if not condition:
            raise AssertionError(name + ": " + repr(detail))
        checks.append({"name": name, "passed": True, "detail": detail})

    def near(name, actual, expected, tolerance=2e-15):
        check(name, abs(actual - expected) <= tolerance,
              {"actual": float(actual), "expected": float(expected), "difference": float(abs(actual - expected))})

    try:
        patient_ids = np.array([f"Synthetic{i:02d}" for i in range(59) for _ in range(2 if i < 58 else 3)])
        folds = np.array([int(pid[-2:]) % 5 for pid in patient_ids], dtype=int)
        target_ids = np.array([f"Drug{i:02d}" for i in range(22)] + ["Gedatolisib", "Palbociclib"])
        y = np.zeros((119, 24))
        data = {"y": y, "patient_ids": patient_ids,
                "sample_ids": np.array([f"SyntheticPDO{i:03d}" for i in range(119)]),
                "drug_ids": target_ids, "library_ids": np.full(119, "lib1")}
        catalog = SimpleNamespace(target_ids=target_ids)
        error = ((np.arange(119)[:, None] % 11) + 1) * 0.01 + (np.arange(24)[None, :] % 5) * 0.002
        preds = {"A": error, "B": -error, "matched_paired_native": error * 0.8}
        metrics, contrasts, decision, patient_rows, target_rows, fold_rows = score.summarize(
            data, preds, error * 0.9, folds, catalog)
        ids = sorted(set(patient_ids))
        scalar_patient = []
        for pid in ids:
            rows = np.flatnonzero(patient_ids == pid)
            cell_values = [float(error[row, target]) ** 2 for row in rows for target in range(24)]
            scalar_patient.append(math.fsum(cell_values) / len(cell_values))
        scalar_mean = math.fsum(scalar_patient) / 59
        sorted_rmse = sorted(math.sqrt(x) for x in scalar_patient)
        position = 0.9 * 58
        lo = int(math.floor(position)); hi = int(math.ceil(position))
        scalar_p90 = sorted_rmse[lo] + (position - lo) * (sorted_rmse[hi] - sorted_rmse[lo])
        near("patient_balanced_expected_mse_matches_scalar", metrics["single64_expected_loss"]["all24"]["mse"], scalar_mean)
        near("p90_expected_patient_rmse_matches_scalar", metrics["single64_expected_loss"]["all24"]["p90_patient_rmse"], scalar_p90)
        check("ragged_fixture_distinguishes_record_weighting", abs(scalar_mean - np.mean(error ** 2)) > 1e-6)
        near("opposite_errors_have_zero_mean_prediction_error", float(np.mean(((preds["A"] + preds["B"]) / 2 - y) ** 2)), 0)
        check("loss_of_mean_prediction_would_falsely_win", metrics["single64_expected_loss"]["all24"]["mse"] > metrics["reference_r9_own24"]["all24"]["mse"])
        check("opposite_error_candidate_is_rejected", decision["carry_forward"] is False)
        check("paired_secondary_win_is_labeled", decision["leading_development_procedure"] == "matched_paired_native" and decision["paired_control_won_when_primary_failed"])
        check("all_patient_rows_retained", len(patient_rows) == 5 * 3 * 59)
        check("all_target_rows_retained", len(target_rows) == 5 * 24)
        check("all_fold_rows_retained", len(fold_rows) == 5 * 3 * 5)
        check("all_three_contrasts_retained", set(contrasts) == {"primary_single_vs_r9", "primary_single_vs_matched", "secondary_matched_vs_r9"})
        delta = np.array(contrasts["primary_single_vs_r9"]["scopes"]["all24"]["patient_delta_mse"])
        rng = np.random.default_rng(20260928)
        indices = rng.integers(0, 59, size=(10000, 59))
        oracle_interval = np.quantile(delta[indices].mean(axis=1), [0.025, 0.975], method="linear")
        saved_interval = contrasts["primary_single_vs_r9"]["scopes"]["all24"]["bootstrap_95_interval"]
        near("bootstrap_matches_existing_default_rng_lower", saved_interval[0], oracle_interval[0], 0)
        near("bootstrap_matches_existing_default_rng_upper", saved_interval[1], oracle_interval[1], 0)

        def fixture(a, b, paired, ref):
            pred = {"A": np.full_like(y, a), "B": np.full_like(y, b), "matched_paired_native": np.full_like(y, paired)}
            return score.summarize(data, pred, np.full_like(y, ref), folds, catalog)

        out = fixture(0.04, -0.04, 0.07, 0.09)
        check("primary_route_requires_and_passes_both_references", out[2]["carry_forward"] and out[2]["leading_development_procedure"] == "single64_expected_loss")
        out = fixture(0.075, -0.075, 0.07, 0.09)
        check("single_beats_r9_but_loses_matched_not_promoted", all(out[2]["primary_checks_by_reference"]["reference_r9_own24"].values()) and not out[2]["carry_forward"])
        check("matched_secondary_retained_when_stronger", out[2]["leading_development_procedure"] == "matched_paired_native")
        out = fixture(0.0, math.sqrt(0.018), 0.1, 0.1)
        ck = out[2]["primary_checks_by_reference"]["reference_r9_own24"]
        check("orientation_fixture_expected_practical_gain_passes", ck["at_least_five_percent_full24_reduction"])
        check("one_bad_orientation_blocks_primary", not ck["orientation_B_strictly_better_full24"] and not out[2]["carry_forward"])
        check("neither_eligible_retains_r9", out[2]["leading_development_procedure"] == "reference_r9_own24")
        expected_p90 = math.sqrt((0.0 + 0.018) / 2)
        near("expected_tail_is_sqrt_mean_loss", out[0]["single64_expected_loss"]["all24"]["p90_patient_rmse"], expected_p90)
        check("expected_tail_is_not_mean_orientation_rmse", abs(expected_p90 - (0 + math.sqrt(0.018)) / 2) > 0.01)

        pf = np.arange(59) % 5
        ref = np.full(59, 20.0)
        ck = score._gate_checks(np.full(59, 19.0), ref, pf)
        check("literal_five_percent_boundary_passes", ck["at_least_five_percent_full24_reduction"])
        ck = score._gate_checks(np.full(59, np.nextafter(19.0, np.inf)), ref, pf)
        check("above_five_percent_boundary_fails_without_fuzz", not ck["at_least_five_percent_full24_reduction"])
        ref = np.ones(59)
        for n in (39, 40):
            loss = np.ones(59); loss[:n] = 0.5
            ck = score._gate_checks(loss, ref, pf)
            check(f"patient_win_boundary_{n}", ck["at_least_40_strict_patient_wins"] == (n == 40))
        for n in (3, 4):
            loss = np.where(pf < n, 0.5, 1.0)
            ck = score._gate_checks(loss, ref, pf)
            check(f"fold_win_boundary_{n}", ck["at_least_four_strict_fold_wins"] == (n == 4))
        loss = np.ones(59); loss[:40] = 0.5
        ck = score._gate_checks(loss, ref, pf)
        check("p90_equality_passes", ck["p90_patient_rmse_not_increased"])
        loss[-6:] = 1.001
        ck = score._gate_checks(loss, ref, pf)
        check("p90_increase_fails", not ck["p90_patient_rmse_not_increased"])
        ck = score._gate_checks(np.full(59, 0.55), ref, pf, {"A": ref, "B": np.full(59, 0.1)})
        check("orientation_equality_fails_strict_gate", not ck["orientation_A_strictly_better_full24"])
        check("exact_patient_ties_are_not_wins", score._counts(np.zeros(59)) == {"patient_wins": 0, "patient_ties": 59, "patient_losses": 0})
        check("tiny_literal_improvement_is_not_tolerance_tie", score._counts(np.full(59, -1e-18))["patient_wins"] == 59)

        for name, alter in [
            ("split_patient_rejected", "fold"),
            ("target_order_rejected", "target"),
            ("incomplete_prediction_rejected", "prediction"),
        ]:
            bad_folds = folds.copy(); bad_catalog = catalog
            bad_preds = {key: value.copy() for key, value in preds.items()}
            if alter == "fold": bad_folds[1] = 1
            if alter == "target": bad_catalog = SimpleNamespace(target_ids=target_ids[::-1])
            if alter == "prediction": bad_preds["B"][0, 0] = np.nan
            rejected = False
            try:
                score.summarize(data, bad_preds, error * 0.9, bad_folds, bad_catalog)
            except ValueError:
                rejected = True
            check(name, rejected)

        check("scoring_module_unchanged_during_checks", sha(Path(score.__file__)) == pins["scoring_sha256"])
        result = {"status": "PASS_GENERATED_ONLY_SCORING_CHECKS", "pins": pins,
            "check_count": len(checks), "checks": checks, "models_fit": 0,
            "real_predictions_read": 0, "source_workbook_accesses": 0, "lib2_response_accesses": 0}
        dump(args.output / "RESULT.json", result)
        dump(args.output / "MANIFEST.json", {"committed": True, "files": {
            p.name: sha(p) for p in sorted(args.output.iterdir()) if p.is_file()}})
        print(json.dumps({"status": result["status"], "check_count": len(checks),
            "result_sha256": sha(args.output / "RESULT.json"), "manifest_sha256": sha(args.output / "MANIFEST.json")}))
    except BaseException as exc:
        dump(args.output / "FAILURE.json", {"exception_type": type(exc).__name__, "message": str(exc),
            "traceback": traceback.format_exc(), "completed_checks": checks, "pins": pins})
        raise


if __name__ == "__main__":
    main()
