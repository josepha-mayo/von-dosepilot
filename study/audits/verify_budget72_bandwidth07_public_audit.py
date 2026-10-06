#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


class Budget72PublicAuditError(ValueError):
    pass


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def same(actual, expected, label: str, tolerance: float = 0.0) -> None:
    if isinstance(expected, float):
        if not math.isclose(float(actual), expected, rel_tol=0.0, abs_tol=tolerance):
            raise Budget72PublicAuditError(label)
    elif actual != expected:
        raise Budget72PublicAuditError(label)


def verify(root: Path) -> dict:
    root = Path(root).resolve()
    audit_path = root / "evidence/budget72_bandwidth07_public_audit_20261006.json"
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    same(audit["schema"], "dosepilot.budget72_bandwidth07.public_audit.v1", "SCHEMA")
    same(
        audit["scope"],
        "PUBLIC_AGGREGATE_AND_FROZEN_LINEAGE_AUDIT_NOT_PRIVATE_NUMERICAL_REPLAY",
        "SCOPE",
    )

    lineage = audit["lineage"]
    same(lineage["freeze_commit"], "b772b3e94a4747019ac06a8b5e7319523b11300d", "FREEZE_COMMIT")
    same(lineage["result_commit"], "e3413b71958566abee4725892ebfe7dde42b4c31", "RESULT_COMMIT")
    same(lineage["result_is_direct_child_of_freeze"], True, "DIRECT_CHILD")
    same(lineage["frozen_sources_unchanged_between_commits"], True, "FROZEN_SOURCES")
    same(lineage["private_input_open_time_independently_attested"], False, "NO_PRIVATE_ATTESTATION")

    for artifact in audit["artifacts"].values():
        path = root / artifact["path"]
        if not path.is_file():
            raise Budget72PublicAuditError("MISSING_ARTIFACT:" + artifact["path"])
        same(sha256(path), artifact["sha256"], "ARTIFACT_HASH:" + artifact["path"])

    evidence = json.loads(
        (root / audit["artifacts"]["aggregate_receipt"]["path"]).read_text(encoding="utf-8")
    )
    same(evidence["schema"], "dosepilot.budget72_bandwidth07_residual.evidence.v1", "EVIDENCE_SCHEMA")
    same(evidence["frozen_before_outcome_commit"], "b772b3e", "EVIDENCE_FREEZE_COMMIT")
    same(evidence["candidate"]["treatment_wells"], 72, "TREATMENT_WELLS")
    same(evidence["candidate"]["plate_wells"], [36, 36], "PLATE_WELLS")

    candidate_mse = 0.0009326007417880046
    candidate_p90 = 0.03770730634910972
    successor_mse = 0.001042745722096212
    successor_p90 = 0.037419695944064885
    base72_mse = 0.0010055928901387746
    same(evidence["candidate"]["mse"], candidate_mse, "CANDIDATE_MSE", 1e-15)
    same(evidence["candidate"]["p90_patient_rmse"], candidate_p90, "CANDIDATE_P90", 1e-15)
    same(audit["candidate"]["mse"], candidate_mse, "AUDIT_CANDIDATE_MSE", 1e-15)
    same(audit["candidate"]["p90_patient_rmse"], candidate_p90, "AUDIT_CANDIDATE_P90", 1e-15)

    vs_base = evidence["vs_base72"]
    same(vs_base["base_mse"], base72_mse, "BASE72_MSE", 1e-15)
    same(vs_base["relative_mse_gain"], (base72_mse - candidate_mse) / base72_mse, "BASE_GAIN", 1e-15)
    same(vs_base["patient_wins"], 47, "BASE_PATIENT_WINS")
    same(vs_base["favorable_outer_folds"], 5, "BASE_FOLDS")
    same(vs_base["target_wins"], 22, "BASE_TARGET_WINS")
    same(vs_base["p90_nonworse"], True, "BASE_TAIL_GATE")
    lo, hi = vs_base["bootstrap_percentile_95_ci"]
    if not lo < hi < 0:
        raise Budget72PublicAuditError("BOOTSTRAP_DIRECTION")

    vs_successor = evidence["vs_current_64_well_successor"]
    same(vs_successor["reference_mse"], successor_mse, "SUCCESSOR_MSE", 1e-15)
    same(vs_successor["reference_p90_patient_rmse"], successor_p90, "SUCCESSOR_P90", 1e-15)
    same(
        vs_successor["relative_mse_gain"],
        (successor_mse - candidate_mse) / successor_mse,
        "SUCCESSOR_GAIN",
        1e-15,
    )
    same(vs_successor["patient_wins"], 48, "SUCCESSOR_PATIENT_WINS")
    same(vs_successor["favorable_outer_folds"], 5, "SUCCESSOR_FOLDS")
    same(vs_successor["p90_nonworse"], False, "SUCCESSOR_TAIL_RECORDED")
    if not candidate_p90 > successor_p90:
        raise Budget72PublicAuditError("SUCCESSOR_TAIL_ARITHMETIC")

    audit_gate = audit["versus_current_64_well_scientific_successor"]
    for key in ("mean_gate_pass", "patient_breadth_gate_pass", "all_five_fold_gate_pass"):
        same(audit_gate[key], True, "GATE_" + key)
    same(audit_gate["tail_gate_pass"], False, "TAIL_GATE_REJECTION")
    same(audit_gate["r13_r18_gates_retained"], True, "R13_R18")

    decision = audit["decision"]
    same(decision["status"], "REJECT_FOR_PROMOTION_PRESERVE_AS_FRONTIER_EVIDENCE", "DECISION")
    same(decision["scientific_successor_replaced"], False, "NO_SCIENTIFIC_REPLACEMENT")
    same(decision["operational_baseline_replaced"], False, "NO_OPERATIONAL_REPLACEMENT")
    same(decision["candidate_promotion_allowed"], False, "NO_PROMOTION")

    selected = evidence["residual_selection"]["outer_selected_options"]
    allowed = [[0.1, 1.0], [0.3, 1.0]]
    if len(selected) != 5 or any(item not in allowed for item in selected):
        raise Budget72PublicAuditError("FROZEN_SELECTIONS")
    same(evidence["integrity"]["floating_replay_status"], "PASS_FLOATING_REPLAY", "RECORDED_REPLAY")
    same(evidence["integrity"]["max_prediction_difference"], 0.0, "RECORDED_MAXDIFF")

    freeze_path = root / audit["artifacts"]["freeze_receipt"]["path"]
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    for section in ("source_sha256", "dependency_sha256"):
        for relative_path, expected_hash in freeze[section].items():
            same(sha256(root / relative_path), expected_hash, "FREEZE_HASH:" + relative_path)

    public = audit["public_reproducibility"]
    same(public["aggregate_receipt_and_arithmetic_checkable"], True, "PUBLIC_AGGREGATE")
    same(public["freeze_source_and_dependency_hashes_checkable"], True, "PUBLIC_FREEZE")
    for key in (
        "patient_level_rows_published",
        "prediction_arrays_published",
        "private_result_json_published",
        "full_prediction_replay_publicly_runnable",
        "independent_numerical_reproduction_claimed",
    ):
        same(public[key], False, "BOUNDARY_" + key)
    for key in ("selection_adjusted", "independent_validation", "clinical_evidence", "protected22_access"):
        same(audit[key], False, "BOUNDARY_" + key)
    same(audit["official_score"], None, "NO_OFFICIAL_SCORE")
    for key in (
        "patient_level_rows_published",
        "prediction_arrays_published",
        "selection_adjusted",
        "candidate_promotion_allowed",
        "protected22_access",
        "independent_validation",
    ):
        same(evidence[key], False, "EVIDENCE_BOUNDARY_" + key)

    document = (root / audit["artifacts"]["public_audit_document"]["path"]).read_text(encoding="utf-8")
    for marker in (
        "rejected for promotion",
        "worse than the successor",
        "rerun from public artifacts alone",
        "not independent validation",
        "Protected22/Lib2 responses were not accessed",
    ):
        if marker not in document:
            raise Budget72PublicAuditError("DOCUMENT_MARKER:" + marker)

    return {
        "status": "PASS",
        "candidate_mse": candidate_mse,
        "candidate_p90_patient_rmse": candidate_p90,
        "successor_mse": successor_mse,
        "successor_p90_patient_rmse": successor_p90,
        "mean_gate_pass": True,
        "patient_breadth_gate_pass": True,
        "all_five_fold_gate_pass": True,
        "tail_gate_pass": False,
        "promotion_decision": "REJECT_PRESERVE",
        "public_prediction_replay_available": False,
        "protected22_access": False,
        "independent_validation": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    print(json.dumps(verify(args.root), indent=2))


if __name__ == "__main__":
    main()
