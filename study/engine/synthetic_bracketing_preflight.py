#!/usr/bin/env python3
"""Random-only bracketing pipeline, leakage and exact physical-join preflight.

Reads frozen input metadata but no real response arrays. Every numeric response
used below is generated in memory. Each invocation preserves its own directory.
"""
from __future__ import annotations

import argparse
import copy
import csv
import json
from pathlib import Path
import traceback
from types import SimpleNamespace

import numpy as np
from threadpoolctl import threadpool_limits

import evaluate as first
import evaluate_bracketing as evaluation
import bracketing_methods as methods
from methods import patient_folds, patient_weights, per_patient_loss
from sparse_methods import LAMBDAS, descriptor_from_manifest


def rejected(action, contains=None):
    try:
        action()
    except (ValueError, TypeError) as exc:
        if contains and contains not in str(exc):
            raise AssertionError(f"Unexpected rejection {exc!s}, expected {contains!r}")
        return str(exc)
    raise AssertionError("Invalid input was accepted")


def synthetic(pool, contract, n_patients=24):
    descriptor = descriptor_from_manifest(pool, "lib1")
    layout = methods.layout_from_contract(descriptor, contract)
    rng = np.random.default_rng(20260928)
    # Unequal numbers of PDOs ensure row weighting cannot masquerade as patient weighting.
    patients = np.repeat(np.asarray([f"synthetic_patient_{i:03d}" for i in range(n_patients)]), [1 + (i % 3) for i in range(n_patients)])
    n, m = len(patients), len(layout.native_ids)
    latent = rng.normal(size=(n_patients, 24))
    row_latent = np.vstack([latent[int(p.rsplit("_", 1)[1])] for p in patients])
    y = 0.5 + 0.1 * row_latent + rng.normal(scale=0.025, size=(n, 24))
    x = np.column_stack([0.5 + (0.1 + 0.08 * ((q % 5) / 4)) * row_latent[:, target] + rng.normal(scale=0.02 + 0.015 * (q % 3), size=n) for q, target in enumerate(layout.native_target_indices)])
    jitter = rng.normal(scale=0.008, size=x.shape)
    paired = np.stack((x + jitter, x - jitter), axis=2)
    sample_ids = np.asarray([f"synthetic_sample_{i:03d}" for i in range(n)])
    wells = np.asarray([[[f"synthetic_run_{row:03d}|p{plate + 1}|A|{q}" for plate in range(2)] for q in range(m)] for row in range(n)])
    data = {"y": y, "sample_ids": sample_ids, "patient_ids": patients, "drug_ids": layout.target_ids, "library_ids": np.asarray(["lib1"] * n)}
    old = {"descriptor": descriptor, "x": paired[:, :150].mean(axis=2), "x_replicates": paired[:, :150], "well_ids": wells[:, :150], "pool": {"selected_records": [{"sample_id": str(sample), "partition": "train", "run_id": f"synthetic_run_{i:03d}"} for i, sample in enumerate(sample_ids)]}, "audit": {"synthetic_only": True}}
    features = {"x": paired.mean(axis=2), "x_replicates": paired, "well_ids": wells, "layout": layout, "old": old, "audit": {"synthetic_only": True, "no_real_responses_read": True}}
    return data, features


def save_rows(path, rows):
    with Path(path).open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def fixture_rows(data, features):
    layout = features["layout"]
    raw, mappings = [], []
    for row in range(len(data["y"])):
        common = {"sample_id": str(data["sample_ids"][row]), "patient_id": str(data["patient_ids"][row]), "library_id": "lib1", "run_id": f"synthetic_run_{row:03d}"}
        for q in range(150, len(layout.native_ids)):
            for plate in range(2):
                raw.append({**common, "drug_id": str(layout.target_ids[layout.native_target_indices[q]]), "plate": f"p{plate + 1}", "dose_nM": layout.native_concentrations[q], "viability": repr(float(features["x_replicates"][row, q, plate])), "drow": "A", "dcol": str(q), "assay_no": "synthetic_assay"})
        for candidate in layout.candidates:
            for position, native in enumerate(candidate["native_indices"]):
                for plate in range(2):
                    mappings.append({**common, "partition": "train", "feature_id": candidate["feature_id"], "drug_id": candidate["drug_id"], "q": str(candidate["q"]), "coordinate_ids": ";".join(candidate["coordinate_ids"]), "native_action_id": str(layout.native_ids[native]), "native_concentration_nM": layout.native_concentrations[native], "node_role": ("lower", "upper")[position], "plate": f"p{plate + 1}", "drow": "A", "dcol": str(native), "assay_no": "synthetic_assay", "z_coefficient_on_this_well_decimal80": repr(candidate["forward_matrix"][0][position] / 2), "m_coefficient_on_this_well_decimal80": repr(candidate["forward_matrix"][1][position] / 2)})
    return raw, mappings


