#!/usr/bin/env python3
"""Frozen two-arm structured-kernel experiment. TRAIN only; no automatic retry."""
from __future__ import annotations
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key]='1'
from pathlib import Path
import argparse, datetime, hashlib, importlib.metadata, json, sys, time, traceback
import numpy as np

OPTIONS=[('identity',0.)]+[(f,l) for f in (.1,.3,.6) for l in (.1,1.,10.)]
FAMILIES=('additive','s2','pair_mix','mean_shape')
ARMS=('pair_mix','mean_shape')
EXPECTED={'r13':.001144858681382854,'s2':.0010701439454817465,'additive':.001060552730112811}
LOCK='8118b562b78b3f55866d6239a38280c942df2c7d81f0b7c4ce71ba0e39ce9ffc'

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,v):
    with Path(p).open('x') as f:json.dump(v,f,indent=2,allow_nan=False);f.write('\n')
def require(ok, message):
    if not ok:raise ValueError(message)
def pt_risks(pred,y,p):
    error=((pred[0]-y)**2+(pred[1]-y)**2)/2
    return np.stack([error[p==g].mean(0) for g in np.unique(p)])
def summarize(pred,y,p,pfold,targets):
    pt=pt_risks(pred,y,p);per=pt.mean(1)
    return {'mse':float(per.mean()),'p90_rmse':float(np.quantile(np.sqrt(per),.9)),
        'fold_mse':[float(per[pfold==f].mean()) for f in range(5)],
        'target_mse':dict(zip(map(str,targets),map(float,pt.mean(0)))),
        'orientation_mse':[float(np.mean([((pred[o,p==g]-y[p==g])**2).mean() for g in np.unique(p)])) for o in (0,1)]}
def compare(candidate, reference, cm, rm, pfold, original=False):
    delta=candidate-reference
    rng=np.random.default_rng(20261002)
    boot=delta[rng.integers(0,len(delta),(10000,len(delta)))].mean(1)
    gains={'relative_gain':1-cm['mse']/rm['mse'],'patient_wins':int((delta<0).sum()),
        'patient_losses':int((delta>0).sum()),'patient_ties':int((delta==0).sum()),
        'fold_wins':sum(a<b for a,b in zip(cm['fold_mse'],rm['fold_mse'])),
        'descriptive_delta_ci95':np.quantile(boot,[.025,.975]).tolist()}
    gate={'mse':bool(cm['mse']<=.95*rm['mse']) if original else bool(cm['mse']<rm['mse']),
          'patient_wins':gains['patient_wins']>=(40 if original else 30),
          'fold_wins':gains['fold_wins']>=(4 if original else 3),
          'p90':bool(cm['p90_rmse']<=rm['p90_rmse'])}
    if original:gate['both_orientation_means_below_reference_expected']=bool(max(cm['orientation_mse'])<rm['mse'])
    gains.update(gate=gate,passes_all=all(gate.values()))
    return gains

