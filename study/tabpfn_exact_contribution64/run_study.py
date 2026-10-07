#!/usr/bin/env python3
from __future__ import annotations
import os
E='D:/von-dosepilot-data/tabpfn_environment_20261007'
for k in ('TABPFN_DISABLE_TELEMETRY','DO_NOT_TRACK','HF_HUB_DISABLE_TELEMETRY','HF_HUB_OFFLINE','TABPFN_NO_BROWSER'):os.environ[k]='1'
for k in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS'):os.environ[k]='1'
os.environ['TABPFN_MODEL_CACHE_DIR']=E+'/models';os.environ['HF_HOME']=E+'/hf_cache';os.environ['TMP']=E+'/tmp';os.environ['TEMP']=E+'/tmp'
import argparse,datetime,gc,hashlib,importlib.metadata,importlib.util,json,socket,sys,time,traceback
from pathlib import Path
import numpy as np,torch
from threadpoolctl import threadpool_limits
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];STUDY=ROOT/'study'
sys.path[:0]=[str(HERE),str(STUDY),str(STUDY/'engine'),str(STUDY/'acceleration'),str(STUDY/'global_conditional_curve64')]
from anchor import observed_weights,known_contribution,predict_target
from full_curves import full_training_curves
from compact_train import load_prepared,read_catalog
from coverage_methods import acquire,catalog_from_features,validate_plan
from fast_coverage import plan_panel_fast
from methods import patient_folds
SEED=202610071519;TARGET=.000521372861048106
NETWORK=[]
def deny(*a,**kw):NETWORK.append('blocked');raise RuntimeError('network forbidden during biological inference')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def dump(p,x):
    with Path(p).open('x',encoding='utf-8',newline='\n') as f:json.dump(x,f,indent=2,allow_nan=False);f.write('\n')
def risks(pred,y,p):
    error=((pred[0]-y)**2+(pred[1]-y)**2)/2
    return np.stack([error[p==g].mean(0) for g in np.unique(p)])
def metrics(pred,y,p,folds):
    r=risks(pred,y,p).mean(1);pf=np.array([folds[np.flatnonzero(p==g)[0]] for g in np.unique(p)])
    return {'mse':float(r.mean()),'p90_patient_rmse':float(np.quantile(np.sqrt(r),.9)), 'fold_mse':[float(r[pf==f].mean()) for f in range(5)]}
def compare(c,r,y,p,folds,names):
    cr=risks(c,y,p);rr=risks(r,y,p);d=cr.mean(1)-rr.mean(1);td=cr.mean(0)-rr.mean(0);cm=metrics(c,y,p,folds);rm=metrics(r,y,p,folds)
    wins=int(np.sum(d<-1e-15));fw=sum(a<b-1e-15 for a,b in zip(cm['fold_mse'],rm['fold_mse']));tail=cm['p90_patient_rmse']<=rm['p90_patient_rmse']+1e-15
    boot=d[np.random.default_rng(SEED).integers(len(d),size=(100000,len(d)))].mean(1)
    return {'relative_mse_gain':1-cm['mse']/rm['mse'],'patient_wins':wins,'patient_losses':int(np.sum(d>1e-15)),
       'fold_wins':fw,'p90_nonworse':tail,'target_wins':int(np.sum(td<-1e-15)),
       'regressing_targets':[str(names[j]) for j in range(24) if td[j]>1e-15],
       'descriptive_bootstrap_95_ci':np.quantile(boot,[.025,.975]).tolist(),
       'gate_pass':bool(cm['mse']<rm['mse']-1e-15 and wins>=30 and fw==5 and tail)}
def check(curves,catalog,reference,checkpoint):
    fr=json.loads((HERE/'FREEZE.json').read_text())
    for k,path in {'curves':curves,'catalog':catalog,'reference':reference,'checkpoint':checkpoint}.items():
        if sha(path)!=fr['inputs'][k]:raise ValueError('input hash '+k)
    for name,h in fr['source_sha256'].items():
        if sha(ROOT/name)!=h:raise ValueError('source changed '+name)
    for name,version in fr['runtime_versions'].items():
        if importlib.metadata.version(name)!=version:raise ValueError('runtime changed '+name)
    return fr

