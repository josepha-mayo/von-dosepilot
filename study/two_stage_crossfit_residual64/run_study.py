#!/usr/bin/env python3
from __future__ import annotations
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import argparse,importlib.util,importlib.metadata,json,sys,time,traceback,socket
from pathlib import Path
import numpy as np
from threadpoolctl import threadpool_limits
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];STUDY=ROOT/'study'
spec=importlib.util.spec_from_file_location('frozen_two_stage_policy_runner',STUDY/'two_stage_risk64/run_study.py')
ts=importlib.util.module_from_spec(spec);spec.loader.exec_module(ts);g=ts.g
sys.path.insert(0,str(HERE));from kernel import Kernel,encode,predict_saved,OPTIONS,DIMENSION
POLICIES=('static','adaptive');SEED=202610080940;NETWORK=[]
def deny(*a,**kw):NETWORK.append('blocked');raise RuntimeError('network disabled during biological fitting')


def make_bank(data,indices):
    ix=np.asarray(indices,int)
    original=g.plan_panel_fast(data['x'][ix],data['y'][ix],data['p'][ix],data['catalog']);g.validate_plan(original,data['catalog'])
    return ts.policy.build_bank(data['full']['values'][ix],data['y'][ix],data['p'][ix],data['catalog'],data['full']['owner'],
      data['full']['query_to_full'],data['full']['q'],data['positions'],original)


def observe_features(bank,query,query_positions):
    base={name:np.empty((2,len(query),24)) for name in POLICIES};features={name:np.empty((2,len(query),DIMENSION)) for name in POLICIES};trace={}
    for seed in (0,1):
        for adaptive,name in ((False,'static'),(True,'adaptive')):
            oracle=ts.PaidOracle(query);first=oracle.initial(bank,seed)
            actions,_=ts.policy.choose_actions(bank,first,seed,adaptive);later=oracle.followup(bank,actions,seed)
            bp=ts.policy.infer(bank,first,actions,later,seed,'ridge')
            phi=encode(bank,first,actions,later,seed,bp,query_positions)
            base[name][seed]=bp;features[name][seed]=phi;key=f'{name}_s{seed}'
            trace[key+'_initial']=first;trace[key+'_actions']=actions;trace[key+'_final']=later;trace[key+'_cells']=np.asarray(oracle.reads,int)
    return base,features,trace


def fit_model(data,fit_indices,tag):
    tr=np.asarray(fit_indices,int);p=data['p'];n=len(tr)
    inner,_=g.patient_folds(p[tr],3,g.evaluate.SALT+'|staged-residual-calibration|'+tag)
    base={name:np.full((2,n,24),np.nan) for name in POLICIES};features={name:np.full((2,n,DIMENSION),np.nan) for name in POLICIES}
    partitions=[]
    for k in range(3):
        fit=tr[inner!=k];held=tr[inner==k]
        if set(p[fit])&set(p[held]):raise ValueError('meta-training patient overlap')
        bank=make_bank(data,fit);bp,phi,trace=observe_features(bank,data['x'][held],data['query_positions'])
        for name in POLICIES:
            for seed in (0,1):base[name][seed,inner==k]=bp[name][seed];features[name][seed,inner==k]=phi[name][seed]
        partitions.append({'calibration_fold':k,'fitting_indices':fit.tolist(),'held_indices':held.tolist()})
    if any(not np.isfinite(v).all() for v in features.values()):raise ValueError('missing honest residual-training rows')
    ids,inv,count=np.unique(p[tr],return_inverse=True,return_counts=True);weights=np.tile(1./(len(ids)*count[inv]),2)/2
    target=np.tile(data['y'][tr],(2,1));kernels={}
    for name in POLICIES:
        kernels[name]=Kernel(features[name].reshape(2*n,DIMENSION),target-base[name].reshape(2*n,24),weights)
    full_bank=make_bank(data,tr)
    return {'bank':full_bank,'kernels':kernels,'partitions':partitions,'training_indices':tr,'calibration_fold':inner,
      'calibration_base':base,'calibration_features':features,'query_positions':data['query_positions']}


