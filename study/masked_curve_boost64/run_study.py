#!/usr/bin/env python3
from __future__ import annotations
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import argparse,datetime,gc,hashlib,importlib.metadata,json,sys,time,traceback
from pathlib import Path
import numpy as np
from threadpoolctl import threadpool_limits
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];STUDY=ROOT/'study'
sys.path[:0]=[str(HERE),str(STUDY),str(STUDY/'engine'),str(STUDY/'acceleration')]
from core import build_rows,fit_model,predict_paid,predict_ridge,export_trees,predict_exported,SEED
from compact_train import load_prepared,read_catalog
from coverage_methods import acquire,catalog_from_features,validate_plan,fit_prediction_context,CoveragePredictor
from fast_coverage import plan_panel_fast
from methods import patient_folds
ARMS=('mask_augmented','original_mask_control');TARGET=.000521372861048106

def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,x):
    with Path(p).open('x',encoding='utf-8',newline='\n') as f:json.dump(x,f,indent=2,allow_nan=False);f.write('\n')
def risk(pred,y,p):
    e=((pred[0]-y)**2+(pred[1]-y)**2)/2
    return np.stack([e[p==g].mean(0) for g in np.unique(p)])
def metrics(pred,y,p,folds):
    r=risk(pred,y,p).mean(1);pf=np.array([folds[np.flatnonzero(p==g)[0]] for g in np.unique(p)])
    return {'mse':float(r.mean()),'p90_patient_rmse':float(np.quantile(np.sqrt(r),.9)),
            'fold_mse':[float(r[pf==f].mean()) for f in range(5)]}
def compare(pred,reference,y,p,folds,names):
    c=risk(pred,y,p);r=risk(reference,y,p);d=c.mean(1)-r.mean(1);t=c.mean(0)-r.mean(0)
    cm,rm=metrics(pred,y,p,folds),metrics(reference,y,p,folds);wins=int((d<-1e-15).sum())
    fw=sum(a<b-1e-15 for a,b in zip(cm['fold_mse'],rm['fold_mse']));tail=cm['p90_patient_rmse']<=rm['p90_patient_rmse']+1e-15
    boot=d[np.random.default_rng(SEED).integers(len(d),size=(100000,len(d)))].mean(1)
    return {'relative_mse_gain':1-cm['mse']/rm['mse'],'patient_wins':wins,'patient_losses':int((d>1e-15).sum()),'fold_wins':fw,
        'p90_nonworse':tail,'target_wins':int((t<-1e-15).sum()),'regressing_targets':[str(names[j]) for j in range(24) if t[j]>1e-15],
        'descriptive_bootstrap_95_ci':np.quantile(boot,[.025,.975]).tolist(),
        'gate_pass':bool(cm['mse']<rm['mse']-1e-15 and wins>=30 and fw==5 and tail)}

class ReplayModel:
    def __init__(self,state):self.state=state
    def predict(self,features):return predict_exported(self.state,features)

