#!/usr/bin/env python3
"""Strict outer-patient isolation for declared standard-control calibration tiers."""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import argparse,hashlib,json,sys,time,traceback
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
import run_local_response_tiers as previous
import control_transfer_tiers as c
m=c.local;core=m.core
from coverage_methods import catalog_from_features
QUALITY=core.DATA/'control_quality_features_public_20261006.csv'
LOCAL_REF=core.DATA/'local_response_tiers_20261008_run1'/'predictions_private.npz'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def utc():return datetime.now(timezone.utc).isoformat()
def dump(p,v):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(v,f,indent=2,allow_nan=False);f.write('\n')
def freeze():
    paths=[HERE/n for n in ('run_control_transfer_tiers.py','control_transfer_tiers.py','test_control_transfer_tiers.py','verify_control_transfer_tiers.py','CONTROL_TRANSFER_TIERS_PROTOCOL.md','run_local_response_tiers.py','local_response_tiers.py','accuracy_tiers.py','run_crossplate64_20261008.py','compact_train.py','verify_local_response_tiers.py')]
    for folder in ('engine','hybrid_residual','acceleration'):paths+=sorted((HERE/folder).glob('*.py'))
    dump(HERE/'CONTROL_TRANSFER_TIERS_FREEZE.json',{'state':'FROZEN_BEFORE_BIOLOGICAL_FIT','utc':utc(),'primary_arm':c.PRIMARY,'source':{str(p.relative_to(HERE)):sha(p) for p in paths},'inputs':{str(p):sha(p) for p in (core.CURVES,core.CATALOG,core.BW,core.BEST,previous.REF128,LOCAL_REF,QUALITY)}})
def check():
    f=json.loads((HERE/'CONTROL_TRANSFER_TIERS_FREEZE.json').read_text())
    if f['state']!='FROZEN_BEFORE_BIOLOGICAL_FIT' or f['primary_arm']!=c.PRIMARY:raise ValueError('freeze mismatch')
    for p,h in f['source'].items():
        if sha(HERE/p)!=h:raise ValueError('source changed '+p)
    for p,h in f['inputs'].items():
        if sha(p)!=h:raise ValueError('input changed '+p)

def outer(x,y,p,Q,catalog,folds,f,query,queryQ):
    tr=np.flatnonzero(folds!=f);te=np.flatnonzero(folds==f)
    if set(p[tr])&set(p[te]):raise ValueError('outer patient overlap')
    inner,_=core.patient_folds(p[tr],3,core.evaluate.SALT+f'|inner|{f}')
    oof={b:np.full((70,2,len(tr),24),np.nan) for b in m.BUDGETS}
    for k in range(3):
        fi=tr[inner!=k];vi=tr[inner==k]
        if set(p[fi])&set(p[vi]):raise ValueError('inner patient overlap')
        fitted=m.fit(x[fi],y[fi],p[fi],catalog)
        for b in m.BUDGETS:oof[b][:,:,inner==k]=m.predict_all(x[vi],fitted[b])
    selected={};scores={};calibration={}
    for b in m.BUDGETS:
        if not np.isfinite(oof[b]).all():raise ValueError('incomplete inner predictions')
        scores[b]=[previous.risk(q,y[tr],p[tr]) for q in oof[b]];selected[b]=int(np.argmin(scores[b]))
        residual=y[tr][None,:,:]-oof[b][selected[b]]
        calibration[b]={o:c.fit(Q[tr],residual[oi],p[tr],o) for oi,o in enumerate(('A','B'))}
    fitted=m.fit(x[tr],y[tr],p[tr],catalog);pred={};states={};plans={};maxdiff=0.;unpaid=0.
    for b in m.BUDGETS:
        plans[b]=fitted[b]['model'][0];states[b]=c.pack(fitted[b]['state'],calibration[b]);base=m.predict_all(query[te],fitted[b])[selected[b]]
        pred[b]={a:np.stack([base[oi]+c.predict(calibration[b][o],queryQ[te],o,a) for oi,o in enumerate(('A','B'))]) for a in c.ARMS}
        for oi,o in enumerate(('A','B')):
            purchased=m.tiers.paid(query[te],plans[b],o)
            masked=np.full_like(query[te],np.nan);masked[:,states[b]['native'],states[b]['plate_'+o]]=purchased
            for a in c.ARMS:
                q=c.replay(states[b],purchased,queryQ[te],o,a,selected[b])
                maxdiff=max(maxdiff,float(np.max(abs(q-pred[b][a][oi]))))
                unpaid=max(unpaid,float(np.max(abs(c.replay(states[b],m.tiers.paid(masked,plans[b],o),queryQ[te],o,a,selected[b])-q))))
    if maxdiff>1e-12 or unpaid>1e-12:raise ValueError('replay/isolation')
    rec={'fold':f,'selected_base':selected,'inner_scores':scores,'train_patients':sorted(set(p[tr])),'test_patients':sorted(set(p[te])),'replay_maxdiff':maxdiff,'unpaid_maxdiff':unpaid,'required_standard_control_summaries':10}
    return pred,states,plans,rec

