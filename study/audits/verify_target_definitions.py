[Reading 139 lines from start (total: 139 lines, 0 remaining)]

#!/usr/bin/env python3
"""Response-free verifier for the public DosePilot target-definition contract."""
from __future__ import annotations
from pathlib import Path
import argparse,hashlib,json,math
from decimal import Decimal
import numpy as np

SCHEMA='dosepilot.target_definitions.v1'

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def require(ok,msg):
    if not ok:
        raise ValueError(msg)

def dose(value):
    d=Decimal(str(value))
    require(d.is_finite() and d>0,'INVALID_DOSE')
    return d

def direct_weights(grid,bounds):
    g=np.asarray([float(dose(x)) for x in grid],dtype=float)
    lo,hi=np.log(np.asarray([float(dose(x)) for x in bounds]))
    x=np.log(g)
    require(len(x)>=2 and np.all(np.diff(x)>0) and x[0]<=lo<hi<=x[-1],'BAD_GEOMETRY')
    out=[]
    for k in range(len(x)):
        v=np.zeros(len(x));v[k]=1.
        internal=(x>lo)&(x<hi)
        xx=np.r_[lo,x[internal],hi]
        yy=np.r_[np.interp(lo,x,v),v[internal],np.interp(hi,x,v)]
        out.append(float(np.sum(np.diff(xx)*(yy[:-1]+yy[1:])/2)/(hi-lo)))
    return np.asarray(out)

