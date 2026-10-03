[Reading 152 lines from start (total: 152 lines, 0 remaining)]

#!/usr/bin/env python3
"""Derive the 24 DosePilot target definitions from the authenticated public TRAIN CSV.

The script reads dose/identity metadata and ignores the viability field numerically.
It does not fit a model, score predictions, or access Protected22/Lib2.
"""
from __future__ import annotations
from pathlib import Path
import argparse,csv,hashlib,json,sys
from decimal import Decimal
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'study'),str(ROOT/'study/engine')]
from compact_train import FIELDS, read_catalog, patient_group, dose_key, integrate

SCHEMA='dosepilot.target_definitions.v1'

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def canonical_decimal(value):
    return str(Decimal(str(value)).normalize())

def quadrature(grid,bounds):
    g=np.asarray([float(x) for x in grid],dtype=float)
    weights=[]
    for i in range(len(g)):
        basis=np.zeros(len(g));basis[i]=1.
        weights.append(integrate(g.tolist(),basis.tolist(),bounds))
    w=np.asarray(weights)
    if abs(w.sum()-1)>1e-12 or (w<-1e-14).any():
        raise ValueError('Invalid normalized trapezoid quadrature')
    return [{'dose_nM':canonical_decimal(grid[i]),'weight':float(v)}
            for i,v in enumerate(w) if abs(v)>1e-15]

def plan_rows(path):
    plan=json.loads(Path(path).read_text())
    if plan.get('schema')!='von.acquisition.v1' or plan.get('treatment_wells')!=64:
        raise ValueError('Unexpected frozen plan')
    rows=plan.get('measurements')
    if not isinstance(rows,list) or len(rows)!=64:
        raise ValueError('Frozen plan must contain 64 rows')
    return plan,sorted(rows,key=lambda r:r['position'])

