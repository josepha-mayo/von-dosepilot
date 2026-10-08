#!/usr/bin/env python3
"""Nested, explicitly costed local response reconstruction. Never submits."""
from __future__ import annotations
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
import argparse,hashlib,json,sys,time,traceback
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
import local_response_tiers as m
core=m.core
if os.name=='nt':
    core.DATA=Path('D:/von-dosepilot-data');core.CURVES=core.DATA/'reconstructed_train'/'train_curves.csv'
    core.BW=core.DATA/'bandwidth_replay_pc_20261004'/'predictions_private.npz'
    core.BEST=core.DATA/'orientation_specific_control_quality_rank1_20261006_run1'/'predictions_private.npz'
from coverage_methods import catalog_from_features
REF128=core.DATA/'accuracy_tiers_20261008_run1'/'predictions_private.npz'
ARM_NAMES=m.NAMES+('nested_primary',)

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def utc():return datetime.now(timezone.utc).isoformat()
def dump(p,value):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')
def risk(q,y,p):
    loss=((q[0]-y)**2+(q[1]-y)**2)/2
    return float(np.mean([loss[p==g].mean() for g in np.unique(p)]))
def freeze():
    names=('run_local_response_tiers.py','local_response_tiers.py','test_local_response_tiers.py','verify_local_response_tiers.py','LOCAL_RESPONSE_TIERS_PROTOCOL.md','accuracy_tiers.py','run_crossplate64_20261008.py','compact_train.py')
    paths=[HERE/n for n in names]
    for folder in ('engine','acceleration','hybrid_residual'):paths+=sorted((HERE/folder).glob('*.py'))
    inputs=[core.CURVES,core.CATALOG,core.BW,core.BEST,REF128]
    inputs+=[core.DATA/'bandwidth_replay_pc_20261004'/f'outer_{f:02d}'/'plan.json' for f in range(5)]
    dump(HERE/'LOCAL_RESPONSE_TIERS_FREEZE.json',{'state':'FROZEN_BEFORE_BIOLOGICAL_FIT','utc':utc(),'source':{str(p.relative_to(HERE)):sha(p) for p in paths},'inputs':{str(p):sha(p) for p in inputs}})
def check():
    fr=json.loads((HERE/'LOCAL_RESPONSE_TIERS_FREEZE.json').read_text())
    if fr['state']!='FROZEN_BEFORE_BIOLOGICAL_FIT':raise ValueError('freeze state')
    for p,h in fr['source'].items():
        if sha(HERE/p)!=h:raise ValueError('source changed '+p)
    for p,h in fr['inputs'].items():
        if sha(p)!=h:raise ValueError('input changed '+p)

def outer(x,y,p,catalog,folds,f,query):
    tr=np.flatnonzero(folds!=f);te=np.flatnonzero(folds==f)
    if set(p[tr])&set(p[te]):raise ValueError('outer patient overlap')
    inner,_=core.patient_folds(p[tr],3,core.evaluate.SALT+f'|inner|{f}')
    oof={b:np.full((70,2,len(tr),24),np.nan) for b in m.BUDGETS}
    for k in range(3):
        fi=tr[inner!=k];vi=tr[inner==k]
        if set(p[fi])&set(p[vi]):raise ValueError('inner patient overlap')
        fits=m.fit(x[fi],y[fi],p[fi],catalog)
        for b in m.BUDGETS:oof[b][:,:,inner==k]=m.predict_all(x[vi],fits[b])
    selected={};scores={}
    for b in m.BUDGETS:
        if not np.isfinite(oof[b]).all():raise ValueError('incomplete inner predictions')
        scores[b]=[risk(q,y[tr],p[tr]) for q in oof[b]]
        selected[b]={a:10*j+int(np.argmin(scores[b][10*j:10*(j+1)])) for j,a in enumerate(m.NAMES)}
        selected[b]['nested_primary']=int(np.argmin(scores[b]))
    fits=m.fit(x[tr],y[tr],p[tr],catalog)
    predictions={};states={};plans={};maxdiff=0.;unpaid=0.
    for b in m.BUDGETS:
        raw=m.predict_all(query[te],fits[b]);states[b]=fits[b]['state'];plans[b]=fits[b]['model'][0]
        predictions[b]={a:raw[idx] for a,idx in selected[b].items()}
        for oi,o in enumerate(('A','B')):
            purchased=m.tiers.paid(query[te],plans[b],o)
            masked=np.full_like(query[te],np.nan);masked[:,states[b]['native'],states[b]['plate_'+o]]=purchased
            for a,idx in selected[b].items():
                replay=m.replay(states[b],purchased,idx)
                maxdiff=max(maxdiff,float(np.max(abs(replay-predictions[b][a][oi]))))
                unpaid=max(unpaid,float(np.max(abs(m.replay(states[b],m.tiers.paid(masked,plans[b],o),idx)-replay))))
    if maxdiff>1e-12 or unpaid>1e-12:raise ValueError('state replay or unpaid-input isolation')
    original=json.loads((core.DATA/'bandwidth_replay_pc_20261004'/f'outer_{f:02d}'/'plan.json').read_text())
    for key in ('selected_native_indices','coordinate_target_indices','orientation_A_plate_indices','orientation_B_plate_indices'):
        if plans[64][key]!=original[key]:raise ValueError('64-well calibration panel mismatch')
    record={'fold':f,'selected':selected,'inner_scores':scores,'train_patients':sorted(set(p[tr])),'test_patients':sorted(set(p[te])),'state_replay_maxdiff':maxdiff,'unpaid_isolation_maxdiff':unpaid,'calibration64_panel_agrees':True}
    return predictions,states,plans,record