def verify(root):
    root=Path(root)
    evidence=json.loads((root/'evidence/target_definitions_20261003.json').read_text())
    catalog=json.loads((root/'study/TRAIN_CATALOG.json').read_text())
    a=json.loads((root/'evidence/frozen_bandwidth_orientation_A_plan_20261003.json').read_text())
    b=json.loads((root/'evidence/frozen_bandwidth_orientation_B_plan_20261003.json').read_text())
    receipt=json.loads((root/'evidence/bandwidth_successor_20261003.json').read_text())
    doc=(root/'docs/TARGET_DEFINITIONS.md').read_text()

    require(evidence['schema']==SCHEMA,'SCHEMA')
    require(evidence['status']=='FROZEN_TARGET_DEFINITIONS_DERIVED_FROM_PUBLIC_TRAIN','STATUS')
    require(evidence['source_curve_sha256']==catalog['prepared_curves_sha256'],'SOURCE_CURVE_HASH')
    require(evidence['catalog_sha256']==sha(root/'study/TRAIN_CATALOG.json'),'CATALOG_HASH')
    require(evidence['orientation_A_plan_sha256']==sha(root/'evidence/frozen_bandwidth_orientation_A_plan_20261003.json'),'PLAN_A_HASH')
    require(evidence['orientation_B_plan_sha256']==sha(root/'evidence/frozen_bandwidth_orientation_B_plan_20261003.json'),'PLAN_B_HASH')
    require(evidence['samples']==119 and evidence['whole_patients']==59 and evidence['targets']==24,'POPULATION')
    require(evidence['viability_values_converted_by_this_script']==0,'NO_RESPONSE_CONVERSION')
    require(evidence['protected_response_access'] is False,'NO_PROTECTED')
    require(evidence['unclipped_viability'] is True,'UNCLIPPED')
    require(not evidence['clinical_response_endpoint'] and not evidence['ic50_endpoint'] and not evidence['drug_ranking_endpoint'],'ENDPOINT_SCOPE')

    defs=evidence['definitions']
    require(len(defs)==24,'TARGET_COUNT')
    require([x['drug_id'] for x in defs]==catalog['target_ids'],'TARGET_ORDER')
    rows_a=sorted(a['measurements'],key=lambda r:r['position'])
    rows_b=sorted(b['measurements'],key=lambda r:r['position'])
    require(len(rows_a)==len(rows_b)==64,'PLAN_ROWS')
    by_drug={d:[] for d in catalog['target_ids']}
    for ra,rb in zip(rows_a,rows_b):
        for key in ('position','native_id','drug_id','concentration_nM','unit'):
            require(ra[key]==rb[key],'AB_IDENTITY_'+key)
        require(ra['plate']!=rb['plate'],'AB_COMPLEMENT')
        by_drug[ra['drug_id']].append({
            'position':int(ra['position']),'native_id':ra['native_id'],
            'dose_nM':str(Decimal(str(ra['concentration_nM'])).normalize()),
            'orientation_A_plate':ra['plate'],'orientation_B_plate':rb['plate']})

    one_plate_nodes=0; selected=0; interpolated=[]
    for i,item in enumerate(defs):
        drug=item['drug_id']
        require(item['target_index']==i,'TARGET_INDEX')
        require(item['compound_drum_id']==catalog['compound_drums_by_target'][drug],'DRUM_ID')
        require(item['integration_interval_nM']==[str(Decimal(x).normalize()) for x in catalog['target_bounds_nM'][drug]],'BOUNDS_'+drug)
        grid=item['full_source_dose_grid_nM']
        require(item['source_dose_count']==len(grid),'GRID_COUNT_'+drug)
        require(len(set(grid))==len(grid),'GRID_DUPLICATE_'+drug)
        require(all(dose(x)>0 for x in grid),'GRID_DOSE_'+drug)
        require(all(dose(grid[k])<dose(grid[k+1]) for k in range(len(grid)-1)),'GRID_ORDER_'+drug)
        lo,hi=map(dose,item['integration_interval_nM'])
        gset={dose(x) for x in grid}
        require(item['lower_bound_is_source_dose']==(lo in gset),'LOWER_BOUND_FLAG_'+drug)
        require(item['upper_bound_is_source_dose']==(hi in gset),'UPPER_BOUND_FLAG_'+drug)
        if lo not in gset:interpolated.append((drug,'lower'))
        if hi not in gset:interpolated.append((drug,'upper'))
        direct=direct_weights(grid,item['integration_interval_nM'])
        recorded=np.zeros(len(grid))
        lookup={dose(x):k for k,x in enumerate(grid)}
        for q in item['nonzero_reference_quadrature']:
            recorded[lookup[dose(q['dose_nM'])]]=float(q['weight'])
        require(np.max(np.abs(direct-recorded))<=2e-15,'QUADRATURE_'+drug)
        require(abs(recorded.sum()-1)<=2e-15 and recorded.min()>=-1e-14,'QUADRATURE_SUM_'+drug)
        require(abs(item['quadrature_weight_sum']-1)<=2e-15,'WEIGHT_SUM_FIELD_'+drug)
        require(item['nonzero_reference_node_count']==int(np.count_nonzero(np.abs(recorded)>1e-15)),'NONZERO_COUNT_'+drug)
        require(item['selected_predictor_inputs']==by_drug[drug],'SELECTED_INPUTS_'+drug)
        require(item['selected_input_count']==len(by_drug[drug]),'SELECTED_COUNT_'+drug)
        selected+=item['selected_input_count'];one_plate_nodes+=item['source_dose_count']
        expected='| '+drug+' | '+', '.join(grid)+' | '+' to '.join(item['integration_interval_nM'])+' | '+', '.join(x['dose_nM'] for x in item['selected_predictor_inputs'])+' | '
        require(expected in doc,'DOC_ROW_'+drug)

    require(one_plate_nodes==208,'FULL_ONE_PLATE_COUNT')
    require(2*one_plate_nodes==416,'FULL_TWO_PLATE_COUNT')
    require(selected==64,'SELECTED_TOTAL')
    require(sorted(x['selected_input_count'] for x in defs)==[2]*8+[3]*16,'ALLOCATION')
    require(interpolated==[('Gedatolisib','lower'),('Palbociclib','lower'),('SN-38','upper'),('TAS-102','lower')],'INTERPOLATED_BOUNDARIES')
    require(a['plate_counts']==b['plate_counts']=={'p1':32,'p2':32},'PLATE_COUNTS')
    require(receipt['final_model']['plan_sha256']==json.loads((root/'evidence/frozen_ooc_execution_schedule_20261003.json').read_text())['original_plan_sha256'],'FINAL_PLAN_BINDING')
    required_phrases=[
      'not IC50','not a drug rank','not a clinical response label',
      '416 source treatment measurements per sample',
      '64 raw purchased normalized-viability values from one orientation only',
      'zero numerical conversions of the viability field']
    for phrase in required_phrases:
        require(phrase in doc,'DOC_SCOPE_'+phrase)
    require('\\n' not in doc,'DOC_TRANSPORT_ESCAPE')
    return {'status':'PASS','schema':SCHEMA,'targets':24,'full_source_nodes_one_plate':208,
            'full_source_treatment_measurements_two_plates':416,'selected_measurements_per_deployment':64,
            'p1_selected':32,'p2_selected':32,'two_dose_targets':8,'three_dose_targets':16,
            'interpolated_boundaries':interpolated,'quadrature_weights_verified':True,
            'target_table_rows_verified':24,'viability_values_read_numerically':False,
            'protected_response_access':False,'private_patient_rows_read':False,
            'biological_validation_created':False}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path('.'))
    p.add_argument('--output',type=Path)
    a=p.parse_args();result=verify(a.root)
    text=json.dumps(result,indent=2)+'\n'
    if a.output:
        if a.output.exists():raise ValueError('Output exists')
        a.output.write_text(text)
    print(text,end='')
if __name__=='__main__':main()
