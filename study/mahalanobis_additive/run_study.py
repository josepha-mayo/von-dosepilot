#!/usr/bin/env python3
"""Run the prefrozen Mahalanobis-additive challenger on the original Lib1 task."""
from __future__ import annotations
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key]='1'
from pathlib import Path
import argparse,datetime,hashlib,json,sys,time,traceback
import numpy as np

OPTIONS=[('identity',0.)]+[(f,l) for f in (.1,.3,.6) for l in (.1,1.,10.)]
INCUMBENT=.0010582750420801538
R13_MSE=.001144858681382854
R18_MSE=.0011414048112341991
R18_P90=.04095930575479935
R18_FOLDS=[.0015065050020425241,.0009277053434741434,.0011360512581447993,.0009124504299761857,.0012318490417423575]
R18_ORIENTATION=[.0011902913101605125,.0010925183123078864]

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def write_new(path,value):
    with Path(path).open('x') as f:
        json.dump(value,f,indent=2,allow_nan=False);f.write('\n')

def patient_target_risk(pred,y,p):
    error=((pred[0]-y)**2+(pred[1]-y)**2)/2
    return np.stack([error[p==g].mean(0) for g in np.unique(p)])

def summarize(pred,y,p,folds,targets):
    pt=patient_target_risk(pred,y,p);per=pt.mean(1)
    ids=np.unique(p);pf=np.array([folds[np.flatnonzero(p==g)[0]] for g in ids])
    return {'mse':float(per.mean()),'p90_rmse':float(np.quantile(np.sqrt(per),.9)),
      'fold_mse':[float(per[pf==f].mean()) for f in range(5)],
      'target_mse':dict(zip(map(str,targets),map(float,pt.mean(0)))),
      'orientation_mse':[float(np.mean([((pred[o,p==g]-y[p==g])**2).mean() for g in ids])) for o in (0,1)]}

def gate(candidate_loss,reference_loss,candidate_metrics,reference_metrics,pfold,original):
    wins=int((candidate_loss<reference_loss).sum())
    losses=int((candidate_loss>reference_loss).sum())
    foldwins=sum(a<b for a,b in zip(candidate_metrics['fold_mse'],reference_metrics['fold_mse']))
    checks={'strictly_lower_mse':candidate_metrics['mse']<reference_metrics['mse'],
            'patient_wins':wins>=(40 if original else 30),
            'favorable_folds':foldwins>=(4 if original else 5),
            'p90_nonworse':candidate_metrics['p90_rmse']<=reference_metrics['p90_rmse']}
    if original:
        checks['mse_reduction_at_least_5pct']=candidate_metrics['mse']<=.95*reference_metrics['mse']
        checks['both_orientation_mse_below_reference_expected_mse']=max(candidate_metrics['orientation_mse'])<reference_metrics['mse']
    return {'patient_wins':wins,'patient_losses':losses,'patient_ties':int((candidate_loss==reference_loss).sum()),
            'fold_wins':foldwins,'relative_gain':1-candidate_metrics['mse']/reference_metrics['mse'],
            'gate':checks,'passes_all':all(checks.values())}

