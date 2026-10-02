#!/usr/bin/env python3
"""Explicit, separately labelled baseline recovery for incomplete additive runs.

Never generates an additive-kernel prediction from incomplete values. Does not
impute, fit, change the acquisition or replace the primary prediction ledger.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import sys
import numpy as np
from additive_inference import AdditiveModel
from additive_workflow import load_backend

BASE_KIND = 'dosepilot.r13_own_drug_component'


def parse_partial(workflow, commitment, measurements):
    workflow.exact_keys(measurements, ['schema', 'commitment_id', 'sample_id',
                       'run_id', 'orientation', 'measurements'], 'partial_measurements')
    if measurements['schema'] != 'dosepilot.spectral_measurements.v1':
        raise workflow.WorkflowError('UNSUPPORTED_MEASUREMENT_SCHEMA')
    for key in ('commitment_id', 'sample_id', 'run_id', 'orientation'):
        if measurements[key] != commitment[key]:
            raise workflow.WorkflowError('MEASUREMENT_FRAME_MISMATCH: ' + key)
    rows = measurements['measurements']
    if not isinstance(rows, list) or len(rows) != 64:
        raise workflow.WorkflowError('EXACT_64_IDENTIFIED_RECORDS_REQUIRED')
    expected = {r['native_id']: r for r in commitment['requests']}
    values = {}
    for row in rows:
        workflow.exact_keys(row, ['native_id', 'drug_id', 'dose_nM', 'plate',
                                 'well_id', 'value'], 'partial_measurement')
        native = row['native_id']
        if not isinstance(native, str) or native not in expected or native in values:
            raise workflow.WorkflowError('UNKNOWN_OR_DUPLICATE_MEASUREMENT')
        for key in ('native_id', 'drug_id', 'dose_nM', 'plate', 'well_id'):
            if row[key] != expected[native][key]:
                raise workflow.WorkflowError('MEASUREMENT_IDENTITY_MISMATCH: ' + native)
        value = row['value']
        if value is not None:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise workflow.WorkflowError('ONLY_EXPLICIT_NULL_DENOTES_MISSING')
            try:
                value = float(value)
            except OverflowError as exc:
                raise workflow.WorkflowError('NONFINITE_MEASUREMENT') from exc
            if not math.isfinite(value):
                raise workflow.WorkflowError('NONFINITE_MEASUREMENT')
        values[native] = value
    if all(value is not None for value in values.values()):
        raise workflow.WorkflowError('COMPLETE_VALUES_USE_PRIMARY_WORKFLOW')
    return values


def compute_baseline(model, workflow, commitment, measurements):
    values = parse_partial(workflow, commitment, measurements)
    baseline = {}
    states = {}
    for j, target in enumerate(model.targets):
        positions = np.flatnonzero(model.a['feature_mask'][j])
        required = [model.native[i] for i in positions]
        missing = [native for native in required if values[native] is None]
        if missing:
            states[target] = {'state': 'WITHHELD', 'missing_inputs': missing}
            continue
        # Only complete own-head inputs enter this arithmetic. No stand-in
        # vector or filled missing coordinate is ever passed to a predictor.
        paid = np.array([values[native] for native in required], float)
        z = (paid-model.a['mean_x'][positions])/model.a['scale_x'][positions]
        output = float(model.a['mean_y'][j]+z@model.a['beta'][positions, j])
        if not math.isfinite(output):
            raise workflow.WorkflowError('NONFINITE_BASELINE_OUTPUT')
        baseline[target] = output
        states[target] = {'state': 'BASELINE_ONLY', 'model_kind': BASE_KIND,
                          'required_inputs': required}
    observed_hashes = {
        native: workflow.sha256_bytes(workflow.canonical(value))
        for native, value in values.items() if value is not None
    }
    return {
        'schema': 'dosepilot.explicit_baseline_recovery.v1',
        'status': 'PARTIAL_BASELINE_ONLY' if baseline else 'NO_BASELINE_OUTPUTS',
        'source_model_kind': model.MODEL_KIND,
        'baseline_model_kind': BASE_KIND,
        'primary_status': 'WITHHELD_INCOMPLETE_INPUT',
        'primary_predictions': {},
        'baseline_predictions': baseline,
        'target_states': states,
        'observed_value_hashes': observed_hashes,
        'received_values': len(observed_hashes),
        'missing_values': 64-len(observed_hashes),
        'kernel_prediction_called': False,
        'missing_values_imputed': False,
        'new_accuracy_claim': False,
        'research_only': True,
        'clinical_use_validated': False,
    }


def recover(model_dir, anchor, commitment_path, measurements_path,
            output_path, ledger_dir, acknowledge_baseline_only=False):
    workflow = load_backend()
    if not acknowledge_baseline_only:
        raise workflow.WorkflowError('EXPLICIT_BASELINE_ONLY_ACKNOWLEDGEMENT_REQUIRED')
    receipt = workflow.model_receipt(model_dir, anchor)
    model = AdditiveModel.load(model_dir)
    commitment, raw_commitment = workflow.load_json(commitment_path)
    workflow.validate_commitment(model, receipt, commitment)
    ledger = workflow.ledger_path(ledger_dir, commitment['frame_id'], '.commitment.json')
    if not ledger.is_file() or ledger.is_symlink():
        raise workflow.WorkflowError('COMMITMENT_NOT_IN_LEDGER')
    recorded_commitment, _ = workflow.load_json(ledger)
    if recorded_commitment != commitment:
        raise workflow.WorkflowError('LEDGER_COMMITMENT_MISMATCH')
    primary_path = workflow.ledger_path(ledger_dir, commitment['frame_id'], '.prediction.json')
    if primary_path.exists():
        raise workflow.WorkflowError('PRIMARY_RESULT_ALREADY_RECORDED')
    measurements, raw_measurements = workflow.load_json(measurements_path)
    report = compute_baseline(model, workflow, commitment, measurements)
    report.update(sample_id=commitment['sample_id'], run_id=commitment['run_id'],
                  orientation=commitment['orientation'])
    report['evidence'] = {
        **receipt,
        'commitment_id': commitment['commitment_id'],
        'commitment_file_sha256': workflow.sha256_bytes(raw_commitment),
        'measurements_file_sha256': workflow.sha256_bytes(raw_measurements),
        'recovery_code_sha256': workflow.digest(Path(__file__)),
        'committed_treatment_wells': 64,
        'controls_declared': len(commitment['controls_outside_treatment_budget']),
        'caller_declared_inventory': True,
        'laboratory_execution_certified': False,
    }
    root = Path(ledger_dir)
    prefix = commitment['frame_id'] + '.baseline_recovery.'
    report_id = workflow.sha256_bytes(workflow.canonical(report))
    report['recovery_id'] = report_id
    recovery_ledger = workflow.ledger_path(ledger_dir, prefix + report_id, '.json')
    # Later recovery reports may fill missing observations, but not rewrite or
    # discard previously recorded measurements. Prior reports stay immutable.
    for path in root.glob(prefix + '*.json'):
        if path.is_symlink():
            raise workflow.WorkflowError('SYMLINK_RECOVERY_LEDGER_REJECTED')
        previous, _ = workflow.load_json(path)
        if not isinstance(previous, dict) or 'recovery_id' not in previous:
            raise workflow.WorkflowError('MALFORMED_RECOVERY_LEDGER')
        body = {k: v for k, v in previous.items() if k != 'recovery_id'}
        expected_id = workflow.sha256_bytes(workflow.canonical(body))
        if previous['recovery_id'] != expected_id or path.name != prefix + expected_id + '.json':
            raise workflow.WorkflowError('RECOVERY_LEDGER_DIGEST_MISMATCH')
        if previous.get('evidence', {}).get('commitment_id') != commitment['commitment_id']:
            raise workflow.WorkflowError('RECOVERY_FRAME_MISMATCH')
        for native, fingerprint in previous['observed_value_hashes'].items():
            if report['observed_value_hashes'].get(native) != fingerprint:
                raise workflow.WorkflowError('PREVIOUS_OBSERVATION_CHANGED_OR_REMOVED')
    paths = [Path(output_path), recovery_ledger, ledger, primary_path,
             Path(commitment_path), Path(measurements_path)]
    if len({path.resolve() for path in paths}) != len(paths):
        raise workflow.WorkflowError('RECOVERY_OUTPUT_PATH_COLLISION')
    if recovery_ledger.exists():
        saved, _ = workflow.load_json(recovery_ledger)
        if saved != report:
            raise workflow.WorkflowError('RECOVERY_LEDGER_MISMATCH')
        if Path(output_path).exists():
            visible, _ = workflow.load_json(output_path)
            if visible != report:
                raise workflow.WorkflowError('RECOVERY_OUTPUT_MISMATCH')
        else:
            workflow.write_new(output_path, report)
    else:
        if Path(output_path).exists():
            raise workflow.WorkflowError('UNLEDGERED_RECOVERY_OUTPUT_EXISTS')
        workflow.write_new(recovery_ledger, report)
        workflow.write_new(output_path, report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('model-dir', 'commitment', 'measurements', 'output', 'ledger-dir'):
        parser.add_argument('--'+name, required=True, type=Path)
    parser.add_argument('--construction-sha256', required=True)
    parser.add_argument('--acknowledge-baseline-only', action='store_true')
    a = parser.parse_args()
    try:
        report = recover(a.model_dir, a.construction_sha256, a.commitment,
                         a.measurements, a.output, a.ledger_dir, a.acknowledge_baseline_only)
        print(json.dumps({'status': report['status'],
                          'baseline_outputs': len(report['baseline_predictions']),
                          'primary_outputs': 0, 'recovery_id': report['recovery_id']}))
        return 0
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print(json.dumps({'status': 'REJECTED', 'reason': str(exc)}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
