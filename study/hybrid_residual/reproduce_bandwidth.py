#!/usr/bin/env python3
"""Reproduce the verified 0.7x additive-kernel bandwidth successor from public TRAIN.

No historical predictions or private metadata kit are inputs. Generated model
archives contain fitted training features and must remain private.
"""
from __future__ import annotations
import os
for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
from pathlib import Path
import argparse,datetime,hashlib,importlib.metadata,json,sys,time,traceback
import numpy as np
from additive_kernel import AdditiveKernel
from bandwidth_additive import BandwidthAdditive
STUDY=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(STUDY),str(STUDY/'engine'),str(STUDY/'acceleration')]
OPTIONS=[('identity',0.)]+[(f,l) for f in (.1,.3,.6) for l in (.1,1.,10.)]
EXPECTED={'bandwidth07':.0010582750420801538,'additive':.001060552730112811,'r13':.001144858681382854}
LOCK='8118b562b78b3f55866d6239a38280c942df2c7d81f0b7c4ce71ba0e39ce9ffc'

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write_new(p,v):
    with Path(p).open('x') as f:json.dump(v,f,indent=2,allow_nan=False);f.write('\n')
def risks(pred,y,p):
    e=((pred[0]-y)**2+(pred[1]-y)**2)/2
    return np.stack([e[p==g].mean(0) for g in np.unique(p)])
def metrics(pred,y,p,folds,targets):
    pt=risks(pred,y,p);per=pt.mean(1)
    pf=np.array([folds[np.flatnonzero(p==g)[0]] for g in np.unique(p)])
    return {'mse':float(per.mean()),'p90_rmse':float(np.quantile(np.sqrt(per),.9)),
      'fold_mse':[float(per[pf==f].mean()) for f in range(5)],
      'target_mse':dict(zip(map(str,targets),map(float,pt.mean(0)))),
      'orientation_mse':[float(np.mean([((pred[o,p==g]-y[p==g])**2).mean() for g in np.unique(p)])) for o in (0,1)]}
