#!/usr/bin/env python3
"""No-refit arithmetic, selection, alignment and prediction audit for RAW-AK."""
from __future__ import annotations
import os
for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
from pathlib import Path
import argparse, datetime, hashlib, json, math, sys
import numpy as np

BASE_OPTIONS = [('identity', 0.0)] + [
    (fraction, penalty) for fraction in (.1, .3, .6) for penalty in (.1, 1.0, 10.0)
]
CANDIDATE_OPTIONS = [('identity', 0.0, 0.0)] + [
    (eta, fraction, penalty) for eta in (0.0, .5, 1.0)
    for fraction in (.1, .3, .6) for penalty in (.1, 1.0, 10.0)
]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def average(values):
    values = list(map(float, values))
    return math.fsum(values) / len(values)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def patient_target_loss(prediction, truth, patients):
    rows = []
    for patient in sorted(set(patients)):
        indices = np.flatnonzero(patients == patient)
        rows.append([
            average(
                ((float(prediction[0, row, target]) - float(truth[row, target])) ** 2
                 + (float(prediction[1, row, target]) - float(truth[row, target])) ** 2) / 2
                for row in indices
            )
            for target in range(24)
        ])
    return np.asarray(rows)


def independent_metrics(prediction, truth, patients, folds, targets):
    matrix = patient_target_loss(prediction, truth, patients)
    patient = np.asarray([average(row) for row in matrix])
    ids = np.asarray(sorted(set(patients)))
    patient_folds = np.asarray([folds[np.flatnonzero(patients == item)[0]] for item in ids])
    return {
        'mse': average(patient),
        'p90_rmse': float(np.quantile(np.sqrt(patient), .9)),
        'fold_mse': [average(patient[patient_folds == fold]) for fold in range(5)],
        'target_mse': dict(zip(map(str, targets), [average(matrix[:, i]) for i in range(24)])),
        'orientation_mse': [average(
            average(((prediction[orientation, patients == item] - truth[patients == item]) ** 2).ravel())
            for item in ids
        ) for orientation in (0, 1)],
        'patient_loss': patient,
        'patient_folds': patient_folds,
    }


def gaussian_groups(query, training, owner):
    result = []
    for target in range(24):
        group = np.flatnonzero(owner == target)
        a, b = query[:, group], training[:, group]
        distance = np.maximum(
            np.sum(a * a, axis=1)[:, None] + np.sum(b * b, axis=1)[None, :]
            - 2 * a @ b.T, 0.0)
        result.append(np.exp(-distance / (2 * len(group))))
    return result


def raw_kernel(query, model):
    training = model['z_training']; owner = model['kernel_owner']
    raw = query @ training.T
    for target, component in enumerate(gaussian_groups(query, training, owner)):
        raw += int((owner == target).sum()) * float(model['group_scale'][target]) * component
    return raw


def recompute_alignment(model):
    z = model['z_training']; residual = model['residual_training_private']
    weights = model['weights']; owner = model['kernel_owner']; sw = np.sqrt(weights)
    centered_residual = residual - weights @ residual
    response = sw[:, None] * (centered_residual @ centered_residual.T / 24) * sw[None, :]
    response_norm = float(np.linalg.norm(response))
    alignments, energy = [], []
    for component in gaussian_groups(z, z, owner):
        right = component @ weights; left = weights @ component
        centered = component - right[:, None] - left[None, :] + float(left @ weights)
        weighted = sw[:, None] * centered * sw[None, :]
        denominator = float(np.linalg.norm(weighted) * response_norm)
        alignments.append(0.0 if denominator <= 1e-14 else max(
            0.0, float(np.sum(weighted * response) / denominator)))
        energy.append(float(np.trace(weighted)))
    alignments = np.asarray(alignments); energy = np.asarray(energy)
    eta = float(model['alignment_eta'])
    if eta == 0:
        scales = np.ones(24)
    elif response_norm <= 1e-14:
        scales = np.ones(24)
    else:
        widths = np.asarray([(owner == target).sum() for target in range(24)], float)
        score = np.maximum(alignments, 1e-12) ** eta
        scales = score * np.sum(widths * energy) / np.sum(widths * energy * score)
    return response_norm, alignments, energy, scales


