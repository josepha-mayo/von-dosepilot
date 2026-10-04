import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_candidate_proposal import verify_proposal
from check_development_registry import RegistryError, verify_registry


class DevelopmentRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[2]
        cls.registry = json.loads(
            (cls.root / "evidence/DEVELOPMENT_SEARCH_REGISTRY.json").read_text()
        )

    def write_registry(self, value):
        temp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        json.dump(value, temp)
        temp.close()
        self.addCleanup(Path(temp.name).unlink)
        return Path(temp.name)

    def write_proposal(self, **updates):
        protocol_path = "study/governance/fixtures/invented_unique_family/PROTOCOL.json"
        protocol_sha = hashlib.sha256((self.root / protocol_path).read_bytes()).hexdigest()
        value = {
            "schema": "dosepilot.candidate_proposal.v1",
            "state": "PREFROZEN_BEFORE_FIT",
            "family_id": "invented_unique_family",
            "family_fingerprint": "invented-unique-mechanism-v1",
            "falsifiable_hypothesis": "A fixed invented mechanism lowers complete-task error.",
            "protocol_path": protocol_path,
            "protocol_sha256": protocol_sha,
            "comparator_family_id": "bandwidth07_additive",
            "task_contract": {
                "samples": 119,
                "whole_patients": 59,
                "targets": 24,
                "physical_treatment_wells": 64,
                "per_plate": 32,
                "outer_patient_folds": 5,
                "inner_patient_folds": 3,
                "primary_metric": "equal-patient/equal-target full24 expected-loss MSE",
                "ab_rule": "average losses across the two separately costed 64-well orientations; never average predictions"
            },
            "outer_outcomes_opened": False,
            "protected22_access": False,
            "automatic_retry": False,
            "outer_outcome_target_or_fold_splicing": False,
            "ab_prediction_averaging": False,
            "promotion_gate": {
                "strictly_lower_mse": True,
                "minimum_patient_wins": 30,
                "required_favorable_outer_folds": 5,
                "p90_nonworse": True,
                "historical_r13_r18_gate_required": True
            }
        }
        value.update(updates)
        temp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        json.dump(value, temp)
        temp.close()
        self.addCleanup(Path(temp.name).unlink)
        return Path(temp.name)

    def test_current_registry_passes(self):
        result = verify_registry(self.root)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["incumbent"], "bandwidth07_additive")
        self.assertTrue(result["protected22_closed"])

    def test_duplicate_family_id_fails(self):
        value = copy.deepcopy(self.registry)
        value["families"][1]["family_id"] = value["families"][0]["family_id"]
        with self.assertRaisesRegex(RegistryError, "FAMILY_ID_UNIQUE"):
            verify_registry(self.root, self.write_registry(value))

    def test_duplicate_fingerprint_fails(self):
        value = copy.deepcopy(self.registry)
        value["families"][1]["family_fingerprint"] = value["families"][0]["family_fingerprint"]
        with self.assertRaisesRegex(RegistryError, "FAMILY_FINGERPRINT_UNIQUE"):
            verify_registry(self.root, self.write_registry(value))

    def test_second_incumbent_fails(self):
        value = copy.deepcopy(self.registry)
        value["families"][0]["status"] = "INCUMBENT"
        with self.assertRaisesRegex(RegistryError, "EXACTLY_ONE_INCUMBENT"):
            verify_registry(self.root, self.write_registry(value))

    def test_rejected_family_cannot_reopen(self):
        value = copy.deepcopy(self.registry)
        next(item for item in value["families"] if item["family_id"] == "simplex_spectral_stacking")["closed"] = False
        with self.assertRaisesRegex(RegistryError, "FAMILY_CLOSED"):
            verify_registry(self.root, self.write_registry(value))

    def test_rejected_family_cannot_enable_retry(self):
        value = copy.deepcopy(self.registry)
        next(item for item in value["families"] if item["family_id"] == "raw_ak_alignment")["automatic_retry"] = True
        with self.assertRaisesRegex(RegistryError, "FAMILY_AUTO_RETRY"):
            verify_registry(self.root, self.write_registry(value))

    def test_superseded_family_cannot_reopen(self):
        value = copy.deepcopy(self.registry)
        next(item for item in value["families"] if item["family_id"] == "structured_additive")["closed"] = False
        with self.assertRaisesRegex(RegistryError, "FAMILY_CLOSED"):
            verify_registry(self.root, self.write_registry(value))

    def test_incumbent_cannot_enable_automatic_retry(self):
        value = copy.deepcopy(self.registry)
        next(item for item in value["families"] if item["family_id"] == "bandwidth07_additive")["automatic_retry"] = True
        with self.assertRaisesRegex(RegistryError, "FAMILY_AUTO_RETRY"):
            verify_registry(self.root, self.write_registry(value))

    def test_family_metric_cannot_drift(self):
        value = copy.deepcopy(self.registry)
        next(item for item in value["families"] if item["family_id"] == "pairwise_anova_interaction")["mse"] = 0.0
        with self.assertRaisesRegex(RegistryError, "FAMILY_MSE"):
            verify_registry(self.root, self.write_registry(value))

    def test_family_evidence_mapping_cannot_drift(self):
        value = copy.deepcopy(self.registry)
        next(item for item in value["families"] if item["family_id"] == "raw_ak_alignment")["evidence"] = "evidence/spectral_successor_20261001.json"
        with self.assertRaisesRegex(RegistryError, "FAMILY_RECORD"):
            verify_registry(self.root, self.write_registry(value))

    def test_evidence_path_escape_fails(self):
        value = copy.deepcopy(self.registry)
        next(item for item in value["families"] if item["family_id"] == "raw_ak_alignment")["evidence"] = "/etc/passwd"
        with self.assertRaisesRegex(RegistryError, "FAMILY_RECORD|EVIDENCE_PATH"):
            verify_registry(self.root, self.write_registry(value))

    def test_incumbent_cannot_claim_independent_validation(self):
        value = copy.deepcopy(self.registry)
        value["incumbent"]["independent_validation"] = True
        with self.assertRaisesRegex(RegistryError, "INCUMBENT_VALIDATION"):
            verify_registry(self.root, self.write_registry(value))

    def test_cross_patient_rejection_rationale_is_pinned(self):
        value = copy.deepcopy(self.registry)
        next(item for item in value["families"] if item["family_id"] == "cross_patient_median_bandwidth")["gate_rationale"]["promotion_gate_passed"] = True
        with self.assertRaisesRegex(RegistryError, "CROSS_PATIENT_GATE_RATIONALE"):
            verify_registry(self.root, self.write_registry(value))

    def test_protected22_cannot_reopen(self):
        value = copy.deepcopy(self.registry)
        value["protected_data_policy"]["future_model_tuning_allowed"] = True
        with self.assertRaisesRegex(RegistryError, "PROTECTED22_TUNING"):
            verify_registry(self.root, self.write_registry(value))

    def test_prefit_rule_cannot_weaken(self):
        value = copy.deepcopy(self.registry)
        value["prefit_rule"]["outer_outcome_target_or_fold_splicing_allowed"] = True
        with self.assertRaisesRegex(RegistryError, "PREFIT_RULE"):
            verify_registry(self.root, self.write_registry(value))

    def test_unique_prefrozen_proposal_passes_without_authorizing_fit(self):
        result = verify_proposal(self.root, self.write_proposal())
        self.assertEqual(result["status"], "PASS")
        self.assertFalse(result["fit_authorized_by_this_check"])

    def test_duplicate_proposal_fails(self):
        proposal = self.write_proposal(family_id="simplex_spectral_stacking")
        with self.assertRaisesRegex(RegistryError, "DUPLICATE_FAMILY_ID"):
            verify_proposal(self.root, proposal)

    def test_scope_change_fails(self):
        task = self.write_proposal()
        value = json.loads(task.read_text())
        value["task_contract"]["physical_treatment_wells"] = 128
        task.write_text(json.dumps(value))
        with self.assertRaisesRegex(RegistryError, "PROPOSAL_TASK_PHYSICAL_TREATMENT_WELLS"):
            verify_proposal(self.root, task)

    def test_metric_change_fails(self):
        task = self.write_proposal()
        value = json.loads(task.read_text())
        value["task_contract"]["primary_metric"] = "sample-weighted MSE"
        task.write_text(json.dumps(value))
        with self.assertRaisesRegex(RegistryError, "PROPOSAL_PRIMARY_METRIC"):
            verify_proposal(self.root, task)

    def test_ab_estimand_change_fails(self):
        task = self.write_proposal()
        value = json.loads(task.read_text())
        value["task_contract"]["ab_rule"] = "average predictions"
        task.write_text(json.dumps(value))
        with self.assertRaisesRegex(RegistryError, "PROPOSAL_AB_RULE"):
            verify_proposal(self.root, task)

    def test_open_outer_outcomes_fails(self):
        with self.assertRaisesRegex(RegistryError, "PROPOSAL_OUTER_OUTCOMES"):
            verify_proposal(self.root, self.write_proposal(outer_outcomes_opened=True))

    def test_protected_access_fails(self):
        with self.assertRaisesRegex(RegistryError, "PROPOSAL_PROTECTED22"):
            verify_proposal(self.root, self.write_proposal(protected22_access=True))

    def test_automatic_retry_fails(self):
        with self.assertRaisesRegex(RegistryError, "PROPOSAL_AUTO_RETRY"):
            verify_proposal(self.root, self.write_proposal(automatic_retry=True))

    def test_outer_splice_fails(self):
        with self.assertRaisesRegex(RegistryError, "PROPOSAL_OUTER_SPLICE"):
            verify_proposal(self.root, self.write_proposal(outer_outcome_target_or_fold_splicing=True))

    def test_ab_prediction_averaging_fails(self):
        with self.assertRaisesRegex(RegistryError, "PROPOSAL_AB_PREDICTION_AVERAGING"):
            verify_proposal(self.root, self.write_proposal(ab_prediction_averaging=True))

    def test_protocol_hash_mismatch_fails(self):
        with self.assertRaisesRegex(RegistryError, "PROPOSAL_PROTOCOL_HASH_MISMATCH"):
            verify_proposal(self.root, self.write_proposal(protocol_sha256="1" * 64))

    def test_protocol_path_escape_fails(self):
        with self.assertRaisesRegex(RegistryError, "PROPOSAL_PROTOCOL_PATH"):
            verify_proposal(self.root, self.write_proposal(protocol_path="../outside.md"))

    def test_unrelated_hashed_file_is_not_a_protocol(self):
        relative = "README.md"
        digest = hashlib.sha256((self.root / relative).read_bytes()).hexdigest()
        with self.assertRaisesRegex(RegistryError, "PROPOSAL_PROTOCOL_PATH"):
            verify_proposal(self.root, self.write_proposal(protocol_path=relative, protocol_sha256=digest))

    def test_non_string_hypothesis_fails(self):
        with self.assertRaisesRegex(RegistryError, "PROPOSAL_HYPOTHESIS"):
            verify_proposal(self.root, self.write_proposal(falsifiable_hypothesis=True))

    def test_changed_promotion_gate_fails(self):
        proposal = self.write_proposal()
        value = json.loads(proposal.read_text())
        value["promotion_gate"]["minimum_patient_wins"] = 1
        proposal.write_text(json.dumps(value))
        with self.assertRaisesRegex(RegistryError, "PROPOSAL_PROMOTION_GATE"):
            verify_proposal(self.root, proposal)

    def test_extra_proposal_field_fails(self):
        proposal = self.write_proposal(unreviewed_override=True)
        with self.assertRaisesRegex(RegistryError, "PROPOSAL_FIELDS"):
            verify_proposal(self.root, proposal)

    def test_extra_nested_task_field_fails(self):
        proposal = self.write_proposal()
        value = json.loads(proposal.read_text())
        value["task_contract"]["effective_targets"] = 1
        proposal.write_text(json.dumps(value))
        with self.assertRaisesRegex(RegistryError, "PROPOSAL_TASK_FIELDS"):
            verify_proposal(self.root, proposal)

    def test_protocol_must_match_proposal(self):
        fixture = json.loads((self.root / "study/governance/fixtures/invented_unique_family/PROTOCOL.json").read_text())
        fixture["protected22_access"] = True
        parent = self.root / "study/governance/fixtures"
        tempdir = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(tempdir.cleanup)
        protocol_path = Path(tempdir.name) / "PROTOCOL.json"
        protocol_path.write_text(json.dumps(fixture))
        relative = str(protocol_path.relative_to(self.root))
        digest = hashlib.sha256(protocol_path.read_bytes()).hexdigest()
        with self.assertRaisesRegex(RegistryError, "PROPOSAL_PROTOCOL_CONTENT"):
            verify_proposal(self.root, self.write_proposal(protocol_path=relative, protocol_sha256=digest))


if __name__ == "__main__":
    unittest.main()