def loader_checks(output, data, features, contract):
    checks = []
    raw, maps = fixture_rows(data, features)
    directory = output / "synthetic_loader"
    directory.mkdir()
    curves, contract_path = directory / "train_curves.csv", directory / "BRACKETING_CONTRACT.json"
    first.dump(contract_path, contract)
    save_rows(curves, raw)
    save_rows(directory / "candidate_native_wells.csv", maps)
    loaded = evaluation.join_native_features(data, features["old"], curves, contract_path, contract)
    assert np.array_equal(loaded["x_replicates"], features["x_replicates"])
    assert np.array_equal(loaded["well_ids"], features["well_ids"])
    checks.append("valid_synthetic_physical_join_recovers_every_native_replicate_and_well")
    mutations = [("raw_lib2", "library_id", "lib2"), ("raw_reserved_sample", "sample_id", "reserved_sample"), ("raw_wrong_patient", "patient_id", "wrong_patient"), ("raw_wrong_run", "run_id", "wrong_run"), ("raw_wrong_plate", "plate", "p3"), ("raw_wrong_drug", "drug_id", "unknown_drug"), ("raw_wrong_concentration", "dose_nM", "987654"), ("raw_wrong_assay", "assay_no", "wrong_assay")]
    for label, field, value in mutations:
        changed = copy.deepcopy(raw)
        changed[0][field] = value
        if label in ("raw_lib2", "raw_reserved_sample"):
            changed[0]["viability"] = "DO_NOT_CONVERT_RESERVED_RESPONSE"
        save_rows(curves, changed)
        message = rejected(lambda: evaluation.join_native_features(data, features["old"], curves, contract_path, contract))
        if label in ("raw_lib2", "raw_reserved_sample"):
            assert "Unreleased" in message
        checks.append("reject_" + label)
    save_rows(curves, raw + [raw[0]])
    rejected(lambda: evaluation.join_native_features(data, features["old"], curves, contract_path, contract), "Duplicate physical")
    checks.append("reject_duplicate_physical_response_before_join")
    save_rows(curves, raw)
    for label, field, value in (("candidate_dose", "native_concentration_nM", "987654"), ("candidate_coeff", "m_coefficient_on_this_well_decimal80", "999"), ("candidate_drug", "drug_id", "wrong_drug"), ("candidate_role", "node_role", "wrong_role"), ("candidate_assay", "assay_no", "wrong_assay"), ("candidate_patient", "patient_id", "wrong_patient"), ("candidate_lib2", "library_id", "lib2")):
        changed = copy.deepcopy(maps)
        changed[0][field] = value
        save_rows(directory / "candidate_native_wells.csv", changed)
        rejected(lambda: evaluation.join_native_features(data, features["old"], curves, contract_path, contract))
        checks.append("reject_" + label)
    save_rows(directory / "candidate_native_wells.csv", maps[:-1])
    rejected(lambda: evaluation.join_native_features(data, features["old"], curves, contract_path, contract))
    checks.append("reject_missing_candidate_map_even_when_node_occurs_elsewhere")
    save_rows(directory / "candidate_native_wells.csv", maps + [maps[0]])
    rejected(lambda: evaluation.join_native_features(data, features["old"], curves, contract_path, contract))
    checks.append("reject_extra_candidate_map_row")
    save_rows(directory / "candidate_native_wells.csv", maps)
    return checks


