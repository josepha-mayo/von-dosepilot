#!/usr/bin/env python3
from __future__ import annotations
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import argparse,importlib.util,json,sys,time,traceback
from pathlib import Path
import numpy as np
from threadpoolctl import threadpool_limits
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];STUDY=ROOT/'study'
spec=importlib.util.spec_from_file_location('frozen_kernel_reference',STUDY/'global_conditional_curve64/run_study.py')
g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
sys.path.insert(0,str(HERE))
from planner import plan_pair,validate_physical,acquire_physical,weights
from sparse_methods import fit_sparse_context
ARMS=('original','distinct_physical','mixed_replication');SEED=202610072250

class PhysicalRidge:
    def __init__(self,context,plan):
        validate_physical(plan);self.mean_x=context.mean_x.copy();self.scale_x=context.scale_x.copy();self.mean_y=context.mean_y.copy()
        self.beta=np.zeros((64,24));owner=np.asarray(plan['coordinate_target_indices'])
        for j in range(24):
            c=np.flatnonzero(owner==j)
            self.beta[c,j]=np.linalg.solve(context.cxx[np.ix_(c,c)]+.01*np.eye(len(c)),context.cxy[c,j])
    def predict(self,paid):
        x=np.asarray(paid,float)
        if x.ndim!=2 or x.shape[1]!=64 or not np.isfinite(x).all():raise ValueError('64 finite paid values required')
        return self.mean_y+((x-self.mean_x)/self.scale_x)@self.beta


def build(x,y,p,catalog,ix):
    original=g.plan_panel_fast(x[ix],y[ix],p[ix],catalog)
    original=dict(original,allows_same_native_on_both_plates=False,original_64_distinct_native_contract_satisfied=True,
         distinct_physical_wells=64,replicated_native_doses=0,policy='original')
    plans=dict(original=original,**plan_pair(x[ix],y[ix],p[ix],catalog));bundles={}
    for arm,plan in plans.items():
        validate_physical(plan,catalog);a,b=[acquire_physical(x[ix],plan,o) for o in ('A','B')]
        ctx=fit_sparse_context(np.r_[a,b],np.r_[y[ix],y[ix]],np.r_[p[ix],p[ix]],np.array([f'paid_slot_{i}' for i in range(64)]),catalog.target_ids)
        base=PhysicalRidge(ctx,plan);z=(np.r_[a,b]-base.mean_x)/base.scale_x;res=np.r_[y[ix]-base.predict(a),y[ix]-base.predict(b)]
        kernel=g.BandwidthAdditive(z,res,np.tile(weights(p[ix]),2)/2,np.asarray(plan['coordinate_target_indices']),.7)
        coefs=[np.zeros_like(res)]+[kernel.coefficients(l,f)[0] for f,l in g.OPTIONS[1:]]
        bundles[arm]={'plan':plan,'base':base,'variants':[{'name':arm,'state':None,'kernel':kernel,'coefs':coefs}]}
    return bundles


def predict_options(x,ix,bundle):
    out=np.empty((10,2,len(ix),24));base=bundle['base'];v=bundle['variants'][0]
    for oi,o in enumerate(('A','B')):
        paid=acquire_physical(x[ix],bundle['plan'],o);bp=base.predict(paid);cross=v['kernel'].centered_cross((paid-base.mean_x)/base.scale_x)
        for k,coef in enumerate(v['coefs']):out[k,oi]=bp+cross@coef
    return out