def derive(curves,catalog_path,plan_a_path,plan_b_path):
    spec=read_catalog(catalog_path)
    if sha(curves)!=spec['prepared_curves_sha256']:
        raise ValueError('Authenticated public TRAIN CSV changed')
    plan_a,a=plan_rows(plan_a_path);plan_b,b=plan_rows(plan_b_path)
    if [r['native_id'] for r in a] != [r['native_id'] for r in b]:
        raise ValueError('A/B treatment identities differ')
    selected={str(t):[] for t in spec['target_ids']}
    for ra,rb in zip(a,b):
        for key in ('position','native_id','drug_id','concentration_nM','unit'):
            if ra[key]!=rb[key]:
                raise ValueError('A/B identity mismatch: '+key)
        if ra['plate']==rb['plate']:
            raise ValueError('A/B plate assignments are not complementary')
        selected[ra['drug_id']].append({
            'position':int(ra['position']),'native_id':ra['native_id'],
            'dose_nM':canonical_decimal(ra['concentration_nM']),
            'orientation_A_plate':ra['plate'],'orientation_B_plate':rb['plate']})

    target_set=set(map(str,spec['target_ids']))
    grids={t:set() for t in target_set}
    seen_sample_drug_plate={}
    samples={}
    row_count=0
    with Path(curves).open(newline='') as handle:
        reader=csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != FIELDS:
            raise ValueError('TRAIN CSV schema changed')
        for row in reader:
            if set(row)!=set(FIELDS) or any(v is None or not v.strip() for v in row.values()):
                raise ValueError('Incomplete TRAIN row')
            if row['library_id']!='lib1' or row['drug_id'] not in target_set or row['plate'] not in ('p1','p2'):
                raise ValueError('Unexpected TRAIN identity')
            if patient_group(row['sample_id'])!=row['patient_id']:
                raise ValueError('Patient grouping mismatch')
            old=samples.setdefault(row['sample_id'],(row['patient_id'],row['run_id']))
            if old!=(row['patient_id'],row['run_id']):
                raise ValueError('Sample identity changed')
            dose=dose_key(row['dose_nM'])
            grids[row['drug_id']].add(dose)
            key=(row['sample_id'],row['drug_id'],row['plate'])
            seen_sample_drug_plate.setdefault(key,set()).add(dose)
            # Deliberately do not convert row['viability'].
            row_count+=1
    if row_count!=spec['expected_train_curve_rows'] or len(samples)!=spec['expected_samples']:
        raise ValueError('TRAIN denominator changed')
    if len({p for p,_ in samples.values()})!=spec['expected_patients']:
        raise ValueError('Patient denominator changed')
    for drug in spec['target_ids']:
        expected=grids[str(drug)]
        copies={tuple(sorted(v)) for k,v in seen_sample_drug_plate.items() if k[1]==str(drug)}
        if copies!={tuple(sorted(expected))}:
            raise ValueError('Dose grid differs across sample/plate for '+str(drug))

    definitions=[]
    for j,drug in enumerate(map(str,spec['target_ids'])):
        grid=sorted(grids[drug]);bounds=spec['target_bounds_nM'][drug]
        lo,hi=map(dose_key,bounds)
        q=quadrature(grid,bounds)
        qd={dose_key(x['dose_nM']) for x in q}
        sel=selected[drug]
        definitions.append({
            'target_index':j,'drug_id':drug,
            'compound_drum_id':spec['compound_drums_by_target'][drug],
            'endpoint':'mean of p1 and p2 normalized log-dose trapezoidal AUCs of unclipped supplied viability',
            'full_source_dose_grid_nM':[canonical_decimal(x) for x in grid],
            'source_dose_count':len(grid),
            'integration_interval_nM':[canonical_decimal(lo),canonical_decimal(hi)],
            'lower_bound_is_source_dose':lo in grids[drug],
            'upper_bound_is_source_dose':hi in grids[drug],
            'boundary_rule':'linear interpolation in log-dose at an integration bound when the bound is not an exact source dose',
            'nonzero_reference_quadrature':q,
            'quadrature_weight_sum':float(sum(x['weight'] for x in q)),
            'nonzero_reference_node_count':len(qd),
            'selected_predictor_inputs':sel,
            'selected_input_count':len(sel),
            'orientation_A_plate_counts':{'p1':sum(x['orientation_A_plate']=='p1' for x in sel),
                                          'p2':sum(x['orientation_A_plate']=='p2' for x in sel)},
            'orientation_B_plate_counts':{'p1':sum(x['orientation_B_plate']=='p1' for x in sel),
                                          'p2':sum(x['orientation_B_plate']=='p2' for x in sel)},
        })
    if sorted(x['selected_input_count'] for x in definitions)!=[2]*8+[3]*16:
        raise ValueError('Frozen 2/3-dose allocation changed')
    return {
      'schema':SCHEMA,'status':'FROZEN_TARGET_DEFINITIONS_DERIVED_FROM_PUBLIC_TRAIN',
      'source_curve_sha256':sha(curves),'catalog_sha256':sha(catalog_path),
      'orientation_A_plan_sha256':sha(plan_a_path),'orientation_B_plan_sha256':sha(plan_b_path),
      'samples':spec['expected_samples'],'whole_patients':spec['expected_patients'],'targets':24,
      'target_aggregation':'For each target, compute normalized log-dose trapezoidal AUC separately on p1 and p2 full source curves, then take their arithmetic mean.',
      'unclipped_viability':True,'clinical_response_endpoint':False,'ic50_endpoint':False,
      'drug_ranking_endpoint':False,'viability_values_converted_by_this_script':0,
      'protected_response_access':False,'definitions':definitions}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--curves',type=Path,required=True)
    p.add_argument('--catalog',type=Path,default=ROOT/'study/TRAIN_CATALOG.json')
    p.add_argument('--plan-a',type=Path,default=ROOT/'evidence/frozen_bandwidth_orientation_A_plan_20261003.json')
    p.add_argument('--plan-b',type=Path,default=ROOT/'evidence/frozen_bandwidth_orientation_B_plan_20261003.json')
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.output.exists():raise ValueError('Output exists; choose a fresh path')
    value=derive(a.curves.resolve(),a.catalog.resolve(),a.plan_a.resolve(),a.plan_b.resolve())
    a.output.write_text(json.dumps(value,indent=2)+'\n')
    print(json.dumps({'status':'PASS','targets':24,'source_curve_sha256':value['source_curve_sha256'],
                      'viability_values_converted':0},indent=2))
if __name__=='__main__':main()