def method_checks(data, features, contract):
    checks = []
    x, y, patients, layout = features["x"], data["y"], data["patient_ids"], features["layout"]
    folds, _ = patient_folds(patients, 5, first.SALT + "|outer")
    training, test = folds != 0, folds == 0
    plan = methods.plan_panel(x[training], y[training], patients[training], layout)
    assert len(plan["selected_native_indices"]) == len(set(plan["selected_native_indices"])) == 32
    assert sum(q < 150 for q in plan["selected_native_indices"]) == 28
    assert len(plan["candidate_scores"]) == 10 and plan["original_upgrade_count"] == 6
    assert all(len(set(features["well_ids"][r, plan["selected_native_indices"]].ravel())) == 64 for r in np.flatnonzero(test))
    checks.append("exact_32_native_pairs_64_wells_22_old_targets_six_upgrades_two_missing_segments")
    for library in ("lib1", "lib2"):
        descriptor = copy.copy(layout.old_descriptor)
        descriptor.library_id = library
        other_layout = methods.layout_from_contract(descriptor, contract)
        assert len(other_layout.native_ids) == 164
        for candidate in other_layout.candidates:
            pair = np.asarray([[0.0, 1.0], [1.4, -0.1], [0.3, 0.3]])
            transformed = pair @ np.asarray(candidate["forward_matrix"]).T
            reconstructed = transformed @ np.asarray(candidate["inverse_matrix"]).T
            assert np.allclose(pair, reconstructed, rtol=0, atol=5e-15)
    checks.append("both_library_20_lossless_maps_recover_unclipped_synthetic_native_means")
    paid_train, paid_test = methods.acquire(x[training], plan), methods.acquire(x[test], plan)
    context = methods.fit_prediction_context(paid_train, y[training], patients[training], plan, layout.target_ids)
    weights = patient_weights(patients[training]); weights /= weights.sum()
    encoded = methods.encode_paid(paid_train, plan)
    mean_x, mean_y = weights @ encoded, weights @ y[training]
    scale = np.maximum(np.sqrt(weights @ (encoded - mean_x) ** 2), 0.05)
    assert np.array_equal(context.mean_x, mean_x) and np.array_equal(context.scale_x, scale)
    assert not np.allclose(mean_y, y[training].mean(axis=0), atol=1e-12, rtol=0)
    checks.append("equal_patient_weights_and_fold_local_point05_scale_floor")
    own = methods.BracketingPredictor(context, plan, 0.1, "own_drug_all24")
    original = own.predict(paid_test)
    for target in range(24):
        poison = paid_test.copy()
        foreign = np.asarray(plan["coordinate_target_indices"]) != target
        poison[:, foreign] += 100.0
        assert np.array_equal(own.predict(poison)[:, target], original[:, target])
        assert not own.beta[foreign, target].any()
    checks.append("all24_own_heads_ignore_every_foreign_paid_measurement_and_have_zero_foreign_coefficients")
    poison = x[test].copy()
    unpaid = np.setdiff1d(np.arange(x.shape[1]), plan["selected_native_indices"])
    poison[:, unpaid] = np.nan
    for family in methods.PREDICTORS:
        for lam in LAMBDAS:
            model = methods.BracketingPredictor(context, plan, lam, family)
            assert np.array_equal(model.predict(methods.acquire(poison, plan)), model.predict(paid_test))
            rejected(lambda: model.predict(x[test]))
    checks.append("all8_models_ignore_unpaid_native_nan_poison_and_reject_full_universe_prediction")
    x_poison, y_poison = x.copy(), y.copy()
    x_poison[test] = np.nan; y_poison[test] = np.nan
    plan2 = methods.plan_panel(x_poison[training], y_poison[training], patients[training], layout)
    assert plan2 == plan
    checks.append("outer_heldout_native_and_auc_poison_cannot_change_training_panel")
    tied = methods.plan_panel(x[training], np.zeros_like(y[training]), patients[training], layout)
    assert [c["q"] for c in tied["missing_drug_candidates"]] == [0.0, 0.0]
    checks.append("exact_q_proxy_ties_select_ascending_position")
    rejected(lambda: methods.BracketingPredictor(context, plan, 0.02, "own_drug_all24"))
    rejected(lambda: methods.BracketingPredictor(context, plan, 0.1, "unfrozen_family"))
    checks.append("unfrozen_penalty_and_architecture_rejected")
    return checks