def fit_outer(xfit,y,p,catalog,folds,fold,xquery):
    tr=np.flatnonzero(folds!=fold);te=np.flatnonzero(folds==fold)
    if set(p[tr])&set(p[te]):raise ValueError('outer overlap')
    inner,_=g.patient_folds(p[tr],3,g.evaluate.SALT+f'|inner|{fold}')
    oof={arm:np.full((10,2,len(tr),24),np.nan) for arm in ARMS}
    for k in range(3):
        fit=tr[inner!=k];val=tr[inner==k]
        if set(p[fit])&set(p[val]):raise ValueError('inner overlap')
        bundles=build(xfit,y,p,catalog,fit)
        for arm in ARMS:
            pr=predict_options(xfit,val,bundles[arm])
            for ci in range(10):
                for o in (0,1):oof[arm][ci,o,inner==k,:]=pr[ci,o]
    if not all(np.isfinite(v).all() for v in oof.values()):raise ValueError('incomplete inner OOF')
    scores={arm:[float(g.risks(v,y[tr],p[tr]).mean()) for v in oof[arm]] for arm in ARMS}
    selected={arm:int(np.argmin(scores[arm])) for arm in ARMS};bundles=build(xfit,y,p,catalog,tr)
    preds={};states={};plans={};poison={};replay={}
    for arm in ARMS:
        bundle=bundles[arm];plan=bundle['plan'];plans[arm]=plan
        preds[arm]=predict_options(xquery,te,bundle)[selected[arm]]
        state=g.payload(bundle,selected[arm]);state['kernel_weights']=bundle['variants'][0]['kernel'].w.copy();states[arm]=state
        replay[arm]=0.;poison[arm]=0.
        for oi,o in enumerate(('A','B')):
            paid=acquire_physical(xquery[te],plan,o);again=g.predict_payload(state,paid,o)
            replay[arm]=max(replay[arm],float(np.max(abs(again-preds[arm][oi]))))
            masked=np.full_like(xquery[te],np.nan);ni=state['native_indices'];pi=state['plate_'+o]
            masked[:,ni,pi]=xquery[te][:,ni,pi]
            again2=g.predict_payload(state,acquire_physical(masked,plan,o),o)
            poison[arm]=max(poison[arm],float(np.max(abs(again2-again))))
    if max(replay.values())>1e-12 or max(poison.values())>1e-12:raise ValueError('saved-state or physical-input invariant failed')
    rec={'fold':fold,'selected_indices':selected,'selected_options':{a:list(g.OPTIONS[selected[a]]) for a in ARMS},'inner_mse':scores,
       'distinct_native_doses':{a:plans[a]['distinct_native_doses'] for a in ARMS},'replicated_native_doses':{a:plans[a]['replicated_native_doses'] for a in ARMS},
       'original_native_contract_satisfied':{a:plans[a]['distinct_native_doses']==64 for a in ARMS},
       'state_replay_maxdiff':replay,'unpaid_poison_maxdiff':poison,'physical_wells':64,'per_plate':[32,32]}
    return preds,states,plans,rec


def check(curves,catalog,reference):
    fr=json.loads((HERE/'FREEZE.json').read_text(encoding='utf-8'))
    for k,p in {'curves':curves,'catalog':catalog,'reference':reference}.items():
        if g.sha(p)!=fr['inputs'][k]:raise ValueError('input changed '+k)
    for rel,h in fr['source_sha256'].items():
        if g.sha(ROOT/rel)!=h:raise ValueError('source changed '+rel)
    return fr


