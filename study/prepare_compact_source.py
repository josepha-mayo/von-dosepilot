#!/usr/bin/env python3
"""Build the fixed Lib1 TRAIN CSV from the exact public workbook, without a private kit.

The metadata recipe is evaluated before any viability cell is requested. All
Lib2 rows are excluded before response access. Real-workbook execution of this
new route remains separately gated; fixture/metadata tests are not that result.
"""
from __future__ import annotations
import argparse
import collections
import csv
import io
import json
from pathlib import Path
import re
import time
import traceback
import xml.etree.ElementTree as ET
import zipfile

from compact_train import FIELDS, dose_key, patient_group, read_catalog, sha256
from prepare_from_source_v3 import HEADERS, NS, extract_train, sheet_member, text


def natural_run(value: str):
    return tuple((0, int(s)) if s.isdigit() else (1, s) for s in re.split(r'(\d+)', value))


def build_manifest(metadata_rows, spec: dict) -> dict:
    """Reconstruct the historical selection solely from input metadata.

    Fixed targets/ranges/catalog came from the prior input-only study contract.
    We select the earliest naturally ordered eligible run, never using responses.
    """
    targets = tuple(spec['target_ids'])
    bounds = {d: tuple(dose_key(v) for v in spec['target_bounds_nM'][d]) for d in targets}
    runs = collections.defaultdict(set)
    grids = collections.defaultdict(set)
    wells = collections.defaultdict(list)
    for row in metadata_rows:
        if row.get('library_id') != 'lib1':
            continue
        sample, run = row.get('sample_id'), row.get('run_id')
        if not sample or not run:
            raise ValueError('Missing Lib1 sample/run identity')
        patient_group(sample)
        runs[sample].add(run)
        drug = row.get('compound_name')
        if (drug not in bounds or row.get('compound_type') != 'single' or
                row.get('concentration_unit') != 'nM'):
            continue
        try:
            d = dose_key(row['concentration'])
        except ValueError:
            continue  # Historical eligibility includes finite positive doses only.
        if row.get('plate') not in ('p1', 'p2'):
            continue
        if row.get('compound_drums') != spec['compound_drums_by_target'][drug]:
            raise ValueError('Target compound identity changed')
        key = (sample, run, drug, row['plate'])
        grids[key].add(d)
        wells[key].append({
            'drow': row['drow'], 'dcol': row['dcol'], 'assay_no': row['assay_no'],
            'concentration_nM': str(d), 'compound_drums': row['compound_drums'],
            'compound_fimm': row['compound_fimm']})
    selected = []
    for sample in sorted(runs):
        eligible = []
        for run in sorted(runs[sample], key=natural_run):
            good = True
            for drug in targets:
                lo, hi = bounds[drug]
                for plate in ('p1', 'p2'):
                    grid = grids.get((sample, run, drug, plate), set())
                    if len(grid) < 2 or min(grid) > lo or max(grid) < hi:
                        good = False
            if good:
                eligible.append(run)
        if not eligible:
            continue
        chosen = eligible[0]
        curves = []
        for drug in targets:
            plates = []
            for plate in ('p1', 'p2'):
                key = (sample, chosen, drug, plate)
                ws = wells[key]
                if len({(w['drow'],w['dcol']) for w in ws}) != len(ws):
                    raise ValueError('Duplicate selected physical well in metadata')
                if len({w['concentration_nM'] for w in ws}) != len(ws):
                    raise ValueError('Duplicate selected native dose in metadata')
                plates.append({'plate':plate, 'positive_doses_nM':[str(v) for v in sorted(grids[key])],
                               'wells':ws,'well_count':len(ws)})
            curves.append({'drug_id':drug,'plates':plates,'well_count':sum(p['well_count'] for p in plates)})
        selected.append({'library_id':'lib1','partition':'train','sample_id':sample,
                         'patient_id':patient_group(sample),'run_id':chosen,'curves':curves,
                         'all_target_well_count':sum(c['well_count'] for c in curves)})
    if (len(selected) != spec['expected_samples'] or
        len({s['patient_id'] for s in selected}) != spec['expected_patients'] or
        sum(s['all_target_well_count'] for s in selected) != spec['expected_train_curve_rows']):
        raise ValueError('Metadata-only selection differs from the fixed TRAIN population')
    return {'selected_samples':selected,
            'target_drugs':[{'drug_id':d,'common_interval_nM':spec['target_bounds_nM'][d]} for d in targets],
            'numeric_response_values_converted':0}


