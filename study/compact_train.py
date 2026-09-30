#!/usr/bin/env python3
"""Rebuild the unchanged DosePilot model inputs from one Lib1 TRAIN curve CSV.

The catalog contains only drug/dose/algorithm metadata. This module does not
access the original workbook, held-out responses, network or old predictions.
"""
from __future__ import annotations

import csv
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
from pathlib import Path
import re
import sys
from typing import Any

import numpy as np

CATALOG_SHA256 = '84eae3976307448ac696852d39d1b2376cce479d8af5e386ce04097020deff5e'
FIELDS = ('sample_id', 'patient_id', 'library_id', 'run_id', 'drug_id', 'plate',
          'dose_nM', 'viability', 'drow', 'dcol', 'assay_no')


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read_catalog(path: Path) -> dict[str, Any]:
    raw = Path(path).read_bytes()
    if sha256(raw) != CATALOG_SHA256:
        raise ValueError('The fixed drug/dose catalog changed')
    return json.loads(raw)


def patient_group(sample: str) -> str:
    match = re.match(r'^(Pt\d+)(?:[._]|$)', sample)
    if match is None:
        raise ValueError('Unrecognized sample-to-patient identity')
    return match.group(1)


def dose_key(value: str) -> Decimal:
    try:
        d = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError('Invalid dose') from None
    if not d.is_finite() or d <= 0:
        raise ValueError('Dose must be finite and positive')
    return Decimal(format(d, '.12g')).normalize()


def catalog_layout(spec: dict[str, Any]):
    from sparse_methods import LibraryDescriptor
    from bracketing_methods import BracketingLayout
    from coverage_methods import CoverageCatalog, validate_catalog
    qids = np.asarray(spec['query_ids'], dtype=str)
    tids = np.asarray(spec['target_ids'], dtype=str)
    weights = np.zeros((len(tids), len(qids)), dtype=float)
    for j, pairs in enumerate(spec['query_nonzero_target_weights']):
        for i, value in pairs:
            weights[j, i] = value
    descriptor = LibraryDescriptor(
        'lib1', qids, tids, np.asarray(spec['query_target_indices'], dtype=int),
        weights, np.asarray(spec['recoverable'], dtype=bool),
        tuple(tuple(s) if s is not None else None for s in spec['supports']))
    # Preserve the old representation: the initial common-pool doses were None
    # in BracketingLayout and supplied separately to CoverageCatalog.
    layout = BracketingLayout(
        descriptor, np.asarray(spec['native_ids'], dtype=str),
        np.asarray(spec['native_target_indices'], dtype=int),
        tuple([None] * len(qids) + spec['native_concentrations_nM'][len(qids):]),
        tuple(spec['bracketing_candidates']))
    catalog = CoverageCatalog(layout.native_ids, tids, layout.native_target_indices,
                              tuple(spec['native_concentrations_nM']), 'lib1')
    validate_catalog(catalog)
    return layout, catalog


def integrate(grid: list[float], values: list[float], bounds: list[str]) -> float:
    x = np.log(np.asarray(grid, dtype=float))
    v = np.asarray(values, dtype=float)
    lo, hi = np.log(np.asarray(bounds, dtype=float))
    if len(x) < 2 or np.any(np.diff(x) <= 0) or not x[0] <= lo < hi <= x[-1]:
        raise ValueError('Grid does not bracket the fixed target interval')
    internal = (x > lo) & (x < hi)
    xx = np.r_[lo, x[internal], hi]
    yy = np.r_[np.interp(lo, x, v), v[internal], np.interp(hi, x, v)]
    return float(np.sum(np.diff(xx) * (yy[:-1] + yy[1:]) / 2) / (hi - lo))