def run(a):
    study=a.study.resolve();here=Path(__file__).resolve().parent
    require(not a.output.exists(),'Output already exists; no refit permitted')
    freeze=json.loads(a.freeze.read_text())
    for name,h in freeze['code_sha256'].items():require(sha(here/name)==h,'Frozen source changed: '+name)
    for name,h in freeze['parent_sha256'].items():require(sha(study/name)==h,'Parent source changed: '+name)
    require(sha(a.curves)==freeze['curves_sha256'],'Exact TRAIN CSV changed')
    require(sha(a.reference)==freeze['reference_predictions_sha256'],'Historical additive artifact changed')
    require(sha(a.r18)==freeze['r18_summary_sha256'],'R18 reference receipt changed')
    require(sha(study/'STUDY_LOCK.json')==LOCK,'Historical study lock changed')
    lock=json.loads((study/'STUDY_LOCK.json').read_text())
    for name,h in lock['engine_files'].items():require(Path(name).name==name and sha(study/'engine'/name)==h,'Original engine changed: '+name)
    for name,v in lock['deps'].items():require(importlib.metadata.version(name)==v,'Pinned environment required: '+name+'=='+v)
    sys.path[:0]=[str(study),str(study/'engine'),str(study/'acceleration'),str(study/'hybrid_residual'),str(here)]
    from compact_train import load_prepared
    from methods import patient_folds
    import evaluate
    from coverage_methods import acquire,fit_prediction_context,CoveragePredictor,catalog_from_features
    from fast_coverage import plan_panel_fast
    from kernel_spectral import KernelSpectral
    from additive_kernel import AdditiveKernel
    from structured_kernel import StructuredKernel
    a.output.mkdir(parents=True,exist_ok=False);start=time.monotonic()
    write(a.output/'STARTED.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'freeze_sha256':sha(a.freeze),'options':OPTIONS,'families':FAMILIES,'old_prediction_input':False,'protected_response_access':False})
    data,feat,_=load_prepared(a.curves,study/'TRAIN_CATALOG.json')
    x,y,p=feat['x_replicates'],data['y'],data['patient_ids'].astype(str)
    require(y.shape==(119,24) and len(np.unique(p))==59 and set(data['library_ids'])=={'lib1'},'Task identity changed')
    catalog=catalog_from_features(feat);folds,_=patient_folds(p,5,evaluate.SALT+'|outer')
    ids=np.unique(p);pf=np.array([folds[np.flatnonzero(p==g)[0]] for g in ids])
    audit=[]
    def build(indices):
        plan=plan_panel_fast(x[indices],y[indices],p[indices],catalog)
        pa,pb=[acquire(x[indices],plan,o) for o in ('A','B')]
        context=fit_prediction_context(pa,pb,y[indices],p[indices],plan,catalog.target_ids)
        base=CoveragePredictor(context,plan,.01)
        z=(np.r_[pa,pb]-base.mean_x)/base.scale_x
        residual=np.r_[y[indices]-base.predict(pa),y[indices]-base.predict(pb)]
        u,inv,count=np.unique(p[indices],return_inverse=True,return_counts=True)
        w=np.tile(1./(len(u)*count[inv]),2)/2
        owner=np.asarray(plan['coordinate_target_indices']);models={}
        for name in FAMILIES:
            if name=='s2':m=KernelSpectral(z,residual,w,False)
            elif name=='additive':m=AdditiveKernel(z,residual,w,owner)
            else:m=StructuredKernel(z,residual,w,owner,name)
            coefs=[np.zeros((len(z),24))]+[m.coefficients(l,f)[0] for f,l in OPTIONS[1:]]
            models[name]=(m,coefs)
        return plan,base,models
    predictions={n:np.full((2,*y.shape),np.nan) for n in (*FAMILIES,'r13')};records=[]
    for outer in range(5):
        tr=np.flatnonzero(folds!=outer);te=np.flatnonzero(folds==outer)
        require(not set(p[tr])&set(p[te]),'Outer patient leakage')
        inner,_=patient_folds(p[tr],3,evaluate.SALT+f'|inner|{outer}')
        oof={n:np.full((10,2,len(tr),24),np.nan) for n in FAMILIES}
        for k in range(3):
            fit=tr[inner!=k];val=tr[inner==k]
            require(not set(p[fit])&set(p[val]),'Inner patient leakage')
            plan,base,models=build(fit)
            for oi,o in enumerate(('A','B')):
                paid=acquire(x[val],plan,o);z=(paid-base.mean_x)/base.scale_x;bp=base.predict(paid)
                for n,(m,coefs) in models.items():
                    cross=m.centered_cross(z)
                    for j,c in enumerate(coefs):oof[n][j,oi,inner==k]=bp+cross@c
            audit.append({'outer':outer,'inner':k,'fit_patients':len(set(p[fit])),'validation_patients':len(set(p[val])),'disjoint':True})
        require(all(np.isfinite(v).all() for v in oof.values()),'Incomplete inner predictions')
        scores={n:[float(pt_risks(v,y[tr],p[tr]).mean()) for v in oof[n]] for n in FAMILIES}
        chosen={n:min(range(10),key=lambda j:(s[j],j)) for n,s in scores.items()}
        plan,base,models=build(tr);d=a.output/f'outer_{outer:02}';d.mkdir()
        write(d/'plan.json',plan)
        np.savez_compressed(d/'inner_oof_private.npz',**oof,y=y[tr],patients=p[tr],folds=inner)
        for n,(m,coefs) in models.items():
            np.savez_compressed(d/(n+'_model_private.npz'),**base.arrays(),**m.arrays(coefs[chosen[n]]),residual_training_private=m.residual)
        indices=np.asarray(plan['selected_native_indices']);require(len(set(indices))==64,'Duplicate native measurement')
        for oi,o in enumerate(('A','B')):
            paid=acquire(x[te],plan,o);z=(paid-base.mean_x)/base.scale_x;bp=base.predict(paid)
            predictions['r13'][oi,te]=bp;pl=np.asarray(plan[f'orientation_{o}_plate_indices'])
            wells=feat['well_ids'][te][:,indices,pl]
            require(all(len(set(v))==64 for v in wells) and (pl==0).sum()==32 and (pl==1).sum()==32,'Physical budget changed')
            masked=np.full_like(x[te],np.nan);masked[:,indices,pl]=paid
            np.testing.assert_array_equal(acquire(masked,plan,o),paid)
            for n,(m,coefs) in models.items():predictions[n][oi,te]=bp+m.predict(z,coefs[chosen[n]])
        r={'fold':outer,'selected':{n:OPTIONS[j] for n,j in chosen.items()},'inner_mse':scores,'unique_wells':64,'per_plate':32,'unpaid_values_masked':True}
        records.append(r);write(d/'selection.json',r)
        print(json.dumps({'fold_completed':outer,'seconds':time.monotonic()-start,'choices':r['selected']}),flush=True)
    require(all(np.isfinite(v).all() for v in predictions.values()),'Incomplete outer predictions')
    np.savez_compressed(a.output/'predictions_private.npz',**predictions,y=y,patients=p,folds=folds,sample_ids=data['sample_ids'],drug_ids=data['drug_ids'])
    write(a.output/'PREDICTIONS_COMMITTED.json',{'sha256':sha(a.output/'predictions_private.npz'),'historical_predictions_opened':False})
    # Reference outcomes are not fit inputs. Open only after all new arrays are saved.
    with np.load(a.reference,allow_pickle=False) as ref:
        for key,value in [('patients',p),('sample_ids',data['sample_ids']),('drug_ids',data['drug_ids']),('folds',folds),('y',y)]:
            require(np.array_equal(ref[key],value),'Historical cohort identity mismatch: '+key)
        parity={n:float(np.max(np.abs(ref[n]-predictions[n]))) for n in EXPECTED}
    require(max(parity.values())<1e-12,'Rebuilt control predictions differ')
    metrics={n:summarize(v,y,p,pf,data['drug_ids']) for n,v in predictions.items()}
    require(all(abs(metrics[n]['mse']-v)<1e-12 for n,v in EXPECTED.items()),'Rebuilt control scores differ')
    r18=json.loads(a.r18.read_text());require(sorted(r18['patient_expected_mse'])==list(ids),'R18 identities differ')
    ref18=np.array([r18['patient_expected_mse'][g] for g in ids]);require(abs(ref18.mean()-r18['mse'])<1e-14,'R18 mean inconsistent')
    m18={'mse':float(ref18.mean()),'p90_rmse':float(np.quantile(np.sqrt(ref18),.9)),
         'fold_mse':[float(ref18[pf==f].mean()) for f in range(5)]}
    require(np.max(np.abs(np.array(m18['fold_mse'])-r18['fold_mse']))<1e-14,'R18 fold identity inconsistent')
    patient_loss={n:pt_risks(v,y,p).mean(1) for n,v in predictions.items()}
    comparisons={};decisions={}
    for arm in ARMS:
        comparisons[arm]={n:compare(patient_loss[arm],patient_loss[n],metrics[arm],metrics[n],pf,n=='r13') for n in ('additive','s2','r13')}
        comparisons[arm]['r18']=compare(patient_loss[arm],ref18,metrics[arm],m18,pf,True)
        decisions[arm]='ELIGIBLE_RESEARCH_SUCCESSOR' if all(c['passes_all'] for c in comparisons[arm].values()) else 'REJECT_RETAIN_ADDITIVE'
    result={'status':'COMPLETE','metrics':metrics,'comparisons':comparisons,'decisions':decisions,'control_prediction_max_errors':parity,
        'cohort':{'samples':119,'patients':59,'targets':24,'wells':64,'per_plate':32},'selections':records,'containment':audit,
        'source_commit':freeze['parent_commit'],'prediction_sha256':sha(a.output/'predictions_private.npz'),'freeze_sha256':sha(a.freeze),
        'private_reference_summary_used':True,'bootstrap_selection_corrected':False,'independent_validation':False,'protected_response_access':False,
        'original_workbook_opened':False,'accepted_entry_changed':False,'seconds':time.monotonic()-start}
    write(a.output/'RESULT.json',result)
    print(json.dumps({'status':'COMPLETE','mse':{n:v['mse'] for n,v in metrics.items()},'comparisons':comparisons,'decisions':decisions},indent=2),flush=True)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('study','curves','reference','r18','freeze','output'):p.add_argument('--'+name,required=True,type=Path)
    a=p.parse_args()
    if a.output.exists():p.error('Output exists: refuse duplicate execution')
    try:run(a)
    except BaseException as exc:
        if a.output.exists():write(a.output/'FAILURE.json',{'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc(),'automatic_retry':False})
        raise
if __name__=='__main__':main()
