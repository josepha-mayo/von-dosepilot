"""Separate control-field, saved-model and metric reconstruction.
Uses an augmented least-squares field solver and explicit pairwise kernel distances.
No regression refit, new biological model selection, or external validation.
"""
from pathlib import Path
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
import argparse,csv,hashlib,json,sys,datetime
import numpy as np
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE),str(ROOT/'study'),str(ROOT/'study/engine'),str(ROOT/'study/global_conditional_curve64')]
from compact_train import load_prepared,read_catalog
from full_curves import full_training_curves
from coverage_methods import catalog_from_features,validate_plan
from data import layout_and_fields


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def risk(pred,y,p):
    per_sample=np.mean((pred-y[None,:,:])**2,axis=0)
    return np.stack([per_sample[p==g].mean(axis=0) for g in np.unique(p)])
def metrics(pred,y,p,folds):
    per_patient=risk(pred,y,p).mean(1);f=np.array([folds[np.flatnonzero(p==g)[0]] for g in np.unique(p)])
    return {'mse':float(per_patient.mean()),'p90_patient_rmse':float(np.quantile(np.sqrt(per_patient),.9)),
            'fold_mse':[float(per_patient[f==i].mean()) for i in range(5)]}


def independent_fields(controls_path,samples,locations):
    groups={}
    with controls_path.open(encoding='utf-8',newline='') as f:
        for row in csv.DictReader(f):
            key=(row['sample_id'],row['plate'],row['control_type'])
            groups.setdefault(key,[]).append([float(row['row']),float(row['column']),float(row['signal'])])
    output={arm:(np.zeros(locations.shape[:2]),np.ones(locations.shape[:2])) for arm in ('identity','flat','spatial')}
    for i,sample in enumerate(samples):
        for pi,plate in enumerate(('p1','p2')):
            idx=np.arange(pi,locations.shape[1],2)
            points=2*(locations[i,idx]-[1.,1.])/[15.,23.]-1
            rows={kind:np.asarray(sorted(groups[(str(sample),plate,kind)])) for kind in ('negative','positive')}
            med={kind:float(np.median(v[:,2])) for kind,v in rows.items()};span=med['negative']-med['positive']
            if span<=0:raise ValueError('invalid controls in independent replay')
            estimates={}
            for kind,values in rows.items():
                cp=2*(values[:,:2]-[1.,1.])/[15.,23.]-1
                resp=(values[:,2]-med[kind])/span
                design=np.column_stack([np.ones(len(cp)),cp]);penalty=np.diag([0.,np.sqrt(.1*len(cp)),np.sqrt(.1*len(cp))])
                beta=np.linalg.lstsq(np.vstack([design,penalty]),np.r_[resp,np.zeros(3)],rcond=None)[0]
                estimates[kind]={'flat':np.full(len(idx),np.mean(resp)),
                                 'spatial':np.column_stack([np.ones(len(idx)),points])@beta}
            for arm in ('flat','spatial'):
                off=estimates['positive'][arm];gain=np.clip(1+estimates['negative'][arm]-off,.25,4.)
                output[arm][0][i,idx]=off;output[arm][1][i,idx]=gain
    return output


