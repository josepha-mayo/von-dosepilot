#!/usr/bin/env python3
"""Local pretrained-prior study. Built with PriorLabs-TabPFN."""
from __future__ import annotations
import os
ENVROOT='D:/von-dosepilot-data/tabpfn_environment_20261007'
for k in ('TABPFN_DISABLE_TELEMETRY','DO_NOT_TRACK','HF_HUB_DISABLE_TELEMETRY','HF_HUB_OFFLINE','TABPFN_NO_BROWSER'):os.environ[k]='1'
os.environ['TABPFN_MODEL_CACHE_DIR']=ENVROOT+'/models';os.environ['HF_HOME']=ENVROOT+'/hf_cache'
os.environ['TMP']=ENVROOT+'/tmp';os.environ['TEMP']=ENVROOT+'/tmp'
for k in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS'):os.environ[k]='2'
import argparse,datetime,gc,hashlib,importlib.metadata,json,platform,socket,sys,time,traceback
from pathlib import Path
import numpy as np
import torch
from threadpoolctl import threadpool_limits
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];STUDY=ROOT/'study'
sys.path[:0]=[str(HERE),str(STUDY),str(STUDY/'engine'),str(STUDY/'acceleration')]
from core import balanced_contexts,feature_order,from_paid,predict_target,SEED
from compact_train import load_prepared
from coverage_methods import acquire,catalog_from_features,validate_plan
from fast_coverage import plan_panel_fast
from methods import patient_folds
import evaluate
ARMS=('full_context','balanced_contexts')
EXPECTED_RETAINED=.001042745722096212;EXPECTED_OPERATING=.0010582750420801538
HALF_TARGET=EXPECTED_RETAINED/2
NETWORK_ATTEMPTS=[]
def deny_network(*a,**kw):
    NETWORK_ATTEMPTS.append('blocked');raise RuntimeError('No network allowed during local biological inference')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def dump(p,x):
    with Path(p).open('x',encoding='utf-8',newline='\n') as f:json.dump(x,f,indent=2,allow_nan=False);f.write('\n')
def risks(pred,y,p):
    e=((pred[0]-y)**2+(pred[1]-y)**2)/2
    return np.stack([e[p==g].mean(0) for g in np.unique(p)])
def metrics(pred,y,p,folds):
    pt=risks(pred,y,p);r=pt.mean(1);pf=np.array([folds[np.flatnonzero(p==g)[0]] for g in np.unique(p)])
    return {'mse':float(r.mean()),'p90_patient_rmse':float(np.quantile(np.sqrt(r),.9)),
       'fold_mse':[float(r[pf==f].mean()) for f in range(5)]}
def comparison(candidate,reference,y,p,folds,names):
    c=risks(candidate,y,p);r=risks(reference,y,p);d=c.mean(1)-r.mean(1);t=c.mean(0)-r.mean(0)
    cm,rm=metrics(candidate,y,p,folds),metrics(reference,y,p,folds)
    wins=int((d<-1e-15).sum());fw=sum(a<b-1e-15 for a,b in zip(cm['fold_mse'],rm['fold_mse']))
    tail=cm['p90_patient_rmse']<=rm['p90_patient_rmse']+1e-15
    rng=np.random.default_rng(SEED);boot=d[rng.integers(len(d),size=(100000,len(d)))].mean(1)
    return {'relative_mse_gain':1-cm['mse']/rm['mse'],'patient_wins':wins,'patient_losses':int((d>1e-15).sum()),
      'fold_wins':fw,'p90_nonworse':tail,'target_wins':int((t<-1e-15).sum()),
      'regressing_targets':[str(names[j]) for j in range(24) if t[j]>1e-15],
      'descriptive_bootstrap_95_ci':np.quantile(boot,[.025,.975]).tolist(),
      'gate_pass':bool(cm['mse']<rm['mse']-1e-15 and wins>=30 and fw==5 and tail)}
