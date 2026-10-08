#!/usr/bin/env python3
"""Nested accuracy/cost comparison, no edits to retained scientific64 or submission."""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import argparse,datetime,hashlib,json,sys,time,traceback
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
import accuracy_tiers as m
core=m.core
if os.name=='nt':
    core.DATA=Path('D:/von-dosepilot-data');core.CURVES=core.DATA/'reconstructed_train'/'train_curves.csv'
    core.BW=core.DATA/'bandwidth_replay_pc_20261004'/'predictions_private.npz'
    core.BEST=core.DATA/'orientation_specific_control_quality_rank1_20261006_run1'/'predictions_private.npz'
from coverage_methods import catalog_from_features
REF72=core.DATA/'budget72_bandwidth07_residual_20261006_run1'/'RESULT.json'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def dump(p,v):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(v,f,indent=2,allow_nan=False);f.write('\n')
def freeze():
    paths=[HERE/n for n in ('run_accuracy_tiers.py','accuracy_tiers.py','test_accuracy_tiers.py','ACCURACY_TIERS_PROTOCOL.md','run_crossplate64_20261008.py','compact_train.py')]
    for name in ('engine','hybrid_residual','acceleration'):paths+=sorted((HERE/name).glob('*.py'))
    dump(HERE/'ACCURACY_TIERS_FREEZE.json',{'state':'FROZEN_BEFORE_BIOLOGICAL_FIT','utc':utc(),'source':{str(p.relative_to(HERE)):sha(p) for p in paths},'inputs':{str(p):sha(p) for p in (core.CURVES,core.CATALOG,core.BW,core.BEST,REF72)}})
def check():
    f=json.loads((HERE/'ACCURACY_TIERS_FREEZE.json').read_text())
    if f['state']!='FROZEN_BEFORE_BIOLOGICAL_FIT':raise ValueError('not frozen')
    for p,h in f['source'].items():
        if sha(HERE/p)!=h:raise ValueError('source changed '+p)
    for p,h in f['inputs'].items():
        if sha(p)!=h:raise ValueError('input changed '+p)

def outer(x,y,p,catalog,folds,f,query):
    tr=np.flatnonzero(folds!=f);te=np.flatnonzero(folds==f)
    if set(p[tr])&set(p[te]):raise ValueError('outer patient overlap')
    inner,_=core.patient_folds(p[tr],3,core.evaluate.SALT+f'|inner|{f}')
    oof={b:np.full((10,2,len(tr),24),np.nan) for b in m.BUDGETS}
    for k in range(3):
        fi=tr[inner!=k];vi=tr[inner==k]
        if set(p[fi])&set(p[vi]):raise ValueError('inner patient overlap')
        models=m.fit_models(x[fi],y[fi],p[fi],catalog)
        for b in m.BUDGETS:oof[b][:,:,inner==k]=m.predict_options(x[vi],models[b])
    if any(not np.isfinite(q).all() for q in oof.values()):raise ValueError('incomplete inner predictions')
    scores={b:[core.metric(q,y[tr],p[tr],inner)[0]['mse'] for q in oof[b]] for b in m.BUDGETS}
    selected={b:int(np.argmin(scores[b])) for b in m.BUDGETS}
    models=m.fit_models(x[tr],y[tr],p[tr],catalog)
    pred={b:m.predict_options(query[te],models[b])[selected[b]] for b in m.BUDGETS}
    states={b:m.payload(models[b],selected[b]) for b in m.BUDGETS};maxdiff=0.;isolation=0.
    for b in m.BUDGETS:
        plan=models[b][0]
        for oi,o in enumerate(('A','B')):
            pp=m.paid(query[te],plan,o);restored=m.replay(states[b],pp)
            maxdiff=max(maxdiff,float(np.max(abs(restored-pred[b][oi]))))
            masked=np.full_like(query[te],np.nan);masked[:,states[b]['native'],states[b]['plate_'+o]]=pp
            isolation=max(isolation,float(np.max(abs(m.replay(states[b],m.paid(masked,plan,o))-restored))))
    if maxdiff>1e-12 or isolation>1e-12:raise ValueError('saved-state or unpaid-input leakage')
    rec={'fold':f,'selected':selected,'inner_scores':scores,'replay_maxdiff':maxdiff,'unpaid_isolation_maxdiff':isolation,'train_patients':sorted(set(p[tr])),'test_patients':sorted(set(p[te]))}
    return pred,states,{b:models[b][0] for b in m.BUDGETS},rec