def execute(curves,catalog_path,reference,checkpoint,out):
    fr=check(curves,catalog_path,reference,checkpoint);out=Path(out);out.mkdir(parents=True,exist_ok=False)
    dump(out/'STARTED.json',{'utc':utc(),'freeze_sha256':sha(HERE/'FREEZE.json'),'runtime_versions':fr['runtime_versions'], 'network_denied':True})
    socket.create_connection=deny;socket.socket.connect=deny;socket.socket.connect_ex=deny
    torch.set_num_threads(1);torch.set_num_interop_threads(1);began=time.perf_counter()
    try:
        data,feat,_=load_prepared(curves,catalog_path);x,y,p=feat['x_replicates'],data['y'],data['patient_ids'].astype(str)
        cat=catalog_from_features(feat);full=full_training_curves(curves,data,feat,cat,read_catalog(catalog_path))
        folds,_=patient_folds(p,5,'von-organoid-sentinel-v1|outer')
        with np.load(reference,allow_pickle=False) as z:
            if not np.array_equal(z['y'],y) or not np.array_equal(z['patients'].astype(str),p) or not np.array_equal(z['folds'],folds):raise ValueError('reference identity')
            retained=z['candidate'].copy();operating=z['bandwidth07'].copy()
        if abs(metrics(retained,y,p,folds)['mse']-.001042745722096212)>1e-15 or abs(metrics(operating,y,p,folds)['mse']-.0010582750420801538)>1e-15:raise ValueError('reference MSE mismatch')
        pred=np.full((2,*y.shape),np.nan);records=[];isolation=None
        with threadpool_limits(limits=1):
            for f in range(5):
                tr=np.flatnonzero(folds!=f);te=np.flatnonzero(folds==f)
                if set(p[tr])&set(p[te]):raise ValueError('patient overlap')
                plan=plan_panel_fast(x[tr],y[tr],p[tr],cat);validate_plan(plan,cat);dump(out/f'fold_{f}_plan.json',plan)
                paidA=acquire(x,plan,'A');paidB=acquire(x,plan,'B');owner=np.asarray(plan['coordinate_target_indices'])
                wa=observed_weights(plan,full['q'],full['query_to_full'],'A');wb=observed_weights(plan,full['q'],full['query_to_full'],'B')
                ka=known_contribution(paidA,wa);kb=known_contribution(paidB,wb)
                np.savez_compressed(out/f'fold_{f}_contexts_private.npz',paid_A=paidA,paid_B=paidB,known_A=ka,known_B=kb,
                    weights_A=wa,weights_B=wb,y=y,train_indices=tr,test_indices=te,patients=p,owner=owner)
                poison=0.
                for o,paid,known,w in (('A',paidA,ka,wa),('B',paidB,kb,wb)):
                    masked=np.full_like(x,np.nan);ni=np.asarray(plan['selected_native_indices']);pi=np.asarray(plan[f'orientation_{o}_plate_indices']);masked[:,ni,pi]=x[:,ni,pi]
                    again=acquire(masked,plan,o);poison=max(poison,float(np.max(abs(again-paid))),float(np.max(abs(known_contribution(again,w)-known))))
                if poison!=0:raise ValueError('unpaid input used')
                for t in range(24):
                    start=time.perf_counter();estimate,missing=predict_target(paidA,paidB,ka,kb,y,p,tr,te,owner,t,f,checkpoint)
                    pred[:,te,t]=estimate
                    np.savez_compressed(out/f'fold_{f}_target_{t}_private.npz',prediction=estimate,missing=missing,known=np.stack([ka[te,t],kb[te,t]]))
                    print(json.dumps({'event':'target_complete','fold':f,'target_index':t,'seconds':time.perf_counter()-start,'total_seconds':time.perf_counter()-began}),flush=True);gc.collect()
                if f==0:
                    changed=y.copy();changed[te]+=71
                    again,unused=predict_target(paidA,paidB,ka,kb,changed,p,tr,te,owner,0,f,checkpoint)
                    isolation=float(np.max(np.abs(again-pred[:,te,0])))
                    if isolation>1e-6:raise ValueError('evaluation labels influence model')
                rec={'fold':f,'training_patients':len(set(p[tr])),'test_patients':len(set(p[te])),'treatment_wells':64,'per_plate':[32,32],'unpaid_poison_maxdiff':poison}
                records.append(rec);dump(out/f'fold_{f}_COMPLETE.json',rec)
        if NETWORK or not np.isfinite(pred).all():raise ValueError('network attempts or incomplete predictions')
        cm=metrics(pred,y,p,folds);vsret=compare(pred,retained,y,p,folds,data['drug_ids']);vsop=compare(pred,operating,y,p,folds,data['drug_ids'])
        np.savez_compressed(out/'predictions_private.npz',candidate=pred,retained64=retained,operating64=operating,y=y,patients=p,folds=folds,sample_ids=data['sample_ids'],drug_ids=data['drug_ids'])
        r={'schema':'dosepilot.tabpfn_exact_contribution64.result.v1','status':'COMPLETE','model_name':'TabPFN-von-DosePilot-Exact64','attribution':'Built with PriorLabs-TabPFN',
          'candidate':cm,'vs_retained64':vsret,'vs_operating64':vsop,'half_error_target':TARGET,'half_error_point_and_tail_met':bool(cm['mse']<=TARGET and vsret['p90_nonworse']),
          'decision':'ELIGIBLE_FOR_INDEPENDENT_REPLAY' if vsret['gate_pass'] and vsop['gate_pass'] else 'REJECT_FOR_PROMOTION',
          'fold_records':records,'quadrature_maxdiff':full['quadrature_maxdiff'],'outer_label_mutation_maxdiff':isolation,'network_attempts':len(NETWORK),
          'treatment_wells':64,'per_plate':[32,32],'new_inference_actions_added':False,'prediction_sha256':sha(out/'predictions_private.npz'),
          'freeze_sha256':sha(HERE/'FREEZE.json'),'checkpoint_sha256':sha(checkpoint),'protected22_access':False,'independent_validation':False,
          'selection_adjusted':False,'automatic_promotion':False,'kaggle_entry_changed':False,'total_seconds':time.perf_counter()-began,'finished_utc':utc()}
        dump(out/'RESULT.json',r);print(json.dumps(r,indent=2),flush=True);return r
    except BaseException as exc:dump(out/'FAILURE.json',{'error':repr(exc),'traceback':traceback.format_exc(),'utc':utc(),'automatic_retry':False});raise

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--curves',type=Path,required=True);ap.add_argument('--catalog',type=Path,required=True);ap.add_argument('--reference',type=Path,required=True);ap.add_argument('--checkpoint',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args();execute(a.curves,a.catalog,a.reference,a.checkpoint,a.out)