def pipeline_checks(output, data, features):
    checks = []
    folds, _ = patient_folds(data["patient_ids"], 5, first.SALT + "|outer")
    # Synthetic comparator fixtures carry no scientific result or promotion claim.
    reference = {"predictions": {"reference_r8_own_hybrid": np.full_like(data["y"], 0.5), "reference_r7_shared": np.full_like(data["y"], 0.5)}, "folds": folds, "old_action_mask": np.zeros((len(folds), 150), dtype=bool), "provenance": {"synthetic_only": True}}
    for fold in range(5):
        train = folds != fold
        ctx = __import__("sparse_methods").fit_sparse_context(features["x"][train, :150], data["y"][train], data["patient_ids"][train], features["layout"].old_descriptor.query_ids, data["drug_ids"])
        selected, _ = __import__("sparse_methods").allocate(ctx, features["layout"].old_descriptor, "broad_drugwise", 0.1)
        reference["old_action_mask"][np.ix_(np.flatnonzero(~train), selected)] = True
    pipeline = output / "synthetic_pipeline"
    summary = evaluation.run(data, features, reference, pipeline, {"synthetic_only": True})
    assert summary["completed"] and summary["heldout_library_used"] is False
    checks.append("complete_synthetic_five_outer_three_inner_two_selector_four_penalty_pipeline")
    with np.load(pipeline / "oof_predictions.npz", allow_pickle=False) as saved:
        assert np.all(saved["action_mask"].sum(axis=1) == 32) and np.all(saved["original_action_mask"].sum(axis=1) == 28)
        assert saved["own_feature_mask"].shape == (5, 24, 32)
        assert np.all(np.isin(saved["own_feature_mask"].sum(axis=2), (1, 2)))
        for i in range(len(saved["y"])):
            assert len(set(saved["paid_source_well_ids"][i].ravel())) == 64
    checks.append("saved_oof_native_masks_own_masks_and_64_physical_ids_are_complete")
    for outer in range(5):
        folder = pipeline / f"outer_{outer:02d}" / "selection"
        selection = json.loads((folder / "selection.json").read_text())
        with np.load(folder / "inner_oof_predictions.npz", allow_pickle=False) as saved:
            for family in methods.PREDICTORS:
                recomputed = []
                for index, lam in enumerate(LAMBDAS):
                    losses = per_patient_loss(saved["y"], saved[f"{family}__lambda_{index}"], saved["patient_ids"])[1]
                    recomputed.append((float(losses.mean()), index, lam))
                minimum = min(recomputed)
                assert selection["selections"][family]["lambda"] == minimum[2]
        for inner in range(3):
            record = json.loads((folder / f"inner_{inner:02d}" / "scores.json").read_text())
            assert not set(record["training_patient_ids"]) & set(record["validation_patient_ids"])
            outer_test = set(data["patient_ids"][folds == outer])
            assert not outer_test & (set(record["training_patient_ids"]) | set(record["validation_patient_ids"]))
            plan = json.loads((folder / f"inner_{inner:02d}" / "plan.json").read_text())
            for chosen in plan["missing_drug_candidates"]:
                scores = [s for s in plan["candidate_scores"] if s["drug_id"] == chosen["drug_id"]]
                best = min(scores, key=lambda item: (item["residual_proxy"], item["q"]))
                assert chosen["feature_id"] == best["feature_id"]
    checks.append("all15_inner_panels_have_patient_isolation_q_minimizers_and_recomputable8_score_selections")
    # Poison full held-out arrays and reconstruct each saved training plan. This
    # checks that every one of the 20 actual fitting splits uses training rows.
    for outer in range(5):
        training = folds != outer
        poisoned_x, poisoned_y = features["x"].copy(), data["y"].copy()
        poisoned_x[~training] = np.nan; poisoned_y[~training] = np.nan
        plan = methods.plan_panel(poisoned_x[training], poisoned_y[training], data["patient_ids"][training], features["layout"])
        assert plan == json.loads((pipeline / f"outer_{outer:02d}" / "plan.json").read_text())
        inner_folds, _ = patient_folds(data["patient_ids"][training], 3, first.SALT + f"|inner|{outer}")
        for inner in range(3):
            inner_train = inner_folds != inner
            ix, iy = poisoned_x[training].copy(), poisoned_y[training].copy()
            ix[~inner_train] = np.nan; iy[~inner_train] = np.nan
            ip = methods.plan_panel(ix[inner_train], iy[inner_train], data["patient_ids"][training][inner_train], features["layout"])
            assert ip == json.loads((pipeline / f"outer_{outer:02d}" / "selection" / f"inner_{inner:02d}" / "plan.json").read_text())
    checks.append("all20_saved_panels_reproduce_bitexact_with_every_heldout_native_and_auc_value_nan_poisoned")
    contrasts = json.loads((pipeline / "paired_patient_contrasts.json").read_text())
    assert all(c["decomposition_max_patient_residual"] < 2e-16 for c in contrasts["contrasts"].values())
    checks.append("all24_equals_weighted_old22_plus_missing2_contrast_identity")
    manifest = json.loads((pipeline / "MANIFEST.json").read_text())
    assert all(first.sha(pipeline / name) == digest for name, digest in manifest["files"].items())
    checks.append("complete_synthetic_run_manifest_every_payload_hash_matches")
    return checks