def execute(out):
    check();out.mkdir(parents=True,exist_ok=False);start=time.monotonic()
    dump(out/'STARTED.json',{'utc':utc(),'python':sys.version,'numpy':np.__version__})
    try:
        data,feat,_=core.load_prepared(core.CURVES,core.CATALOG)
        x=feat['x_replicates'];y=data['y'];p=data['patient_ids'].astype(str);catalog=catalog_from_features(feat)
        folds,_=core.patient_folds(p,5,core.evaluate.SALT+'|outer')
        rz=np.load(core.BW,allow_pickle=False);bz=np.load(core.BEST,allow_pickle=False)
        for ref in (rz,bz):
            if not np.array_equal(ref['y'],y) or not np.array_equal(ref['patients'].astype(str),p) or not np.array_equal(ref['folds'],folds):raise ValueError('reference identity')
        pred={b:np.full((2,len(y),24),np.nan) for b in m.BUDGETS};records=[];state0=None
        for f in range(5):
            guesses,states,plans,r=outer(x,y,p,catalog,folds,f,x);te=folds==f
            for b in m.BUDGETS:
                pred[b][:,te]=guesses[b];np.savez_compressed(out/f'fold_{f}_budget{b}_model.npz',**states[b])
                dump(out/f'fold_{f}_budget{b}_plan.json',plans[b])
                np.savez_compressed(out/f'fold_{f}_budget{b}_paid.npz',A=m.paid(x[te],plans[b],'A'),B=m.paid(x[te],plans[b],'B'),indices=np.flatnonzero(te))
            records.append(r);dump(out/f'fold_{f}_record.json',r)
            if f==0:state0=states
            print(json.dumps({'fold_finished':f,'options':{b:m.OPTIONS[r['selected'][b]] for b in m.BUDGETS}}),flush=True)
        changed_x=x.copy();changed_y=y.copy();changed_x[folds==0]+=73.;changed_y[folds==0]-=97.
        mutated,st,_,rr=outer(changed_x,changed_y,p,catalog,folds,0,x)
        mutation=max(float(np.max(abs(mutated[b]-pred[b][:,folds==0]))) for b in m.BUDGETS)
        state_diff=max(float(np.max(abs(st[b][k]-state0[b][k]))) for b in m.BUDGETS for k in st[b])
        if mutation>1e-12 or state_diff>1e-12 or rr['selected']!=records[0]['selected']:raise ValueError('outer-label dependency')
        control=float(np.max(abs(pred[64]-rz['bandwidth07'])))
        if control>1e-12:raise ValueError('original64 control mismatch '+str(control))
        best=core.metric(bz['candidate'],y,p,folds);operating=core.metric(rz['bandwidth07'],y,p,folds)
        if abs(best[0]['mse']-core.EXPECTED_BEST)>1e-13 or abs(operating[0]['mse']-core.EXPECTED_BW)>1e-13:raise ValueError('comparator metric mismatch')
        reference72=json.loads(REF72.read_text())['candidate'];mse72=float(reference72['mse'])
        results={}
        for b in m.BUDGETS:
            if not np.isfinite(pred[b]).all():raise ValueError('incomplete predictions')
            met=core.metric(pred[b],y,p,folds);vs=core.compare(met,best)
            ratio=best[0]['mse']/met[0]['mse'];tail=met[0]['p90']<=best[0]['p90']
            error=((pred[b][0]-y)**2+(pred[b][1]-y)**2)/2
            baseerr=((bz['candidate'][0]-y)**2+(bz['candidate'][1]-y)**2)/2
            delta=np.array([(error-baseerr)[p==g].mean() for g in np.unique(p)])
            rng=np.random.default_rng(2026100814);boot=delta[rng.integers(len(delta),size=(100000,len(delta)))].mean(1)
            results[str(b)]={'metrics':met[0],'treatment_wells':b,'distinct_native_doses':b,'per_plate':[b//2,b//2],'well_count_ratio_vs64':b/64,'additional_treatment_wells':b-64,'accuracy_only_comparison_vs_scientific64':vs,'mse_improvement_factor_vs64':ratio,'mse_improvement_factor_vs72':mse72/met[0]['mse'],'accuracy_only_half_error_met':bool(ratio>=2 and tail),'half_72_error_met_accuracy_only':bool(met[0]['mse']<=mse72/2 and tail),'same_budget_half_error_met':bool(b==64 and ratio>=2 and tail),'descriptive_paired_patient_delta_95ci':np.quantile(boot,[.025,.975]).tolist(),'comparison_is_cost_matched':b==64}
        np.savez_compressed(out/'predictions_private.npz',**{f'budget{b}':v for b,v in pred.items()},y=y,patients=p,folds=folds,sample_ids=data['sample_ids'],drug_ids=data['drug_ids'],scientific64=bz['candidate'],operating64=rz['bandwidth07'])
        result={'schema':'dosepilot.accuracy_tiers.result.v1','status':'COMPLETE','role':'REPEATED_ADAPTIVE_DEVELOPMENT_COST_ACCURACY_TRADEOFF','tiers':results,'reference_scientific64':best[0],'reference72_recorded':reference72,'original_control_maxdiff':control,'outer_mutation_maxdiff':mutation,'outer_state_maxdiff':state_diff,'same_budget_2x_achieved':results['64']['same_budget_half_error_met'],'no_protected22':True,'independent_validation':False,'submission_changed':False,'freeze_sha256':sha(HERE/'ACCURACY_TIERS_FREEZE.json'),'prediction_sha256':sha(out/'predictions_private.npz'),'seconds':time.monotonic()-start,'finished_utc':utc()}
        dump(out/'RESULT.json',result)
        print(json.dumps({b:{'mse':v['metrics']['mse'],'p90':v['metrics']['p90'],'error_reduction_factor64':v['mse_improvement_factor_vs64'],'error_reduction_factor72':v['mse_improvement_factor_vs72'],'extra_wells':v['additional_treatment_wells'],'accuracy_only_2x':v['accuracy_only_half_error_met'],'same_budget_2x':v['same_budget_half_error_met']} for b,v in results.items()},indent=2),flush=True)
    except BaseException as e:
        dump(out/'FAILURE.json',{'error':repr(e),'traceback':traceback.format_exc(),'utc':utc()});raise

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--freeze',action='store_true');ap.add_argument('--out',type=Path);a=ap.parse_args()
    if a.freeze:freeze()
    elif a.out:execute(a.out)
    else:ap.error('use --freeze or --out')