def execute(out):
    check();out.mkdir(parents=True,exist_ok=False);start=time.monotonic()
    dump(out/'STARTED.json',{'utc':utc(),'python':sys.version,'numpy':np.__version__})
    try:
        data,features,_=core.load_prepared(core.CURVES,core.CATALOG)
        x=features['x_replicates'];y=data['y'];p=data['patient_ids'].astype(str);cat=catalog_from_features(features)
        folds,_=core.patient_folds(p,5,core.evaluate.SALT+'|outer')
        rz=np.load(core.BW,allow_pickle=False);bz=np.load(core.BEST,allow_pickle=False);tz=np.load(REF128,allow_pickle=False)
        for ref in (rz,bz,tz):
            if not np.array_equal(ref['y'],y) or not np.array_equal(ref['patients'].astype(str),p) or not np.array_equal(ref['folds'],folds):raise ValueError('comparison identity')
        pred={b:{a:np.full((2,len(y),24),np.nan) for a in ARM_NAMES} for b in m.BUDGETS}
        records=[];state0=None
        for f in range(5):
            predictions,states,plans,record=outer(x,y,p,cat,folds,f,x);te=folds==f
            for b in m.BUDGETS:
                for a in ARM_NAMES:pred[b][a][:,te]=predictions[b][a]
                np.savez_compressed(out/f'fold_{f}_budget{b}_model.npz',**states[b])
                dump(out/f'fold_{f}_budget{b}_plan.json',plans[b])
                np.savez_compressed(out/f'fold_{f}_budget{b}_paid.npz',A=m.tiers.paid(x[te],plans[b],'A'),B=m.tiers.paid(x[te],plans[b],'B'),indices=np.flatnonzero(te))
            records.append(record);dump(out/f'fold_{f}_record.json',record)
            if f==0:state0=states
            print(json.dumps({'fold_complete':f,'selected_primary':{b:m.NAMES[record['selected'][b]['nested_primary']//10] for b in m.BUDGETS}}),flush=True)
        changed_x=x.copy();changed_y=y.copy();changed_x[folds==0]+=47.;changed_y[folds==0]-=83.
        altered,states,_,rr=outer(changed_x,changed_y,p,cat,folds,0,x)
        mutation=max(float(np.max(abs(altered[b][a]-pred[b][a][:,folds==0]))) for b in m.BUDGETS for a in ARM_NAMES)
        statediff=0.
        for b in m.BUDGETS:
            for key in states[b]:
                if np.asarray(states[b][key]).dtype.kind in 'USO':
                    if not np.array_equal(states[b][key],state0[b][key]):raise ValueError('membership dependency')
                else:statediff=max(statediff,float(np.max(abs(states[b][key]-state0[b][key]))))
        if mutation>1e-12 or statediff>1e-12 or rr['selected']!=records[0]['selected']:raise ValueError('held-patient dependency')
        control64=float(np.max(abs(pred[64]['original']-rz['bandwidth07'])))
        control128=float(np.max(abs(pred[128]['original']-tz['budget128'])))
        if max(control64,control128)>1e-12:raise ValueError('archived control mismatch')
        best=core.metric(bz['candidate'],y,p,folds);old128=core.metric(tz['budget128'],y,p,folds)
        if abs(best[0]['mse']-core.EXPECTED_BEST)>1e-13 or abs(old128[0]['mse']-.0005102658031862283)>1e-13:raise ValueError('reference metrics')
        results={};allarrays={}
        for b in m.BUDGETS:
            results[str(b)]={};own=core.metric(pred[b]['original'],y,p,folds)
            for a in ARM_NAMES:
                q=pred[b][a]
                if not np.isfinite(q).all():raise ValueError('missing final predictions')
                met=core.metric(q,y,p,folds);vs=core.compare(met,best);vsown=core.compare(met,own);vs128=core.compare(met,old128)
                gate=lambda v:v['relative_gain']>0 and v['patient_wins']>=30 and v['fold_wins']==5 and v['p90_nonworse']
                results[str(b)][a]={'metrics':met[0],'vs_scientific64':vs,'vs_same_cost_original':vsown,'vs_reference128':vs128,'physical_wells':b,'added_wells_vs64':b-64,'wells_saved_vs128':128-b,'accuracy_only_2x_vs64':bool(met[0]['mse']<=core.TWOX and vs['p90_nonworse']),'same_budget_2x_vs64':bool(b==64 and met[0]['mse']<=core.TWOX and vs['p90_nonworse']),'same64_promotion_gate':bool(b==64 and gate(vs) and gate(vsown))}
                allarrays[f'budget{b}_{a}']=q
        integrated=bz['candidate']+pred[64]['nested_primary']-pred[64]['original']
        met=core.metric(integrated,y,p,folds);vs=core.compare(met,best)
        integration={'metrics':met[0],'vs_scientific64':vs,'physical_wells':64,'extra_controls_vs_retained64':0,'same_budget_2x':bool(met[0]['mse']<=core.TWOX and vs['p90_nonworse']),'promotion_screen':bool(gate(vs)),'status':'INTEGRATION_DIAGNOSTIC_NOT_FRESH_FULL_LEGACY_REBUILD'}
        np.savez_compressed(out/'predictions_private.npz',**allarrays,integration64=integrated,y=y,patients=p,folds=folds,sample_ids=data['sample_ids'],drug_ids=data['drug_ids'],scientific64=bz['candidate'],reference128=tz['budget128'])
        result={'schema':'dosepilot.local_response_tiers.v1','status':'COMPLETE','role':'REPEATED_ADAPTIVE_DEVELOPMENT_NOT_INDEPENDENT_CONFIRMATION','primary_arm':'budget64_nested_primary','tiers':results,'integration64':integration,'control64_maxdiff':control64,'control128_maxdiff':control128,'outer_label_mutation_maxdiff':mutation,'outer_state_mutation_maxdiff':statediff,'half_error_target64':core.TWOX,'protected22_access':False,'independent_validation':False,'submission_changed':False,'verified_models_replaced':False,'source_freeze_sha256':sha(HERE/'LOCAL_RESPONSE_TIERS_FREEZE.json'),'prediction_sha256':sha(out/'predictions_private.npz'),'seconds':time.monotonic()-start,'finished_utc':utc()}
        dump(out/'RESULT.json',result)
        print(json.dumps({'nested':{b:results[str(b)]['nested_primary'] for b in m.BUDGETS},'integration64':integration,'seconds':result['seconds']},indent=2),flush=True)
    except BaseException as e:
        dump(out/'FAILURE.json',{'error':repr(e),'traceback':traceback.format_exc(),'utc':utc()});raise

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--freeze',action='store_true');ap.add_argument('--out',type=Path);a=ap.parse_args()
    if a.freeze:freeze()
    elif a.out:execute(a.out)
    else:ap.error('use --freeze or --out')
