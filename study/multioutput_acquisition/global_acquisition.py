"""One fitting-only, fixed-budget block sweep for multioutput measurement choice.

This is a regularized linear covariance proxy, not a calibrated uncertainty
estimate, a global optimum, or held-patient accuracy. Each block retains its
original number of doses and plate positions. No response is read at inference
except the 64 values specified by the resulting fixed plan.
"""
from __future__ import annotations
import copy
from decimal import Decimal
from itertools import combinations
import numpy as np
from coverage_methods import validate_catalog, validate_plan

PROXY_ALPHA = 0.1
MIN_PROXY_GAIN = 1e-12


def moments(replicates, y, patients):
    x, y = np.asarray(replicates, float), np.asarray(y, float)
    p = np.asarray(patients, str)
    if (x.ndim != 3 or x.shape[-1] != 2 or y.shape != (len(x), 24)
        or p.shape != (len(x),) or not len(p) or not np.isfinite(x).all()
        or not np.isfinite(y).all()):
        raise ValueError('Malformed fitting data')
    ids, inv, count = np.unique(p, return_inverse=True, return_counts=True)
    w = np.tile(1./(len(ids)*count[inv]), 2)/2
    full = np.vstack([x.reshape(len(x), -1), x[:, :, ::-1].reshape(len(x), -1)])
    yy = np.tile(y, (2, 1))
    mx, my = w@full, w@yy
    scale = np.maximum(np.sqrt(w@((full-mx)**2)), 0.05)
    z = (full-mx)/scale
    centered = yy-my
    gram = (z.T*w)@z
    cross = (z.T*w)@centered
    variance = float(np.sum(w@(centered*centered)))
    return gram, cross, variance


def direct_proxy(gram, cross, variance, columns):
    c = np.asarray(columns, int)
    g = gram[np.ix_(c, c)] + PROXY_ALPHA*np.eye(len(c))
    b = cross[c]
    return float((variance-np.sum(b*np.linalg.solve(g, b)))/24)


def block_scores(gram, cross, variance, retained, candidates):
    """Schur-complement scores, algebraically equivalent to full solves."""
    retained = np.asarray(retained, int)
    hr = gram[np.ix_(retained, retained)] + PROXY_ALPHA*np.eye(len(retained))
    br = cross[retained]
    solve_br = np.linalg.solve(hr, br)
    explained_retained = float(np.sum(br*solve_br))
    # Solve once for the complete native universe, then reuse small blocks.
    solve_all = np.linalg.solve(hr, gram[retained])
    out = []
    for candidate in candidates:
        c = np.asarray(candidate, int)
        qr = gram[np.ix_(c, retained)]
        schur = gram[np.ix_(c, c)] + PROXY_ALPHA*np.eye(len(c)) - qr@solve_all[:, c]
        schur = (schur+schur.T)/2
        conditional = cross[c]-qr@solve_br
        extra = float(np.sum(conditional*np.linalg.solve(schur, conditional)))
        out.append(float((variance-explained_retained-extra)/24))
    return np.asarray(out)


def optimize(replicates, y, patients, catalog, starting_plan):
    """Perform exactly one lexicographic sweep, starting from fitting-only R13."""
    validate_catalog(catalog); validate_plan(starting_plan, catalog)
    gram, cross, variance = moments(replicates, y, patients)
    selected = np.asarray(starting_plan['selected_native_indices'], int).copy()
    owner = np.asarray(starting_plan['coordinate_target_indices'], int)
    plates = np.asarray(starting_plan['orientation_A_plate_indices'], int)
    initial = direct_proxy(gram, cross, variance, 2*selected+plates)
    current = initial
    records = []
    for target in sorted(range(24), key=lambda j: str(catalog.target_ids[j])):
        pos = np.flatnonzero(owner == target)
        others = np.flatnonzero(owner != target)
        native = sorted(map(int, np.flatnonzero(catalog.native_target_indices == target)),
                        key=lambda i: (Decimal(catalog.concentrations[i]), str(catalog.native_ids[i])))
        previous = tuple(map(int, selected[pos]))
        options = [previous] + [c for c in combinations(native, len(pos)) if c != previous]
        candidates = [2*np.asarray(s)+plates[pos] for s in options]
        retained = 2*selected[others]+plates[others]
        scores = block_scores(gram, cross, variance, retained, candidates)
        best = min(range(len(scores)), key=lambda i: (scores[i], i))
        # Require a strictly meaningful improvement in proxy arithmetic. There
        # is no post-result patient/target-specific rule and no extra sweep.
        accepted = scores[best] < scores[0] - MIN_PROXY_GAIN
        if not accepted:
            best = 0
        before = current
        selected[pos] = options[best]
        current = direct_proxy(gram, cross, variance, 2*selected+plates)
        if current > before + 1e-12 or abs(current-scores[best]) > 1e-11:
            raise ValueError('Proxy monotonicity or Schur identity failed')
        records.append({'target': str(catalog.target_ids[target]),
            'options': len(options), 'selected_option': best, 'changed': bool(accepted),
            'previous_native_indices': list(previous),
            'selected_native_indices': list(map(int, selected[pos])),
            'proxy_before': before, 'proxy_after': current,
            'all_proxy_scores': scores.tolist()})
    plan = copy.deepcopy(starting_plan)
    for name in ('choices', 'all_subset_scores'):
        if name in plan:
            plan['starting_r13_'+name] = plan.pop(name)
    plan.update(selected_native_indices=selected.tolist(),
                selected_native_ids=list(map(str, catalog.native_ids[selected])),
                selected_concentrations_nM=[str(catalog.concentrations[i]) for i in selected],
                acquisition_kind='dosepilot.fitting_only_global_covariance_sweep.v1',
                proxy_alpha=PROXY_ALPHA, sweeps=1,
                proxy_initial=initial, proxy_final=current,
                search_records=records,
                changed_targets=sum(r['changed'] for r in records))
    validate_plan(plan, catalog)
    if (plan['coordinate_target_indices'] != starting_plan['coordinate_target_indices']
        or plan['orientation_A_plate_indices'] != starting_plan['orientation_A_plate_indices']):
        raise ValueError('Acquisition altered fixed costs')
    return plan