def check_freeze(curves,catalog,reference,checkpoint):
    fr=json.loads((HERE/'FREEZE.json').read_text(encoding='utf-8'))
    for k,p in {'curves':curves,'catalog':catalog,'reference':reference,'checkpoint':checkpoint}.items():
        if sha(p)!=fr['inputs'][k]:raise ValueError('input hash changed '+k)
    for path,h in fr['source_sha256'].items():
        if sha(ROOT/path)!=h:raise ValueError('source changed '+path)
    for name,version in fr['runtime_versions'].items():
        if importlib.metadata.version(name)!=version:raise ValueError('runtime version changed '+name)
    return fr

def execute(curves,catalog_path,reference_path,checkpoint,out):
    fr=check_freeze(curves,catalog_path,reference_path,checkpoint)
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    dump(out/'STARTED.json',{'utc':utc(),'freeze_sha256':sha(HERE/'FREEZE.json'),'python':sys.version,
        'runtime_versions':fr['runtime_versions'],'checkpoint_sha256':sha(checkpoint),'telemetry_disabled':True,'network_denied':True})
    socket.create_connection=deny_network;socket.socket.connect=deny_network;socket.socket.connect_ex=deny_network
    torch.set_num_threads(2);torch.set_num_interop_threads(1)
    began=time.perf_counter()
    try:
        data,feat,_=load_prepared(curves,catalog_path);x,y,p=feat['x_replicates'],data['y'],data['patient_ids'].astype(str);samples=data['sample_ids'].astype(str)
        catalog=catalog_from_features(feat);folds,_=patient_folds(p,5,evaluate.SALT+'|outer')
        with np.load(reference_path,allow_pickle=False) as z:
            if not np.array_equal(z['y'],y) or not np.array_equal(z['patients'].astype(str),p) or not np.array_equal(z['folds'],folds):raise ValueError('reference identity mismatch')
            retained=z['candidate'].copy();operating=z['bandwidth07'].copy()
        if abs(metrics(retained,y,p,folds)['mse']-EXPECTED_RETAINED)>1e-15 or abs(metrics(operating,y,p,folds)['mse']-EXPECTED_OPERATING)>1e-15:
            raise ValueError('reference metrics mismatch')
        predictions={a:np.full((2,*y.shape),np.nan) for a in ARMS};records=[];isolation={}
        with threadpool_limits(limits=2):
            for fold in range(5):
                tr=np.flatnonzero(folds!=fold);te=np.flatnonzero(folds==fold)
                if set(p[tr])&set(p[te]):raise ValueError('patient overlap')
                plan=plan_panel_fast(x[tr],y[tr],p[tr],catalog);validate_plan(plan,catalog)
                dump(out/f'fold_{fold}_plan.json',plan)
                paid_A=acquire(x,plan,'A');paid_B=acquire(x,plan,'B');owner=np.asarray(plan['coordinate_target_indices'])
                balanced=balanced_contexts(p,samples,tr);contexts_by_arm={'full_context':[tr],'balanced_contexts':balanced}
                np.savez_compressed(out/f'fold_{fold}_contexts_private.npz',training_indices=tr,test_indices=te,
                    balanced0=balanced[0],balanced1=balanced[1],paid_A=paid_A,paid_B=paid_B,targets=y,patient_ids=p,sample_ids=samples)
                max_poison=0.
                for o,paid in (('A',paid_A),('B',paid_B)):
                    masked=np.full_like(x,np.nan);native=np.asarray(plan['selected_native_indices']);plate=np.asarray(plan[f'orientation_{o}_plate_indices'])
                    masked[:,native,plate]=x[:,native,plate]
                    max_poison=max(max_poison,float(np.max(np.abs(acquire(masked,plan,o)-paid))))
                if max_poison!=0.:raise ValueError('query extraction used unpurchased cells')
                fold_start=time.perf_counter()
                for target in range(24):
                    start=time.perf_counter();details={}
                    for arm in ARMS:
                        pr,members,_=predict_target(paid_A,paid_B,y,p,samples,tr,te,owner,target,fold,checkpoint,
                            contexts=contexts_by_arm[arm])
                        predictions[arm][:,te,target]=pr
                        np.savez_compressed(out/f'fold_{fold}_target_{target}_{arm}_private.npz',prediction=pr,members=members)
                        details[arm]={'contexts':len(contexts_by_arm[arm]),'finite':True}
                    print(json.dumps({'event':'target_complete','fold':fold,'target_index':target,
                        'seconds':time.perf_counter()-start,'total_seconds':time.perf_counter()-began}),flush=True)
                    gc.collect()
                if fold==0:
                    # Rebuild acquisition after changing outer-test labels only; the model contexts remain fitting-only.
                    changed=y.copy();changed[te]+=np.arange(24)[None,:]+71
                    altered_plan=plan_panel_fast(x[tr],changed[tr],p[tr],catalog)
                    if altered_plan['selected_native_indices']!=plan['selected_native_indices']:raise ValueError('outer-label acquisition leakage')
                    for arm in ARMS:
                        repeat,_,_=predict_target(paid_A,paid_B,changed,p,samples,tr,te,owner,0,fold,checkpoint,
                            contexts=contexts_by_arm[arm])
                        delta=float(np.max(np.abs(repeat-predictions[arm][:,te,0])))
                        if delta>1e-6:raise ValueError('outer-test labels influence local model')
                        isolation[arm]=delta
                records.append({'fold':fold,'training_patients':len(np.unique(p[tr])),'test_patients':len(np.unique(p[te])),
                    'training_organoids':len(tr),'balanced_context_rows':[len(v)*2 for v in balanced],
                    'full_context_rows':2*len(tr),'unpaid_poison_maxdiff':max_poison,'seconds':time.perf_counter()-fold_start,
                    'treatment_wells':64,'per_plate':[32,32]})
                dump(out/f'fold_{fold}_COMPLETE.json',records[-1])
                print(json.dumps({'event':'fold_complete','fold':fold,'seconds':time.perf_counter()-fold_start}),flush=True)
        if NETWORK_ATTEMPTS:raise ValueError('unexpected network access attempt')
        results={}
        for arm in ARMS:
            pred=predictions[arm]
            if not np.isfinite(pred).all():raise ValueError('incomplete final predictions')
            cm=metrics(pred,y,p,folds);vsret=comparison(pred,retained,y,p,folds,data['drug_ids']);vsop=comparison(pred,operating,y,p,folds,data['drug_ids'])
            results[arm]={'metrics':cm,'vs_retained64':vsret,'vs_operating64':vsop,
                'half_error_point_and_tail_met':bool(cm['mse']<=HALF_TARGET and vsret['p90_nonworse']),
                'decision':'ELIGIBLE_FOR_INDEPENDENT_REPLAY' if vsret['gate_pass'] and vsop['gate_pass'] else 'REJECT_FOR_PROMOTION'}
        np.savez_compressed(out/'predictions_private.npz',**predictions,retained64=retained,operating64=operating,
             y=y,patients=p,folds=folds,sample_ids=samples,drug_ids=data['drug_ids'])
        result={'schema':'dosepilot.tabpfn_v2_patient_balanced64.result.v1','status':'COMPLETE','model_name':'TabPFN-von-DosePilot-64',
            'attribution':'Built with PriorLabs-TabPFN','primary_arm':'full_context','arms':results,'fold_records':records,
            'outer_label_mutation_maxdiff':isolation,'network_attempts':len(NETWORK_ATTEMPTS),'checkpoint_sha256':sha(checkpoint),
            'prediction_sha256':sha(out/'predictions_private.npz'),'freeze_sha256':sha(HERE/'FREEZE.json'),
            'half_error_target':HALF_TARGET,'treatment_wells':64,'per_plate':[32,32],
            'protected22_access':False,'independent_validation':False,'selection_adjusted':False,'automatic_promotion':False,
            'kaggle_entry_changed':False,'total_seconds':time.perf_counter()-began,'finished_utc':utc()}
        dump(out/'RESULT.json',result);print(json.dumps(result,indent=2),flush=True);return result
    except BaseException as exc:
        dump(out/'FAILURE.json',{'error':repr(exc),'traceback':traceback.format_exc(),'utc':utc(),'automatic_retry':False});raise

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--curves',type=Path,required=True);ap.add_argument('--catalog',type=Path,required=True)
    ap.add_argument('--reference',type=Path,required=True);ap.add_argument('--checkpoint',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args();execute(a.curves,a.catalog,a.reference,a.checkpoint,a.out)