def execute(out):
    check();out.mkdir(parents=True,exist_ok=False);started=time.monotonic();dump(out/'STARTED.json',{'utc':utc(),'python':sys.version,'numpy':np.__version__})
    try:
        data,features,_=core.load_prepared(core.CURVES,core.CATALOG)
        x=features['x_replicates'];y=data['y'];p=data['patient_ids'].astype(str);cat=catalog_from_features(features)
        Q=c.load_quality(QUALITY,data['sample_ids']);folds,_=core.patient_folds(p,5,core.evaluate.SALT+'|outer')
        best=np.load(core.BEST,allow_pickle=False);base=np.load(LOCAL_REF,allow_pickle=False);old128=np.load(previous.REF128,allow_pickle=False)
        for ref in (best,base,old128):
            if not np.array_equal(ref['y'],y) or not np.array_equal(ref['patients'].astype(str),p) or not np.array_equal(ref['folds'],folds):raise ValueError('source identity')
        pred={b:{a:np.full((2,len(y),24),np.nan) for a in c.ARMS} for b in m.BUDGETS};records=[];state0=None
        for f in range(5):
            vals,states,plans,rec=outer(x,y,p,Q,cat,folds,f,x,Q);te=folds==f
            for b in m.BUDGETS:
                for a in c.ARMS:pred[b][a][:,te]=vals[b][a]
                np.savez_compressed(out/f'fold_{f}_budget{b}_model.npz',**states[b])
                dump(out/f'fold_{f}_budget{b}_plan.json',plans[b])
                np.savez_compressed(out/f'fold_{f}_budget{b}_paid.npz',A=m.tiers.paid(x[te],plans[b],'A'),B=m.tiers.paid(x[te],plans[b],'B'),Q=Q[te],indices=np.flatnonzero(te))
            records.append(rec);dump(out/f'fold_{f}_record.json',rec)
            if f==0:state0=states
            print(json.dumps({'fold_complete':f,'base_options':rec['selected_base']}),flush=True)
        xx=x.copy();yy=y.copy();qq=Q.copy();xx[folds==0]+=71.;yy[folds==0]-=93.;qq[folds==0]+=19.
        altered,st,_,rr=outer(xx,yy,p,qq,cat,folds,0,x,Q)
        mutation=max(float(np.max(abs(altered[b][a]-pred[b][a][:,folds==0]))) for b in m.BUDGETS for a in c.ARMS)
        state_diff=0.
        for b in m.BUDGETS:
            for k in st[b]:
                if st[b][k].dtype.kind in 'USO':
                    if not np.array_equal(st[b][k],state0[b][k]):raise ValueError('membership changed')
                else:state_diff=max(state_diff,float(np.max(abs(st[b][k]-state0[b][k]))))
        if mutation>1e-12 or state_diff>1e-12 or rr['selected_base']!=records[0]['selected_base']:raise ValueError('outer-held data affected training')
        control=max(float(np.max(abs(pred[b]['uncalibrated']-base[f'budget{b}_nested_primary']))) for b in m.BUDGETS)
        if control>1e-12:raise ValueError('prior query-local procedure did not reproduce')
        best_metrics=core.metric(best['candidate'],y,p,folds);old128_metrics=core.metric(old128['budget128'],y,p,folds)
        tiers={};arrays={}
        for b in m.BUDGETS:
            tiers[str(b)]={};same=core.metric(pred[b]['uncalibrated'],y,p,folds)
            for a in c.ARMS:
                q=pred[b][a]
                if not np.isfinite(q).all():raise ValueError('incomplete predictions')
                met=core.metric(q,y,p,folds);vs=core.compare(met,best_metrics);vs128=core.compare(met,old128_metrics);vsbase=core.compare(met,same)
                gate=lambda v:v['relative_gain']>0 and v['patient_wins']>=30 and v['fold_wins']==5 and v['p90_nonworse']
                tiers[str(b)][a]={'metrics':met[0],'physical_treatment_wells':b,'standard_control_summaries_required':0 if a=='uncalibrated' else 10,'vs_retained64':vs,'vs_verified128':vs128,'vs_same_cost_uncalibrated':vsbase,'mse_reduction_factor_vs64':best_metrics[0]['mse']/met[0]['mse'],'accuracy_only_half_error':bool(met[0]['mse']<=core.TWOX and vs['p90_nonworse']),'same64_half_error':bool(b==64 and met[0]['mse']<=core.TWOX and vs['p90_nonworse']),'same64_promotion_screen':bool(b==64 and a!='uncalibrated' and gate(vs) and gate(vsbase))}
                arrays[f'budget{b}_{a}']=q
        np.savez_compressed(out/'predictions_private.npz',**arrays,y=y,patients=p,folds=folds,sample_ids=data['sample_ids'],drug_ids=data['drug_ids'],retained64=best['candidate'],verified128=old128['budget128'])
        result={'schema':'dosepilot.control_transfer_tiers.v1','status':'COMPLETE','primary_arm':c.PRIMARY,'primary_objective_budget':64,'role':'REPEATED_ADAPTIVE_DEVELOPMENT_NOT_INDEPENDENT_CONFIRMATION','tiers':tiers,'uncalibrated_reproduction_maxdiff':control,'outer_label_curve_control_mutation_maxdiff':mutation,'outer_state_mutation_maxdiff':state_diff,'same_budget_half_error_target':core.TWOX,'protected22_access':False,'original_models_replaced':False,'submission_changed':False,'independent_validation':False,'freeze_sha256':sha(HERE/'CONTROL_TRANSFER_TIERS_FREEZE.json'),'prediction_sha256':sha(out/'predictions_private.npz'),'seconds':time.monotonic()-started,'finished_utc':utc()}
        dump(out/'RESULT.json',result)
        print(json.dumps({b:{a:{'mse':v['metrics']['mse'],'p90':v['metrics']['p90'],'ratio64':v['mse_reduction_factor_vs64'],'vs128':v['vs_verified128'],'vs64':v['vs_retained64'],'half_error':v['accuracy_only_half_error']} for a,v in arms.items()} for b,arms in tiers.items()},indent=2),flush=True)
    except BaseException as e:
        dump(out/'FAILURE.json',{'error':repr(e),'traceback':traceback.format_exc(),'utc':utc()});raise

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--freeze',action='store_true');ap.add_argument('--out',type=Path);a=ap.parse_args()
    if a.freeze:freeze()
    elif a.out:execute(a.out)
    else:ap.error('use --freeze or --out')
