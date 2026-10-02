#!/usr/bin/env python3
"""One explicit commit/recover/predict interface for a constructed additive model.

This version combines durable create-exclusive publication, the numerically
verified compiled predictor, per-frame advisory transactions and automatic
recovery-history checking. It never changes the fitted model or imputes data.
Use a fresh runtime commitment; old code-bound commitments are not migrated.
"""
from pathlib import Path
import argparse
import importlib.util
import json
import sys

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
sys.path[:0] = [str(HERE), str(STUDY/'hybrid_residual')]
from durable_workflow import load_backend as durable_backend
from frame_lock import frame_lock

POLICY = 'dosepilot.durable_complete_lifecycle.v1'


def load_backend():
    backend = durable_backend()
    previous = backend.model_receipt
    hashes = {name: backend.digest(path) for name, path in {
        'lifecycle': HERE/'lifecycle.py',
        'frame_lock': HERE/'frame_lock.py',
        'baseline_recovery': STUDY/'hybrid_residual/recover_baseline.py',
        'recovery_completion': STUDY/'hybrid_residual/complete_recovery.py',
    }.items()}
    def receipt(model_dir, construction_sha256):
        return dict(previous(model_dir, construction_sha256),
                    lifecycle_policy=POLICY, lifecycle_code_sha256=hashes)
    backend.model_receipt = receipt
    return backend


def _recovery_module(name, backend):
    path = STUDY/'hybrid_residual'/(name+'.py')
    spec = importlib.util.spec_from_file_location('_dosepilot_lifecycle_'+name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # Only this isolated module instance changes. The original entry points
    # and imported model classes are neither modified nor monkey-patched.
    module.load_backend = lambda: backend
    return module


def execute(command, *, model_dir, construction_sha256, ledger_dir,
            commitment, inventory=None, template=None, measurements=None,
            output=None, acknowledge_baseline_only=False, _on_locked=None):
    if command not in ('commit', 'recover', 'predict'):
        raise ValueError('UNKNOWN_LIFECYCLE_COMMAND')
    backend = load_backend()
    receipt = backend.model_receipt(model_dir, construction_sha256)
    if command == 'commit':
        if inventory is None or template is None:
            raise ValueError('INVENTORY_AND_TEMPLATE_REQUIRED')
        identity, _ = backend.load_json(inventory)
    else:
        if measurements is None or output is None:
            raise ValueError('MEASUREMENTS_AND_OUTPUT_REQUIRED')
        identity, _ = backend.load_json(commitment)
    if not isinstance(identity, dict):
        raise ValueError('IDENTITY_DOCUMENT_MUST_BE_OBJECT')
    sample = backend.text_id(identity.get('sample_id'), 'sample_id')
    run = backend.text_id(identity.get('run_id'), 'run_id')
    frame = backend.frame_id(receipt, sample, run)
    # No temporary marker is used as a mutex. A real process-held lock covers
    # the history read, consistency checks and every publication in one frame.
    with frame_lock(ledger_dir, frame):
        if _on_locked is not None:
            _on_locked()
        snapshot_path = inventory if command == 'commit' else commitment
        current_identity, _ = backend.load_json(snapshot_path)
        if current_identity != identity:
            raise ValueError('IDENTITY_CHANGED_DURING_LOCK_ACQUISITION')
        if command == 'commit':
            return backend.commit(model_dir, construction_sha256, inventory,
                                  commitment, template, ledger_dir)
        if command == 'recover':
            recovery = _recovery_module('recover_baseline', backend)
            return recovery.recover(model_dir, construction_sha256, commitment,
                                    measurements, output, ledger_dir,
                                    acknowledge_baseline_only)
        history = list(Path(ledger_dir).glob(frame+'.baseline_recovery.*.json'))
        if history:
            completion = _recovery_module('complete_recovery', backend)
            return completion.complete(model_dir, construction_sha256, commitment,
                                       measurements, output, ledger_dir)
        return backend.predict(model_dir, construction_sha256, commitment,
                               measurements, output, ledger_dir)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for command in ('commit', 'recover', 'predict'):
        p = sub.add_parser(command)
        for name in ('model-dir', 'ledger-dir', 'commitment'):
            p.add_argument('--'+name, required=True, type=Path)
        p.add_argument('--construction-sha256', required=True)
        if command == 'commit':
            p.add_argument('--inventory', required=True, type=Path)
            p.add_argument('--template', required=True, type=Path)
        else:
            p.add_argument('--measurements', required=True, type=Path)
            p.add_argument('--output', required=True, type=Path)
        if command == 'recover':
            p.add_argument('--acknowledge-baseline-only', action='store_true')
    a = vars(parser.parse_args())
    try:
        result = execute(**a)
        if a['command'] == 'commit':
            summary = {'status': 'COMMITTED', 'committed_wells': 64,
                       'commitment_id': result['commitment_id']}
        elif a['command'] == 'recover':
            summary = {'status': result['status'], 'primary_outputs': 0,
                       'baseline_outputs': len(result['baseline_predictions'])}
        else:
            summary = {'status': result['status'],
                       'primary_outputs': len(result['predictions'])}
        print(json.dumps(dict(summary, lifecycle_policy=POLICY)))
        return 0
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print(json.dumps({'status': 'REJECTED', 'reason': str(exc)}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