def fit_fold(xfit,y,p,catalog,bounds,folds,f,xquery,out=None):
    tr=np.flatnonzero(folds!=f);te=np.flatnonzero(folds==f)
    if set(p[tr])&set(p[te]):raise ValueError('whole-patient overlap')
    plan=plan_panel_fast(xfit[tr],y[tr],p[tr],catalog);validate_plan(plan,catalog)
    if out is not None:dump(out/f'fold_{f}_plan.json',plan)
    trainA=acquire(xfit[tr],plan,'A');trainB=acquire(xfit[tr],plan,'B')
    ref=CoveragePredictor(fit_prediction_context(trainA,trainB,y[tr],p[tr],plan,catalog.target_ids),plan,.01)
    queryA=acquire(xquery[te],plan,'A');queryB=acquire(xquery[te],plan,'B');owner=np.asarray(plan['coordinate_target_indices'])
    records={};predictions={};r13=np.stack([ref.predict(queryA),ref.predict(queryB)])
    for arm in ARMS:
        began=time.perf_counter();xx,yy,w,states,inventory=build_rows(xfit[tr],y[tr],p[tr],catalog,bounds,plan,arm=='mask_augmented')
        tree=fit_model(xx,yy,w);tree_state=export_trees(tree)
        estimate=np.stack([predict_paid(tree,states,paid,plan,catalog,bounds,o) for o,paid in (('A',queryA),('B',queryB))])
        replay=np.stack([predict_paid(ReplayModel(tree_state),states,paid,plan,catalog,bounds,o) for o,paid in (('A',queryA),('B',queryB))])
        diff=float(np.max(np.abs(estimate-replay)))
        if diff>1e-12:raise ValueError('tree-node replay disagreement')
        own=np.stack([np.column_stack([predict_ridge(states[j],paid[:,owner==j]) for j in range(24)]) for paid in (queryA,queryB)])
        basediff=float(np.max(np.abs(own-r13)))
        if basediff>1e-12:raise ValueError('original own-ridge head changed')
        poison=0.
        for oi,o in enumerate(('A','B')):
            native=np.asarray(plan['selected_native_indices']);plate=np.asarray(plan[f'orientation_{o}_plate_indices'])
            masked=np.full_like(xquery[te],np.nan);masked[:,native,plate]=xquery[te][:,native,plate]
            paid=acquire(masked,plan,o);check=predict_paid(tree,states,paid,plan,catalog,bounds,o)
            poison=max(poison,float(np.max(np.abs(check-estimate[oi]))))
        if poison>1e-12:raise ValueError('unpaid input affected prediction')
        if out is not None:
            teachers={}
            for j,state in enumerate(states):
                teachers.update({f'head_{j}_{key}':np.asarray(value) for key,value in state.items()})
            np.savez_compressed(out/f'fold_{f}_{arm}_model_private.npz',**tree_state,**teachers,plan_json=np.asarray(json.dumps(plan)),bounds_json=np.asarray(json.dumps(bounds)))
            np.savez_compressed(out/f'fold_{f}_{arm}_predictions_private.npz',prediction=estimate,r13=r13,test_indices=te)
        predictions[arm]=estimate
        records[arm]={'virtual_training_rows':len(xx),'real_training_patients':len(np.unique(p[tr])),'real_training_organoids':len(tr),
           'total_sample_weight':float(w.sum()),'inventory':inventory,'tree_count':int(tree_state['tree_count']),
           'saved_tree_replay_maxdiff':diff,'original_own_ridge_maxdiff':basediff,'unpaid_poison_maxdiff':poison,
           'seconds':time.perf_counter()-began,'treatment_wells':64,'per_plate':[32,32]}
        if out is not None:print(json.dumps({'event':'arm_fold_complete','fold':f,'arm':arm,'virtual_rows':len(xx),'seconds':time.perf_counter()-began}),flush=True)
        del xx,yy,w,tree,tree_state;gc.collect()
    return predictions,r13,records