def verify(run,curves,catalog_path,controls):
    frpath=HERE/'FREEZE.json';fr=json.loads(frpath.read_text(encoding='utf-8'));r=json.loads((run/'RESULT.json').read_text(encoding='utf-8'))
    assert r['status']=='COMPLETE' and r['primary_arm']=='spatial'
    for key,p in {'curves':curves,'catalog':catalog_path,'controls':controls}.items():assert sha(p)==fr['inputs'][key],key
    for name,h in fr['source_sha256'].items():assert sha(ROOT/name)==h,name
    assert sha(frpath)==r['freeze_sha256'] and sha(run/'predictions_private.npz')==r['prediction_sha256']
    data,feat,_=load_prepared(curves,catalog_path);catalog=catalog_from_features(feat)
    full=full_training_curves(curves,data,feat,catalog,read_catalog(catalog_path))
    original_fields=layout_and_fields(curves,controls,data,catalog,full)
    fields=independent_fields(controls,data['sample_ids'],original_fields['position_metadata'])
    max_field=0.
    for arm,(off,gain) in fields.items():
        max_field=max(max_field,float(np.max(abs(off-original_fields['offsets'][arm]))),float(np.max(abs(gain-original_fields['gains'][arm]))))
    assert max_field<1e-12,max_field
    with np.load(run/'predictions_private.npz',allow_pickle=False) as z:arr={k:z[k].copy() for k in z.files}
    y,p,folds=arr['y'],arr['patients'].astype(str),arr['folds']
    assert np.array_equal(y,data['y']) and np.array_equal(p,data['patient_ids'].astype(str))
    predictions={arm:np.full_like(arr[arm],np.nan) for arm in fields};model_hashes={};physical_checks=[]
    for f in range(5):
        plan=json.loads((run/f'fold_{f}_plan.json').read_text(encoding='utf-8'));validate_plan(plan,catalog)
        te=np.flatnonzero(folds==f);native=np.asarray(plan['selected_native_indices']);assert len(set(native))==64
        for arm in fields:
            mp=run/f'fold_{f}_{arm}_model_private.npz';model_hashes[mp.name]=sha(mp)
            with np.load(mp,allow_pickle=False) as z:s={k:z[k].copy() for k in z.files}
            off=fields[arm][0][te];gain=fields[arm][1][te]
            for oi,o in enumerate(('A','B')):
                plate=np.asarray(plan[f'orientation_{o}_plate_indices']);assert np.bincount(plate,minlength=2).tolist()==[32,32]
                physical=2*full['query_to_full'][native]+plate;assert np.array_equal(physical,s['physical_'+o])
                raw=feat['x_replicates'][te][:,native,plate]
                latent=(raw-off[:,physical])/gain[:,physical]
                standardized=(latent-s['mean_x'])/s['scale_x']
                whole=s['mean_curve']+standardized@s['beta_curve']
                base=(off+gain*whole)@s['quadrature'];train=s['kernel_z'];kernel=standardized@train.T
                for target in range(24):
                    cols=np.flatnonzero(s['kernel_owner']==target)
                    distance=np.sum((standardized[:,None,cols]-train[None,:,cols])**2,axis=2)
                    kernel+=len(cols)*np.exp(-distance/(.98*len(cols)))
                centered=kernel-(kernel@s['kernel_weights'])[:,None]-s['kernel_mean'][None,:]+float(s['kernel_grand'])
                predictions[arm][oi,te]=base+centered@s['coef']
        physical_checks.append({'fold':f,'wells':64,'per_plate':[32,32]})
    max_prediction=max(float(np.max(abs(predictions[arm]-arr[arm]))) for arm in fields);assert max_prediction<1e-12,max_prediction
    report={};max_metric=0.
    for arm,prediction in predictions.items():
        cm=metrics(prediction,y,p,folds);stored=r['arms'][arm]['metrics']
        diff=max(abs(cm['mse']-stored['mse']),abs(cm['p90_patient_rmse']-stored['p90_patient_rmse']),max(abs(a-b) for a,b in zip(cm['fold_mse'],stored['fold_mse'])))
        max_metric=max(max_metric,diff);assert diff<1e-12
        comparisons={}
        for reference,key in (('retained64','vs_retained64'),('operating64','vs_operating64')):
            d=risk(arr[arm],y,p).mean(1)-risk(arr[reference],y,p).mean(1)
            rm=metrics(arr[reference],y,p,folds);sm=metrics(arr[arm],y,p,folds)
            wins=int(np.sum(d<-1e-15));fw=sum(a<b-1e-15 for a,b in zip(sm['fold_mse'],rm['fold_mse']))
            tail=bool(sm['p90_patient_rmse']<=rm['p90_patient_rmse']+1e-15)
            boot=d[np.random.default_rng(202610072227).integers(len(d),size=(100000,len(d)))].mean(1)
            ci=np.quantile(boot,[.025,.975]);expected=r['arms'][arm][key]
            assert wins==expected['patient_wins'] and fw==expected['fold_wins'] and tail==expected['p90_nonworse']
            np.testing.assert_allclose(ci,expected['descriptive_bootstrap_95_ci'],atol=1e-15,rtol=0)
            gate=bool(sm['mse']<rm['mse']-1e-15 and wins>=30 and fw==5 and tail);assert gate==expected['gate_pass']
            comparisons[key]={'relative_mse_gain':1-sm['mse']/rm['mse'],'patient_wins':wins,'fold_wins':fw,'p90_nonworse':tail,'gate_pass':gate}
        report[arm]={'metrics':cm,'comparisons':comparisons,'decision':r['arms'][arm]['decision'],
           'half_error_point_and_tail_met':r['arms'][arm]['half_error_point_and_tail_met']}
    assert max(r['outer_label_curve_mutation_maxdiff'].values())<=1e-12 and max(r['outer_state_mutation_maxdiff'].values())<=1e-12
    audit={'schema':'dosepilot.control_transport64.audit.v1','status':'PASS_INDEPENDENT_CONTROL_AND_SAVED_MODEL_REPLAY','arms':report,
       'source_hashes_checked':len(fr['source_sha256']),'outer_models_replayed':15,'independent_field_maxdiff':max_field,
       'prediction_maxdiff':max_prediction,'metric_maxdiff':max_metric,'physical_checks':physical_checks,
       'model_sha256':model_hashes,'prediction_sha256':r['prediction_sha256'],'result_sha256':sha(run/'RESULT.json'),
       'new_treatment_wells':0,'new_control_wells':0,'fresh_regression_refit':False,'independent_biological_validation':False,
       'patient_arrays_published':False,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    with (run/'INDEPENDENT_AUDIT.json').open('x',encoding='utf-8',newline='\n') as f:json.dump(audit,f,indent=2);f.write('\n')
    print(json.dumps({k:v for k,v in audit.items() if k!='model_sha256'},indent=2),flush=True);return audit

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--run',type=Path,required=True);ap.add_argument('--curves',type=Path,required=True)
    ap.add_argument('--catalog',type=Path,required=True);ap.add_argument('--controls',type=Path,required=True)
    a=ap.parse_args();verify(a.run,a.curves,a.catalog,a.controls)