def predict_all(model,query):
    base,features,trace=observe_features(model['bank'],query,model['query_positions']);out={}
    for name in POLICIES:
        out[name]=model['kernels'][name].predict_all(features[name].reshape(2*len(query),DIMENSION),base[name].reshape(2*len(query),24)).reshape(10,2,len(query),24)
    return out,base,features,trace


def fit_outer(data,folds,f,query):
    tr=np.flatnonzero(folds!=f);te=np.flatnonzero(folds==f);p=data['p']
    if set(p[tr])&set(p[te]):raise ValueError('outer patient overlap')
    inner,_=g.patient_folds(p[tr],3,g.evaluate.SALT+f'|inner|{f}')
    oof={name:np.full((10,2,len(tr),24),np.nan) for name in POLICIES}
    for k in range(3):
        fit=tr[inner!=k];held=tr[inner==k]
        if set(p[fit])&set(p[held]):raise ValueError('inner patient overlap')
        model=fit_model(data,fit,f'outer{f}:inner{k}');pr,_,_,_=predict_all(model,data['x'][held])
        for name in POLICIES:
            for option in range(10):
                for seed in (0,1):oof[name][option,seed,inner==k]=pr[name][option,seed]
    scores={name:[float(g.risks(q,data['y'][tr],p[tr]).mean()) for q in oof[name]] for name in POLICIES}
    if any(not np.isfinite(v).all() for v in oof.values()):raise ValueError('missing inner validation predictions')
    selected={name:int(np.argmin(scores[name])) for name in POLICIES}
    model=fit_model(data,tr,f'outer{f}:full');options,base,features,trace=predict_all(model,query)
    predictions={name:options[name][selected[name]] for name in POLICIES}
    states={name:model['kernels'][name].arrays(selected[name]) for name in POLICIES}
    replay=0.;poison=0.
    for name in POLICIES:
        reconstructed=predict_saved(states[name],features[name].reshape(2*len(query),DIMENSION),base[name].reshape(2*len(query),24)).reshape(2,len(query),24)
        replay=max(replay,float(np.max(abs(reconstructed-predictions[name]))))
        for seed in (0,1):
            key=f'{name}_s{seed}';masked=np.full_like(query,np.nan)
            for row,requests in enumerate(trace[key+'_cells']):
                for native,plate in requests:masked[row,native,plate]=query[row,native,plate]
            oracle=ts.PaidOracle(masked);first=oracle.initial(model['bank'],seed)
            actions,_=ts.policy.choose_actions(model['bank'],first,seed,name=='adaptive')
            if not np.array_equal(actions,trace[key+'_actions']):raise ValueError('unpaid dependency in policy')
            last=oracle.followup(model['bank'],actions,seed);bp=ts.policy.infer(model['bank'],first,actions,last,seed,'ridge')
            phi=encode(model['bank'],first,actions,last,seed,bp,model['query_positions'])
            poisoned=predict_saved(states[name],phi,bp);poison=max(poison,float(np.max(abs(poisoned-predictions[name][seed]))))
    if replay>1e-12 or poison>1e-12:raise ValueError('saved inference or unpaid value invariant')
    record={'fold':f,'arms':{name:{'selected_index':selected[name],'selected_option':OPTIONS[selected[name]],'inner_mse':scores[name]} for name in POLICIES},
      'saved_prediction_maxdiff':replay,'unpaid_poison_maxdiff':poison,'residual_training_is_patient_crossfitted':True}
    return predictions,base,record,model,states,trace


def check(curves,catalog,reference,raw_reference):
    fr=json.loads((HERE/'FREEZE.json').read_text())
    for k,path in {'curves':curves,'catalog':catalog,'reference':reference,'raw_policy_reference':raw_reference}.items():
        if g.sha(path)!=fr['inputs'][k]:raise ValueError('input changed '+k)
    for p,h in fr['source_sha256'].items():
        if g.sha(ROOT/p)!=h:raise ValueError('source changed '+p)
    for name,version in fr['runtime_versions'].items():
        if importlib.metadata.version(name)!=version:raise ValueError('runtime changed '+name)
    return fr