def execute(args):
    root=args.study.resolve()
    sys.path[:0]=[str(root),str(root/'engine'),str(root/'acceleration'),str(root/'hybrid_residual'),str(root/'mahalanobis_additive')]
    from compact_train import load_prepared
    from methods import patient_folds
    import evaluate
    from coverage_methods import acquire,fit_prediction_context,CoveragePredictor,catalog_from_features
    from fast_coverage import plan_panel_fast
    from bandwidth_additive import BandwidthAdditive
    from mahalanobis_additive import MahalanobisAdditive

    if args.output.exists():
        raise ValueError('Output exists; refuse duplicate attempt')
    protocol=json.loads((root/'mahalanobis_additive/PROTOCOL.json').read_text())
    proposal=json.loads((root/'mahalanobis_additive/PROPOSAL.json').read_text())
    if protocol['state']!='PREFROZEN_BEFORE_FIT' or proposal['outer_outcomes_opened'] is not False:
        raise ValueError('Proposal not prefrozen')
    if proposal['protected22_access'] is not False or proposal['automatic_retry'] is not False:
        raise ValueError('Forbidden proposal state')
    data,feat,_=load_prepared(args.curves,root/'TRAIN_CATALOG.json')
    x,y,p=feat['x_replicates'],data['y'],data['patient_ids'].astype(str)
    if y.shape!=(119,24) or len(np.unique(p))!=59 or set(data['library_ids'])!={'lib1'}:
        raise ValueError('Historical task changed')
    catalog=catalog_from_features(feat)
    outer,_=patient_folds(p,5,evaluate.SALT+'|outer')
    pred={n:np.full((2,*y.shape),np.nan) for n in ('mahalanobis','bandwidth07','r13')}
    args.output.mkdir(parents=True,exist_ok=False)
    write_new(args.output/'STARTED.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
      'protocol_sha256':sha(root/'mahalanobis_additive/PROTOCOL.json'),
      'proposal_sha256':sha(root/'mahalanobis_additive/PROPOSAL.json'),
      'source_sha256':sha(root/'mahalanobis_additive/mahalanobis_additive.py'),
      'curves_sha256':sha(args.curves),'protected_response_access':False,'automatic_retry':False})
    records=[];started=time.monotonic()

    def build(ix):
        plan=plan_panel_fast(x[ix],y[ix],p[ix],catalog)
        pa,pb=[acquire(x[ix],plan,o) for o in ('A','B')]
        ctx=fit_prediction_context(pa,pb,y[ix],p[ix],plan,catalog.target_ids)
        base=CoveragePredictor(ctx,plan,.01)
        z=(np.r_[pa,pb]-base.mean_x)/base.scale_x
        residual=np.r_[y[ix]-base.predict(pa),y[ix]-base.predict(pb)]
        ids,inv,count=np.unique(p[ix],return_inverse=True,return_counts=True)
        w=np.tile(1./(len(ids)*count[inv]),2)/2
        owner=np.asarray(plan['coordinate_target_indices'])
        models={'mahalanobis':MahalanobisAdditive(z,residual,w,owner,.5,.7),
                'bandwidth07':BandwidthAdditive(z,residual,w,owner,.7)}
        bundles={}
        for name,m in models.items():
            coefs=[np.zeros((len(z),24))]+[m.coefficients(l,f)[0] for f,l in OPTIONS[1:]]
            bundles[name]=(m,coefs)
        return plan,base,bundles

    for fold in range(5):
        tr=np.flatnonzero(outer!=fold);te=np.flatnonzero(outer==fold)
        inner,_=patient_folds(p[tr],3,evaluate.SALT+f'|inner|{fold}')
        oof={n:np.full((10,2,len(tr),24),np.nan) for n in ('mahalanobis','bandwidth07')}
        for k in range(3):
            fit=tr[inner!=k];va=tr[inner==k]
            if set(p[fit])&set(p[va]):
                raise ValueError('Inner patient leakage')
            plan,base,bundles=build(fit)
            for oi,o in enumerate(('A','B')):
                paid=acquire(x[va],plan,o);zq=(paid-base.mean_x)/base.scale_x;bp=base.predict(paid)
                for name,(m,coefs) in bundles.items():
                    cross=m.centered_cross(zq)
                    for ci,c in enumerate(coefs):
                        oof[name][ci,oi,inner==k]=bp+cross@c
        if not all(np.isfinite(v).all() for v in oof.values()):
            raise ValueError('Incomplete inner predictions')
        scores={n:[float(patient_target_risk(q,y[tr],p[tr]).mean()) for q in oof[n]] for n in oof}
        chosen={n:min(range(10),key=lambda i:(scores[n][i],i)) for n in oof}
        plan,base,bundles=build(tr);folder=args.output/f'outer_{fold:02}';folder.mkdir()
        write_new(folder/'plan.json',plan)
        np.savez_compressed(folder/'inner_predictions_private.npz',**oof,y=y[tr],patients=p[tr],folds=inner)
        for name,(m,coefs) in bundles.items():
            np.savez_compressed(folder/(name+'_model_private.npz'),**base.arrays(),**m.arrays(coefs[chosen[name]]))
        idx=np.asarray(plan['selected_native_indices'])
        for oi,o in enumerate(('A','B')):
            plate=np.asarray(plan[f'orientation_{o}_plate_indices'])
            if len(idx)!=64 or len(set(idx.tolist()))!=64 or (plate==0).sum()!=32 or (plate==1).sum()!=32:
                raise ValueError('Physical budget changed')
            paid=acquire(x[te],plan,o);zq=(paid-base.mean_x)/base.scale_x;bp=base.predict(paid)
            pred['r13'][oi,te]=bp
            for name,(m,coefs) in bundles.items():
                pred[name][oi,te]=bp+m.centered_cross(zq)@coefs[chosen[name]]
        rec={'fold':fold,'selected':{n:OPTIONS[chosen[n]] for n in chosen},'inner_mse':scores,
             'wells':64,'per_plate':32,'rho':.5,'bandwidth':.7}
        records.append(rec);write_new(folder/'selection.json',rec);print(json.dumps({'fold':fold,'selected':rec['selected']}),flush=True)

    if not all(np.isfinite(v).all() for v in pred.values()):
        raise ValueError('Incomplete outer predictions')
    np.savez_compressed(args.output/'predictions_private.npz',**pred,y=y,patients=p,folds=outer,
                        sample_ids=data['sample_ids'],drug_ids=data['drug_ids'])
    write_new(args.output/'PREDICTIONS_COMMITTED.json',{'sha256':sha(args.output/'predictions_private.npz'),'r18_opened':False})
    metrics={n:summarize(q,y,p,outer,data['drug_ids']) for n,q in pred.items()}
    if abs(metrics['bandwidth07']['mse']-INCUMBENT)>1e-12 or abs(metrics['r13']['mse']-R13_MSE)>1e-12:
        raise ValueError('Historical controls did not reproduce')
    ids=np.unique(p);pf=np.array([outer[np.flatnonzero(p==g)[0]] for g in ids])
    loss={n:patient_target_risk(q,y,p).mean(1) for n,q in pred.items()}
    r18=json.loads(args.r18.read_text())
    if sorted(r18['patient_expected_mse'])!=list(ids):
        raise ValueError('R18 patient identity mismatch')
    r18_loss=np.array([r18['patient_expected_mse'][g] for g in ids])
    if abs(r18_loss.mean()-R18_MSE)>1e-14:
        raise ValueError('R18 mean mismatch')
    r18_metrics={'mse':R18_MSE,'p90_rmse':R18_P90,'fold_mse':R18_FOLDS,'orientation_mse':R18_ORIENTATION}
    comparisons={
      'bandwidth07':gate(loss['mahalanobis'],loss['bandwidth07'],metrics['mahalanobis'],metrics['bandwidth07'],pf,False),
      'r13':gate(loss['mahalanobis'],loss['r13'],metrics['mahalanobis'],metrics['r13'],pf,True),
      'r18':gate(loss['mahalanobis'],r18_loss,metrics['mahalanobis'],r18_metrics,pf,True)}
    decision='PROMOTE' if all(v['passes_all'] for v in comparisons.values()) else 'REJECT_RETAIN_BANDWIDTH07'
    result={'status':'COMPLETE','family_id':'mahalanobis_group_additive','decision':decision,
      'metrics':metrics,'comparisons':comparisons,'selections':records,
      'prediction_sha256':sha(args.output/'predictions_private.npz'),
      'same64wells':True,'new_model_fit':True,'repeated_adaptive_development':True,
      'independent_validation':False,'protected_response_access':False,'automatic_retry':False,
      'seconds':time.monotonic()-started}
    write_new(args.output/'RESULT.json',result)
    print(json.dumps({'decision':decision,'mse':{n:m['mse'] for n,m in metrics.items()},'comparisons':comparisons},indent=2))
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--study',type=Path,required=True)
    p.add_argument('--curves',type=Path,required=True)
    p.add_argument('--r18',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    try:
        execute(a)
    except BaseException as exc:
        if a.output.exists():
            write_new(a.output/'FAILURE.json',{'error':str(exc),'traceback':traceback.format_exc(),'automatic_retry':False})
        raise
if __name__=='__main__':
    main()
