#!/usr/bin/env python3
"""One frozen RAW-AK Lib1 TRAIN experiment; no automatic retry."""
from __future__ import annotations
import os
for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
from pathlib import Path
import argparse, datetime, hashlib, importlib.metadata, json, sys, time, traceback
import numpy as np

BASE_OPTIONS = [('identity', 0.0)] + [(f, l) for f in (.1, .3, .6) for l in (.1, 1.0, 10.0)]
CANDIDATE_OPTIONS = [('identity', 0.0, 0.0)] + [
    (eta, f, l) for eta in (0.0, .5, 1.0)
    for f in (.1, .3, .6) for l in (.1, 1.0, 10.0)
]
EXPECTED = {'additive': .001060552730112811, 's2': .0010701439454817465,
            'r13': .001144858681382854, 'r18': .0011414048112341991}


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path, value):
    with Path(path).open('x') as handle:
        json.dump(value, handle, indent=2, allow_nan=False); handle.write('\n')
def require(condition, message):
    if not condition: raise ValueError(message)
def risks(prediction, truth, patients):
    error = ((prediction[0] - truth) ** 2 + (prediction[1] - truth) ** 2) / 2
    return np.stack([error[patients == group].mean(0) for group in np.unique(patients)])
def metrics(prediction, truth, patients, folds, targets):
    patient_target = risks(prediction, truth, patients); patient = patient_target.mean(1)
    ids = np.unique(patients)
    patient_fold = np.array([folds[np.flatnonzero(patients == group)[0]] for group in ids])
    return {
        'mse': float(patient.mean()),
        'p90_rmse': float(np.quantile(np.sqrt(patient), .9)),
        'fold_mse': [float(patient[patient_fold == fold].mean()) for fold in range(5)],
        'target_mse': dict(zip(map(str, targets), map(float, patient_target.mean(0)))),
        'orientation_mse': [float(np.mean([
            ((prediction[o, patients == group] - truth[patients == group]) ** 2).mean()
            for group in ids])) for o in (0, 1)],
    }


def compare(candidate_loss, reference_loss, candidate_metrics, reference_metrics,
            patient_folds, original=False):
    delta = candidate_loss - reference_loss
    rng = np.random.default_rng(20261003)
    bootstrap = delta[rng.integers(0, len(delta), (10000, len(delta)))].mean(1)
    wins = int((delta < 0).sum())
    fold_wins = sum(a < b for a, b in zip(candidate_metrics['fold_mse'], reference_metrics['fold_mse']))
    gate = {
        'mse': bool(candidate_metrics['mse'] <= .95 * reference_metrics['mse']) if original
               else bool(candidate_metrics['mse'] < reference_metrics['mse']),
        'patients': wins >= (40 if original else 30),
        'folds': fold_wins >= (4 if original else 3),
        'p90': candidate_metrics['p90_rmse'] <= reference_metrics['p90_rmse'],
    }
    if original:
        gate['each_orientation_below_reference_expected'] = (
            max(candidate_metrics['orientation_mse']) < reference_metrics['mse'])
    return {
        'relative_gain': 1 - candidate_metrics['mse'] / reference_metrics['mse'],
        'patient_wins': wins,
        'patient_losses': int((delta > 0).sum()),
        'ties': int((delta == 0).sum()),
        'fold_wins': fold_wins,
        'descriptive_delta_ci95': np.quantile(bootstrap, [.025, .975]).tolist(),
        'gate': gate, 'pass': all(gate.values()),
    }


