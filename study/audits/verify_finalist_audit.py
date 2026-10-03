[Reading 74 lines from start (total: 74 lines, 0 remaining)]

#!/usr/bin/env python3
"""Response-free finalist audit for the public DosePilot evidence package."""
from pathlib import Path
import argparse,csv,hashlib,json

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def require(ok,msg):
    if not ok: raise ValueError(msg)

def verify(root):
    root=Path(root)
    manifest=json.loads((root/'evidence/finalist_audit_manifest_20261003.json').read_text())
    receipt=json.loads((root/'evidence/bandwidth_successor_20261003.json').read_text())
    index=json.loads((root/'evidence/EVIDENCE_INDEX.json').read_text())
    rows=list(csv.DictReader((root/'evidence/bandwidth_target_deltas_20261003.csv').open()))
    pins=manifest['pinned_sha256']
    mapping={
      'bandwidth_receipt':'evidence/bandwidth_successor_20261003.json',
      'evidence_index':'evidence/EVIDENCE_INDEX.json',
      'kaggle_writeup':'docs/KAGGLE_WRITEUP.md',
      'bandwidth_method':'study/hybrid_residual/bandwidth_additive.py',
      'bandwidth_inference':'study/hybrid_residual/bandwidth_inference.py',
      'bandwidth_reproduction':'study/hybrid_residual/reproduce_bandwidth.py',
      'target_delta_csv':'evidence/bandwidth_target_deltas_20261003.csv'}
    for name,rel in mapping.items():
        require(sha(root/rel)==pins[name],'HASH_MISMATCH:'+name)
    current=manifest['current_model']; idx=index['bandwidth_successor']
    require(current['model_kind']==receipt['model_kind']==idx['model_kind'],'MODEL_KIND')
    require(current['bandwidth_multiplier']==receipt['bandwidth_multiplier']==idx['bandwidth_multiplier']==.7,'BANDWIDTH')
    require(abs(current['mse']-receipt['metrics']['bandwidth07']['mse'])<1e-15,'MSE')
    require(abs(current['p90_rmse']-receipt['metrics']['bandwidth07']['p90_rmse'])<1e-15,'P90')
    require(current['patient_wins_vs_additive']==receipt['comparisons']['additive']['patient_wins']==38,'WINS_ADDITIVE')
    require(current['fold_wins_vs_additive']==receipt['comparisons']['additive']['fold_wins']==5,'FOLDS_ADDITIVE')
    require(receipt['comparisons']['additive']['passes_all'] is True,'INCUMBENT_GATE')
    require(receipt['comparisons']['r13']['passes_all'] and receipt['comparisons']['r18']['passes_all'],'HISTORICAL_GATE')
    contract=manifest['evaluation_contract']
    require(contract['samples']==119 and contract['whole_patients']==59 and contract['targets']==24,'COHORT')
    require(contract['physical_wells_per_deployment']==64 and contract['plate_wells_per_deployment']==[32,32],'PHYSICAL_BUDGET')
    require('Never average A/B predictions' in contract['orientation_semantics'],'ORIENTATION_SEMANTICS')
    rep=manifest['reproduction']
    require(rep['public_input_replay']=='PASS' and not rep['old_prediction_input'] and not rep['private_metadata_kit_used'],'PUBLIC_REPLAY')
    require(rep['runtime_record_checks']==238 and rep['runtime_max_prediction_difference']<=2.3e-16,'RUNTIME_REPLAY')
    require(rep['single_missing_positions_checked']==64 and rep['all_missing_cases_withheld'],'MISSINGNESS')
    require(len(rows)==24 and len({r['target'] for r in rows})==24,'TARGET_ROWS')
    deltas={r['target']:float(r['delta_vs_additive']) for r in rows}
    regress=sorted(k for k,v in deltas.items() if v>0)
    nonworse=sum(v<=0 for v in deltas.values())
    require(nonworse==receipt['target_nonworse_vs_additive']==14,'TARGET_NONWORSE')
    require(regress==sorted(receipt['target_regressions_vs_additive']),'TARGET_REGRESSIONS')
    limits=manifest['limitations']
    require(limits['repeated_adaptive_development'] and limits['independent_validation'] is False,'VALIDATION_SCOPE')
    require(limits['protected22_used'] is False and limits['official_competition_score'] is None,'NO_PROTECTED_OR_SCORE')
    writeup=(root/'docs/KAGGLE_WRITEUP.md').read_text()
    require('Live fictional-data demo:' in writeup,'LIVE_DEMO_LINK')
    require('0.0010582750' in writeup,'WRITEUP_CURRENT_MSE')
    forbidden=['bandwidth-0.7 successor is independent validation','official leaderboard score:']
    for phrase in forbidden: require(phrase not in writeup.lower(),'OVERCLAIM:'+phrase)
    return {'status':'PASS','manifest_schema':manifest['schema'],'current_mse':current['mse'],
      'physical_wells_per_deployment':64,'plate_counts':[32,32],'target_rows':24,
      'target_nonworse':nonworse,'target_regressions':len(regress),
      'public_replay':'PASS','runtime_record_checks':238,'protected_data_read':False,
      'private_patient_rows_read':False,'independent_validation_claimed':False}

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path('.'));p.add_argument('--output',type=Path)
    a=p.parse_args();result=verify(a.root)
    text=json.dumps(result,indent=2)+'\n'
    if a.output:
        if a.output.exists():raise ValueError('Output exists')
        a.output.write_text(text)
    print(text,end='')
if __name__=='__main__':main()
