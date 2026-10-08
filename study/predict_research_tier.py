#!/usr/bin/env python3
"""Research-only offline inference for an explicitly costed DosePilot tier."""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import argparse,csv,hashlib,json,math
from pathlib import Path
import numpy as np
from accuracy_tiers import replay

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def predict_file(model_dir,input_path,orientation,output_path):
    if output_path.exists():raise ValueError('Refusing to overwrite the output file')
    manifest=json.loads((model_dir/'manifest.json').read_text())
    if manifest.get('schema')!='von.dosepilot.research_tier.v1' or not manifest.get('research_only'):raise ValueError('Unknown or unlabelled model manifest')
    for key in ('model_file','plan_file'):
        if Path(manifest[key]).name!=manifest[key]:raise ValueError('Manifest filename must not traverse directories')
    model_path=model_dir/manifest['model_file'];plan_path=model_dir/manifest['plan_file']
    if sha(model_path)!=manifest['model_sha256'] or sha(plan_path)!=manifest['plan_sha256']:raise ValueError('Model or physical plan hash mismatch')
    state=np.load(model_path,allow_pickle=False);plan=json.loads(plan_path.read_text());budget=int(manifest['treatment_wells'])
    if int(state['budget'])!=budget or budget!=int(plan['treatment_wells']):raise ValueError('Measurement budget mismatch')
    if orientation not in ('A','B'):raise ValueError('Choose exactly one alternative layout')
    ids=plan['selected_native_ids'];plates=plan[f'orientation_{orientation}_plate_indices']
    expected=[(str(q),'p'+str(int(pl)+1)) for q,pl in zip(ids,plates)]
    if len(expected)!=budget or len(set(expected))!=budget or len(set(ids))!=budget:raise ValueError('Invalid native/physical plan')
    lookup={key:i for i,key in enumerate(expected)};samples={}
    with input_path.open(newline='',encoding='utf-8-sig') as f:
        reader=csv.DictReader(f)
        if reader.fieldnames!=['sample_id','query_id','plate','viability']:raise ValueError('Expected sample_id,query_id,plate,viability header')
        for row_number,row in enumerate(reader,2):
            if None in row or any(row[k] is None for k in reader.fieldnames):raise ValueError(f'Malformed row {row_number}')
            sample=row['sample_id'].strip();key=(row['query_id'].strip(),row['plate'].strip())
            if not sample or key not in lookup:raise ValueError(f'Unknown sample or unpurchased physical measurement at row {row_number}')
            values=samples.setdefault(sample,{})
            if key in values:raise ValueError(f'Duplicate physical measurement at row {row_number}')
            value=float(row['viability'])
            if not math.isfinite(value):raise ValueError(f'Nonfinite viability at row {row_number}')
            values[key]=value
    if not samples:raise ValueError('No samples supplied')
    names=sorted(samples)
    for name in names:
        if set(samples[name])!=set(expected):raise ValueError(f'{name}: exactly {budget} purchased measurements are required; got {len(samples[name])}')
    paid=np.array([[samples[name][key] for key in expected] for name in names],float)
    predictions=replay(state,paid)
    targets=manifest['target_ids']
    if predictions.shape!=(len(names),24) or len(targets)!=24 or len(set(targets))!=24 or not np.isfinite(predictions).all():raise ValueError('Invalid output shape or values')
    with output_path.open('x',encoding='utf-8',newline='') as f:
        writer=csv.writer(f);writer.writerow(['sample_id']+targets)
        for name,row in zip(names,predictions):writer.writerow([name]+row.tolist())
    return {'status':'RESEARCH_PREDICTIONS_WRITTEN','samples':len(names),'outputs_per_sample':24,'purchased_wells_per_sample':budget,'alternative_layout':orientation,'clinical_validation':False,'output':str(output_path)}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-dir',type=Path,required=True);parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--orientation',choices=['A','B'],required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(predict_file(args.model_dir,args.input,args.orientation,args.output)),flush=True)
