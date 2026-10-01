"""Identity-checked inference for a constructed spectral research model.

A single missing required measurement withholds all 24 outputs. This global
correction does not inherit the original own-head selective-abstention rule.
The caller supplies real well identities; this is not a laboratory inventory
service and cannot verify that a submitted value came from that physical well.
"""
from __future__ import annotations
import argparse
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import numpy as np


def digest(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def dose(value):
    if isinstance(value, bool):
        raise ValueError('Boolean dose is invalid')
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError('Invalid dose identity') from None
    if not d.is_finite() or d <= 0:
        raise ValueError('Dose must be positive and finite')
    return d


class SpectralModel:
    def __init__(self, arrays, plan):
        self.a = {k: np.array(v, copy=True) for k, v in arrays.items()}
        self.plan = plan
        for key, shape in [('mean_x', (64,)), ('scale_x', (64,)),
                           ('mean_y', (24,)), ('beta', (64, 24)),
                           ('correction', (64, 24))]:
            if key not in self.a or self.a[key].shape != shape or not np.isfinite(self.a[key]).all():
                raise ValueError('Malformed model parameter: ' + key)
        if np.any(self.a['scale_x'] < .05):
            raise ValueError('Invalid feature scale')
        self.native = list(map(str, self.a['native_ids']))
        self.targets = list(map(str, self.a['drug_ids']))
        if len(self.native) != 64 or len(set(self.native)) != 64 or len(self.targets) != 24 or len(set(self.targets)) != 24:
            raise ValueError('Model identity counts changed')
        if self.native != plan['selected_native_ids']:
            raise ValueError('Model/plan native identities differ')
        self.owner = np.asarray(plan['coordinate_target_indices'])
        if self.owner.shape != (64,) or not np.isin(self.owner, np.arange(24)).all():
            raise ValueError('Invalid ownership')
        counts = np.bincount(self.owner.astype(int), minlength=24)
        if (counts == 2).sum() != 8 or (counts == 3).sum() != 16:
            raise ValueError('Invalid 24-head allocation')
        if len(plan['selected_concentrations_nM']) != 64:
            raise ValueError('Dose vector changed')
        self.doses = [dose(x) for x in plan['selected_concentrations_nM']]
        a = np.asarray(plan['orientation_A_plate_indices'])
        b = np.asarray(plan['orientation_B_plate_indices'])
        if a.shape != (64,) or b.shape != (64,) or not np.isin(a, (0, 1)).all() or not np.array_equal(b, 1-a) or np.count_nonzero(a == 0) != 32:
            raise ValueError('Invalid complementary physical layouts')
        for orientation, plates in [('A', a), ('B', b)]:
            if not np.array_equal(self.a['plate_' + orientation], plates):
                raise ValueError('Model/plan plate mismatch')
        mask = np.equal(np.arange(24)[:, None], self.owner[None, :])
        if not np.array_equal(self.a['feature_mask'], mask) or np.any(self.a['beta'][~mask.T] != 0):
            raise ValueError('Baseline head dependency mismatch')
        self.plates = {'A': a, 'B': b}

    @classmethod
    def load(cls, directory):
        directory = Path(directory)
        receipt = json.loads((directory/'CONSTRUCTION.json').read_text())
        for name, key in [('plan.json', 'plan_sha256'), ('model_private.npz', 'model_sha256')]:
            if digest(directory/name) != receipt[key]:
                raise ValueError('Constructed artifact digest mismatch: ' + name)
        with np.load(directory/'model_private.npz', allow_pickle=False) as z:
            arrays = {k: z[k].copy() for k in z.files}
        if receipt['selected'][0] == 'identity':
            arrays['correction'] = np.zeros((64, 24))
        return cls(arrays, json.loads((directory/'plan.json').read_text()))

    def predict(self, request):
        if not isinstance(request, dict):
            raise ValueError('Measurement request must be an object')
        orientation = request.get('orientation')
        sample, run = request.get('sample_id'), request.get('run_id')
        if orientation not in ('A', 'B') or not isinstance(sample, str) or not sample.strip() or not isinstance(run, str) or not run.strip():
            raise ValueError('Explicit sample, run and one deployment orientation required')
        rows = request.get('measurements')
        if not isinstance(rows, list) or len(rows) != 64:
            raise ValueError('All 64 required measurements are needed; all outputs withheld')
        positions = {n: i for i, n in enumerate(self.native)}
        observed = set(); wells = set(); paid = np.empty(64)
        for r in rows:
            if not isinstance(r, dict):
                raise ValueError('Measurement records must be objects')
            n = r.get('native_id')
            if n not in positions or n in observed:
                raise ValueError('Unknown or duplicate native identity')
            i = positions[n]; observed.add(n)
            if r.get('sample_id') != sample or r.get('run_id') != run:
                raise ValueError('Mixed sample or run identities')
            if r.get('drug_id') != self.targets[int(self.owner[i])] or dose(r.get('dose_nM')) != self.doses[i]:
                raise ValueError('Drug or exact concentration identity differs from plan')
            expected_plate = 'p' + str(int(self.plates[orientation][i]) + 1)
            if r.get('plate') != expected_plate:
                raise ValueError('Measurement belongs to the wrong deployment plate')
            well = r.get('well_id')
            if not isinstance(well, str) or not well.strip() or (expected_plate, well) in wells:
                raise ValueError('Missing or duplicated physical well identity')
            wells.add((expected_plate, well))
            value = r.get('value')
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not np.isfinite(value):
                raise ValueError('A required value is missing or nonfinite; all outputs withheld')
            paid[i] = value
        z = (paid-self.a['mean_x'])/self.a['scale_x']
        y = self.a['mean_y'] + z @ self.a['beta'] + z @ self.a['correction']
        if not np.isfinite(y).all():
            raise ValueError('Nonfinite output; all outputs withheld')
        return {'status': 'COMPLETE', 'sample_id': sample, 'run_id': run,
                'orientation': orientation, 'purchased_wells': 64,
                'predictions': dict(zip(self.targets, map(float, y))),
                'research_only': True, 'clinical_use_validated': False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model-dir', required=True, type=Path)
    p.add_argument('--measurements', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    args = p.parse_args()
    if args.output.exists():
        p.error('Output exists; preserve it and choose a new path')
    try:
        result = SpectralModel.load(args.model_dir).predict(json.loads(args.measurements.read_text()))
        code = 0
    except (ValueError, KeyError, TypeError, OSError) as exc:
        result = {'status': 'WITHHELD', 'predictions': {}, 'reason': str(exc), 'research_only': True}
        code = 2
    with args.output.open('x') as f:
        json.dump(result, f, indent=2, allow_nan=False)
        f.write('\n')
    return code


if __name__ == '__main__':
    raise SystemExit(main())