def from_curve_bytes(raw: bytes, spec: dict[str, Any], *, require_pin: bool = True):
    """Construct all targets and physical inputs from authenticated TRAIN bytes.

    require_pin=False is solely for explicit local malformed/invented fixtures;
    the public command path always uses True.
    """
    if require_pin and sha256(raw) != spec['prepared_curves_sha256']:
        raise ValueError('The fixed Lib1 TRAIN curve bytes changed')
    layout, catalog = catalog_layout(spec)
    rows = csv.DictReader(io.StringIO(raw.decode('utf-8'), newline=''))
    if tuple(rows.fieldnames or ()) != FIELDS:
        raise ValueError('Curve CSV schema changed')
    target_set = set(catalog.target_ids)
    curves: dict[tuple[str, str, str], dict[Decimal, tuple[float, str]]] = {}
    samples: dict[str, tuple[str, str]] = {}
    seen_wells: set[tuple[str, str, str, str, str]] = set()
    count = 0
    for row in rows:
        if set(row) != set(FIELDS) or any(v is None or not v.strip() for v in row.values()):
            raise ValueError('Incomplete CSV row')
        if row['library_id'] != 'lib1':
            raise ValueError('Only the previously released Lib1 TRAIN input is permitted')
        if row['plate'] not in ('p1', 'p2') or row['drug_id'] not in target_set:
            raise ValueError('Unknown plate or target identity')
        if patient_group(row['sample_id']) != row['patient_id']:
            raise ValueError('Sample and patient identity disagree')
        identity = (row['patient_id'], row['run_id'])
        old = samples.setdefault(row['sample_id'], identity)
        if old != identity:
            raise ValueError('One sample has inconsistent patient/run identities')
        physical = (row['sample_id'], row['run_id'], row['plate'], row['drow'], row['dcol'])
        if physical in seen_wells:
            raise ValueError('Repeated physical measurement')
        seen_wells.add(physical)
        d = dose_key(row['dose_nM'])
        key = (row['sample_id'], row['drug_id'], row['plate'])
        curve = curves.setdefault(key, {})
        if d in curve:
            raise ValueError('Repeated native dose on one sample/drug/plate')
        # Identity checks precede every numerical response conversion.
        try:
            value = float(row['viability'])
        except ValueError:
            raise ValueError('Required TRAIN viability is nonnumeric') from None
        if not np.isfinite(value):
            raise ValueError('Required TRAIN viability is nonfinite')
        well_id = '|'.join((row['run_id'], row['plate'], row['drow'], row['dcol']))
        curve[d] = (value, well_id)
        count += 1
    sample_ids = sorted(samples)
    patient_ids = [samples[s][0] for s in sample_ids]
    if (len(sample_ids) != spec['expected_samples'] or
            len(set(patient_ids)) != spec['expected_patients'] or
            count != spec['expected_train_curve_rows']):
        raise ValueError('Complete frozen TRAIN population/denominator changed')
    n, t, m = len(sample_ids), len(catalog.target_ids), len(catalog.native_ids)
    if len(curves) != n * t * 2:
        raise ValueError('A required sample/drug/plate curve is missing')
    target_rep = np.empty((n, t, 2), dtype=float)
    pair_x = np.empty((n, m, 2), dtype=float)
    well_ids = np.empty((n, m, 2), dtype=object)
    for i, sample in enumerate(sample_ids):
        for j, drug in enumerate(catalog.target_ids):
            for r, plate in enumerate(('p1', 'p2')):
                curve = curves[(sample, str(drug), plate)]
                grid = sorted(curve)
                target_rep[i, j, r] = integrate(
                    [float(d) for d in grid], [curve[d][0] for d in grid],
                    spec['target_bounds_nM'][str(drug)])
        for q, target in enumerate(catalog.native_target_indices):
            drug = str(catalog.target_ids[target])
            d = dose_key(catalog.concentrations[q])
            for r, plate in enumerate(('p1', 'p2')):
                if d not in curves[(sample, drug, plate)]:
                    raise ValueError('Required source-native measurement is absent')
                pair_x[i, q, r], well_ids[i, q, r] = curves[(sample, drug, plate)][d]
        if len(set(well_ids[i].ravel())) != 2 * m:
            raise ValueError('Native catalog aliases a physical measurement')
    data = {'y': target_rep.mean(axis=2), 'sample_ids': np.asarray(sample_ids),
            'patient_ids': np.asarray(patient_ids), 'drug_ids': catalog.target_ids.copy(),
            'library_ids': np.asarray(['lib1'] * n)}
    old_pool = {'queries': [{'query_id': str(qid), 'concentration_nM': catalog.concentrations[q]}
                            for q, qid in enumerate(layout.old_descriptor.query_ids)]}
    features = {'x': pair_x.mean(axis=2), 'x_replicates': pair_x,
                'well_ids': well_ids.astype(str), 'layout': layout,
                'old': {'pool': old_pool, 'descriptor': layout.old_descriptor},
                'audit': {'samples': n, 'whole_patients': len(set(patient_ids)),
                          'targets': t, 'native_pairs': m, 'curve_rows': count,
                          'lib2_response_values_converted': 0,
                          'source_workbook_opened': False,
                          'reconstructed_from_one_train_curve_csv': True,
                          'curve_sha256': sha256(raw)}}
    return data, features, target_rep


def load_prepared(curves_path: Path, catalog_path: Path):
    spec = read_catalog(catalog_path)
    return from_curve_bytes(Path(curves_path).read_bytes(), spec, require_pin=True)
