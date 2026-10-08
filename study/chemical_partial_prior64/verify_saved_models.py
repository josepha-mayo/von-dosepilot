"""Independent numeric replay and equal-patient metric audit; no model fitting.
It does not establish independent biological validation or fresh training replay.
"""
from pathlib import Path
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
import argparse,hashlib,json,sys,datetime
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'study'),str(ROOT/'study/engine')]
from compact_train import load_prepared
from methods import patient_folds
from coverage_methods import catalog_from_features,validate_plan
ARMS=('operating_reproduction','regularized_pooled_control','chemical_partial_primary')
SEED=202610080050

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def risks(pred,y,p):
    loss=(np.square(pred[0]-y)+np.square(pred[1]-y))/2
    return np.stack([loss[p==g].mean(0) for g in np.unique(p)])
def metric(pred,y,p,fold):
    risk=risks(pred,y,p).mean(1);pf=np.array([fold[np.flatnonzero(p==g)[0]] for g in np.unique(p)])
    return {'mse':float(risk.mean()),'p90_patient_rmse':float(np.quantile(np.sqrt(risk),.9)),
            'fold_mse':[float(risk[pf==f].mean()) for f in range(5)]}

def verify(run,curves,catalog,source):
    run=Path(run);frpath=ROOT/'study/chemical_partial_prior64/FREEZE.json';fr=json.loads(frpath.read_text(encoding='utf-8'))
    result=json.loads((run/'RESULT.json').read_text(encoding='utf-8'))
    assert result['status']=='COMPLETE' and result['primary_arm']=='chemical_partial_primary'
    assert sha(frpath)==result['freeze_sha256'] and sha(source)==fr['inputs']['external_prepared']
    assert sha(curves)==fr['inputs']['curves'] and sha(catalog)==fr['inputs']['catalog']
    for rel,digest in fr['source_sha256'].items():assert sha(ROOT/rel)==digest,rel
    assert sha(run/'predictions_private.npz')==result['prediction_sha256']
    with np.load(source,allow_pickle=False) as z:bank={k:z[k].copy() for k in z.files}
    source_audit=json.loads((ROOT/'evidence/chemical_partial_source_bank_20261008.json').read_text(encoding='utf-8'))
    identity=json.loads((ROOT/'evidence/chemical_identity_audit_20261008.json').read_text(encoding='utf-8'))
    assert sha(source)==source_audit['bank_sha256']
    assert source_audit['supported_targets']==20 and identity['validated_targets']==20
    assert not source_audit['organoid_response_values_parsed'] and not source_audit['external_response_extrapolation_used']
    assert list(map(str,bank['drug_names']))==[r['drug'] for r in source_audit['records']]
    max_source_diagonal_error=0.;supported=[]
    for j,row in enumerate(source_audit['records']):
        pooled=bank[f'pooled_{j}'];partial=bank[f'partial_{j}'];doses=bank[f'doses_nM_{j}']
        assert pooled.shape==partial.shape==(len(doses),len(doses)) and np.isfinite(partial).all()
        np.linalg.cholesky(pooled);np.linalg.cholesky(partial)
        max_source_diagonal_error=max(max_source_diagonal_error,float(np.max(np.abs(np.diag(partial)-1))))
        if row['status']=='PARTIAL_CHEMICAL_DOSE_TRANSFER':
            assert row['matched_cells']>=20 and len(row['covered_indices'])>=2
            assert row['source_response_extrapolation'] is False
            chemical=identity['rows'][j];assert chemical['drug']==row['drug']
            for nsc in row['candidates']:
                checks=[v for v in chemical['source_confirmation_checks'] if v['nsc']==nsc]
                assert len(checks)==1 and checks[0]['standardized_cids']==[chemical['compound_cid']]
            supported.append(row['drug'])
        else:np.testing.assert_array_equal(pooled,partial)
    assert len(supported)==20 and max_source_diagonal_error<1e-12
    data,feat,_=load_prepared(curves,catalog);cat=catalog_from_features(feat)
    with np.load(run/'predictions_private.npz',allow_pickle=False) as z:a={k:z[k].copy() for k in z.files}
    y,p,folds=a['y'],a['patients'].astype(str),a['folds']
    assert np.array_equal(y,data['y']) and np.array_equal(p,data['patient_ids'].astype(str))
    ff,_=patient_folds(p,5,'von-organoid-sentinel-v1|outer');assert np.array_equal(ff,folds)
    assert np.array_equal(a['sample_ids'].astype(str),data['sample_ids'].astype(str))
    assert np.array_equal(a['drug_ids'].astype(str),data['drug_ids'].astype(str))
    fresh={name:np.full_like(a[name],np.nan) for name in ARMS};hashes={};plans=[]
    for f in range(5):
        planpath=run/f'fold_{f}_plan.json';plan=json.loads(planpath.read_text());validate_plan(plan,cat)
        hashes[planpath.name]=sha(planpath);ix=np.flatnonzero(folds==f)
        for name in ARMS:
            path=run/f'fold_{f}_{name}_model_private.npz';hashes[path.name]=sha(path)
            with np.load(path,allow_pickle=False) as z:s={k:z[k].copy() for k in z.files}
            native=s['native_indices'];assert np.array_equal(native,plan['selected_native_indices']) and len(set(native))==64
            for oi,o in enumerate(('A','B')):
                plate=s['plate_'+o];assert np.array_equal(plate,plan[f'orientation_{o}_plate_indices'])
                assert np.bincount(plate,minlength=2).tolist()==[32,32]
                paid=feat['x_replicates'][ix][:,native,plate]
                base=s['mean_y_'+o]+((paid-s['mean_x_'+o])/s['scale_x_'+o])@s['beta_'+o]
                zq=(paid-s['canonical_mean'])/s['canonical_scale'];zt=s['kernel_z'];raw=zq@zt.T
                for target in range(24):
                    columns=np.flatnonzero(s['kernel_owner']==target)
                    distance=np.sum((zq[:,None,columns]-zt[None,:,columns])**2,axis=2)
                    raw+=len(columns)*np.exp(-distance/(.98*len(columns)))
                k=raw-np.sum(raw*s['kernel_weights'][None,:],axis=1)[:,None]-s['kernel_mean'][None,:]+float(s['kernel_grand'])
                fresh[name][oi,ix]=base+k@s['coef']
        plans.append({'fold':f,'wells':64,'per_plate':[32,32]})
    max_prediction=max(float(np.max(np.abs(fresh[n]-a[n]))) for n in ARMS);assert max_prediction<1e-12
    metrics={name:metric(fresh[name],y,p,folds) for name in ARMS}
    retained=metric(a['retained64'],y,p,folds);assert abs(retained['mse']-.001042745722096212)<1e-15
    assert abs(metrics['operating_reproduction']['mse']-.0010582750420801538)<1e-12
    max_metric=0.;arms={}
    for name in ARMS[1:]:
        stored=result['arms'][name];actual=metrics[name]
        diff=max(abs(actual['mse']-stored['metrics']['mse']),abs(actual['p90_patient_rmse']-stored['metrics']['p90_patient_rmse']),
          max(abs(x-z) for x,z in zip(actual['fold_mse'],stored['metrics']['fold_mse'])))
        max_metric=max(max_metric,diff);assert diff<1e-15
        comp={}
        for reference,key in (('retained64','vs_retained64'),('operating_reproduction','vs_operating64')):
            ref=a[reference] if reference=='retained64' else fresh[reference]
            rm=metric(ref,y,p,folds);d=risks(fresh[name],y,p).mean(1)-risks(ref,y,p).mean(1)
            wins=int(np.sum(d<-1e-15));fw=sum(x<z-1e-15 for x,z in zip(actual['fold_mse'],rm['fold_mse']))
            tail=actual['p90_patient_rmse']<=rm['p90_patient_rmse']+1e-15
            boot=d[np.random.default_rng(SEED).integers(len(d),size=(100000,len(d)))].mean(1)
            ci=np.quantile(boot,[.025,.975]);sr=stored[key]
            assert wins==sr['patient_wins'] and fw==sr['fold_wins'] and tail==sr['p90_nonworse']
            np.testing.assert_allclose(ci,sr['descriptive_bootstrap_95_ci'],atol=1e-15,rtol=0)
            gate=actual['mse']<rm['mse']-1e-15 and wins>=30 and fw==5 and tail;assert gate==sr['gate_pass']
            comp[key]={'patient_wins':wins,'fold_wins':fw,'p90_nonworse':bool(tail),'gate_pass':bool(gate)}
        arms[name]={'metrics':actual,'comparisons':comp,'decision':stored['decision'],'half_error_target_met':stored['half_error_target_met']}
    for name in ARMS[1:]:
        half=metrics[name]['mse']<=.000521372861048106 and metrics[name]['p90_patient_rmse']<=retained['p90_patient_rmse']+1e-15
        assert half==result['arms'][name]['half_error_target_met']
    assert result['absolute_concentration_alignment_used'] and not result['external_response_extrapolation_used']
    assert result['uncovered_regions_use_conditional_prior']
    assert result['network_attempts']==0 and not result['protected22_access'] and not result['kaggle_entry_changed']
    for rec in result['outer_label_and_curve_mutation'].values():assert rec['prediction_maxdiff']<=1e-12 and rec['state_maxdiff']<=1e-12
    out={'schema':'dosepilot.chemical_partial_prior64.audit.v1','status':'PASS_INDEPENDENT_SAVED_MODEL_REPLAY',
       'arms':arms,'replayed_outer_models':15,'prediction_maxdiff':max_prediction,'metric_maxdiff':max_metric,
       'source_correlation_diagonal_maxdiff':max_source_diagonal_error,'supported_targets':supported,'source_hashes_checked':len(fr['source_sha256']),
       'physical_plans':plans,'component_sha256':hashes,'prediction_sha256':sha(run/'predictions_private.npz'),
       'result_sha256':sha(run/'RESULT.json'),'fresh_training_refit':False,'independent_biological_validation':False,
       'patient_arrays_published':False,'source_raw_data_republished':False,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    with (run/'INDEPENDENT_AUDIT.json').open('x',encoding='utf-8',newline='\n') as f:json.dump(out,f,indent=2);f.write('\n')
    print(json.dumps({k:v for k,v in out.items() if k!='component_sha256'},indent=2),flush=True);return out

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--run',type=Path,required=True);ap.add_argument('--curves',type=Path,required=True)
    ap.add_argument('--catalog',type=Path,required=True);ap.add_argument('--source',type=Path,required=True)
    a=ap.parse_args();verify(a.run,a.curves,a.catalog,a.source)