def iter_lib1_metadata(raw: bytes):
    """Read A:N metadata only. O/P response fields are never decoded here."""
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        if len(z.namelist()) != len(set(z.namelist())):
            raise ValueError('Duplicate workbook ZIP member')
        shared = []
        if 'xl/sharedStrings.xml' in z.namelist():
            root = ET.fromstring(z.read('xl/sharedStrings.xml'))
            shared = [''.join(n.itertext()) for n in root.findall('m:si',NS)]
        member = sheet_member(z)
        header_seen = False
        last_row = 0
        with z.open(member) as f:
            for _, row in ET.iterparse(f, events=('end',)):
                if row.tag != '{'+NS['m']+'}row':
                    continue
                number = row.get('r','')
                if not re.fullmatch(r'[1-9][0-9]*',number) or int(number)<=last_row:
                    raise ValueError('Unordered/noncanonical XML row')
                last_row = int(number)
                cells = {}
                for c in row.findall('m:c',NS):
                    match = re.fullmatch(r'([A-Z]+)([1-9][0-9]*)',c.get('r',''))
                    if not match or match.group(2)!=number or match.group(1) in cells:
                        raise ValueError('Invalid/repeated source coordinate')
                    cells[match.group(1)] = c
                if not header_seen:
                    if number!='1' or [text(cells.get(chr(65+i)),shared) for i in range(16)]!=HEADERS:
                        raise ValueError('Source header changed')
                    header_seen=True
                elif text(cells.get('E'),shared)=='lib1':
                    yield {HEADERS[i]:text(cells.get(chr(65+i)),shared) for i in range(14)}
                row.clear()
        if not header_seen:
            raise ValueError('Missing source header')


def canonical_csv(rows) -> bytes:
    f=io.StringIO(newline='')
    writer=csv.DictWriter(f,fieldnames=FIELDS)
    writer.writeheader();writer.writerows(rows)
    return f.getvalue().encode('utf-8')


def dump(path: Path, value):
    with path.open('x') as f:f.write(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-xlsx',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--execute-lib1-only',action='store_true',
                   help='Explicitly request the reviewed TRAIN-only source reconstruction')
    a=p.parse_args()
    if not a.execute_lib1_only:
        p.error('Source reconstruction is explicit: add --execute-lib1-only after reviewing the scope')
    if a.output.exists():raise SystemExit('Refusing existing output; preserve prior attempts')
    spec=read_catalog(Path(__file__).with_name('TRAIN_CATALOG.json'))
    raw=a.source_xlsx.read_bytes()
    if sha256(raw)!=spec['source_sha256']:raise SystemExit('Exact public source hash mismatch')
    a.output.mkdir(parents=True,exist_ok=False)
    dump(a.output/'ATTEMPT_STARTED.json',{'unix':time.time(),'source_sha256':sha256(raw),
        'catalog_sha256':sha256(Path(__file__).with_name('TRAIN_CATALOG.json').read_bytes()),
        'scope':'Metadata then Lib1 TRAIN values only','automatic_retry':False})
    observed=[]
    try:
        manifest=build_manifest(iter_lib1_metadata(raw),spec)
        dump(a.output/'METADATA_PASS.json',{'samples':len(manifest['selected_samples']),
             'selected_wells':sum(s['all_target_well_count'] for s in manifest['selected_samples']),
             'response_values_decoded':0})
        # Both passes consume the same authenticated byte snapshot.
        dump(a.output/'TRAIN_ACCESS_STARTED.json',{'status':'TRAIN access may have started',
             'lib2_values_authorized':False,'expected_train_requests':spec['expected_train_curve_rows']})
        arrays,tidy,audit=extract_train(io.BytesIO(raw),manifest,observed.append)
        output=canonical_csv(tidy)
        actual=sha256(output)
        if actual!=spec['prepared_curves_sha256']:
            raise ValueError('New TRAIN CSV differs from its historical exact byte identity')
        with (a.output/'train_curves.csv').open('xb') as f:f.write(output)
        dump(a.output/'SOURCE_RESULT.json',{'status':'PASS','source_sha256':sha256(raw),
             'curves_sha256':actual,'bytes':len(output),'audit':audit,
             'private_metadata_kit_used':False,'same_verified_snapshot':True,
             'clinical_or_independent_validation':False})
    except Exception as exc:
        dump(a.output/'FAILURE.json',{'type':type(exc).__name__,'message':str(exc),
             'traceback':traceback.format_exc(),'selected_cells_requested':len(observed),
             'automatic_retry':False})
        raise

if __name__=='__main__':main()
