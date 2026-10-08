"""Fit a separately labelled 128-well research artifact after verified evaluation."""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import argparse,csv,json,hashlib
from pathlib import Path
import numpy as np
import run_accuracy_tiers as r

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,v):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(v,f,indent=2,allow_nan=False);f.write('\n')
def main(run):
    r.check();result=json.loads((run/'RESULT.json').read_text());verification=json.loads((run/'VERIFICATION.json').read_text())
    if verification['status']!='PASS' or verification['result_sha256']!=sha(run/'RESULT.json'):raise ValueError('verified result required')
    if result['tiers']['128']['treatment_wells']!=128 or result['tiers']['128']['comparison_is_cost_matched']:raise ValueError('cost identity')
    out=run/'deployment128_private';out.mkdir(exist_ok=False)
    data,feat,_=r.core.load_prepared(r.core.CURVES,r.core.CATALOG)
    x=feat['x_replicates'];y=data['y'];p=data['patient_ids'].astype(str);cat=r.catalog_from_features(feat)
    selections=[int(json.loads((run/f'fold_{f}_record.json').read_text())['selected']['128']) for f in range(5)]
    counts=np.bincount(selections,minlength=10);option=int(np.argmax(counts))
    model=r.m.fit_models(x,y,p,cat)[128];plan=model[0];state=r.m.payload(model,option)
    expected=r.m.predict_options(x,model)[option];maximum=0.
    for oi,o in enumerate(('A','B')):
        maximum=max(maximum,float(np.max(abs(r.m.replay(state,r.m.paid(x,plan,o))-expected[oi]))))
    if maximum>1e-12:raise ValueError('final-state serialization mismatch')
    np.savez_compressed(out/'model.npz',**state);dump(out/'plan.json',plan)
    manifest={'schema':'von.dosepilot.research_tier.v1','name':'von-dosepilot-128-research','treatment_wells':128,'distinct_native_doses':128,'per_plate':[64,64],'additional_treatment_wells_vs_retained64':64,'cost_matched_to_64':False,'research_only':True,'independent_biological_validation':False,'clinical_validation':False,'same_budget_2x_achieved':False,'training_samples':119,'training_whole_patients':59,'training_source_sha256':sha(r.core.CURVES),'evaluation_result_sha256':sha(run/'RESULT.json'),'evaluation_is_repeated_adaptive_development':True,'crossvalidated_method_mse':result['tiers']['128']['metrics']['mse'],'not_a_validation_score_of_this_all_train_fit':True,'deployment_option_rule':'mode of outer training-selected spectral options; lowest-index tie break','outer_selected_options':selections,'deployment_option_index':option,'deployment_option':r.m.OPTIONS[option],'model_file':'model.npz','plan_file':'plan.json','model_sha256':sha(out/'model.npz'),'plan_sha256':sha(out/'plan.json'),'target_ids':data['drug_ids'].astype(str).tolist(),'saved_model_replay_maxdiff':maximum,'private_artifact_warning':'Kernel training coordinates contain research response values. Do not publish this directory as an aggregate-only evidence release.'}
    dump(out/'manifest.json',manifest)
    with (out/'synthetic_input_A.csv').open('x',newline='') as f:
        writer=csv.writer(f);writer.writerow(['sample_id','query_id','plate','viability'])
        for identity,plate in zip(plan['selected_native_ids'],plan['orientation_A_plate_indices']):writer.writerow(['fictional-demo',identity,'p'+str(plate+1),1.0])
    (out/'README.md').write_text('# von DosePilot 128-well research model\n\nThis is a separate higher-measurement tier, not a replacement for the retained64-well model. One inference needs128 distinct paid treatment wells,64 from each plate. A/B are alternatives, not an ensemble. The manifest records repeated-development evidence, not clinical validation.\n\nRun the source study/predict_research_tier.py with --model-dir this directory, --input synthetic_input_A.csv, --orientation A and a NEW --output path. The supplied CSV is fictional and contains no patient responses. Missing, extra, duplicate or nonfinite observations are rejected.\n\nThe model archive includes training coordinates and stays private on D:. Do not publish it alongside aggregate evidence.\n',encoding='utf-8')
    print(json.dumps({'status':'CREATED_RESEARCH_ONLY','directory':str(out),'well_count':128,'additional_wells_vs64':64,'option':r.m.OPTIONS[option],'serialization_maxdiff':maximum,'model_sha256':manifest['model_sha256'],'same_budget_2x':False}),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('run',type=Path);a=p.parse_args();main(a.run)