def execute(curves,catalog_path,reference,out):
    fr=check(curves,catalog_path,reference);out=Path(out);out.mkdir(parents=True,exist_ok=False);started=time.perf_counter()
    g.dump(out/'STARTED.json',{'utc':g.utc(),'freeze_sha256':g.sha(HERE/'FREEZE.json'),'python':sys.version,'numpy':np.__version__,
        'physical_wells':64,'original_distinct_native_constraint_relaxed_in_primary_arm':True,'automatic_promotion':False})
    try:
        data,feat,_=g.load_prepared(curves,catalog_path);x,y,p=feat['x_replicates'],data['y'],data['patient_ids'].astype(str);catalog=g.catalog_from_features(feat)
        folds,_=g.patient_folds(p,5,g.evaluate.SALT+'|outer')
        with np.load(reference,allow_pickle=False) as z:
            if not np.array_equal(z['y'],y) or not np.array_equal(z['patients'].astype(str),p) or not np.array_equal(z['folds'],folds):raise ValueError('reference identity')
            retained=z['candidate'].copy();operating=z['bandwidth07'].copy()
        if abs(g.metrics(retained,y,p,folds)['mse']-g.EXPECTED_SCI)>1e-15:raise ValueError('retained reference changed')
        predictions={arm:np.full((2,*y.shape),np.nan) for arm in ARMS};records=[];first=None
        with threadpool_limits(limits=1):
            for f in range(5):
                pr,states,plans,rec=fit_outer(x,y,p,catalog,folds,f,x)
                for arm in ARMS:
                    predictions[arm][:,folds==f]=pr[arm];g.dump(out/f'fold_{f}_{arm}_plan.json',plans[arm]);np.savez_compressed(out/f'fold_{f}_{arm}_model_private.npz',**states[arm])
                if f==0:first={a:{k:np.asarray(v).copy() for k,v in s.items()} for a,s in states.items()}
                records.append(rec);g.dump(out/f'fold_{f}_COMPLETE.json',rec)
                print(json.dumps({'event':'outer_complete','fold':f,'native_counts':rec['distinct_native_doses'],'selected':rec['selected_options']}),flush=True)
            changed_x=x.copy();changed_y=y.copy();changed_x[folds==0]+=37;changed_y[folds==0]+=71
            sentinel,states,unused,srec=fit_outer(changed_x,changed_y,p,catalog,folds,0,x)
        mutation={a:float(np.max(abs(sentinel[a]-predictions[a][:,folds==0]))) for a in ARMS}
        statediff={a:max(float(np.max(abs(states[a][k]-first[a][k]))) for k in first[a]) for a in ARMS}
        if max(mutation.values())>1e-12 or max(statediff.values())>1e-12 or srec['selected_indices']!=records[0]['selected_indices']:raise ValueError('outer test training path')
        benchmark=g.metrics(predictions['original'],y,p,folds)
        if abs(benchmark['mse']-g.EXPECTED_BASE)>1e-12:raise ValueError('original benchmark not reproduced')
        g.SEED=SEED;arms={}
        for arm,pr in predictions.items():
            cm=g.metrics(pr,y,p,folds);cr=g.compare(pr,retained,y,p,folds,data['drug_ids']);co=g.compare(pr,operating,y,p,folds,data['drug_ids'])
            contract=all(r['original_native_contract_satisfied'][arm] for r in records)
            arms[arm]={'metrics':cm,'vs_retained64':cr,'vs_operating64':co,'same_physical_budget_gate_pass':bool(cr['gate_pass'] and co['gate_pass']),
                'half_error_point_and_tail_met':bool(cm['mse']<=g.HALF_TARGET and cr['p90_nonworse']),
                'original_64_distinct_native_contract_satisfied_on_outer_plans':contract,
                'decision':'REVIEW_NEW_DESIGN_CONTRACT_AND_REPLAY' if cr['gate_pass'] and co['gate_pass'] else 'REJECT_FOR_PROMOTION'}
        np.savez_compressed(out/'predictions_private.npz',**predictions,retained64=retained,operating64=operating,y=y,patients=p,folds=folds,sample_ids=data['sample_ids'],drug_ids=data['drug_ids'])
        r={'schema':'dosepilot.mixed_physical_replication64.result.v1','status':'COMPLETE','primary_arm':'mixed_replication','arms':arms,
           'fold_records':records,'physical_wells':64,'per_plate':[32,32],'half_error_target':g.HALF_TARGET,'original_distinct_native_constraint_explicitly_relaxed':True,
           'baseline_mse_difference':abs(benchmark['mse']-g.EXPECTED_BASE),'outer_label_curve_mutation_maxdiff':mutation,'outer_state_mutation_maxdiff':statediff,
           'prediction_sha256':g.sha(out/'predictions_private.npz'),'freeze_sha256':g.sha(HERE/'FREEZE.json'),
           'protected22_access':False,'independent_validation':False,'selection_adjusted':False,'automatic_promotion':False,'kaggle_entry_changed':False,
           'new_control_wells':0,'new_treatment_wells':0,'seconds':time.perf_counter()-started,'finished_utc':g.utc()}
        g.dump(out/'RESULT.json',r);print(json.dumps(r,indent=2),flush=True);return r
    except BaseException as exc:g.dump(out/'FAILURE.json',{'error':repr(exc),'traceback':traceback.format_exc(),'utc':g.utc(),'automatic_retry':False});raise

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--curves',type=Path,required=True);ap.add_argument('--catalog',type=Path,required=True);ap.add_argument('--reference',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args();execute(a.curves,a.catalog,a.reference,a.out)