def freeze_checks(output):
    """Exercise authorization before any loader using only generated fake inputs."""
    directory = output / "synthetic_freeze"
    directory.mkdir()
    project = Path(evaluation.__file__).resolve().parents[2]
    args = SimpleNamespace(protocol=directory / "PROTOCOL.txt", freeze=directory / "FREEZE.json", output=directory / "unused_attempt")
    args.protocol.write_text("Synthetic protocol fixture only.\n")
    fake_hashes = {}
    for name in evaluation.INPUT_HASHES:
        path = directory / (name + ".fake")
        path.write_text("Synthetic input bytes: " + name + "\n")
        setattr(args, name, path)
        fake_hashes[name] = first.sha(path)
    freeze = {"authorization": "exactly one TRAIN-only bracketing run", "protocol_sha256": first.sha(args.protocol), "code": {name: evaluation.code_hashes()[name] for name in evaluation.NEW_CODE}, "attempt": str(args.output.resolve().relative_to(project))}
    original_hashes = evaluation.INPUT_HASHES
    evaluation.INPUT_HASHES = fake_hashes
    messages = []
    try:
        first.dump(args.freeze, freeze)
        assert evaluation.check_freeze(args) == freeze
        for label, mutation in (("wrong_authorization", {"authorization": "anything"}), ("wrong_protocol", {"protocol_sha256": "0" * 64}), ("wrong_code", {"code": {**freeze["code"], "bracketing_methods.py": "0" * 64}}), ("wrong_attempt", {"attempt": "unused_wrong_attempt"})):
            first.dump(args.freeze, {**freeze, **mutation})
            messages.append({"case": label, "rejection": rejected(lambda: evaluation.check_freeze(args))})
        first.dump(args.freeze, freeze)
        args.train.write_text("Corrupted synthetic input bytes\n")
        messages.append({"case": "wrong_input_hash", "rejection": rejected(lambda: evaluation.check_freeze(args), "before numerical access")})
        assert not args.output.exists()
        first.dump(directory / "expected_rejections.json", messages)
    finally:
        evaluation.INPUT_HASHES = original_hashes
    return ["root_authorization_protocol_code_input_and_attempt_hash_gates_reject_before_loading"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--query-pool", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    first.dump(args.output / "STARTED.json", {"synthetic_only": True, "seed": 20260928, "code_hashes": evaluation.code_hashes()})
    try:
        if first.sha(args.query_pool) != evaluation.mechanism_eval.QUERY_POOL_SHA256 or first.sha(args.contract) != evaluation.CONTRACT_SHA256:
            raise ValueError("Synthetic preflight input metadata hash changed")
        pool, contract = json.loads(args.query_pool.read_text()), json.loads(args.contract.read_text())
        data, features = synthetic(pool, contract)
        with threadpool_limits(limits=1):
            checks = method_checks(data, features, contract)
            small_data = {k: (v[:3] if k != "drug_ids" else v) for k, v in data.items()}
            small_features = {**features, "x": features["x"][:3], "x_replicates": features["x_replicates"][:3], "well_ids": features["well_ids"][:3], "old": {**features["old"], "x": features["old"]["x"][:3], "x_replicates": features["old"]["x_replicates"][:3], "well_ids": features["old"]["well_ids"][:3]}}
            checks += loader_checks(args.output, small_data, small_features, contract)
            checks += pipeline_checks(args.output, data, features)
            checks += freeze_checks(args.output)
        first.dump(args.output / "checks.json", {"passed": True, "count": len(checks), "checks": checks, "synthetic_only": True, "real_train_responses_read": 0, "lib2_response_values_converted": 0, "code_hashes": evaluation.code_hashes()})
        print(json.dumps({"event": "synthetic_bracketing_pass", "checks": len(checks), "output": str(args.output)}))
    except Exception as exc:
        first.dump(args.output / "FAILURE.json", {"failed": True, "message": str(exc), "exception_type": type(exc).__name__, "traceback": traceback.format_exc(), "synthetic_only": True, "preserve_first_failure": True, "code_hashes": evaluation.code_hashes()})
        raise


if __name__ == "__main__":
    main()
