"""Independent physical-cell counting, numerical model replay and metrics.
Does not trust or import the candidate's planner/predictor implementation.
"""
from pathlib import Path
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
import argparse,hashlib,json,sys,datetime
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'study'),str(ROOT/'study/engine')]
from compact_train import load_prepared
from coverage_methods import catalog_from_features
from methods import patient_folds
ARMS=('original','distinct_physical','mixed_replication')

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def patient_risks(q,y,p):
    e=np.mean((q-y[None,:,:])**2,axis=0)
    return np.stack([e[p==group].mean(0) for group in np.unique(p)])
def metrics(q,y,p,folds):
    loss=patient_risks(q,y,p).mean(1);pf=np.array([folds[np.flatnonzero(p==group)[0]] for group in np.unique(p)])
    return {'mse':float(loss.mean()),'p90_patient_rmse':float(np.quantile(np.sqrt(loss),.9)),
            'fold_mse':[float(loss[pf==i].mean()) for i in range(5)]}

def verify(run,curves,catalog_path):
    frpath=ROOT/'study/mixed_physical_replication64/FREEZE.json';fr=json.loads(frpath.read_text());r=json.loads((run/'RESULT.json').read_text())
    assert r['status']=='COMPLETE' and r['primary_arm']=='mixed_replication'
    assert sha(curves)==fr['inputs']['curves'] and sha(catalog_path)==fr['inputs']['catalog']
    for rel,h in fr['source_sha256'].items():assert sha(ROOT/rel)==h,rel
    assert sha(frpath)==r['freeze_sha256'] and sha(run/'predictions_private.npz')==r['prediction_sha256']
    data,feat,_=load_prepared(curves,catalog_path);catalog=catalog_from_features(feat)
    with np.load(run/'predictions_private.npz',allow_pickle=False) as z:arr={k:z[k].copy() for k in z.files}
    y,p,folds=arr['y'],arr['patients'].astype(str),arr['folds']
    assert np.array_equal(y,data['y']) and np.array_equal(p,data['patient_ids'].astype(str))
    expected,_=patient_folds(p,5,'von-organoid-sentinel-v1|outer');assert np.array_equal(folds,expected)
    assert y.shape==(119,24) and len(set(p))==59
    computed={a:np.full_like(arr[a],np.nan) for a in ARMS};physical_records=[];hashes={}
    for f in range(5):
        te=np.flatnonzero(folds==f)
        for arm in ARMS:
            plan_path=run/f'fold_{f}_{arm}_plan.json';plan=json.loads(plan_path.read_text());hashes[plan_path.name]=sha(plan_path)
            mp=run/f'fold_{f}_{arm}_model_private.npz';hashes[mp.name]=sha(mp)
            with np.load(mp,allow_pickle=False) as z:s={k:z[k].copy() for k in z.files}
            native=np.asarray(plan['selected_native_indices'],int);own=np.asarray(plan['coordinate_target_indices'],int)
            assert native.shape==(64,) and np.array_equal(native,s['native_indices'])
            assert np.array_equal(own,catalog.native_target_indices[native])
            counts=np.bincount(own,minlength=24);assert sum(counts==2)==8 and sum(counts==3)==16
            native_count=len(set(native.tolist()));assert native_count==plan['distinct_native_doses']
            if arm!='mixed_replication':assert native_count==64
            for oi,o in enumerate(('A','B')):
                plates=np.asarray(plan[f'orientation_{o}_plate_indices'],int)
                assert np.array_equal(plates,s['plate_'+o]) and np.bincount(plates,minlength=2).tolist()==[32,32]
                keys={(int(n),int(q)) for n,q in zip(native,plates)};assert len(keys)==64
                for j in range(24):assert set(plates[own==j])=={0,1}
                paid=feat['x_replicates'][te][:,native,plates]
                base=s['mean_y_'+o]+((paid-s['mean_x_'+o])/s['scale_x_'+o])@s['beta_'+o]
                zq=(paid-s['canonical_mean'])/s['canonical_scale'];zt=s['kernel_z'];raw=zq@zt.T
                for j in range(24):
                    c=np.flatnonzero(s['kernel_owner']==j);distance=np.sum((zq[:,None,c]-zt[None,:,c])**2,axis=2)
                    raw+=len(c)*np.exp(-distance/(.98*len(c)))
                centered=raw-(raw@s['kernel_weights'])[:,None]-s['kernel_mean'][None,:]+float(s['kernel_grand'])
                computed[arm][oi,te]=base+centered@s['coef']
            assert np.array_equal(np.asarray(plan['orientation_B_plate_indices']),1-np.asarray(plan['orientation_A_plate_indices']))
            physical_records.append({'fold':f,'arm':arm,'distinct_physical_wells':64,'per_plate':[32,32],
                 'distinct_native_doses':native_count,'replicated_native_doses':64-native_count,
                 'original_64_distinct_native_contract_satisfied':native_count==64})
    maxpred=max(float(np.max(abs(computed[a]-arr[a]))) for a in ARMS);assert maxpred<1e-12
    report={};maxmetric=0.
    for arm in ARMS:
        m=metrics(computed[arm],y,p,folds);stored=r['arms'][arm]['metrics']
        diff=max(abs(m['mse']-stored['mse']),abs(m['p90_patient_rmse']-stored['p90_patient_rmse']),max(abs(a-b) for a,b in zip(m['fold_mse'],stored['fold_mse'])))
        maxmetric=max(maxmetric,diff);assert diff<1e-12
        comparisons={}
        for ref,key in (('retained64','vs_retained64'),('operating64','vs_operating64')):
            # Use byte-matched original arrays for strict near-tie gate comparison.
            cm=metrics(arr[arm],y,p,folds);rm=metrics(arr[ref],y,p,folds)
            d=patient_risks(arr[arm],y,p).mean(1)-patient_risks(arr[ref],y,p).mean(1)
            wins=int(sum(d<-1e-15));fw=sum(a<b-1e-15 for a,b in zip(cm['fold_mse'],rm['fold_mse']))
            tail=bool(cm['p90_patient_rmse']<=rm['p90_patient_rmse']+1e-15);gate=bool(cm['mse']<rm['mse']-1e-15 and wins>=30 and fw==5 and tail)
            rs=r['arms'][arm][key];assert wins==rs['patient_wins'] and fw==rs['fold_wins'] and tail==rs['p90_nonworse'] and gate==rs['gate_pass']
            bootstrap=d[np.random.default_rng(202610072250).integers(len(d),size=(100000,len(d)))].mean(1)
            np.testing.assert_allclose(np.quantile(bootstrap,[.025,.975]),rs['descriptive_bootstrap_95_ci'],atol=1e-15,rtol=0)
            comparisons[key]={'relative_mse_gain':1-cm['mse']/rm['mse'],'patient_wins':wins,'fold_wins':fw,'p90_nonworse':tail,'gate_pass':gate}
        report[arm]={'metrics':m,'comparisons':comparisons,'decision':r['arms'][arm]['decision'],
          'half_error_point_and_tail_met':r['arms'][arm]['half_error_point_and_tail_met'],
          'native_contract_satisfied_on_all_outer_plans':all(q['original_64_distinct_native_contract_satisfied'] for q in physical_records if q['arm']==arm)}
    assert max(r['outer_label_curve_mutation_maxdiff'].values())<=1e-12 and max(r['outer_state_mutation_maxdiff'].values())<=1e-12
    audit={'schema':'dosepilot.mixed_physical_replication64.audit.v1','status':'PASS_INDEPENDENT_PHYSICAL_AND_MODEL_REPLAY',
       'arms':report,'physical_plan_checks':physical_records,'outer_models_replayed':15,'source_hashes_checked':len(fr['source_sha256']),
       'prediction_maxdiff':maxpred,'metric_maxdiff':maxmetric,'artifact_sha256':hashes,'result_sha256':sha(run/'RESULT.json'),
       'prediction_sha256':r['prediction_sha256'],'fresh_regression_refit':False,'independent_biological_validation':False,
       'original_native_contract_relaxation_disclosed':True,'automatic_promotion':False,'patient_arrays_published':False,
       'utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    with (run/'INDEPENDENT_AUDIT.json').open('x',encoding='utf-8',newline='\n') as f:json.dump(audit,f,indent=2);f.write('\n')
    print(json.dumps({k:v for k,v in audit.items() if k!='artifact_sha256'},indent=2),flush=True);return audit

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--run',type=Path,required=True);ap.add_argument('--curves',type=Path,required=True);ap.add_argument('--catalog',type=Path,required=True)
    a=ap.parse_args();verify(a.run,a.curves,a.catalog)