def execute(args):
    study = args.study.resolve(); here = Path(__file__).resolve().parent
    require(not args.output.exists(), 'Output already exists; refuse duplicate execution')
    freeze = json.loads(args.freeze.read_text())
    for name, digest in freeze['source'].items():
        require(sha(here / name) == digest, 'Frozen source changed: ' + name)
    for name, digest in freeze['parent_source'].items():
        require(sha(study / name) == digest, 'Parent source changed: ' + name)
    require(sha(args.cache) == freeze['cache_sha256'], 'Input cache changed')
    require(sha(args.r18) == freeze['r18_sha256'], 'R18 artifact changed')
    lock = json.loads((study / 'STUDY_LOCK.json').read_text())
    for name, digest in lock['engine_files'].items():
        require(sha(study / 'engine' / name) == digest, 'Historical engine changed: ' + name)
    for name, version in lock['deps'].items():
        require(importlib.metadata.version(name) == version, 'Pinned dependency required: ' + name + '==' + version)
    sys.path[:0] = [str(study), str(study / 'engine'), str(study / 'acceleration'),
                    str(study / 'hybrid_residual'), str(here)]
    from methods import patient_folds
    import evaluate
    from coverage_methods import CoverageCatalog, CoveragePredictor, acquire, fit_prediction_context
    from fast_coverage import plan_panel_fast
    from kernel_spectral import KernelSpectral
    from additive_kernel import AdditiveKernel
    from aligned_additive_kernel import AlignedAdditiveKernel

    with np.load(args.cache, allow_pickle=False) as source:
        data = {key: source[key].copy() for key in source.files}
    x, y = data['x'], data['y']; patients = data['patient_ids'].astype(str)
    catalog = CoverageCatalog(data['native_ids'], data['drug_ids'],
                              data['native_target_indices'], tuple(data['concentrations']))
    require(y.shape == (119, 24) and len(set(patients)) == 59
            and set(data['library_ids']) == {'lib1'}, 'Task identity changed')
    args.output.mkdir(parents=True, exist_ok=False); started = time.monotonic()
    write(args.output / 'STARTED.json', {
        'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'freeze_sha256': sha(args.freeze), 'candidate_options': CANDIDATE_OPTIONS,
        'protected_response_access': False, 'original_workbook_opened': False,
        'automatic_retry': False,
    })
    outer_folds, _ = patient_folds(patients, 5, evaluate.SALT + '|outer')
    names = ('raw_ak', 'additive', 's2', 'r13')
    predictions = {name: np.full((2, *y.shape), np.nan) for name in names}
    records = []; containment = []; eta0_parity = 0.0

    def build(indices):
        nonlocal eta0_parity
        plan = plan_panel_fast(x[indices], y[indices], patients[indices], catalog)
        paid_a, paid_b = [acquire(x[indices], plan, o) for o in ('A', 'B')]
        context = fit_prediction_context(paid_a, paid_b, y[indices], patients[indices],
                                         plan, catalog.target_ids)
        base = CoveragePredictor(context, plan, .01)
        z = (np.r_[paid_a, paid_b] - base.mean_x) / base.scale_x
        residual = np.r_[y[indices] - base.predict(paid_a), y[indices] - base.predict(paid_b)]
        _, inverse, count = np.unique(patients[indices], return_inverse=True, return_counts=True)
        weights = np.tile(1. / (len(count) * count[inverse]), 2) / 2
        owner = np.asarray(plan['coordinate_target_indices'])
        additive = AdditiveKernel(z, residual, weights, owner)
        s2 = KernelSpectral(z, residual, weights, False)
        aligned = {eta: AlignedAdditiveKernel(z, residual, weights, owner, eta)
                   for eta in (0.0, .5, 1.0)}
        additive_coefficients = [np.zeros_like(residual)] + [
            additive.coefficients(lam, fraction)[0] for fraction, lam in BASE_OPTIONS[1:]
        ]
        s2_coefficients = [np.zeros_like(residual)] + [
            s2.coefficients(lam, fraction)[0] for fraction, lam in BASE_OPTIONS[1:]
        ]
        aligned_coefficients = {}
        for eta, model in aligned.items():
            aligned_coefficients[eta] = [
                model.coefficients(lam, fraction)[0]
                for fraction in (.1, .3, .6) for lam in (.1, 1.0, 10.0)
            ]
        eta0_parity = max(
            eta0_parity,
            float(np.max(np.abs(aligned[0.0].raw_cross(z) - additive.raw_cross(z)))),
            max(float(np.max(np.abs(a - b))) for a, b in
                zip(aligned_coefficients[0.0], additive_coefficients[1:])),
        )
        require(eta0_parity < 1e-10, 'Eta-zero incumbent parity failed')
        require(aligned[0.5].response_gram_norm > 1e-14,
                'Real fitting response Gram energy is degenerate')
        return plan, base, additive, additive_coefficients, s2, s2_coefficients, aligned, aligned_coefficients

    def predict_options(indices, bundle):
        nonlocal eta0_parity
        plan, base, additive, add_coef, s2, s2_coef, aligned, aligned_coef = bundle
        candidate = np.empty((28, 2, len(indices), 24))
        additive_out = np.empty((10, 2, len(indices), 24))
        s2_out = np.empty((10, 2, len(indices), 24))
        for orientation_index, orientation in enumerate(('A', 'B')):
            paid = acquire(x[indices], plan, orientation)
            z = (paid - base.mean_x) / base.scale_x; baseline = base.predict(paid)
            candidate[0, orientation_index] = baseline
            add_cross = additive.centered_cross(z); s2_cross = s2.centered_cross(z)
            for option, coefficient in enumerate(add_coef):
                additive_out[option, orientation_index] = baseline + add_cross @ coefficient
            for option, coefficient in enumerate(s2_coef):
                s2_out[option, orientation_index] = baseline + s2_cross @ coefficient
            offset = 1
            for eta in (0.0, .5, 1.0):
                cross = aligned[eta].centered_cross(z)
                for coefficient in aligned_coef[eta]:
                    candidate[offset, orientation_index] = baseline + cross @ coefficient
                    offset += 1
            eta0_parity = max(eta0_parity, float(np.max(np.abs(
                candidate[1:10, orientation_index] - additive_out[1:10, orientation_index]))))
            require(eta0_parity < 1e-10, 'Eta-zero query prediction parity failed')
        return candidate, additive_out, s2_out

    for outer in range(5):
        train = np.flatnonzero(outer_folds != outer); test = np.flatnonzero(outer_folds == outer)
        require(not set(patients[train]) & set(patients[test]), 'Outer patient leakage')
        inner_folds, _ = patient_folds(patients[train], 3, evaluate.SALT + f'|inner|{outer}')
        inner_candidate = np.full((28, 2, len(train), 24), np.nan)
        inner_additive = np.full((10, 2, len(train), 24), np.nan)
        inner_s2 = np.full((10, 2, len(train), 24), np.nan)
        folder = args.output / f'outer_{outer:02}'; folder.mkdir()
        for inner in range(3):
            fit = train[inner_folds != inner]; validation = train[inner_folds == inner]
            require(not set(patients[fit]) & set(patients[validation]), 'Inner patient leakage')
            candidate, additive_out, s2_out = predict_options(validation, build(fit))
            mask = inner_folds == inner
            inner_candidate[:, :, mask] = candidate
            inner_additive[:, :, mask] = additive_out
            inner_s2[:, :, mask] = s2_out
            containment.append({'outer': outer, 'inner': inner,
                                'fit_patients': len(set(patients[fit])),
                                'validation_patients': len(set(patients[validation])),
                                'disjoint': True})
        require(np.isfinite(inner_candidate).all() and np.isfinite(inner_additive).all()
                and np.isfinite(inner_s2).all(), 'Incomplete inner predictions')
        candidate_scores = [float(risks(value, y[train], patients[train]).mean())
                            for value in inner_candidate]
        additive_scores = [float(risks(value, y[train], patients[train]).mean())
                           for value in inner_additive]
        s2_scores = [float(risks(value, y[train], patients[train]).mean())
                     for value in inner_s2]
        choices = {
            'raw_ak': min(range(28), key=lambda i: (candidate_scores[i], i)),
            'additive': min(range(10), key=lambda i: (additive_scores[i], i)),
            's2': min(range(10), key=lambda i: (s2_scores[i], i)),
        }
        bundle = build(train); candidate, additive_out, s2_out = predict_options(test, bundle)
        predictions['raw_ak'][:, test] = candidate[choices['raw_ak']]
        predictions['additive'][:, test] = additive_out[choices['additive']]
        predictions['s2'][:, test] = s2_out[choices['s2']]
        predictions['r13'][:, test] = candidate[0]
        plan, base, additive, add_coef, s2, s2_coef, aligned, aligned_coef = bundle
        native = np.asarray(plan['selected_native_indices'])
        require(len(set(native)) == 64, 'Duplicate selected native measurement')
        for orientation in ('A', 'B'):
            plate = np.asarray(plan[f'orientation_{orientation}_plate_indices'])
            physical = data['well_ids'][test][:, native, plate]
            require((plate == 0).sum() == 32 and (plate == 1).sum() == 32
                    and all(len(set(row)) == 64 for row in physical), 'Physical budget changed')
            paid = acquire(x[test], plan, orientation)
            masked = np.full_like(x[test], np.nan); masked[:, native, plate] = paid
            np.testing.assert_array_equal(acquire(masked, plan, orientation), paid)
        write(folder / 'plan.json', plan)
        np.savez_compressed(folder / 'inner_predictions_private.npz', raw_ak=inner_candidate,
                            additive=inner_additive, s2=inner_s2, y=y[train],
                            patients=patients[train], inner_folds=inner_folds)
        selected = choices['raw_ak']
        if selected:
            eta, _, _ = CANDIDATE_OPTIONS[selected]
            model = aligned[eta]; coefficient = aligned_coef[eta][(selected - 1) % 9]
            np.savez_compressed(folder / 'raw_ak_model_private.npz', **base.arrays(),
                                **model.arrays(coefficient), residual_training_private=model.residual,
                                selected_identity=np.asarray(False))
        else:
            np.savez_compressed(folder / 'raw_ak_model_private.npz', **base.arrays(),
                                selected_identity=np.asarray(True))
        record = {
            'fold': outer,
            'selected': {
                'raw_ak': CANDIDATE_OPTIONS[choices['raw_ak']],
                'additive': BASE_OPTIONS[choices['additive']],
                's2': BASE_OPTIONS[choices['s2']],
            },
            'inner_mse': {'raw_ak': candidate_scores, 'additive': additive_scores,
                          's2': s2_scores},
            'distinct_physical_wells': 64, 'per_plate': 32,
            'unpaid_values_masked': True,
        }
        records.append(record); write(folder / 'selection.json', record)
        print(json.dumps({'fold_completed': outer, 'selected': record['selected'],
                          'seconds': time.monotonic() - started}), flush=True)

    require(all(np.isfinite(value).all() for value in predictions.values()),
            'Incomplete held-patient predictions')
    np.savez_compressed(args.output / 'predictions_private.npz', **predictions, y=y,
                        patients=patients, folds=outer_folds,
                        sample_ids=data['sample_ids'], drug_ids=data['drug_ids'])
    write(args.output / 'PREDICTIONS_COMMITTED.json', {
        'sha256': sha(args.output / 'predictions_private.npz'),
        'historical_r18_prediction_arrays_parsed': False,
    })
    summaries = {name: metrics(value, y, patients, outer_folds, data['drug_ids'])
                 for name, value in predictions.items()}
    for name in ('additive', 's2', 'r13'):
        require(abs(summaries[name]['mse'] - EXPECTED[name]) <= 1e-12,
                'Historical control failed: ' + name)
    with np.load(args.r18, allow_pickle=False) as reference:
        for key, value in [('y', y), ('sample_ids', data['sample_ids']),
                           ('patient_ids', patients), ('drug_ids', data['drug_ids']),
                           ('folds', outer_folds)]:
            require(np.array_equal(reference[key], value), 'R18 identity mismatch: ' + key)
        r18 = np.stack([reference['candidate_A'], reference['candidate_B']])
    summaries['r18'] = metrics(r18, y, patients, outer_folds, data['drug_ids'])
    require(abs(summaries['r18']['mse'] - EXPECTED['r18']) <= 1e-12, 'R18 score changed')
    patient_loss = {name: risks(value, y, patients).mean(1)
                    for name, value in {**predictions, 'r18': r18}.items()}
    patient_ids = np.unique(patients)
    patient_folds = np.array([outer_folds[np.flatnonzero(patients == group)[0]]
                              for group in patient_ids])
    comparisons = {
        reference: compare(patient_loss['raw_ak'], patient_loss[reference],
                           summaries['raw_ak'], summaries[reference], patient_folds,
                           reference in ('r13', 'r18'))
        for reference in ('additive', 's2', 'r13', 'r18')
    }
    additive_equivalence_max_error = float(np.max(
        np.abs(predictions['raw_ak'] - predictions['additive'])))
    equivalent_to_additive = additive_equivalence_max_error <= 1e-12
    if equivalent_to_additive:
        comparisons['additive']['gate']['mse'] = False
        comparisons['additive']['pass'] = False
    additive_target = summaries['additive']['target_mse']
    target_regressions = [name for name, value in summaries['raw_ak']['target_mse'].items()
                          if value > additive_target[name]]
    patient_regressions = [str(name) for name, c, r in
                           zip(patient_ids, patient_loss['raw_ak'], patient_loss['additive'])
                           if c > r]
    decision = ('ELIGIBLE_RESEARCH_SUCCESSOR' if all(item['pass'] for item in comparisons.values())
                else 'REJECT_RETAIN_ADDITIVE')
    result = {
        'status': 'COMPLETE', 'decision': decision, 'metrics': summaries,
        'comparisons': comparisons, 'selections': records, 'containment': containment,
        'eta0_parity_max_error': eta0_parity,
        'additive_equivalence_max_error': additive_equivalence_max_error,
        'equivalent_to_additive': equivalent_to_additive,
        'target_regressions_vs_additive': target_regressions,
        'patient_regressions_vs_additive': patient_regressions,
        'cohort': {'samples': 119, 'patients': 59, 'targets': 24,
                   'wells_per_alternative': 64, 'per_plate': 32},
        'prediction_sha256': sha(args.output / 'predictions_private.npz'),
        'freeze_sha256': sha(args.freeze), 'input_role': 'authorized_private_lib1_train_cache',
        'independent_validation': False, 'bootstrap_selection_corrected': False,
        'protected_response_access': False, 'original_workbook_opened': False,
        'accepted_entry_changed': False, 'elapsed_seconds': time.monotonic() - started,
    }
    write(args.output / 'RESULT.json', result)
    print(json.dumps({'status': result['status'], 'decision': decision,
                      'mse': {name: value['mse'] for name, value in summaries.items()},
                      'comparisons': comparisons,
                      'target_regressions': target_regressions,
                      'patient_regressions': patient_regressions}, indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('study', 'cache', 'r18', 'freeze', 'output'):
        parser.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists(): parser.error('Output exists; refuse duplicate attempt')
    try: execute(args)
    except BaseException as exc:
        if args.output.exists():
            write(args.output / 'FAILURE.json', {'type': type(exc).__name__,
                  'message': str(exc), 'traceback': traceback.format_exc(),
                  'automatic_retry': False})
        raise


if __name__ == '__main__': main()