def run(args):
    result = json.loads((args.run / 'RESULT.json').read_text())
    with np.load(args.run / 'predictions_private.npz', allow_pickle=False) as source:
        values = {key: source[key].copy() for key in source.files}
    with np.load(args.cache, allow_pickle=False) as source:
        cache = {key: source[key].copy() for key in source.files}
    require(sha(args.run / 'predictions_private.npz') == result['prediction_sha256'],
            'Prediction artifact changed')
    require(np.array_equal(cache['y'], values['y'])
            and np.array_equal(cache['sample_ids'], values['sample_ids'])
            and np.array_equal(cache['patient_ids'].astype(str), values['patients'])
            and np.array_equal(cache['drug_ids'], values['drug_ids']), 'Cache identity changed')
    truth, patients, folds = values['y'], values['patients'], values['folds']
    checked, max_difference = 0, 0.0

    def close(name, actual, recorded, tolerance=1e-12):
        nonlocal checked, max_difference
        difference = float(np.max(np.abs(np.asarray(actual, float) - np.asarray(recorded, float))))
        checked += 1; max_difference = max(max_difference, difference)
        require(difference <= tolerance, name + ' differs')

    metrics = {}
    for name in ('raw_ak', 'additive', 's2', 'r13'):
        metrics[name] = independent_metrics(values[name], truth, patients, folds, values['drug_ids'])
        recorded = result['metrics'][name]
        close(name + '/mse', metrics[name]['mse'], recorded['mse'])
        close(name + '/p90', metrics[name]['p90_rmse'], recorded['p90_rmse'])
        close(name + '/folds', metrics[name]['fold_mse'], recorded['fold_mse'])
        close(name + '/orientations', metrics[name]['orientation_mse'], recorded['orientation_mse'])
        close(name + '/targets', list(metrics[name]['target_mse'].values()),
              list(recorded['target_mse'].values()))
    with np.load(args.r18, allow_pickle=False) as source:
        require(np.array_equal(source['y'], truth) and np.array_equal(source['folds'], folds),
                'R18 task identity changed')
        r18 = np.stack([source['candidate_A'], source['candidate_B']])
    metrics['r18'] = independent_metrics(r18, truth, patients, folds, values['drug_ids'])
    for key in ('mse', 'p90_rmse', 'fold_mse', 'orientation_mse'):
        close('r18/' + key, metrics['r18'][key], result['metrics']['r18'][key])

    for reference in ('additive', 's2', 'r13', 'r18'):
        candidate, old = metrics['raw_ak'], metrics[reference]
        delta = candidate['patient_loss'] - old['patient_loss']
        wins = int((delta < 0).sum()); fold_wins = sum(
            left < right for left, right in zip(candidate['fold_mse'], old['fold_mse']))
        original = reference in ('r13', 'r18')
        gate = {
            'mse': bool(candidate['mse'] <= .95 * old['mse']) if original
                   else bool(candidate['mse'] < old['mse']),
            'patients': wins >= (40 if original else 30),
            'folds': fold_wins >= (4 if original else 3),
            'p90': candidate['p90_rmse'] <= old['p90_rmse'],
        }
        if original:
            gate['each_orientation_below_reference_expected'] = (
                max(candidate['orientation_mse']) < old['mse'])
        comparison = result['comparisons'][reference]
        close(reference + '/gain', 1 - candidate['mse'] / old['mse'], comparison['relative_gain'])
        close(reference + '/wins', wins, comparison['patient_wins'], 0)
        close(reference + '/losses', int((delta > 0).sum()), comparison['patient_losses'], 0)
        close(reference + '/ties', int((delta == 0).sum()), comparison['ties'], 0)
        close(reference + '/fold_wins', fold_wins, comparison['fold_wins'], 0)
        rng = np.random.default_rng(20261003)
        bootstrap = delta[rng.integers(0, len(delta), (10000, len(delta)))].mean(1)
        close(reference + '/interval', np.quantile(bootstrap, [.025, .975]),
              comparison['descriptive_delta_ci95'], 2e-12)
        equivalent = float(np.max(np.abs(values['raw_ak'] - values['additive']))) <= 1e-12
        if reference == 'additive' and equivalent:
            gate['mse'] = False
        require(gate == comparison['gate'] and all(gate.values()) == comparison['pass'],
                reference + ' gate differs')

    sys.path[:0] = [str(args.study / 'engine')]
    from coverage_methods import acquire
    model_checks = 0; alignment_difference = 0.0; prediction_difference = 0.0
    for outer in range(5):
        folder = args.run / f'outer_{outer:02}'
        selection = json.loads((folder / 'selection.json').read_text())
        with np.load(folder / 'inner_predictions_private.npz', allow_pickle=False) as source:
            for family, options in (('raw_ak', CANDIDATE_OPTIONS),
                                    ('additive', BASE_OPTIONS), ('s2', BASE_OPTIONS)):
                scores = [average(patient_target_loss(prediction, source['y'],
                                                       source['patients']).mean(1))
                          for prediction in source[family]]
                close(f'outer{outer}/{family}/inner', scores,
                      selection['inner_mse'][family], 2e-12)
                selected = min(range(len(scores)), key=lambda index: (scores[index], index))
                require(list(options[selected]) == selection['selected'][family],
                        f'Outer {outer} {family} selection differs')
        plan = json.loads((folder / 'plan.json').read_text())
        test = folds == outer
        with np.load(folder / 'raw_ak_model_private.npz', allow_pickle=False) as source:
            model = {key: source[key].copy() for key in source.files}
        identity = bool(model['selected_identity'])
        require(identity == (selection['selected']['raw_ak'][0] == 'identity'),
                'Identity marker differs')
        for orientation_index, orientation in enumerate(('A', 'B')):
            paid = acquire(cache['x'][test], plan, orientation)
            query = (paid - model['mean_x']) / model['scale_x']
            predicted = model['mean_y'] + query @ model['beta']
            if not identity:
                response_norm, alignments, energy, scales = recompute_alignment(model)
                alignment_difference = max(alignment_difference,
                    abs(response_norm - float(model['response_gram_norm'])),
                    float(np.max(np.abs(alignments - model['group_alignments']))),
                    float(np.max(np.abs(energy - model['group_energy']))),
                    float(np.max(np.abs(scales - model['group_scale']))))
                raw = raw_kernel(query, model)
                centered = (raw - (raw @ model['weights'])[:, None]
                            - model['train_kernel_mean'][None, :] + float(model['kernel_grand']))
                predicted += centered @ model['dual_coefficients']
            difference = float(np.max(np.abs(predicted - values['raw_ak'][orientation_index, test])))
            prediction_difference = max(prediction_difference, difference)
            require(difference <= 1e-11, 'Held-patient model reload differs')
        model_checks += 1
    require(alignment_difference <= 1e-11, 'Alignment reconstruction differs')
    equivalent_error = float(np.max(np.abs(values['raw_ak'] - values['additive'])))
    close('additive_equivalence', equivalent_error, result['additive_equivalence_max_error'])
    require((equivalent_error <= 1e-12) == result['equivalent_to_additive'],
            'Equivalence decision differs')
    expected_decision = ('ELIGIBLE_RESEARCH_SUCCESSOR' if
                         all(item['pass'] for item in result['comparisons'].values())
                         else 'REJECT_RETAIN_ADDITIVE')
    require(expected_decision == result['decision'], 'Final decision differs')
    report = {
        'status': 'PASS',
        'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'arithmetic_checks': checked,
        'max_metric_difference': max_difference,
        'selected_model_checks': model_checks,
        'alignment_reconstruction_max_difference': alignment_difference,
        'held_patient_prediction_max_difference': prediction_difference,
        'all_declared_gates_recomputed': True,
        'model_fit_called': False,
        'authorized_private_lib1_cache_read': True,
        'original_workbook_opened': False,
        'protected_response_access': False,
        'result_sha256': sha(args.run / 'RESULT.json'),
        'predictions_sha256': sha(args.run / 'predictions_private.npz'),
        'verifier_sha256': sha(__file__),
    }
    with args.output.open('x') as handle:
        json.dump(report, handle, indent=2, allow_nan=False); handle.write('\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('run', 'cache', 'r18', 'study', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    run(parser.parse_args())