def execute(curves,catalog_path,reference,out):
    fr=json.loads((HERE/'FREEZE.json').read_text(encoding='utf-8'))
    for name,path in {'curves':curves,'catalog':catalog_path,'reference':reference}.items():
        if sha(path)!=fr['inputs'][name]:raise ValueError('input hash changed '+name)
    for name,digest in fr['source_sha256'].items():
        if sha(ROOT/name)!=digest:raise ValueError('source changed '+name)
    for name,version in fr['runtime_versions'].items():
        if importlib.metadata.version(name)!=version:raise ValueError('runtime changed '+name)
    out=Path(out);out.mkdir(parents=True,exist_ok=False);dump(out/'STARTED.json',{'utc':utc(),'freeze_sha256':sha(HERE/'FREEZE.json'),'protected22_access':False})
    try:
        data,features,_=load_prepared(curves,catalog_path);x,y,p=features['x_replicates'],data['y'],data['patient_ids'].astype(str)
        catalog=catalog_from_features(features);bounds=read_catalog(catalog_path)['target_bounds_nM'];folds,_=patient_folds(p,5,'von-organoid-sentinel-v1|outer')
        with np.load(reference,allow_pickle=False) as z:
            if not np.array_equal(z['y'],y) or not np.array_equal(z['patients'].astype(str),p) or not np.array_equal(z['folds'],folds):raise ValueError('reference identity')
            retained=z['candidate'].copy();operating=z['bandwidth07'].copy()
        if abs(metrics(retained,y,p,folds)['mse']-.001042745722096212)>1e-15 or abs(metrics(operating,y,p,folds)['mse']-.0010582750420801538)>1e-15:raise ValueError('reference MSE mismatch')
        predictions={arm:np.full((2,*y.shape),np.nan) for arm in ARMS};r13=np.full((2,*y.shape),np.nan);records=[]
        with threadpool_limits(limits=1):
            for f in range(5):
                pp,rr,rec=fit_fold(x,y,p,catalog,bounds,folds,f,x,out)
                for arm in ARMS:predictions[arm][:,folds==f]=pp[arm]
                r13[:,folds==f]=rr;records.append({'fold':f,'arms':rec});dump(out/f'fold_{f}_COMPLETE.json',records[-1])
            changed_x=x.copy();changed_y=y.copy();changed_x[folds==0]+=73;changed_y[folds==0]+=113
            sentinel,_,_=fit_fold(changed_x,changed_y,p,catalog,bounds,folds,0,x)
        isolation={arm:float(np.max(np.abs(sentinel[arm]-predictions[arm][:,folds==0]))) for arm in ARMS}
        if any(v>1e-12 for v in isolation.values()):raise ValueError('outer-test training leakage')
        r13m=metrics(r13,y,p,folds)
        if abs(r13m['mse']-.0011448586813828537)>1e-12:raise ValueError('original R13 changed')
        arms={}
        for arm in ARMS:
            pr=predictions[arm]
            if not np.isfinite(pr).all():raise ValueError('incomplete candidate')
            cm=metrics(pr,y,p,folds);vsret=compare(pr,retained,y,p,folds,data['drug_ids']);vsop=compare(pr,operating,y,p,folds,data['drug_ids'])
            arms[arm]={'metrics':cm,'vs_retained64':vsret,'vs_operating64':vsop,'half_error_point_and_tail_met':bool(cm['mse']<=TARGET and vsret['p90_nonworse']),
                 'decision':'ELIGIBLE_FOR_FRESH_REPLAY' if vsret['gate_pass'] and vsop['gate_pass'] else 'REJECT_FOR_PROMOTION'}
        np.savez_compressed(out/'predictions_private.npz',**predictions,r13=r13,retained64=retained,operating64=operating,y=y,patients=p,folds=folds,sample_ids=data['sample_ids'],drug_ids=data['drug_ids'])
        result={'schema':'dosepilot.masked_curve_boost64.result.v1','status':'COMPLETE','primary_arm':'mask_augmented','arms':arms,'fold_records':records,
           'outer_label_curve_mutation_maxdiff':isolation,'r13_metrics':r13m,'treatment_wells':64,'per_plate':[32,32],
           'prediction_sha256':sha(out/'predictions_private.npz'),'freeze_sha256':sha(HERE/'FREEZE.json'),'half_error_target':TARGET,
           'synthetic_masks_are_not_new_patients':True,'protected22_access':False,'independent_validation':False,'selection_adjusted':False,
           'automatic_promotion':False,'kaggle_entry_changed':False,'finished_utc':utc()}
        dump(out/'RESULT.json',result);print(json.dumps({'status':result['status'],'arms':arms,'isolation':isolation},indent=2),flush=True);return result
    except BaseException as exc:dump(out/'FAILURE.json',{'error':repr(exc),'traceback':traceback.format_exc(),'utc':utc(),'automatic_retry':False});raise

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--curves',type=Path,required=True);ap.add_argument('--catalog',type=Path,required=True);ap.add_argument('--reference',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args();execute(a.curves,a.catalog,a.reference,a.out)