def execute(curves,catalog_path,reference,raw_reference,out):
    fr=check(curves,catalog_path,reference,raw_reference);out=Path(out);out.mkdir(parents=True,exist_ok=False)
    g.dump(out/'STARTED.json',{'utc':g.utc(),'freeze_sha256':g.sha(HERE/'FREEZE.json'),'network_denied':True,'runtime_versions':fr['runtime_versions']})
    socket.create_connection=deny;socket.socket.connect=deny;socket.socket.connect_ex=deny;began=time.perf_counter()
    try:
        d,feat,_=g.load_prepared(curves,catalog_path);cat=g.catalog_from_features(feat)
        full=g.full_training_curves(curves,d,feat,cat,g.read_catalog(catalog_path));positions=ts.metadata(curves,cat,full)
        full_position=np.zeros(len(full['owner']))
        for j in range(24):full_position[full['owner']==j]=positions[j]
        data={'x':feat['x_replicates'],'y':d['y'],'p':d['patient_ids'].astype(str),'catalog':cat,'full':full,'positions':positions,
              'query_positions':full_position[full['query_to_full']]}
        y,p=data['y'],data['p'];folds,_=g.patient_folds(p,5,g.evaluate.SALT+'|outer')
        with np.load(reference,allow_pickle=False) as z:
            if not np.array_equal(z['y'],y) or not np.array_equal(z['patients'].astype(str),p) or not np.array_equal(z['folds'],folds):raise ValueError('reference identity')
            retained=z['candidate'].copy();operating=z['bandwidth07'].copy()
        with np.load(raw_reference,allow_pickle=False) as z:
            if not np.array_equal(z['y'],y) or not np.array_equal(z['patients'].astype(str),p) or not np.array_equal(z['folds'],folds):raise ValueError('raw policy reference identity')
            raw_ref={name:z[name+'_ridge'].copy() for name in POLICIES}
        predictions={name:np.full((2,*y.shape),np.nan) for name in POLICIES};raw={name:np.full((2,*y.shape),np.nan) for name in POLICIES}
        records=[];firstbank=None;firststates=None
        with threadpool_limits(limits=1):
            for f in range(5):
                ix=np.flatnonzero(folds==f);pr,bp,rec,model,states,trace=fit_outer(data,folds,f,data['x'][ix])
                for name in POLICIES:
                    predictions[name][:,ix]=pr[name];raw[name][:,ix]=bp[name]
                    np.savez_compressed(out/f'fold_{f}_{name}_kernel_private.npz',**states[name])
                np.savez_compressed(out/f'fold_{f}_bank_private.npz',**model['bank'])
                np.savez_compressed(out/f'fold_{f}_query_trace_private.npz',**trace,query_positions=data['query_positions'])
                calibration={'train_indices':model['training_indices'],'calibration_fold':model['calibration_fold']}
                for name in POLICIES:calibration[name+'_features']=model['calibration_features'][name];calibration[name+'_base']=model['calibration_base'][name]
                np.savez_compressed(out/f'fold_{f}_calibration_private.npz',**calibration)
                g.dump(out/f'fold_{f}_calibration_partitions_private.json',model['partitions']);g.dump(out/f'fold_{f}_COMPLETE.json',rec);records.append(rec)
                if f==0:firstbank={k:v.copy() for k,v in model['bank'].items()};firststates={a:{k:np.asarray(v).copy() for k,v in s.items()} for a,s in states.items()}
                print(json.dumps({'event':'outer_complete','fold':f,'choices':{n:rec['arms'][n]['selected_option'] for n in POLICIES},'elapsed_seconds':time.perf_counter()-began}),flush=True)
            changed=dict(data);changed['x']=data['x'].copy();changed['y']=y.copy();changed['full']=dict(full);changed['full']['values']=full['values'].copy()
            changed['x'][folds==0]+=71;changed['y'][folds==0]-=103;changed['full']['values'][folds==0]+=137
            sentinel,_,srec,smodel,sstates,_=fit_outer(changed,folds,0,data['x'][folds==0])
        bankdiff=max(float(np.max(abs(smodel['bank'][k]-firstbank[k]))) for k in firstbank)
        isolation={}
        for name in POLICIES:
            pd=float(np.max(abs(sentinel[name]-predictions[name][:,folds==0])))
            sd=max(float(np.max(abs(np.asarray(sstates[name][k])-firststates[name][k]))) for k in firststates[name])
            if pd>1e-12 or sd>1e-12 or bankdiff>1e-12 or srec['arms'][name]['selected_index']!=records[0]['arms'][name]['selected_index']:raise ValueError('outer evaluation label path')
            isolation[name]={'prediction_maxdiff':pd,'kernel_state_maxdiff':sd,'bank_maxdiff':bankdiff}
        replay=max(float(np.max(abs(raw[name]-raw_ref[name]))) for name in POLICIES)
        if replay>1e-12:raise ValueError('raw acquisition/predictor changed from preceding frozen trial')
        if NETWORK or any(not np.isfinite(v).all() for v in predictions.values()):raise ValueError('network or incomplete predictions')
        g.SEED=SEED;arms={}
        for name in POLICIES:
            m=g.metrics(predictions[name],y,p,folds);vr=g.compare(predictions[name],retained,y,p,folds,d['drug_ids']);vo=g.compare(predictions[name],operating,y,p,folds,d['drug_ids'])
            arms[name]={'metrics':m,'vs_retained64':vr,'vs_operating64':vo,'vs_same_policy_raw':g.compare(predictions[name],raw[name],y,p,folds,d['drug_ids']),
              'half_error_numeric_target_met':bool(m['mse']<=g.HALF_TARGET and vr['p90_nonworse']),
              'decision':'NUMERICALLY_ELIGIBLE_REQUIRES_WORKFLOW_REVIEW' if vr['gate_pass'] and vo['gate_pass'] else 'REJECT_FOR_PROMOTION'}
        np.savez_compressed(out/'predictions_private.npz',**predictions,static_raw=raw['static'],adaptive_raw=raw['adaptive'],retained64=retained,operating64=operating,
           y=y,patients=p,folds=folds,sample_ids=d['sample_ids'],drug_ids=d['drug_ids'])
        result={'schema':'dosepilot.two_stage_crossfit_residual64.result.v1','status':'COMPLETE','primary_arm':'adaptive','arms':arms,
           'adaptive_vs_static':g.compare(predictions['adaptive'],predictions['static'],y,p,folds,d['drug_ids']),
           'fold_records':records,'outer_label_and_curve_mutation':isolation,'raw_policy_prediction_replay_maxdiff':replay,
           'treatment_wells':64,'per_plate':[32,32],'round_budgets':[48,16],'derived_features':DIMENSION,
           'single_round_operational_contract_preserved':False,'sequential_lab_feasibility_validated':False,
           'residual_training_uses_global_outer_OOF':False,'network_attempts':len(NETWORK),
           'prediction_sha256':g.sha(out/'predictions_private.npz'),'freeze_sha256':g.sha(HERE/'FREEZE.json'),
           'protected22_access':False,'independent_validation':False,'selection_adjusted':False,'automatic_promotion':False,'kaggle_entry_changed':False,
           'elapsed_seconds':time.perf_counter()-began,'finished_utc':g.utc()}
        g.dump(out/'RESULT.json',result);print(json.dumps({k:v for k,v in result.items() if k!='fold_records'},indent=2),flush=True);return result
    except BaseException as exc:g.dump(out/'FAILURE.json',{'error':repr(exc),'traceback':traceback.format_exc(),'utc':g.utc(),'automatic_retry':False});raise

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--curves',type=Path,required=True);ap.add_argument('--catalog',type=Path,required=True);ap.add_argument('--reference',type=Path,required=True);ap.add_argument('--raw-reference',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args();execute(a.curves,a.catalog,a.reference,a.raw_reference,a.out)
