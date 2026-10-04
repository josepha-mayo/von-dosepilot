#!/usr/bin/env python3
"""Validate DosePilot's response-free development search registry."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


class RegistryError(ValueError):
    pass


EXPECTED_TASK = {
    "samples": 119,
    "whole_patients": 59,
    "targets": 24,
    "physical_treatment_wells": 64,
    "per_plate": 32,
    "outer_patient_folds": 5,
    "inner_patient_folds": 3,
}

EXPECTED_PRIMARY_METRIC = "equal-patient/equal-target full24 expected-loss MSE"
EXPECTED_AB_RULE = "average losses across the two separately costed 64-well orientations; never average predictions"

REQUIRED_CLOSED = {
    "s1_hard_reduced_rank_residual",
    "s1_full_rank_residual",
    "s3_fixed_plan_full_residual",
    "s4_fixed_plan_soft_residual",
    "r22_prior_center",
    "r23_corrected_covariance",
    "optimized_interpolation_control",
    "shift_constraint",
    "pairwise_anova_interaction",
    "mean_contrast_kernel",
    "raw_ak_alignment",
    "forced_multioutput_acquisition_sweep",
    "bandwidth14_additive",
    "cross_patient_median_bandwidth",
    "simplex_spectral_stacking",
    "isotonic_paid_features",
    "matern32_own_drug",
}

EXPECTED_MSE = {
    "r13_own_drug_ridge": 0.001144858681382854,
    "r18_exploratory": 0.0011414048112341991,
    "s2_soft_spectral": 0.0010701439454817465,
    "s1_hard_reduced_rank_residual": 0.0010871592831997162,
    "s1_full_rank_residual": 0.0010848257091747118,
    "s3_fixed_plan_full_residual": 0.0010977058957504665,
    "s4_fixed_plan_soft_residual": 0.0010790799124368396,
    "r22_prior_center": 0.001143256661767395,
    "r23_corrected_covariance": 0.0011421341320843055,
    "optimized_interpolation_control": 0.002416810289196867,
    "shift_constraint": 0.0011448586813828537,
    "structured_additive": 0.001060552730112811,
    "pairwise_anova_interaction": 0.0010628861933534165,
    "mean_contrast_kernel": 0.001064080098040721,
    "raw_ak_alignment": 0.0010608377525825187,
    "forced_multioutput_acquisition_sweep": 0.0010665434003468322,
    "bandwidth07_additive": 0.0010582750420801538,
    "bandwidth14_additive": 0.00106370935859072,
    "cross_patient_median_bandwidth": 0.0010574875414830203,
    "simplex_spectral_stacking": 0.0010620901334091122,
    "isotonic_paid_features": 0.0010731733783205333,
    "matern32_own_drug": 0.001146185234155711,
}

EXPECTED_FAMILY = {
    "r13_own_drug_ridge": ("own-drug-ridge-fixed64", "HISTORICAL_REFERENCE", "SUPERSEDED_AS_INCUMBENT", "evidence/spectral_successor_20261001.json"),
    "r18_exploratory": ("r18-lower-point-unpromoted", "UNPROMOTED_REFERENCE", "DO_NOT_PROMOTE", "evidence/spectral_successor_20261001.json"),
    "s2_soft_spectral": ("soft-spectral-residual-shrinkage", "SUPERSEDED", "SUPERSEDED_AS_INCUMBENT", "evidence/spectral_successor_20261001.json"),
    "s1_hard_reduced_rank_residual": ("s1-hard-reduced-rank-residual", "REJECTED", "REJECT_R18_MARGIN", "evidence/spectral_successor_20261001.json"),
    "s1_full_rank_residual": ("s1-full-rank-residual-control", "REJECTED", "REJECT_R18_MARGIN", "evidence/spectral_successor_20261001.json"),
    "s3_fixed_plan_full_residual": ("s3-fixed-plan-full-residual", "REJECTED", "REJECT_MARGIN_AND_BREADTH", "evidence/spectral_successor_20261001.json"),
    "s4_fixed_plan_soft_residual": ("s4-fixed-plan-soft-residual", "REJECTED", "REJECT_PATIENT_BREADTH", "evidence/spectral_successor_20261001.json"),
    "r22_prior_center": ("r22-prior-center", "UNPROMOTED_REFERENCE", "DO_NOT_PROMOTE", "evidence/aggregate_results.json"),
    "r23_corrected_covariance": ("r23-corrected-covariance", "UNPROMOTED_REFERENCE", "DO_NOT_PROMOTE", "evidence/aggregate_results.json"),
    "optimized_interpolation_control": ("optimized-piecewise-linear-interpolation-acquisition", "REJECTED", "REJECT_RETAIN_R13", "evidence/optimized_interpolation_control.json"),
    "shift_constraint": ("shift-constrained-r13-head", "REJECTED", "REJECT_RETAIN_R13", "evidence/public_comparison_replay_20260930.json"),
    "structured_additive": ("structured-additive-group-kernel", "SUPERSEDED", "SUPERSEDED_AS_INCUMBENT", "evidence/structured_kernels_recovery_20261002.json"),
    "pairwise_anova_interaction": ("centered-pairwise-group-product-kernel", "REJECTED", "REJECT_RETAIN_ADDITIVE", "evidence/structured_kernels_recovery_20261002.json"),
    "mean_contrast_kernel": ("group-mean-within-group-contrast-kernel", "REJECTED", "REJECT_RETAIN_ADDITIVE", "evidence/structured_kernels_recovery_20261002.json"),
    "raw_ak_alignment": ("raw-feature-additive-kernel-alignment", "REJECTED", "REJECT_RETAIN_ADDITIVE", "evidence/aligned_additive_20261003.json"),
    "forced_multioutput_acquisition_sweep": ("forced-multioutput-acquisition-sweep-existing-head", "REJECTED", "REJECT_RETAIN_ADDITIVE", "evidence/lifecycle_acquisition_20261002.json"),
    "bandwidth07_additive": ("structured-additive-bandwidth-0.7", "INCUMBENT", "PROMOTE", "evidence/bandwidth_successor_20261003.json"),
    "bandwidth14_additive": ("structured-additive-bandwidth-1.4", "REJECTED", "REJECT_RETAIN_BANDWIDTH07", "evidence/bandwidth_successor_20261003.json"),
    "cross_patient_median_bandwidth": ("cross-patient-median-distance-bandwidth", "REJECTED", "REJECT_RETAIN_BANDWIDTH07", "evidence/cross_patient_bandwidth_20261004.json"),
    "simplex_spectral_stacking": ("patient-balanced-simplex-spectral-stack", "REJECTED", "REJECT_RETAIN_BANDWIDTH07", "evidence/simplex_stacking_20261004.json"),
    "isotonic_paid_features": ("fixed-equal-weight-within-drug-nonincreasing-pava-before-own-drug-and-bandwidth07-features-v1", "REJECTED", "REJECT_RETAIN_BANDWIDTH07", "evidence/isotonic_paid_features_20261004.json"),
    "matern32_own_drug": ("linear-plus-matern32-own-drug", "REJECTED", "REJECT_AND_RETAIN_R13", "evidence/r34_nonlinear_challenger.json"),
}


def evidence_mse(root: Path, family_id: str) -> float:
    """Extract the registered MSE from its public aggregate evidence."""
    if family_id in {"r13_own_drug_ridge", "r18_exploratory", "s2_soft_spectral"}:
        value = load(root / "evidence/spectral_successor_20261001.json")["metrics"]
        key = {"r13_own_drug_ridge": "r13", "r18_exploratory": "r18", "s2_soft_spectral": "r13_soft"}[family_id]
        return value[key]["mse"]
    if family_id in {"s1_hard_reduced_rank_residual", "s1_full_rank_residual", "s3_fixed_plan_full_residual", "s4_fixed_plan_soft_residual"}:
        method = {
            "s1_hard_reduced_rank_residual": "S1 hard reduced-rank residual",
            "s1_full_rank_residual": "S1 full-rank residual control",
            "s3_fixed_plan_full_residual": "S3 fixed-plan full residual",
            "s4_fixed_plan_soft_residual": "S4 fixed-plan soft residual",
        }[family_id]
        rows = load(root / "evidence/spectral_successor_20261001.json")["other_completed_candidates"]
        return next(row["mse"] for row in rows if row["method"] == method)
    if family_id in {"r22_prior_center", "r23_corrected_covariance"}:
        methods = load(root / "evidence/aggregate_results.json")["methods"]
        return methods["R22_prior_center_not_promoted" if family_id == "r22_prior_center" else "R23_corrected_covariance_not_promoted"]
    if family_id == "optimized_interpolation_control":
        return load(root / "evidence/optimized_interpolation_control.json")["patient_balanced_mse"]["optimized_interpolation"]
    if family_id == "shift_constraint":
        return load(root / "evidence/public_comparison_replay_20260930.json")["shift_constraint"]["candidate_mse"]
    if family_id in {"structured_additive", "pairwise_anova_interaction", "mean_contrast_kernel"}:
        value = load(root / "evidence/structured_kernels_recovery_20261002.json")["research"]["mse"]
        key = {"structured_additive": "recovered_additive_control", "pairwise_anova_interaction": "new_pair_mixture", "mean_contrast_kernel": "new_mean_contrast"}[family_id]
        return value[key]
    if family_id == "raw_ak_alignment":
        return load(root / "evidence/aligned_additive_20261003.json")["metrics"]["raw_ak"]["mse"]
    if family_id == "forced_multioutput_acquisition_sweep":
        return load(root / "evidence/lifecycle_acquisition_20261002.json")["acquisition_study"]["metrics"]["forced_sweep"]["mse"]
    if family_id in {"bandwidth07_additive", "bandwidth14_additive"}:
        value = load(root / "evidence/bandwidth_successor_20261003.json")
        return value["metrics"]["bandwidth07"]["mse"] if family_id == "bandwidth07_additive" else value["rejected_wider_bandwidth"]["mse"]
    if family_id == "cross_patient_median_bandwidth":
        return load(root / "evidence/cross_patient_bandwidth_20261004.json")["metrics"]["cross_patient_median"]["mse"]
    if family_id == "simplex_spectral_stacking":
        return load(root / "evidence/simplex_stacking_20261004.json")["candidate"]["mse"]
    if family_id == "isotonic_paid_features":
        return load(root / "evidence/isotonic_paid_features_20261004.json")["metrics"]["isotonic_candidate"]["mse"]
    if family_id == "matern32_own_drug":
        return load(root / "evidence/r34_nonlinear_challenger.json")["candidate_mse"]
    fail("UNKNOWN_FAMILY: " + family_id)


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def fail(label: str) -> None:
    raise RegistryError(label)


def verify_registry(root: Path, registry_path: Path | None = None) -> dict:
    root = Path(root)
    path = registry_path or root / "evidence/DEVELOPMENT_SEARCH_REGISTRY.json"
    registry = load(path)
    if registry.get("schema") != "dosepilot.development_search_registry.v1":
        fail("REGISTRY_SCHEMA")
    if registry.get("as_of_date") != "2026-10-04":
        fail("REGISTRY_DATE")
    if registry.get("scope") != "curated public aggregate registry for the original Lib1 TRAIN repeated-development task":
        fail("REGISTRY_SCOPE")
    coverage = registry.get("coverage", {})
    if coverage != {
        "registered_families": 22,
        "exhaustive_historical_search_claimed": False,
        "inclusion_rule": "Public aggregate model or acquisition candidates; conventional and reproduction-only controls are not enumerated as candidate families.",
        "limitation": "The gate blocks exact IDs and fingerprints recorded here; it does not prove novelty against every private or historical experiment.",
    }:
        fail("REGISTRY_COVERAGE")
    task = registry.get("task_contract", {})
    for key, expected in EXPECTED_TASK.items():
        if task.get(key) != expected:
            fail("TASK_CONTRACT_" + key.upper())
    if task.get("primary_metric") != EXPECTED_PRIMARY_METRIC:
        fail("TASK_PRIMARY_METRIC")
    if task.get("ab_rule") != EXPECTED_AB_RULE:
        fail("TASK_AB_RULE")

    prefit = registry.get("prefit_rule", {})
    expected_prefit = {
        "unique_family_id_required": True,
        "unique_family_fingerprint_required": True,
        "prefrozen_protocol_required": True,
        "same_task_denominator_required": True,
        "automatic_retry_of_rejected_family_allowed": False,
        "outer_outcome_target_or_fold_splicing_allowed": False,
        "protected22_access_allowed": False,
        "proposal_checker": "study/governance/check_candidate_proposal.py",
    }
    if prefit != expected_prefit:
        fail("PREFIT_RULE")

    policy = registry.get("protected_data_policy", {})
    if policy.get("protected22_lib2_status") != "EXPOSED_CLOSED_FOR_MODEL_DEVELOPMENT":
        fail("PROTECTED22_STATUS")
    if policy.get("future_model_tuning_allowed") is not False:
        fail("PROTECTED22_TUNING")
    if policy.get("rescue_or_subgroup_search_allowed") is not False:
        fail("PROTECTED22_RESCUE")
    expected_policy_sources = [
        "evidence/PROTECTED22_ACCESS_STATUS.json",
        "docs/PROTECTED22_RESULT.md",
        "docs/EVIDENCE_LEDGER.md",
    ]
    if policy.get("policy_sources") != expected_policy_sources:
        fail("PROTECTED22_SOURCE")
    for relative in expected_policy_sources:
        if not (root / relative).is_file():
            fail("PROTECTED22_SOURCE_MISSING")
    access = load(root / expected_policy_sources[0])
    if access.get("status") != "EXPOSED_DO_NOT_TREAT_AS_HOLDOUT":
        fail("PROTECTED22_SOURCE_STATUS")
    if access.get("automatic_retry_authorized") is not False:
        fail("PROTECTED22_SOURCE_RETRY")
    if access.get("independent_confirmation") is not False:
        fail("PROTECTED22_SOURCE_CONFIRMATION")

    families = registry.get("families", [])
    if not families:
        fail("EMPTY_REGISTRY")
    ids = [item.get("family_id") for item in families]
    fingerprints = [item.get("family_fingerprint") for item in families]
    if None in ids or len(ids) != len(set(ids)):
        fail("FAMILY_ID_UNIQUE")
    if None in fingerprints or len(fingerprints) != len(set(fingerprints)):
        fail("FAMILY_FINGERPRINT_UNIQUE")

    incumbents = [item for item in families if item.get("status") == "INCUMBENT"]
    if len(incumbents) != 1:
        fail("EXACTLY_ONE_INCUMBENT")
    incumbent = incumbents[0]
    top = registry.get("incumbent", {})
    if incumbent["family_id"] != top.get("family_id"):
        fail("INCUMBENT_ID")
    if not math.isclose(incumbent["mse"], top.get("mse", math.nan), rel_tol=0, abs_tol=1e-15):
        fail("INCUMBENT_MSE")
    if incumbent.get("closed") is not False or incumbent.get("decision") != "PROMOTE":
        fail("INCUMBENT_STATE")
    if top.get("evidence") != "evidence/bandwidth_successor_20261003.json":
        fail("INCUMBENT_EVIDENCE")
    if not math.isclose(top.get("p90_rmse", math.nan), 0.0378942853087202, rel_tol=0, abs_tol=1e-15):
        fail("INCUMBENT_P90")
    if top.get("independent_validation") is not False:
        fail("INCUMBENT_VALIDATION")

    by_id = {item["family_id"]: item for item in families}
    if set(by_id) != set(EXPECTED_MSE):
        fail("FAMILY_SET")
    for family_id, expected in EXPECTED_MSE.items():
        if not math.isclose(by_id[family_id].get("mse", math.nan), expected, rel_tol=0, abs_tol=1e-15):
            fail("FAMILY_MSE: " + family_id)
        fingerprint, status, decision, evidence = EXPECTED_FAMILY[family_id]
        item = by_id[family_id]
        if (item.get("family_fingerprint"), item.get("status"), item.get("decision"), item.get("evidence")) != (fingerprint, status, decision, evidence):
            fail("FAMILY_RECORD: " + family_id)
        if not math.isclose(evidence_mse(root, family_id), expected, rel_tol=0, abs_tol=1e-15):
            fail("FAMILY_EVIDENCE_MSE: " + family_id)
        expected_closed = family_id != "bandwidth07_additive"
        if item.get("closed") is not expected_closed:
            fail("FAMILY_CLOSED: " + family_id)
        if item.get("automatic_retry") is not False:
            fail("FAMILY_AUTO_RETRY: " + family_id)
    if by_id["forced_multioutput_acquisition_sweep"].get("metric_variant") != "forced_sweep":
        fail("MULTIOUTPUT_METRIC_VARIANT")
    if not REQUIRED_CLOSED.issubset(by_id):
        fail("REQUIRED_CLOSED_MISSING")
    for family_id in REQUIRED_CLOSED:
        item = by_id[family_id]
        if item.get("status") not in {"REJECTED", "UNPROMOTED_REFERENCE"} or item.get("closed") is not True:
            fail("REJECTED_NOT_CLOSED: " + family_id)
        if item.get("automatic_retry") is not False:
            fail("REJECTED_AUTO_RETRY: " + family_id)
        if item.get("decision") == "PROMOTE":
            fail("REJECTED_DECISION: " + family_id)

    for item in families:
        evidence = (root / item.get("evidence", "")).resolve()
        try:
            relative = evidence.relative_to(root.resolve())
        except ValueError as exc:
            raise RegistryError("EVIDENCE_PATH: " + item["family_id"]) from exc
        if not relative.parts or relative.parts[0] not in {"evidence", "docs"}:
            fail("EVIDENCE_PATH: " + item["family_id"])
        if not evidence.is_file():
            fail("MISSING_EVIDENCE: " + item["family_id"])

    cpm = by_id["cross_patient_median_bandwidth"].get("gate_rationale", {})
    expected_cpm = {
        "lower_point_estimate": True,
        "all_five_folds_required": True,
        "observed_favorable_folds": 4,
        "promotion_gate_passed": False,
        "reason": "Lower adaptive point estimate did not pass the prefrozen all-five-fold successor gate.",
    }
    if cpm != expected_cpm:
        fail("CROSS_PATIENT_GATE_RATIONALE")
    cpm_receipt = load(root / "evidence/cross_patient_bandwidth_20261004.json")
    if cpm_receipt["candidate_vs_bandwidth07"]["fold_wins"] != 4 or cpm_receipt["candidate_vs_bandwidth07"]["gate"]["all_five_folds_favorable"] is not False:
        fail("CROSS_PATIENT_GATE_EVIDENCE")

    boundary = registry.get("claim_boundary", {})
    for key in (
        "new_model_fit",
        "new_biological_accuracy_result",
        "independent_validation",
        "private_or_protected_inputs_read",
        "accepted_kaggle_entry_changed",
    ):
        if boundary.get(key) is not False:
            fail("CLAIM_BOUNDARY_" + key.upper())
    if boundary.get("official_competition_score") is not None:
        fail("CLAIM_BOUNDARY_SCORE")

    return {
        "status": "PASS",
        "families": len(families),
        "closed_rejected_families": sum(item.get("status") == "REJECTED" for item in families),
        "incumbent": incumbent["family_id"],
        "incumbent_mse": incumbent["mse"],
        "protected22_closed": True,
        "private_or_protected_inputs_read": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--registry", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify_registry(args.root, args.registry), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
