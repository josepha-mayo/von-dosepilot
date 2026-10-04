#!/usr/bin/env python3
"""Reject duplicate or scope-changing model proposals before any fit begins."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from check_development_registry import (
    EXPECTED_AB_RULE,
    EXPECTED_PRIMARY_METRIC,
    EXPECTED_TASK,
    RegistryError,
    load,
    verify_registry,
)


EXPECTED_PROMOTION_GATE = {
    "strictly_lower_mse": True,
    "minimum_patient_wins": 30,
    "required_favorable_outer_folds": 5,
    "p90_nonworse": True,
    "historical_r13_r18_gate_required": True,
}


def load_strict_json(path: Path, invalid_label: str) -> dict:
    def reject_duplicates(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise RegistryError("PROPOSAL_PROTOCOL_DUPLICATE_KEY")
            value[key] = item
        return value

    try:
        return json.loads(path.read_text(), object_pairs_hook=reject_duplicates)
    except json.JSONDecodeError as exc:
        raise RegistryError(invalid_label) from exc


def verify_proposal(root: Path, proposal_path: Path, registry_path: Path | None = None) -> dict:
    root = Path(root)
    registry_path = registry_path or root / "evidence/DEVELOPMENT_SEARCH_REGISTRY.json"
    verify_registry(root, registry_path)
    registry = load(registry_path)
    proposal = load_strict_json(proposal_path, "PROPOSAL_JSON")

    if proposal.get("schema") != "dosepilot.candidate_proposal.v1":
        raise RegistryError("PROPOSAL_SCHEMA")
    allowed_proposal_keys = {
        "schema",
        "state",
        "family_id",
        "family_fingerprint",
        "falsifiable_hypothesis",
        "protocol_path",
        "protocol_sha256",
        "comparator_family_id",
        "task_contract",
        "promotion_gate",
        "outer_outcomes_opened",
        "protected22_access",
        "automatic_retry",
        "outer_outcome_target_or_fold_splicing",
        "ab_prediction_averaging",
    }
    if set(proposal) != allowed_proposal_keys:
        raise RegistryError("PROPOSAL_FIELDS")
    if proposal.get("state") != "PREFROZEN_BEFORE_FIT":
        raise RegistryError("PROPOSAL_NOT_PREFROZEN")
    family_id = proposal.get("family_id")
    fingerprint = proposal.get("family_fingerprint")
    if not family_id or not fingerprint:
        raise RegistryError("PROPOSAL_IDENTITY")
    if family_id in {item["family_id"] for item in registry["families"]}:
        raise RegistryError("DUPLICATE_FAMILY_ID")
    if fingerprint in {item["family_fingerprint"] for item in registry["families"]}:
        raise RegistryError("DUPLICATE_FAMILY_FINGERPRINT")

    task = proposal.get("task_contract", {})
    expected_task_keys = set(EXPECTED_TASK) | {"primary_metric", "ab_rule"}
    if set(task) != expected_task_keys:
        raise RegistryError("PROPOSAL_TASK_FIELDS")
    for key, expected in EXPECTED_TASK.items():
        if task.get(key) != expected:
            raise RegistryError("PROPOSAL_TASK_" + key.upper())
    if task.get("primary_metric") != EXPECTED_PRIMARY_METRIC:
        raise RegistryError("PROPOSAL_PRIMARY_METRIC")
    if task.get("ab_rule") != EXPECTED_AB_RULE:
        raise RegistryError("PROPOSAL_AB_RULE")
    if proposal.get("comparator_family_id") != registry["incumbent"]["family_id"]:
        raise RegistryError("PROPOSAL_COMPARATOR")
    if proposal.get("outer_outcomes_opened") is not False:
        raise RegistryError("PROPOSAL_OUTER_OUTCOMES")
    if proposal.get("protected22_access") is not False:
        raise RegistryError("PROPOSAL_PROTECTED22")
    if proposal.get("automatic_retry") is not False:
        raise RegistryError("PROPOSAL_AUTO_RETRY")
    if proposal.get("outer_outcome_target_or_fold_splicing") is not False:
        raise RegistryError("PROPOSAL_OUTER_SPLICE")
    if proposal.get("ab_prediction_averaging") is not False:
        raise RegistryError("PROPOSAL_AB_PREDICTION_AVERAGING")
    if proposal.get("promotion_gate") != EXPECTED_PROMOTION_GATE:
        raise RegistryError("PROPOSAL_PROMOTION_GATE")
    protocol_sha = proposal.get("protocol_sha256")
    protocol_relative = proposal.get("protocol_path")
    if not isinstance(protocol_sha, str) or len(protocol_sha) != 64:
        raise RegistryError("PROPOSAL_PROTOCOL_SHA")
    try:
        int(protocol_sha, 16)
    except ValueError as exc:
        raise RegistryError("PROPOSAL_PROTOCOL_SHA") from exc
    if not isinstance(protocol_relative, str) or not protocol_relative:
        raise RegistryError("PROPOSAL_PROTOCOL_PATH")
    protocol_path = (root / protocol_relative).resolve()
    try:
        protocol_path.relative_to(root.resolve())
    except ValueError as exc:
        raise RegistryError("PROPOSAL_PROTOCOL_PATH") from exc
    if not protocol_path.is_file():
        raise RegistryError("PROPOSAL_PROTOCOL_PATH")
    relative_parts = protocol_path.relative_to(root.resolve()).parts
    if not relative_parts or relative_parts[0] != "study" or protocol_path.name != "PROTOCOL.json":
        raise RegistryError("PROPOSAL_PROTOCOL_PATH")
    actual_protocol_sha = hashlib.sha256(protocol_path.read_bytes()).hexdigest()
    if actual_protocol_sha != protocol_sha:
        raise RegistryError("PROPOSAL_PROTOCOL_HASH_MISMATCH")
    hypothesis = proposal.get("falsifiable_hypothesis")
    if not isinstance(hypothesis, str) or len(hypothesis.strip()) < 20:
        raise RegistryError("PROPOSAL_HYPOTHESIS")
    protocol = load_strict_json(protocol_path, "PROPOSAL_PROTOCOL_JSON")
    expected_protocol_fields = {
        "schema": "dosepilot.frozen_protocol.v1",
        "state": proposal["state"],
        "family_id": family_id,
        "family_fingerprint": fingerprint,
        "falsifiable_hypothesis": hypothesis,
        "comparator_family_id": proposal["comparator_family_id"],
        "task_contract": proposal["task_contract"],
        "promotion_gate": EXPECTED_PROMOTION_GATE,
        "outer_outcomes_opened": False,
        "protected22_access": False,
        "automatic_retry": False,
        "outer_outcome_target_or_fold_splicing": False,
        "ab_prediction_averaging": False,
    }
    for key, expected in expected_protocol_fields.items():
        if protocol.get(key) != expected:
            raise RegistryError("PROPOSAL_PROTOCOL_CONTENT: " + key)
    method_summary = protocol.get("method_summary")
    if not isinstance(method_summary, str) or len(method_summary.strip()) < 80:
        raise RegistryError("PROPOSAL_PROTOCOL_METHOD")
    allowed_protocol_keys = set(expected_protocol_fields) | {"method_summary"}
    if set(protocol) != allowed_protocol_keys:
        raise RegistryError("PROPOSAL_PROTOCOL_FIELDS")

    return {
        "status": "PASS",
        "family_id": family_id,
        "family_fingerprint": fingerprint,
        "comparator": registry["incumbent"]["family_id"],
        "physical_treatment_wells": task["physical_treatment_wells"],
        "protocol_path": protocol_relative,
        "protocol_sha256": protocol_sha,
        "protected22_access": False,
        "fit_authorized_by_this_check": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--proposal", type=Path, required=True)
    parser.add_argument("--registry", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify_proposal(args.root, args.proposal, args.registry), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