def execute(curves,out,fit_final):
    from threadpoolctl import threadpool_limits
    from compact_train import load_prepared
    from coverage_methods import acquire,fit_prediction_context,CoveragePredictor,catalog_from_features
    from fast_coverage import plan_panel_fast
    from methods import patient_folds
    import evaluate
    if out.exists():raise ValueError('Output exists; choose a fresh directory')
    if sha(STUDY/'STUDY_LOCK.json')!=LOCK:raise ValueError('Historical study lock changed')
    lock=json.loads((STUDY/'STUDY_LOCK.json').read_text())
    for n,h in lock['engine_files'].items():
        if Path(n).name!=n or sha(STUDY/'engine'/n)!=h:raise ValueError('Historical scientific engine changed: '+n)
    for n,v in lock['deps'].items():
        if importlib.metadata.version(n)!=v:raise ValueError('Pinned dependency required: '+n+'=='+v)
    data,feat,_=load_prepared(curves,STUDY/'TRAIN_CATALOG.json')
    x,y,p=feat['x_replicates'],data['y'],data['patient_ids'].astype(str);catalog=catalog_from_features(feat)
    if y.shape!=(119,24) or len(set(p))!=59 or set(data['library_ids'])!={'lib1'}:raise ValueError('Historical task changed')
    out.mkdir(parents=True,exist_ok=False);start=time.monotonic()
    write_new(out/'STARTED.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
      'curves_sha256':sha(curves),
      'code_sha256':{n:sha(Path(__file__).with_name(n)) for n in ['reproduce_bandwidth.py','bandwidth_additive.py','additive_kernel.py']},
      'bandwidth_multiplier':.7,'options':OPTIONS,'old_prediction_input':False,'private_metadata_kit_used':False,'protected_response_access':False})
    outer,_=patient_folds(p,5,evaluate.SALT+'|outer')
    names=('bandwidth07','additive');pred={n:np.full((2,*y.shape),np.nan) for n in (*names,'r13')};records=[]
    def build(ix):
        plan=plan_panel_fast(x[ix],y[ix],p[ix],catalog)
        pa,pb=[acquire(x[ix],plan,o) for o in ('A','B')]
        context=fit_prediction_context(pa,pb,y[ix],p[ix],plan,catalog.target_ids);base=CoveragePredictor(context,plan,.01)
        z=(np.r_[pa,pb]-base.mean_x)/base.scale_x;res=np.r_[y[ix]-base.predict(pa),y[ix]-base.predict(pb)]
        ids,inverse,count=np.unique(p[ix],return_inverse=True,return_counts=True);w=np.tile(1./(len(ids)*count[inverse]),2)/2
        owner=np.asarray(plan['coordinate_target_indices'])
        models={'bandwidth07':BandwidthAdditive(z,res,w,owner,.7),'additive':AdditiveKernel(z,res,w,owner)}
        return plan,base,{n:(m,[np.zeros((len(z),24))]+[m.coefficients(l,f)[0] for f,l in OPTIONS[1:]]) for n,m in models.items()}
    def choose(indices,salt):
        inner,_=patient_folds(p[indices],3,salt);oof={n:np.full((10,2,len(indices),24),np.nan) for n in names}
        for k in range(3):
            tr=indices[inner!=k];va=indices[inner==k]
            if set(p[tr])&set(p[va]):raise ValueError('Patient leakage')
            plan,base,models=build(tr)
            for oi,o in enumerate(('A','B')):
                paid=acquire(x[va],plan,o);zq=(paid-base.mean_x)/base.scale_x;bp=base.predict(paid)
                for n,(m,coefs) in models.items():
                    cross=m.centered_cross(zq)
                    for ci,c in enumerate(coefs):oof[n][ci,oi,inner==k]=bp+cross@c
        scores={n:[float(risks(q,y[indices],p[indices]).mean()) for q in oof[n]] for n in names}
        chosen={n:min(range(10),key=lambda i:(scores[n][i],i)) for n in names}
        return chosen,scores,oof,inner
    with threadpool_limits(limits=1):
        for f in range(5):
            tr=np.flatnonzero(outer!=f);te=np.flatnonzero(outer==f)
            chosen,scores,oof,inner=choose(tr,evaluate.SALT+f'|inner|{f}')
            plan,base,models=build(tr);folder=out/f'outer_{f:02}';folder.mkdir()
            write_new(folder/'plan.json',plan)
            np.savez_compressed(folder/'inner_predictions_private.npz',**oof,y=y[tr],patients=p[tr],folds=inner)
            for n,(m,coefs) in models.items():
                np.savez_compressed(folder/(n+'_model_private.npz'),**base.arrays(),**m.arrays(coefs[chosen[n]]))
            idx=np.asarray(plan['selected_native_indices'])
            for oi,o in enumerate(('A','B')):
                paid=acquire(x[te],plan,o);zq=(paid-base.mean_x)/base.scale_x;bp=base.predict(paid);pred['r13'][oi,te]=bp
                pl=np.asarray(plan[f'orientation_{o}_plate_indices']);wells=feat['well_ids'][te][:,idx,pl]
                if (pl==0).sum()!=32 or (pl==1).sum()!=32 or not all(len(set(v))==64 for v in wells):raise ValueError('Physical budget changed')
                for n,(m,coefs) in models.items():pred[n][oi,te]=bp+m.centered_cross(zq)@coefs[chosen[n]]
            rec={'fold':f,'selected':{n:OPTIONS[chosen[n]] for n in names},'inner_scores':scores,'wells':64,'per_plate':32}
            records.append(rec);write_new(folder/'selection.json',rec);print(json.dumps({'fold':f,'selected':rec['selected']}),flush=True)
        if not all(np.isfinite(v).all() for v in pred.values()):raise ValueError('Incomplete predictions')
        np.savez_compressed(out/'predictions_private.npz',**pred,y=y,patients=p,folds=outer,sample_ids=data['sample_ids'],drug_ids=data['drug_ids'])
        ms={n:metrics(q,y,p,outer,data['drug_ids']) for n,q in pred.items()}
        matches={n:abs(ms[n]['mse']-v)<=1e-12 for n,v in EXPECTED.items()}
        cp=risks(pred['bandwidth07'],y,p).mean(1);ap=risks(pred['additive'],y,p).mean(1)
        pf=np.array([outer[np.flatnonzero(p==g)[0]] for g in np.unique(p)])
        comparison={'relative_gain':1-ms['bandwidth07']['mse']/ms['additive']['mse'],
          'patient_wins':int((cp<ap).sum()),'patient_losses':int((cp>ap).sum()),
          'fold_wins':sum(a<b for a,b in zip(ms['bandwidth07']['fold_mse'],ms['additive']['fold_mse'])),
          'p90_nonworse':ms['bandwidth07']['p90_rmse']<=ms['additive']['p90_rmse']}
        result={'status':'PASS' if all(matches.values()) else 'MISMATCH','metrics':ms,'expected_matches':matches,
          'comparison_vs_additive':comparison,'selections':records,'source_route':'public_derived_csv',
          'bandwidth_multiplier':.7,'old_prediction_input':False,'private_metadata_kit_used':False,
          'protected_response_access':False,'independent_validation':False,
          'r18_gate_source':'Separately verified private historical ledger, not an input to this public replay',
          'prediction_sha256':sha(out/'predictions_private.npz'),'seconds':time.monotonic()-start}
        write_new(out/'RESULT.json',result)
        if not all(matches.values()):raise ValueError('Verified bandwidth result did not reproduce')
        if fit_final:
            rows=np.arange(len(y));chosen,scores,_,_=choose(rows,evaluate.SALT+'|bandwidth_additive_final')
            plan,base,models=build(rows);m,coefs=models['bandwidth07'];option=OPTIONS[chosen['bandwidth07']]
            dst=out/'final_model';dst.mkdir()
            arrays=dict(base.arrays(),**m.arrays(coefs[chosen['bandwidth07']]),
              native_ids=np.asarray(plan['selected_native_ids']),drug_ids=data['drug_ids'],
              plate_A=np.asarray(plan['orientation_A_plate_indices']),plate_B=np.asarray(plan['orientation_B_plate_indices']))
            np.savez_compressed(dst/'model_private.npz',**arrays);write_new(dst/'plan.json',plan)
            write_new(dst/'CONSTRUCTION.json',{'model_kind':'dosepilot.additive_kernel_bandwidth.v1',
              'bandwidth_multiplier':.7,'selected':option,'inner_mse':scores['bandwidth07'],
              'training_samples':119,'training_patients':59,'plan_sha256':sha(dst/'plan.json'),
              'model_sha256':sha(dst/'model_private.npz'),'private_training_features_in_model':True,
              'new_validation':False,'requires_all64_values':True})
        print(json.dumps({'status':result['status'],'mse':{n:m['mse'] for n,m in ms.items()},'comparison':comparison},indent=2))
    return result
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--curves',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--fit-final',action='store_true');a=ap.parse_args()
    if a.output.exists():ap.error('Output exists; choose a fresh path')
    try:execute(a.curves,a.output,a.fit_final)
    except BaseException as exc:
        if a.output.exists():write_new(a.output/'FAILURE.json',{'error':str(exc),'traceback':traceback.format_exc(),'automatic_retry':False})
        raise
if __name__=='__main__':main()
