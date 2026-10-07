"""Independent saved-model prediction/metric recomputation. No parameter fitting."""
from pathlib import Path
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
import argparse,hashlib,json,sys,platform,datetime
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'study'),str(ROOT/'study/engine')]
from compact_train import load_prepared

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def verify(run,curves,catalog):
    result=json.loads((run/'RESULT.json').read_text(encoding='utf-8'))
    freeze_path=ROOT/'study/patient_deleted_acquisition64/FREEZE.json';fr=json.loads(freeze_path.read_text(encoding='utf-8'))
    assert sha(curves)==fr['inputs']['curves'];assert sha(catalog)==fr['inputs']['catalog']
    assert sha(freeze_path)==result['freeze_sha256']
    for rel,h in fr['files'].items():assert sha(ROOT/rel)==h,rel
    assert sha(run/'predictions_private.npz')==result['prediction_sha256']
    data,feat,_=load_prepared(curves,catalog)
    with np.load(run/'predictions_private.npz',allow_pickle=False) as z:
        y=z['y'];patients=z['patients'].astype(str);folds=z['folds'];saved=z['candidate']
        assert np.array_equal(y,data['y']) and np.array_equal(patients,data['patient_ids'])
    recomputed=np.full_like(saved,np.nan);model_hashes={}
    for fold in range(5):
        model_path=run/f'fold_{fold}_model_private.npz';model_hashes[model_path.name]=sha(model_path)
        with np.load(model_path,allow_pickle=False) as z:s={k:z[k].copy() for k in z.files}
        ix=np.flatnonzero(folds==fold);native=s['native_indices'];assert len(native)==len(np.unique(native))==64
        for oi,o in enumerate(('A','B')):
            plate=s['plate_'+o];assert np.bincount(plate,minlength=2).tolist()==[32,32]
            paid=feat['x_replicates'][ix][:,native,plate]
            linear=s['mean_y_'+o]+((paid-s['mean_x_'+o])/s['scale_x_'+o])@s['beta_'+o]
            normalized=(paid-s['canonical_mean'])/s['canonical_scale'];train=s['kernel_z']
            raw=normalized@train.T
            for target in range(24):
                columns=np.flatnonzero(s['kernel_owner']==target)
                differences=normalized[:,None,columns]-train[None,:,columns]
                distances=np.sum(differences*differences,axis=2)
                raw+=len(columns)*np.exp(-distances/(2*len(columns)*0.49))
            k=raw-np.sum(raw*s['kernel_weights'][None,:],axis=1)[:,None]-s['kernel_mean'][None,:]+float(s['kernel_grand'])
            recomputed[oi,ix]=linear+k@s['coef']
    maxdiff=float(np.max(np.abs(recomputed-saved)));assert maxdiff<1e-12,maxdiff
    group_losses=[];group_fold=[]
    for group in np.unique(patients):
        mask=patients==group;assert len(np.unique(folds[mask]))==1
        group_losses.append(sum(float(np.mean((recomputed[o,mask]-y[mask])**2)) for o in (0,1))/2)
        group_fold.append(int(folds[mask][0]))
    group_losses=np.asarray(group_losses);group_fold=np.asarray(group_fold)
    ms={'mse':float(group_losses.mean()),'p90_patient_rmse':float(np.quantile(np.sqrt(group_losses),.9)),
        'fold_mse':[float(group_losses[group_fold==f].mean()) for f in range(5)]}
    metricdiff=max(abs(ms['mse']-result['candidate']['mse']),abs(ms['p90_patient_rmse']-result['candidate']['p90_patient_rmse']),max(abs(a-b) for a,b in zip(ms['fold_mse'],result['candidate']['fold_mse'])))
    assert metricdiff<1e-15
    out={'status':'PASS_INDEPENDENT_SAVED_MODEL_REPLAY','replayed_outer_models':5,'source_hashes_checked':len(fr['files']),
       'prediction_maxdiff':maxdiff,'metric_maxdiff':metricdiff,'candidate_metrics':ms,'model_sha256':model_hashes,
       'prediction_sha256':sha(run/'predictions_private.npz'),'result_sha256':sha(run/'RESULT.json'),
       'fresh_training_refit':False,'protected22_access':False,'independent_biological_validation':False,
       'python':sys.version,'numpy':np.__version__,'platform':platform.platform(),'utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    with (run/'SAVED_MODEL_VERIFICATION.json').open('x',encoding='utf-8',newline='\n') as f:json.dump(out,f,indent=2);f.write('\n')
    print(json.dumps(out,indent=2));return out

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--run',type=Path,required=True);ap.add_argument('--curves',type=Path,required=True);ap.add_argument('--catalog',type=Path,required=True)
    a=ap.parse_args();verify(a.run,a.curves,a.catalog)
